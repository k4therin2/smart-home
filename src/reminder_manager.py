"""
Smart Home Assistant - Reminder Manager

Manages reminders with scheduling and notifications.
Part of WP-4.1: Todo List & Reminders feature.
"""

import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DATABASE_PATH = DATA_DIR / "reminders.db"

# Valid repeat intervals
VALID_INTERVALS = ["daily", "weekly", "monthly"]


class ReminderManager:
    """
    Manages reminders with scheduling and notifications.

    Provides CRUD operations for reminders with support for:
    - One-time and repeating reminders
    - Links to todo items
    - Natural language time parsing
    - Snooze functionality
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize ReminderManager with database connection.

        Args:
            database_path: Path to SQLite database file
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    todo_id INTEGER,
                    message TEXT NOT NULL,
                    remind_at TIMESTAMP NOT NULL,
                    repeat_interval TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    triggered_at TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reminders_status
                ON reminders(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reminders_remind_at
                ON reminders(remind_at)
            """)

        logger.info(f"ReminderManager initialized with database at {self.database_path}")

    def set_reminder(
        self,
        message: str,
        remind_at: datetime,
        todo_id: int | None = None,
        repeat_interval: str | None = None,
    ) -> int:
        """
        Create a new reminder.

        Args:
            message: Reminder message text
            remind_at: When to trigger the reminder
            todo_id: Optional linked todo item ID
            repeat_interval: Repeat interval ('daily', 'weekly', 'monthly', or None)

        Returns:
            ID of the created reminder

        Raises:
            ValueError: If message is empty or remind_at is in the past
        """
        if not message or not message.strip():
            raise ValueError("message cannot be empty")

        if remind_at < datetime.now():
            raise ValueError("remind_at must be in the future")

        message = message.strip()

        if repeat_interval and repeat_interval not in VALID_INTERVALS:
            repeat_interval = None

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reminders (message, remind_at, todo_id, repeat_interval)
                VALUES (?, ?, ?, ?)
            """,
                (message, remind_at.isoformat(), todo_id, repeat_interval),
            )

            reminder_id = cursor.lastrowid
            logger.info(f"Created reminder {reminder_id}: '{message}' at {remind_at}")
            return reminder_id

    def get_reminder(self, reminder_id: int) -> dict[str, Any] | None:
        """
        Get a reminder by ID.

        Args:
            reminder_id: Reminder ID

        Returns:
            Reminder dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    def get_pending_reminders(self) -> list[dict[str, Any]]:
        """
        Get all pending reminders ordered by time.

        Returns:
            List of pending reminder dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM reminders
                WHERE status = 'pending'
                ORDER BY remind_at ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_due_reminders(self, window_seconds: int = 60) -> list[dict[str, Any]]:
        """
        Get reminders that are due now (within the time window).

        Args:
            window_seconds: Time window in seconds (default 60)

        Returns:
            List of due reminder dicts
        """
        now = datetime.now()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM reminders
                WHERE status = 'pending'
                AND remind_at <= ?
                ORDER BY remind_at ASC
            """,
                (now.isoformat(),),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def trigger_reminder(self, reminder_id: int) -> dict[str, Any]:
        """
        Trigger a reminder (mark as triggered and return notification info).

        Args:
            reminder_id: Reminder ID

        Returns:
            Dict with success status, message, and any linked todo info
        """
        reminder = self.get_reminder(reminder_id)
        if not reminder:
            return {"success": False, "error": "Reminder not found"}

        now = datetime.now().isoformat()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'triggered', triggered_at = ?
                WHERE id = ?
            """,
                (now, reminder_id),
            )

        logger.info(f"Triggered reminder {reminder_id}")

        # Handle repeating reminders
        if reminder["repeat_interval"]:
            self._schedule_next_occurrence(reminder)

        return {
            "success": True,
            "message": reminder["message"],
            "todo_id": reminder["todo_id"],
            "triggered_at": now,
        }

    def _schedule_next_occurrence(self, reminder: dict):
        """Schedule the next occurrence of a repeating reminder."""
        interval = reminder["repeat_interval"]
        current_time = datetime.fromisoformat(reminder["remind_at"])

        if interval == "daily":
            next_time = current_time + timedelta(days=1)
        elif interval == "weekly":
            next_time = current_time + timedelta(weeks=1)
        elif interval == "monthly":
            # Approximate month as 30 days
            next_time = current_time + timedelta(days=30)
        else:
            return

        # Ensure next time is in the future
        while next_time < datetime.now():
            if interval == "daily":
                next_time += timedelta(days=1)
            elif interval == "weekly":
                next_time += timedelta(weeks=1)
            else:
                next_time += timedelta(days=30)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reminders (message, remind_at, todo_id, repeat_interval)
                VALUES (?, ?, ?, ?)
            """,
                (reminder["message"], next_time.isoformat(), reminder["todo_id"], interval),
            )

        logger.info(f"Scheduled next occurrence of '{reminder['message']}' at {next_time}")

    def dismiss_reminder(self, reminder_id: int) -> bool:
        """
        Dismiss a reminder (mark as dismissed without triggering).

        Args:
            reminder_id: Reminder ID

        Returns:
            True if dismissed, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE reminders
                SET status = 'dismissed'
                WHERE id = ?
            """,
                (reminder_id,),
            )
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Dismissed reminder {reminder_id}")
            return success

    def delete_reminder(self, reminder_id: int) -> bool:
        """
        Delete a reminder.

        Args:
            reminder_id: Reminder ID

        Returns:
            True if deleted, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Deleted reminder {reminder_id}")
            return success

    def snooze_reminder(
        self,
        reminder_id: int,
        new_time: datetime | None = None,
        minutes: int | None = None,
    ) -> bool:
        """
        Snooze a reminder to a new time.

        Args:
            reminder_id: Reminder ID
            new_time: New remind_at time (mutually exclusive with minutes)
            minutes: Minutes from now to snooze (mutually exclusive with new_time)

        Returns:
            True if snoozed, False if not found
        """
        if new_time is None and minutes is None:
            raise ValueError("Either new_time or minutes must be provided")

        if minutes is not None:
            new_time = datetime.now() + timedelta(minutes=minutes)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE reminders
                SET remind_at = ?, status = 'pending'
                WHERE id = ?
            """,
                (new_time.isoformat(), reminder_id),
            )
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Snoozed reminder {reminder_id} to {new_time}")
            return success

    def get_stats(self) -> dict[str, int]:
        """
        Get reminder statistics.

        Returns:
            Dict with total, pending, triggered, and dismissed counts
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'triggered' THEN 1 ELSE 0 END) as triggered,
                    SUM(CASE WHEN status = 'dismissed' THEN 1 ELSE 0 END) as dismissed
                FROM reminders
            """)
            row = cursor.fetchone()
            return {
                "total": row["total"] or 0,
                "pending": row["pending"] or 0,
                "triggered": row["triggered"] or 0,
                "dismissed": row["dismissed"] or 0,
            }

    def parse_reminder_time(self, time_string: str) -> datetime | None:
        """
        Parse a natural language time string into a datetime.

        Supports formats like:
        - "3pm", "3:00pm", "15:00"
        - "in 2 hours", "in 30 minutes"
        - "tomorrow at 9am"

        Args:
            time_string: Natural language time string

        Returns:
            Parsed datetime or None if unparseable
        """
        time_string = time_string.lower().strip()
        now = datetime.now()

        # Try relative time: "in X hours/minutes"
        relative_match = re.match(r"in\s+(\d+)\s+(hour|minute|min)s?", time_string)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            if unit.startswith("hour"):
                return now + timedelta(hours=amount)
            else:
                return now + timedelta(minutes=amount)

        # Try "tomorrow at Xam/pm"
        tomorrow_match = re.match(r"tomorrow\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_string)
        if tomorrow_match:
            hour = int(tomorrow_match.group(1))
            minute = int(tomorrow_match.group(2) or 0)
            period = tomorrow_match.group(3)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Try absolute time: "Xpm", "X:XXpm", "XX:XX"
        time_match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_string)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            elif period is None and hour < 12:
                # Assume 24-hour format or context-aware
                pass

            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time has passed today, assume tomorrow
            if result <= now:
                result += timedelta(days=1)

            return result

        return None


# Singleton instance
_reminder_manager: ReminderManager | None = None


def get_reminder_manager() -> ReminderManager:
    """Get the singleton ReminderManager instance."""
    global _reminder_manager
    if _reminder_manager is None:
        _reminder_manager = ReminderManager()
    return _reminder_manager
