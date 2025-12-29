"""
Presence Manager - Track user presence for automation.

This module manages:
- Multi-source presence detection (WiFi, GPS, manual)
- Presence state tracking (home/away/arriving/leaving)
- Pattern learning for departure/arrival predictions
- Vacuum automation triggers
"""

import logging
import sqlite3
import threading
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.ha_client import get_ha_client
from src.utils import send_health_alert


logger = logging.getLogger(__name__)


class PresenceState(str, Enum):
    """Valid presence states."""

    HOME = "home"
    AWAY = "away"
    ARRIVING = "arriving"
    LEAVING = "leaving"
    UNKNOWN = "unknown"


class PresenceSource(str, Enum):
    """Sources of presence detection."""

    ROUTER = "router"
    GPS = "gps"
    BLUETOOTH = "bluetooth"
    MANUAL = "manual"
    PATTERN = "pattern"
    UNKNOWN = "unknown"


# Default confidence scores by source type
SOURCE_CONFIDENCE = {
    "router": 0.95,  # WiFi is very reliable for home detection
    "gps": 0.8,  # GPS can have accuracy issues
    "bluetooth": 0.85,
    "manual": 1.0,  # User explicit input
    "pattern": 0.6,  # Predictions have lower confidence
    "unknown": 0.5,
}

# Source priority (higher = more trusted)
SOURCE_PRIORITY = {
    "router": 10,
    "bluetooth": 8,
    "gps": 5,
    "pattern": 2,
    "manual": 15,  # Manual always wins
    "unknown": 1,
}


