"""
Smart Home Assistant - Timer and Alarm Manager

Manages countdown timers and scheduled alarms with SQLite persistence.
Part of WP-4.3: Timers & Alarms feature.
"""

import json
import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DATABASE_PATH = DATA_DIR / "timers.db"


class TimerStatus(Enum):
    """Status values for timers."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class AlarmStatus(Enum):
    """Status values for alarms."""

    PENDING = "pending"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"


class TimerManager:
    """
    Manages countdown timers and scheduled alarms with SQLite persistence.

    Provides CRUD operations for timers and alarms with support for:
    - Named timers ("pizza timer", "laundry timer")
    - Multiple simultaneous timers
    - Alarms with repeat schedules
    - Natural language duration/time parsing
    - Snooze functionality for alarms
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize TimerManager with database connection.

        Args:
            database_path: Path to SQLite database file (defaults to DATA_DIR/timers.db)
        """
        self.database_path = database_path or DEFAULT_DATABASE_PATH
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database operations."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as error:
            connection.rollback()
            logger.error(f"Database error: {error}")
            raise
        finally:
            connection.close()

    def _initialize_database(self):
        """Create tables if they don't exist."""
        with self._get_cursor() as cursor:
            # Create timers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    duration_seconds INTEGER NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'running',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    triggered_at TIMESTAMP
                )
            """)

            # Create alarms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alarms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    alarm_time TIMESTAMP NOT NULL,
                    repeat_days TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    triggered_at TIMESTAMP,
                    snooze_count INTEGER DEFAULT 0
                )
            """)

            # Create indexes for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timers_status
                ON timers(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timers_end_time
                ON timers(end_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alarms_status
                ON alarms(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alarms_alarm_time
                ON alarms(alarm_time)
            """)

        logger.info(f"TimerManager initialized with database at {self.database_path}")

    # ==================== TIMER OPERATIONS ====================

    def create_timer(
        self,
        duration_seconds: int,
        name: str | None = None,
    ) -> int:
        """
        Create a new countdown timer.

        Args:
            duration_seconds: Timer duration in seconds (must be positive)
            name: Optional timer name (e.g., "pizza timer")

        Returns:
            ID of the created timer

        Raises:
            ValueError: If duration_seconds is <= 0
        """
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")

        end_time = datetime.now() + timedelta(seconds=duration_seconds)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO timers (name, duration_seconds, end_time, status)
                VALUES (?, ?, ?, ?)
            """,
                (name, duration_seconds, end_time.isoformat(), TimerStatus.RUNNING.value),
            )

            timer_id = cursor.lastrowid
            logger.info(
                f"Created timer {timer_id}: {duration_seconds}s" + (f" ('{name}')" if name else "")
            )
            return timer_id

    def get_timer(self, timer_id: int) -> dict[str, Any] | None:
        """
        Get a timer by ID.

        Args:
            timer_id: Timer ID

        Returns:
            Timer dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM timers WHERE id = ?", (timer_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    def get_timer_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Find an active timer by name (case-insensitive partial match).

        Args:
            name: Timer name to search for

        Returns:
            Timer dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM timers
                WHERE status = 'running'
                AND LOWER(name) LIKE LOWER(?)
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (f"%{name}%",),
            )

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_timers(self) -> list[dict[str, Any]]:
        """
        Get all running timers.

        Returns:
            List of timer dicts ordered by end_time
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM timers
                WHERE status = 'running'
                ORDER BY end_time ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_expired_timers(self) -> list[dict[str, Any]]:
        """
        Get timers that have expired but not been completed.

        Returns:
            List of expired timer dicts
        """
        now = datetime.now().isoformat()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM timers
                WHERE status = 'running'
                AND end_time <= ?
                ORDER BY end_time ASC
            """,
                (now,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def cancel_timer(self, timer_id: int) -> bool:
        """
        Cancel a running timer.

        Args:
            timer_id: Timer ID

        Returns:
            True if timer was cancelled, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE timers
                SET status = ?
                WHERE id = ? AND status = 'running'
            """,
                (TimerStatus.CANCELLED.value, timer_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Cancelled timer {timer_id}")
            return success

    def complete_timer(self, timer_id: int) -> dict[str, Any]:
        """
        Complete (trigger) a timer.

        Args:
            timer_id: Timer ID

        Returns:
            Dict with success status and timer info
        """
        timer = self.get_timer(timer_id)
        if not timer:
            return {"success": False, "error": "Timer not found"}

        now = datetime.now().isoformat()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE timers
                SET status = ?, triggered_at = ?
                WHERE id = ?
            """,
                (TimerStatus.COMPLETED.value, now, timer_id),
            )

        logger.info(f"Completed timer {timer_id}")

        return {
            "success": True,
            "timer_id": timer_id,
            "name": timer.get("name"),
            "duration_seconds": timer["duration_seconds"],
            "triggered_at": now,
        }

    def get_remaining_seconds(self, timer_id: int) -> int:
        """
        Get remaining seconds for a timer.

        Args:
            timer_id: Timer ID

        Returns:
            Remaining seconds (0 if expired or not found)
        """
        timer = self.get_timer(timer_id)
        if not timer or timer["status"] != "running":
            return 0

        end_time = datetime.fromisoformat(timer["end_time"])
        remaining = (end_time - datetime.now()).total_seconds()
        return max(0, int(remaining))

    # ==================== ALARM OPERATIONS ====================

    def create_alarm(
        self,
        alarm_time: datetime,
        name: str | None = None,
        repeat_days: list[str] | None = None,
    ) -> int:
        """
        Create a new alarm.

        Args:
            alarm_time: When the alarm should trigger
            name: Optional alarm name
            repeat_days: Optional list of weekdays for repeating (e.g., ["monday", "friday"])

        Returns:
            ID of the created alarm

        Raises:
            ValueError: If alarm_time is in the past
        """
        if alarm_time < datetime.now():
            raise ValueError("alarm_time cannot be in the past")

        repeat_json = json.dumps(repeat_days) if repeat_days else None

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO alarms (name, alarm_time, repeat_days, status)
                VALUES (?, ?, ?, ?)
            """,
                (name, alarm_time.isoformat(), repeat_json, AlarmStatus.PENDING.value),
            )

            alarm_id = cursor.lastrowid
            logger.info(
                f"Created alarm {alarm_id}: {alarm_time}" + (f" ('{name}')" if name else "")
            )
            return alarm_id

    def get_alarm(self, alarm_id: int) -> dict[str, Any] | None:
        """
        Get an alarm by ID.

        Args:
            alarm_id: Alarm ID

        Returns:
            Alarm dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM alarms WHERE id = ?", (alarm_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            result = dict(row)
            # Parse repeat_days JSON
            if result.get("repeat_days"):
                result["repeat_days"] = json.loads(result["repeat_days"])
            return result

    def get_active_alarms(self) -> list[dict[str, Any]]:
        """
        Get all pending alarms.

        Returns:
            List of alarm dicts ordered by alarm_time
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM alarms
                WHERE status IN ('pending', 'snoozed')
                ORDER BY alarm_time ASC
            """)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                alarm = dict(row)
                if alarm.get("repeat_days"):
                    alarm["repeat_days"] = json.loads(alarm["repeat_days"])
                result.append(alarm)
            return result

    def get_due_alarms(self) -> list[dict[str, Any]]:
        """
        Get alarms that are due (past alarm_time but not triggered).

        Returns:
            List of due alarm dicts
        """
        now = datetime.now().isoformat()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM alarms
                WHERE status IN ('pending', 'snoozed')
                AND alarm_time <= ?
                ORDER BY alarm_time ASC
            """,
                (now,),
            )
            rows = cursor.fetchall()

            result = []
            for row in rows:
                alarm = dict(row)
                if alarm.get("repeat_days"):
                    alarm["repeat_days"] = json.loads(alarm["repeat_days"])
                result.append(alarm)
            return result

    def cancel_alarm(self, alarm_id: int) -> bool:
        """
        Cancel a pending alarm.

        Args:
            alarm_id: Alarm ID

        Returns:
            True if alarm was cancelled, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE alarms
                SET status = ?
                WHERE id = ? AND status IN ('pending', 'snoozed')
            """,
                (AlarmStatus.CANCELLED.value, alarm_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Cancelled alarm {alarm_id}")
            return success

    def trigger_alarm(self, alarm_id: int) -> dict[str, Any]:
        """
        Trigger an alarm (mark as triggered).

        Args:
            alarm_id: Alarm ID

        Returns:
            Dict with success status and alarm info
        """
        alarm = self.get_alarm(alarm_id)
        if not alarm:
            return {"success": False, "error": "Alarm not found"}

        now = datetime.now().isoformat()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE alarms
                SET status = ?, triggered_at = ?
                WHERE id = ?
            """,
                (AlarmStatus.TRIGGERED.value, now, alarm_id),
            )

        logger.info(f"Triggered alarm {alarm_id}")

        # Handle repeating alarms
        if alarm.get("repeat_days"):
            self._schedule_next_occurrence(alarm)

        return {
            "success": True,
            "alarm_id": alarm_id,
            "name": alarm.get("name"),
            "triggered_at": now,
        }

    def snooze_alarm(self, alarm_id: int, minutes: int = 10) -> bool:
        """
        Snooze an alarm for a specified number of minutes.

        Args:
            alarm_id: Alarm ID
            minutes: Minutes to snooze (default 10)

        Returns:
            True if alarm was snoozed, False if not found
        """
        new_time = datetime.now() + timedelta(minutes=minutes)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE alarms
                SET alarm_time = ?, status = 'pending', snooze_count = snooze_count + 1
                WHERE id = ?
            """,
                (new_time.isoformat(), alarm_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Snoozed alarm {alarm_id} for {minutes} minutes")
            return success

    def _schedule_next_occurrence(self, alarm: dict):
        """Schedule the next occurrence of a repeating alarm."""
        repeat_days = alarm.get("repeat_days", [])
        if not repeat_days:
            return

        current_time = datetime.fromisoformat(alarm["alarm_time"])
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        # Find next occurrence
        for days_ahead in range(1, 8):
            next_day = current_time + timedelta(days=days_ahead)
            day_name = day_names[next_day.weekday()]

            if day_name in repeat_days:
                next_time = next_day.replace(
                    hour=current_time.hour, minute=current_time.minute, second=0, microsecond=0
                )

                with self._get_cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO alarms (name, alarm_time, repeat_days, status)
                        VALUES (?, ?, ?, 'pending')
                    """,
                        (alarm.get("name"), next_time.isoformat(), json.dumps(repeat_days)),
                    )

                logger.info(f"Scheduled next occurrence of '{alarm.get('name')}' at {next_time}")
                return

    # ==================== PARSING UTILITIES ====================

    def parse_duration(self, duration_string: str) -> int | None:
        """
        Parse a natural language duration string into seconds.

        Supports formats like:
        - "10 minutes", "10 min"
        - "2 hours", "2 hr"
        - "30 seconds", "30 sec"
        - "1 hour 30 minutes"

        Args:
            duration_string: Natural language duration

        Returns:
            Duration in seconds, or None if unparseable
        """
        duration_string = duration_string.lower().strip()
        total_seconds = 0

        # Patterns for hours, minutes, seconds
        hour_match = re.search(r"(\d+)\s*(?:hour|hr)s?", duration_string)
        minute_match = re.search(r"(\d+)\s*(?:minute|min)s?", duration_string)
        second_match = re.search(r"(\d+)\s*(?:second|sec)s?", duration_string)

        if hour_match:
            total_seconds += int(hour_match.group(1)) * 3600
        if minute_match:
            total_seconds += int(minute_match.group(1)) * 60
        if second_match:
            total_seconds += int(second_match.group(1))

        return total_seconds if total_seconds > 0 else None

    def parse_alarm_time(self, time_string: str) -> datetime | None:
        """
        Parse a natural language time string into a datetime.

        Supports formats like:
        - "7am", "7:30pm"
        - "07:00", "15:30"
        - "tomorrow at 7am"

        Args:
            time_string: Natural language time string

        Returns:
            Parsed datetime or None if unparseable
        """
        time_string = time_string.lower().strip()
        now = datetime.now()

        # Check for "tomorrow at"
        tomorrow_match = re.match(r"tomorrow\s+at\s+(.+)", time_string)
        if tomorrow_match:
            time_part = tomorrow_match.group(1)
            parsed_time = self._parse_time_of_day(time_part)
            if parsed_time:
                tomorrow = now + timedelta(days=1)
                return tomorrow.replace(
                    hour=parsed_time[0], minute=parsed_time[1], second=0, microsecond=0
                )
            return None

        # Parse time of day
        parsed_time = self._parse_time_of_day(time_string)
        if parsed_time:
            result = now.replace(
                hour=parsed_time[0], minute=parsed_time[1], second=0, microsecond=0
            )

            # If time has passed today, assume tomorrow
            if result <= now:
                result += timedelta(days=1)

            return result

        return None

    def _parse_time_of_day(self, time_string: str) -> tuple[int, int] | None:
        """
        Parse a time-of-day string into (hour, minute) tuple.

        Args:
            time_string: Time string like "7am", "15:30"

        Returns:
            Tuple of (hour, minute) or None
        """
        time_string = time_string.strip().lower()

        # Try 12-hour format: "7am", "7:30pm"
        match_12h = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_string)
        if match_12h:
            hour = int(match_12h.group(1))
            minute = int(match_12h.group(2) or 0)
            period = match_12h.group(3)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return (hour, minute)

        # Try 24-hour format: "07:00", "15:30"
        match_24h = re.match(r"(\d{1,2}):(\d{2})", time_string)
        if match_24h:
            hour = int(match_24h.group(1))
            minute = int(match_24h.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)

        return None

    # ==================== FORMATTING UTILITIES ====================

    def format_duration(self, seconds: int) -> str:
        """
        Format seconds as human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            Human-readable string like "5 minutes 30 seconds"
        """
        if seconds <= 0:
            return "0 seconds"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        parts = []
        if hours > 0:
            parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
        if minutes > 0:
            parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
        if secs > 0 and hours == 0:  # Only show seconds if under an hour
            parts.append(f"{secs} second" + ("s" if secs != 1 else ""))

        return " ".join(parts) if parts else "0 seconds"

    # ==================== STATISTICS ====================

    def get_stats(self) -> dict[str, int]:
        """
        Get timer and alarm statistics.

        Returns:
            Dict with counts for timers and alarms
        """
        with self._get_cursor() as cursor:
            # Timer stats
            cursor.execute("SELECT COUNT(*) FROM timers")
            total_timers = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM timers WHERE status = 'running'")
            active_timers = cursor.fetchone()[0]

            # Alarm stats
            cursor.execute("SELECT COUNT(*) FROM alarms")
            total_alarms = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alarms WHERE status IN ('pending', 'snoozed')")
            active_alarms = cursor.fetchone()[0]

            return {
                "total_timers": total_timers,
                "active_timers": active_timers,
                "total_alarms": total_alarms,
                "active_alarms": active_alarms,
            }


# Singleton instance
_timer_manager: TimerManager | None = None


def get_timer_manager() -> TimerManager:
    """Get the singleton TimerManager instance."""
    global _timer_manager
    if _timer_manager is None:
        _timer_manager = TimerManager()
    return _timer_manager
