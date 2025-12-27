"""
Location Manager - Track user location for context-aware commands.

This module manages:
- Voice puck registration with room assignments
- User location tracking from puck activity
- Room name normalization and alias resolution
- Location history and staleness detection
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import DATA_DIR, ROOM_ALIASES, ROOM_ENTITY_MAP


logger = logging.getLogger(__name__)


class LocationManager:
    """
    Manages user location tracking for context-aware smart home commands.

    Features:
    - Voice puck registration with room assignments
    - User location tracking from voice puck activity
    - Default/fallback location configuration
    - Location history and staleness detection
    - Thread-safe database operations
    """

    def __init__(self, db_path: str | None = None, stale_timeout_minutes: int = 30):
        """
        Initialize the LocationManager.

        Args:
            db_path: Path to SQLite database. Defaults to DATA_DIR/locations.db
            stale_timeout_minutes: Minutes after which location is considered stale
        """
        if db_path is None:
            db_path = str(DATA_DIR / "locations.db")

        self.db_path = db_path
        self.stale_timeout_minutes = stale_timeout_minutes
        self._lock = threading.Lock()

        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(f"LocationManager initialized with database at {self.db_path}")

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

            # Voice pucks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_pucks (
                    device_id TEXT PRIMARY KEY,
                    room_name TEXT NOT NULL,
                    display_name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User locations table (single row for current location)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_locations (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    room_name TEXT NOT NULL,
                    source TEXT DEFAULT 'manual',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Location history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS location_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_name TEXT NOT NULL,
                    source TEXT DEFAULT 'manual',
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Settings table (for default location, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS location_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.commit()

    # ========== Room Name Utilities ==========

    def normalize_room_name(self, room_name: str) -> str:
        """
        Normalize a room name to snake_case format.

        Args:
            room_name: Room name in any format

        Returns:
            Normalized room name in snake_case
        """
        if not room_name:
            return ""

        # Strip whitespace and convert to lowercase
        normalized = room_name.strip().lower()

        # Replace spaces with underscores
        normalized = normalized.replace(" ", "_")

        # Remove any double underscores
        while "__" in normalized:
            normalized = normalized.replace("__", "_")

        return normalized

    def resolve_room_alias(self, room_name: str) -> str:
        """
        Resolve room alias to canonical room name.

        Args:
            room_name: Room name or alias

        Returns:
            Canonical room name
        """
        if not room_name:
            return ""

        # First normalize
        normalized = room_name.strip().lower()

        # Check if it's an alias
        if normalized in ROOM_ALIASES:
            return ROOM_ALIASES[normalized]

        # Not an alias, return normalized snake_case
        return self.normalize_room_name(room_name)

    def is_valid_room(self, room_name: str) -> bool:
        """
        Check if a room name is valid (exists in ROOM_ENTITY_MAP or is a valid alias).

        Args:
            room_name: Room name to validate

        Returns:
            True if room is valid
        """
        resolved = self.resolve_room_alias(room_name)
        return resolved in ROOM_ENTITY_MAP

    # ========== Voice Puck Management ==========

    def register_voice_puck(
        self, device_id: str, room_name: str, display_name: str | None = None
    ) -> bool:
        """
        Register a voice puck with its room assignment.

        Args:
            device_id: Unique device identifier from Home Assistant
            room_name: Room where the puck is located
            display_name: Human-readable name for the puck

        Returns:
            True if registration successful
        """
        normalized_room = self.resolve_room_alias(room_name)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR REPLACE INTO voice_pucks
                    (device_id, room_name, display_name, updated_at)
                    VALUES (?, ?, ?, ?)
                """,
                (device_id, normalized_room, display_name, datetime.now().isoformat()),
            )
            conn.commit()

        logger.info(f"Registered voice puck {device_id} in {normalized_room}")
        return True

    def get_voice_puck(self, device_id: str) -> dict[str, Any] | None:
        """
        Get voice puck information by device_id.

        Args:
            device_id: Device identifier

        Returns:
            Dict with puck info or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voice_pucks WHERE device_id = ?", (device_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def update_voice_puck_room(self, device_id: str, room_name: str) -> bool:
        """
        Update the room assignment for a voice puck.

        Args:
            device_id: Device identifier
            room_name: New room name

        Returns:
            True if update successful
        """
        normalized_room = self.resolve_room_alias(room_name)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    UPDATE voice_pucks
                    SET room_name = ?, updated_at = ?
                    WHERE device_id = ?
                """,
                (normalized_room, datetime.now().isoformat(), device_id),
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Updated puck {device_id} to room {normalized_room}")
                return True
            return False

    def list_voice_pucks(self) -> list[dict[str, Any]]:
        """
        List all registered voice pucks.

        Returns:
            List of puck information dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM voice_pucks ORDER BY room_name")
            return [dict(row) for row in cursor.fetchall()]

    def delete_voice_puck(self, device_id: str) -> bool:
        """
        Delete a voice puck registration.

        Args:
            device_id: Device identifier

        Returns:
            True if deletion successful
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM voice_pucks WHERE device_id = ?", (device_id,))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Deleted voice puck {device_id}")
                return True
            return False

    # ========== Location Inference ==========

    def get_room_from_puck(self, device_id: str) -> str | None:
        """
        Get the room associated with a voice puck.

        Args:
            device_id: Voice puck device identifier

        Returns:
            Room name or None if puck not registered
        """
        puck = self.get_voice_puck(device_id)
        if puck:
            return puck["room_name"]
        return None

    def get_room_from_context(self, context: dict[str, Any] | None) -> str | None:
        """
        Extract room from Home Assistant webhook context.

        Args:
            context: HA conversation webhook context dict

        Returns:
            Room name or None if cannot be determined
        """
        if not context:
            return None

        device_id = context.get("device_id")
        if not device_id:
            return None

        return self.get_room_from_puck(device_id)

    def record_puck_activity(self, device_id: str) -> bool:
        """
        Record activity from a voice puck and update user location.

        Args:
            device_id: Voice puck device identifier

        Returns:
            True if location was updated
        """
        room = self.get_room_from_puck(device_id)
        if room:
            self.set_user_location(room, source="voice_puck")
            return True
        return False

    # ========== User Location Tracking ==========

    def set_user_location(self, room_name: str, source: str = "manual") -> bool:
        """
        Set the user's current location.

        Args:
            room_name: Room where user is located
            source: How location was determined (manual, voice_puck, etc.)

        Returns:
            True if location was set
        """
        normalized_room = self.resolve_room_alias(room_name)
        now = datetime.now().isoformat()

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()

            # Update or insert current location
            cursor.execute(
                """
                    INSERT OR REPLACE INTO user_locations
                    (id, room_name, source, updated_at)
                    VALUES (1, ?, ?, ?)
                """,
                (normalized_room, source, now),
            )

            # Record in history
            cursor.execute(
                """
                    INSERT INTO location_history
                    (room_name, source, timestamp)
                    VALUES (?, ?, ?)
                """,
                (normalized_room, source, now),
            )

            conn.commit()

        logger.debug(f"User location set to {normalized_room} (source: {source})")
        return True

    def get_user_location(self) -> str | None:
        """
        Get the user's current location.

        Returns:
            Room name or None if not set
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT room_name FROM user_locations WHERE id = 1")
            row = cursor.fetchone()

            if row:
                return row["room_name"]
            return None

    def get_user_location_info(self) -> dict[str, Any] | None:
        """
        Get detailed information about user's current location.

        Returns:
            Dict with location info or None if not set
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_locations WHERE id = 1")
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def clear_user_location(self) -> bool:
        """
        Clear the user's current location.

        Returns:
            True if location was cleared
        """
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_locations WHERE id = 1")
            conn.commit()
            return True

    # ========== Default Location ==========

    def set_default_location(self, room_name: str) -> bool:
        """
        Set the default fallback location.

        Args:
            room_name: Default room to use when location unknown

        Returns:
            True if default was set
        """
        normalized_room = self.resolve_room_alias(room_name)

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT OR REPLACE INTO location_settings
                    (key, value)
                    VALUES ('default_location', ?)
                """,
                (normalized_room,),
            )
            conn.commit()

        logger.info(f"Default location set to {normalized_room}")
        return True

    def get_default_location(self) -> str | None:
        """
        Get the default fallback location.

        Returns:
            Default room name or None if not set
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM location_settings WHERE key = 'default_location'")
            row = cursor.fetchone()

            if row:
                return row["value"]
            return None

    def get_effective_location(self, explicit_room: str | None = None) -> str | None:
        """
        Get the effective location using priority chain.

        Priority:
        1. Explicit room parameter (if provided)
        2. Current tracked location
        3. Default location

        Args:
            explicit_room: Explicitly specified room (highest priority)

        Returns:
            Room name or None if no location can be determined
        """
        # Priority 1: Explicit room
        if explicit_room:
            return self.resolve_room_alias(explicit_room)

        # Priority 2: Current location (if not stale)
        current = self.get_user_location()
        if current and not self.is_location_stale():
            return current

        # Priority 3: Default location
        return self.get_default_location()

    # ========== Location History ==========

    def get_location_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get location history entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of history entries, most recent first
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT room_name, source, timestamp
                FROM location_history
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    # ========== Staleness Detection ==========

    def is_location_stale(self) -> bool:
        """
        Check if the current location is stale (too old to be reliable).

        Returns:
            True if location is stale or not set
        """
        location_info = self.get_user_location_info()

        if not location_info:
            return True

        updated_at_str = location_info.get("updated_at")
        if not updated_at_str:
            return True

        try:
            updated_at = datetime.fromisoformat(updated_at_str)
            stale_threshold = datetime.now() - timedelta(minutes=self.stale_timeout_minutes)
            return updated_at < stale_threshold
        except (ValueError, TypeError):
            return True