class PresenceManager:
    """
    Manages user presence detection for smart home automation.

    Features:
    - Multi-source presence detection (WiFi, GPS, manual)
    - Presence state tracking (home/away/arriving/leaving)
    - Pattern learning for typical departure/arrival times
    - Callback hooks for vacuum automation
    - Thread-safe database operations
    """

    VALID_STATES = {"home", "away", "arriving", "leaving", "unknown"}

    def __init__(
        self,
        db_path: str | None = None,
        home_zone_radius: int = 100,
        arriving_distance: int = 500,
        vacuum_start_delay: int = 5,
    ):
        """
        Initialize the PresenceManager.

        Args:
            db_path: Path to SQLite database. Defaults to DATA_DIR/presence.db
            home_zone_radius: Radius in meters for home zone
            arriving_distance: Distance in meters to trigger 'arriving' state
            vacuum_start_delay: Minutes to wait before starting vacuum after departure
        """
        if db_path is None:
            db_path = str(DATA_DIR / "presence.db")

        self.db_path = db_path
        self._lock = threading.Lock()

        # Default settings
        self._home_zone_radius = home_zone_radius
        self._arriving_distance = arriving_distance
        self._vacuum_start_delay = vacuum_start_delay

        # Callbacks for presence events
        self._on_departure_callbacks: list[Callable] = []
        self._on_arrival_callbacks: list[Callable] = []

        # Tracker states cache
        self._tracker_states: dict[str, dict[str, Any]] = {}

        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(f"PresenceManager initialized with database at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get a thread-safe database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Presence state table (single row for current state)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presence_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state TEXT NOT NULL DEFAULT 'unknown',
                    source TEXT DEFAULT 'unknown',
                    confidence REAL DEFAULT 0.5,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)

            # Device trackers registration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_trackers (
                    entity_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    display_name TEXT,
                    priority INTEGER DEFAULT 5,
                    enabled INTEGER DEFAULT 1,
                    last_state TEXT,
                    last_updated TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Presence history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presence_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state TEXT NOT NULL,
                    source TEXT,
                    confidence REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for history queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_presence_history_timestamp
                ON presence_history(timestamp)
            """)

            # Pattern learning table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presence_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    hour INTEGER NOT NULL,
                    minute INTEGER NOT NULL,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for pattern queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_patterns_type_day
                ON presence_patterns(pattern_type, day_of_week)
            """)

            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presence_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Initialize settings if not present
            cursor.execute(
                """
                INSERT OR IGNORE INTO presence_settings (key, value)
                VALUES ('home_zone_radius', ?)
            """,
                (str(self._home_zone_radius),),
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO presence_settings (key, value)
                VALUES ('arriving_distance', ?)
            """,
                (str(self._arriving_distance),),
            )

            cursor.execute(
                """
                INSERT OR IGNORE INTO presence_settings (key, value)
                VALUES ('vacuum_start_delay', ?)
            """,
                (str(self._vacuum_start_delay),),
            )

            conn.commit()

    # ========== Device Tracker Management ==========

    def register_device_tracker(
        self,
        entity_id: str,
        source_type: str,
        display_name: str | None = None,
        priority: int | None = None,
    ) -> bool:
        """
        Register a device tracker for presence detection.

        Args:
            entity_id: Home Assistant entity ID (e.g., device_tracker.phone)
            source_type: Type of tracker (gps, router, bluetooth)
            display_name: Human-readable name
            priority: Priority for conflict resolution (higher = more trusted)

        Returns:
            True if registration successful
        """
        if priority is None:
            priority = SOURCE_PRIORITY.get(source_type, 5)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR REPLACE INTO device_trackers
                    (entity_id, source_type, display_name, priority, enabled)
                    VALUES (?, ?, ?, ?, 1)
                """,
                (entity_id, source_type, display_name, priority),
            )
            conn.commit()

        logger.info(f"Registered device tracker: {entity_id} ({source_type})")
        return True

    def get_device_tracker(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get device tracker information.

        Args:
            entity_id: Device tracker entity ID

        Returns:
            Tracker info dict or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM device_trackers WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()

            if row:
                result = dict(row)
                result["enabled"] = bool(result.get("enabled", 1))
                return result
            return None

    def list_device_trackers(self) -> list[dict[str, Any]]:
        """
        List all registered device trackers.

        Returns:
            List of tracker info dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM device_trackers ORDER BY priority DESC")
            trackers = []
            for row in cursor.fetchall():
                tracker = dict(row)
                tracker["enabled"] = bool(tracker.get("enabled", 1))
                trackers.append(tracker)
            return trackers

    def remove_device_tracker(self, entity_id: str) -> bool:
        """
        Remove a device tracker.

        Args:
            entity_id: Device tracker entity ID

        Returns:
            True if removal successful
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM device_trackers WHERE entity_id = ?", (entity_id,))
            conn.commit()
            success = cursor.rowcount > 0

        if success:
            logger.info(f"Removed device tracker: {entity_id}")
        return success

    def update_tracker_priority(self, entity_id: str, priority: int) -> bool:
        """
        Update tracker priority.

        Args:
            entity_id: Device tracker entity ID
            priority: New priority value

        Returns:
            True if update successful
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    UPDATE device_trackers
                    SET priority = ?
                    WHERE entity_id = ?
                """,
                (priority, entity_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def set_tracker_enabled(self, entity_id: str, enabled: bool) -> bool:
        """
        Enable or disable a tracker.

        Args:
            entity_id: Device tracker entity ID
            enabled: Whether tracker is enabled

        Returns:
            True if update successful
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    UPDATE device_trackers
                    SET enabled = ?
                    WHERE entity_id = ?
                """,
                (1 if enabled else 0, entity_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ========== Presence State Management ==========

    def set_presence_state(
        self,
        state: str,
        source: str = "unknown",
        confidence: float | None = None,
        record_history: bool = True,
    ) -> bool:
        """
        Set the current presence state.

        Args:
            state: Presence state (home, away, arriving, leaving)
            source: Source of detection
            confidence: Confidence score (0-1)
            record_history: Whether to record in history

        Returns:
            True if state was set

        Raises:
            ValueError: If state is invalid
        """
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid presence state: {state}. Valid states: {self.VALID_STATES}")

        if confidence is None:
            confidence = SOURCE_CONFIDENCE.get(source, 0.5)

        now = datetime.now().isoformat()
        old_state = self.get_presence_state()
        old_state_value = old_state.get("state", "unknown")

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Update current state
            cursor.execute(
                """
                    INSERT OR REPLACE INTO presence_state
                    (id, state, source, confidence, updated_at)
                    VALUES (1, ?, ?, ?, ?)
                """,
                (state, source, confidence, now),
            )

            # Record in history if state changed
            if record_history and state != old_state_value:
                cursor.execute(
                    """
                        INSERT INTO presence_history
                        (state, source, confidence, timestamp)
                        VALUES (?, ?, ?, ?)
                    """,
                    (state, source, confidence, now),
                )

                # Record pattern if transitioning between home/away
                if old_state_value == "home" and state in ["away", "leaving"]:
                    self._record_departure_pattern(cursor, now)
                elif old_state_value in ["away", "arriving"] and state == "home":
                    self._record_arrival_pattern(cursor, now)

            conn.commit()

        # Fire callbacks on state transitions
        if state != old_state_value:
            if old_state_value == "home" and state in ["away", "leaving"]:
                self._fire_departure_callbacks()
            elif old_state_value in ["away", "leaving"] and state in ["home", "arriving"]:
                self._fire_arrival_callbacks()

            # Send Slack alert for presence state changes (WP-10.5)
            self._send_presence_alert(old_state_value, state, source, confidence)

        logger.debug(f"Presence state set to {state} (source: {source}, confidence: {confidence})")
        return True

    def _send_presence_alert(
        self,
        old_state: str,
        new_state: str,
        source: str,
        confidence: float,
    ) -> None:
        """
        Send Slack alert for presence state change.

        Args:
            old_state: Previous presence state
            new_state: New presence state
            source: Source of detection
            confidence: Confidence score
        """
        try:
            send_health_alert(
                title=f"Presence State Change: {new_state.capitalize()}",
                message=f"Presence changed from {old_state} to {new_state}",
                severity="info",
                component="presence",
                details={
                    "previous_state": old_state,
                    "new_state": new_state,
                    "source": source,
                    "confidence": confidence,
                },
            )
        except Exception as error:
            logger.error(f"Failed to send presence alert: {error}")

    def _record_departure_pattern(self, cursor, timestamp_str: str):
        """Record departure time for pattern learning."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            cursor.execute(
                """
                INSERT INTO presence_patterns
                (pattern_type, day_of_week, hour, minute, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("departure", timestamp.weekday(), timestamp.hour, timestamp.minute, timestamp_str),
            )
        except Exception as error:
            logger.error(f"Error recording departure pattern: {error}")

    def _record_arrival_pattern(self, cursor, timestamp_str: str):
        """Record arrival time for pattern learning."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            cursor.execute(
                """
                INSERT INTO presence_patterns
                (pattern_type, day_of_week, hour, minute, recorded_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                ("arrival", timestamp.weekday(), timestamp.hour, timestamp.minute, timestamp_str),
            )
        except Exception as error:
            logger.error(f"Error recording arrival pattern: {error}")

    def get_presence_state(self) -> dict[str, Any]:
        """
        Get the current presence state.

        Returns:
            Dict with state info (state, source, confidence, updated_at)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM presence_state WHERE id = 1")
            row = cursor.fetchone()

            if row:
                return dict(row)

            return {
                "id": 1,
                "state": "unknown",
                "source": "unknown",
                "confidence": 0.0,
                "updated_at": None,
                "expires_at": None,
            }

    # ========== Multi-Source Detection ==========

    def update_from_tracker(
        self, entity_id: str, state: str, distance_from_home: float | None = None
    ) -> bool:
        """
        Update presence based on device tracker state.

        Args:
            entity_id: Device tracker entity ID
            state: Tracker state (home, not_home, away, etc.)
            distance_from_home: Distance from home in meters (for GPS)

        Returns:
            True if presence was updated
        """
        tracker = self.get_device_tracker(entity_id)
        if not tracker:
            # Auto-register if not found
            self.register_device_tracker(entity_id, "unknown")
            tracker = self.get_device_tracker(entity_id)

        if not tracker or not tracker.get("enabled", True):
            return False

        source_type = tracker.get("source_type", "unknown")
        priority = tracker.get("priority", 5)

        # Normalize state
        if state in ["home", "Home"]:
            normalized_state = "home"
        elif state in ["not_home", "away", "Away"]:
            # Check if arriving based on distance
            if distance_from_home is not None:
                arriving_dist = self.get_arriving_distance()
                if distance_from_home <= arriving_dist:
                    normalized_state = "arriving"
                else:
                    normalized_state = "away"
            else:
                normalized_state = "away"
        else:
            normalized_state = "away"

        # Cache tracker state
        self._tracker_states[entity_id] = {
            "state": normalized_state,
            "updated_at": datetime.now().isoformat(),
            "source_type": source_type,
            "priority": priority,
        }

        # Update last state in database
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    UPDATE device_trackers
                    SET last_state = ?, last_updated = ?
                    WHERE entity_id = ?
                """,
                (normalized_state, datetime.now().isoformat(), entity_id),
            )
            conn.commit()

        # Calculate combined presence state
        return self._calculate_combined_presence()

    def _calculate_combined_presence(self) -> bool:
        """
        Calculate combined presence from all tracker states.

        Uses priority-weighted voting with confidence adjustment.

        Returns:
            True if presence was updated
        """
        if not self._tracker_states:
            return False

        # Group by state
        home_weight = 0
        away_weight = 0
        arriving_weight = 0

        for entity_id, tracker_info in self._tracker_states.items():
            state = tracker_info.get("state")
            priority = tracker_info.get("priority", 5)
            source_type = tracker_info.get("source_type", "unknown")
            base_confidence = SOURCE_CONFIDENCE.get(source_type, 0.5)

            weight = priority * base_confidence

            if state == "home":
                home_weight += weight
            elif state == "arriving":
                arriving_weight += weight
            else:  # away or other
                away_weight += weight

        # Determine final state
        if home_weight > away_weight and home_weight > arriving_weight:
            final_state = "home"
            total_weight = home_weight + away_weight + arriving_weight
            confidence = home_weight / total_weight if total_weight > 0 else 0.5
        elif arriving_weight > away_weight:
            final_state = "arriving"
            total_weight = home_weight + away_weight + arriving_weight
            confidence = arriving_weight / total_weight if total_weight > 0 else 0.5
        else:
            final_state = "away"
            total_weight = home_weight + away_weight + arriving_weight
            confidence = away_weight / total_weight if total_weight > 0 else 0.5

        # Check for conflicts that lower confidence
        if home_weight > 0 and away_weight > 0:
            confidence *= 0.8  # Lower confidence due to conflicting sources

        return self.set_presence_state(final_state, source="combined", confidence=confidence)

    # ========== Presence History ==========

    def get_presence_history(
        self, limit: int = 20, start_date: datetime | None = None, end_date: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Get presence history entries.

        Args:
            limit: Maximum entries to return
            start_date: Filter from this date
            end_date: Filter to this date

        Returns:
            List of history entries, newest first
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM presence_history"
            params = []
            conditions = []

            if start_date:
                conditions.append("timestamp >= ?")
                params.append(start_date.isoformat())

            if end_date:
                conditions.append("timestamp <= ?")
                params.append(end_date.isoformat())

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    # ========== Pattern Learning ==========

    def _record_pattern(self, pattern_type: str, day_of_week: int, hour: int, minute: int):
        """
        Record a pattern for learning.

        Args:
            pattern_type: 'departure' or 'arrival'
            day_of_week: 0-6 (Monday-Sunday)
            hour: 0-23
            minute: 0-59
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT INTO presence_patterns
                    (pattern_type, day_of_week, hour, minute, recorded_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                (pattern_type, day_of_week, hour, minute, datetime.now().isoformat()),
            )
            conn.commit()

    def get_patterns(self) -> list[dict[str, Any]]:
        """
        Get all recorded patterns.

        Returns:
            List of pattern records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM presence_patterns ORDER BY recorded_at DESC LIMIT 100")
            return [dict(row) for row in cursor.fetchall()]

    def predict_departure(self, day_of_week: int) -> dict[str, Any] | None:
        """
        Predict typical departure time for a day of week.

        Args:
            day_of_week: 0-6 (Monday-Sunday)

        Returns:
            Dict with predicted hour, minute, and confidence, or None
        """
        return self._predict_pattern("departure", day_of_week)

    def predict_arrival(self, day_of_week: int) -> dict[str, Any] | None:
        """
        Predict typical arrival time for a day of week.

        Args:
            day_of_week: 0-6 (Monday-Sunday)

        Returns:
            Dict with predicted hour, minute, and confidence, or None
        """
        return self._predict_pattern("arrival", day_of_week)

    def _predict_pattern(
        self, pattern_type: str, day_of_week: int, min_data_points: int = 3
    ) -> dict[str, Any] | None:
        """
        Predict pattern time based on historical data.

        Args:
            pattern_type: 'departure' or 'arrival'
            day_of_week: 0-6
            min_data_points: Minimum data points for reliable prediction

        Returns:
            Prediction dict or None if not enough data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT hour, minute FROM presence_patterns
                WHERE pattern_type = ? AND day_of_week = ?
                ORDER BY recorded_at DESC
                LIMIT 20
            """,
                (pattern_type, day_of_week),
            )

            rows = cursor.fetchall()

            if len(rows) < min_data_points:
                return None

            # Calculate average time
            total_minutes = sum(row["hour"] * 60 + row["minute"] for row in rows)
            avg_minutes = total_minutes / len(rows)

            avg_hour = int(avg_minutes // 60)
            avg_minute = int(avg_minutes % 60)

            # Calculate confidence based on variance
            variance = sum(
                (row["hour"] * 60 + row["minute"] - avg_minutes) ** 2 for row in rows
            ) / len(rows)

            # Lower variance = higher confidence
            # Normalize: 0 variance = 1.0 confidence, high variance = low confidence
            confidence = max(0.3, 1.0 - (variance / (60 * 60)))  # 60 min variance = ~0.3

            return {
                "hour": avg_hour,
                "minute": avg_minute,
                "confidence": round(confidence, 2),
                "data_points": len(rows),
            }

    # ========== Manual Override ==========

    def manual_set_presence(self, state: str, duration_minutes: int | None = None) -> bool:
        """
        Manually set presence state (override).

        Args:
            state: Presence state
            duration_minutes: Optional duration for override

        Returns:
            True if set successfully
        """
        if state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {state}")

        expires_at = None
        if duration_minutes:
            expires_at = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR REPLACE INTO presence_state
                    (id, state, source, confidence, updated_at, expires_at)
                    VALUES (1, ?, 'manual', 1.0, ?, ?)
                """,
                (state, datetime.now().isoformat(), expires_at),
            )

            # Record in history
            cursor.execute(
                """
                    INSERT INTO presence_history
                    (state, source, confidence, timestamp)
                    VALUES (?, 'manual', 1.0, ?)
                """,
                (state, datetime.now().isoformat()),
            )

            conn.commit()

        logger.info(f"Manual presence override: {state}")
        return True

    def clear_manual_override(self) -> bool:
        """
        Clear manual override (revert to automatic detection).

        Returns:
            True if cleared
        """
        # Clear tracker states cache to force recalculation
        if self._tracker_states:
            self._calculate_combined_presence()
        else:
            # No trackers, set to unknown
            with self._lock, self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                        UPDATE presence_state
                        SET state = 'unknown', source = 'unknown',
                            confidence = 0.5, expires_at = NULL
                        WHERE id = 1
                    """)
                conn.commit()

        logger.info("Manual presence override cleared")
        return True

    # ========== Vacuum Automation ==========

    def on_departure(self, callback: Callable):
        """
        Register callback for departure events.

        Args:
            callback: Function to call on departure
        """
        self._on_departure_callbacks.append(callback)

    def on_arrival(self, callback: Callable):
        """
        Register callback for arrival events.

        Args:
            callback: Function to call on arrival
        """
        self._on_arrival_callbacks.append(callback)

    def _fire_departure_callbacks(self):
        """Fire all departure callbacks."""
        for callback in self._on_departure_callbacks:
            try:
                callback()
            except Exception as error:
                logger.error(f"Error in departure callback: {error}")

    def _fire_arrival_callbacks(self):
        """Fire all arrival callbacks."""
        for callback in self._on_arrival_callbacks:
            try:
                callback()
            except Exception as error:
                logger.error(f"Error in arrival callback: {error}")

    def set_vacuum_start_delay(self, minutes: int) -> bool:
        """
        Set delay before vacuum starts after departure.

        Args:
            minutes: Delay in minutes

        Returns:
            True if set successfully
        """
        return self._set_setting("vacuum_start_delay", str(minutes))

    def get_vacuum_start_delay(self) -> int:
        """
        Get vacuum start delay.

        Returns:
            Delay in minutes
        """
        value = self._get_setting("vacuum_start_delay")
        return int(value) if value else self._vacuum_start_delay

    # ========== Settings ==========

    def set_home_zone_radius(self, meters: int) -> bool:
        """Set home zone radius in meters."""
        return self._set_setting("home_zone_radius", str(meters))

    def get_home_zone_radius(self) -> int:
        """Get home zone radius in meters."""
        value = self._get_setting("home_zone_radius")
        return int(value) if value else self._home_zone_radius

    def set_arriving_distance(self, meters: int) -> bool:
        """Set distance at which 'arriving' is detected."""
        return self._set_setting("arriving_distance", str(meters))

    def get_arriving_distance(self) -> int:
        """Get arriving distance in meters."""
        value = self._get_setting("arriving_distance")
        return int(value) if value else self._arriving_distance

    def get_settings(self) -> dict[str, Any]:
        """Get all presence settings."""
        return {
            "home_zone_radius": self.get_home_zone_radius(),
            "arriving_distance": self.get_arriving_distance(),
            "vacuum_start_delay": self.get_vacuum_start_delay(),
        }

    def _set_setting(self, key: str, value: str) -> bool:
        """Set a setting value."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR REPLACE INTO presence_settings (key, value)
                    VALUES (?, ?)
                """,
                (key, value),
            )
            conn.commit()
        return True

    def _get_setting(self, key: str) -> str | None:
        """Get a setting value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM presence_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    # ========== Home Assistant Integration ==========

    def discover_ha_trackers(self) -> list[dict[str, Any]]:
        """
        Discover device trackers from Home Assistant.

        Returns:
            List of discovered device trackers
        """
        try:
            client = get_ha_client()
            all_states = client.get_all_states()

            trackers = []
            for state in all_states:
                entity_id = state.get("entity_id", "")
                if entity_id.startswith("device_tracker."):
                    trackers.append(
                        {
                            "entity_id": entity_id,
                            "state": state.get("state"),
                            "attributes": state.get("attributes", {}),
                        }
                    )

            return trackers
        except Exception as error:
            logger.error(f"Error discovering HA trackers: {error}")
            return []

    def sync_tracker_from_ha(self, entity_id: str) -> bool:
        """
        Sync a device tracker state from Home Assistant.

        Args:
            entity_id: Device tracker entity ID

        Returns:
            True if sync successful
        """
        try:
            client = get_ha_client()
            state = client.get_state(entity_id)

            if state:
                tracker_state = state.get("state", "unknown")
                attributes = state.get("attributes", {})

                # Get distance if available (GPS trackers)
                distance = None
                if "latitude" in attributes and "longitude" in attributes:
                    # Could calculate distance from home here
                    # For now, just use state
                    pass

                return self.update_from_tracker(
                    entity_id, state=tracker_state, distance_from_home=distance
                )

            return False
        except Exception as error:
            logger.error(f"Error syncing tracker from HA: {error}")
            return False


# Singleton instance
_presence_manager: PresenceManager | None = None


def get_presence_manager() -> PresenceManager:
    """Get or create the PresenceManager singleton."""
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager
