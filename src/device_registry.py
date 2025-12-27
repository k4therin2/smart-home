"""
Smart Home Assistant - Device Registry

Manages device registration, room assignments, and naming consistency.
Part of WP-5.2: Device Organization Assistant.
"""

import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DATABASE_PATH = DATA_DIR / "devices.db"


class DeviceType(Enum):
    """Supported device types."""

    LIGHT = "light"
    SWITCH = "switch"
    SENSOR = "sensor"
    COVER = "cover"
    CLIMATE = "climate"
    MEDIA_PLAYER = "media_player"
    VACUUM = "vacuum"
    FAN = "fan"
    LOCK = "lock"
    CAMERA = "camera"
    BINARY_SENSOR = "binary_sensor"
    SCENE = "scene"
    SCRIPT = "script"
    AUTOMATION = "automation"
    OTHER = "other"


SUPPORTED_DEVICE_TYPES = [device_type.value for device_type in DeviceType]

# Default rooms to create
DEFAULT_ROOMS = [
    {"name": "living_room", "display_name": "Living Room", "zone": "main_floor"},
    {"name": "bedroom", "display_name": "Bedroom", "zone": "upstairs"},
    {"name": "kitchen", "display_name": "Kitchen", "zone": "main_floor"},
    {"name": "bathroom", "display_name": "Bathroom", "zone": "main_floor"},
    {"name": "office", "display_name": "Office", "zone": "main_floor"},
    {"name": "garage", "display_name": "Garage", "zone": "main_floor"},
    {"name": "hallway", "display_name": "Hallway", "zone": "main_floor"},
]

# Default zones to create
DEFAULT_ZONES = [
    {"name": "main_floor", "display_name": "Main Floor"},
    {"name": "upstairs", "display_name": "Upstairs"},
    {"name": "downstairs", "display_name": "Downstairs"},
    {"name": "outside", "display_name": "Outside"},
]

# Common room name aliases
ROOM_ALIASES = {
    "front_room": "living_room",
    "lounge": "living_room",
    "family_room": "living_room",
    "sitting_room": "living_room",
    "bed_room": "bedroom",
    "master": "master_bedroom",
    "master_bed": "master_bedroom",
    "bath": "bathroom",
    "restroom": "bathroom",
    "wc": "bathroom",
    "study": "office",
    "home_office": "office",
    "work_room": "office",
}


class DeviceRegistry:
    """
    Manages device registration, room/zone assignments, and naming consistency.

    Provides:
    - Device registration with metadata
    - Room and zone management
    - Naming normalization and validation
    - HA synchronization support
    - Device organization statistics
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize DeviceRegistry with database connection.

        Args:
            database_path: Path to SQLite database (defaults to DATA_DIR/devices.db)
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
        """Create tables and default data if they don't exist."""
        with self._get_cursor() as cursor:
            # Create zones table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    name TEXT PRIMARY KEY,
                    display_name TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create rooms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    name TEXT PRIMARY KEY,
                    display_name TEXT,
                    zone_name TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (zone_name) REFERENCES zones(name)
                )
            """)

            # Create devices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_id TEXT UNIQUE NOT NULL,
                    device_type TEXT NOT NULL,
                    friendly_name TEXT,
                    room_name TEXT,
                    zone_name TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    ha_device_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_name) REFERENCES rooms(name),
                    FOREIGN KEY (zone_name) REFERENCES zones(name)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_devices_entity_id
                ON devices(entity_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_devices_room
                ON devices(room_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_devices_type
                ON devices(device_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_rooms_zone
                ON rooms(zone_name)
            """)

            # Create default zones
            for zone in DEFAULT_ZONES:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO zones (name, display_name)
                    VALUES (?, ?)
                """,
                    (zone["name"], zone["display_name"]),
                )

            # Create default rooms
            for room in DEFAULT_ROOMS:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO rooms (name, display_name, zone_name)
                    VALUES (?, ?, ?)
                """,
                    (room["name"], room["display_name"], room.get("zone")),
                )

        logger.info(f"DeviceRegistry initialized with database at {self.database_path}")

    # =========================================================================
    # Device Operations
    # =========================================================================

    def register_device(
        self,
        entity_id: str,
        device_type: DeviceType,
        friendly_name: str,
        room_name: str | None = None,
        zone_name: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        ha_device_id: str | None = None,
    ) -> int:
        """
        Register a new device.

        Args:
            entity_id: Home Assistant entity ID (e.g., "light.living_room")
            device_type: Type of device
            friendly_name: Human-readable name
            room_name: Optional room assignment
            zone_name: Optional zone assignment
            manufacturer: Optional manufacturer name
            model: Optional model name/number
            ha_device_id: Optional HA device ID

        Returns:
            ID of the created device record

        Raises:
            ValueError: If entity_id is empty or already registered
        """
        if not entity_id or not entity_id.strip():
            raise ValueError("entity_id cannot be empty")

        entity_id = entity_id.strip()

        # Check for duplicate
        existing = self.get_device_by_entity_id(entity_id)
        if existing:
            raise ValueError(f"Device {entity_id} is already registered")

        # Normalize room name if provided
        if room_name:
            room_name = self.normalize_room_name(room_name)
            self._ensure_room_exists(room_name)

        # Normalize zone name if provided
        if zone_name:
            zone_name = self.normalize_room_name(zone_name)
            self._ensure_zone_exists(zone_name)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO devices (
                    entity_id, device_type, friendly_name, room_name, zone_name,
                    manufacturer, model, ha_device_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entity_id,
                    device_type.value if isinstance(device_type, DeviceType) else device_type,
                    friendly_name,
                    room_name,
                    zone_name,
                    manufacturer,
                    model,
                    ha_device_id,
                ),
            )

            device_id = cursor.lastrowid
            logger.info(f"Registered device {entity_id} (ID: {device_id})")
            return device_id

    def get_device(self, device_id: int) -> dict[str, Any] | None:
        """
        Get a device by ID.

        Args:
            device_id: Device record ID

        Returns:
            Device dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    def get_device_by_entity_id(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get a device by its Home Assistant entity ID.

        Args:
            entity_id: Home Assistant entity ID

        Returns:
            Device dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM devices WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    def rename_device(self, device_id: int, new_name: str) -> bool:
        """
        Rename a device.

        Args:
            device_id: Device record ID
            new_name: New friendly name

        Returns:
            True if device was renamed, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE devices
                SET friendly_name = ?, updated_at = ?
                WHERE id = ?
            """,
                (new_name, datetime.now().isoformat(), device_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Renamed device {device_id} to '{new_name}'")
            return success

    def move_device_to_room(self, device_id: int, room_name: str) -> bool:
        """
        Move a device to a different room.

        Args:
            device_id: Device record ID
            room_name: Target room name

        Returns:
            True if device was moved, False if not found
        """
        room_name = self.normalize_room_name(room_name)
        self._ensure_room_exists(room_name)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE devices
                SET room_name = ?, updated_at = ?
                WHERE id = ?
            """,
                (room_name, datetime.now().isoformat(), device_id),
            )

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Moved device {device_id} to room '{room_name}'")
            return success

    def get_all_devices(self) -> list[dict[str, Any]]:
        """
        Get all registered devices.

        Returns:
            List of device dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM devices ORDER BY friendly_name")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_devices_by_room(self, room_name: str) -> list[dict[str, Any]]:
        """
        Get all devices in a specific room.

        Args:
            room_name: Room name

        Returns:
            List of device dicts
        """
        room_name = self.normalize_room_name(room_name)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM devices
                WHERE room_name = ?
                ORDER BY friendly_name
            """,
                (room_name,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_devices_by_type(self, device_type: DeviceType) -> list[dict[str, Any]]:
        """
        Get all devices of a specific type.

        Args:
            device_type: Device type to filter by

        Returns:
            List of device dicts
        """
        type_value = device_type.value if isinstance(device_type, DeviceType) else device_type

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM devices
                WHERE device_type = ?
                ORDER BY friendly_name
            """,
                (type_value,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_unassigned_devices(self) -> list[dict[str, Any]]:
        """
        Get all devices without room assignment.

        Returns:
            List of device dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM devices
                WHERE room_name IS NULL
                ORDER BY friendly_name
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # Room Operations
    # =========================================================================

    def create_room(
        self,
        name: str,
        display_name: str,
        zone_name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """
        Create a new room.

        Args:
            name: Room identifier (snake_case)
            display_name: Human-readable name
            zone_name: Optional zone assignment
            description: Optional description

        Returns:
            True if room was created, False if already exists
        """
        name = self.normalize_room_name(name)

        if zone_name:
            zone_name = self.normalize_room_name(zone_name)

        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rooms (name, display_name, zone_name, description)
                    VALUES (?, ?, ?, ?)
                """,
                    (name, display_name, zone_name, description),
                )
                logger.info(f"Created room '{name}'")
                return True
        except sqlite3.IntegrityError:
            return False

    def get_rooms(self) -> list[dict[str, Any]]:
        """
        Get all rooms.

        Returns:
            List of room dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM rooms ORDER BY name")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_rooms_by_zone(self, zone_name: str) -> list[dict[str, Any]]:
        """
        Get all rooms in a specific zone.

        Args:
            zone_name: Zone name

        Returns:
            List of room dicts
        """
        zone_name = self.normalize_room_name(zone_name)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM rooms
                WHERE zone_name = ?
                ORDER BY name
            """,
                (zone_name,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_room(self, room_name: str) -> bool:
        """
        Delete a room. Devices in this room will be unassigned.

        Args:
            room_name: Room name to delete

        Returns:
            True if room was deleted, False if not found
        """
        room_name = self.normalize_room_name(room_name)

        with self._get_cursor() as cursor:
            # Unassign devices first
            cursor.execute(
                """
                UPDATE devices
                SET room_name = NULL, updated_at = ?
                WHERE room_name = ?
            """,
                (datetime.now().isoformat(), room_name),
            )

            # Delete the room
            cursor.execute("DELETE FROM rooms WHERE name = ?", (room_name,))

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted room '{room_name}'")
            return success

    def _ensure_room_exists(self, room_name: str):
        """Ensure a room exists, creating it if necessary."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO rooms (name, display_name)
                VALUES (?, ?)
            """,
                (room_name, room_name.replace("_", " ").title()),
            )

    # =========================================================================
    # Zone Operations
    # =========================================================================

    def create_zone(
        self,
        name: str,
        display_name: str,
        description: str | None = None,
    ) -> bool:
        """
        Create a new zone.

        Args:
            name: Zone identifier (snake_case)
            display_name: Human-readable name
            description: Optional description

        Returns:
            True if zone was created, False if already exists
        """
        name = self.normalize_room_name(name)

        try:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO zones (name, display_name, description)
                    VALUES (?, ?, ?)
                """,
                    (name, display_name, description),
                )
                logger.info(f"Created zone '{name}'")
                return True
        except sqlite3.IntegrityError:
            return False

    def get_zones(self) -> list[dict[str, Any]]:
        """
        Get all zones.

        Returns:
            List of zone dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM zones ORDER BY name")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def _ensure_zone_exists(self, zone_name: str):
        """Ensure a zone exists, creating it if necessary."""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO zones (name, display_name)
                VALUES (?, ?)
            """,
                (zone_name, zone_name.replace("_", " ").title()),
            )

    # =========================================================================
    # Naming Validation
    # =========================================================================

    def normalize_room_name(self, name: str) -> str:
        """
        Normalize a room name to snake_case.

        Args:
            name: Room name in any format

        Returns:
            Normalized room name (lowercase, underscores)
        """
        # Convert to lowercase
        normalized = name.lower().strip()

        # Replace common separators with underscore
        normalized = re.sub(r"[\s\-]+", "_", normalized)

        # Remove any non-alphanumeric characters except underscore
        normalized = re.sub(r"[^a-z0-9_]", "", normalized)

        # Remove consecutive underscores
        normalized = re.sub(r"_+", "_", normalized)

        # Strip leading/trailing underscores
        normalized = normalized.strip("_")

        return normalized

    def get_naming_suggestions(self, room_name: str) -> list[str]:
        """
        Get naming suggestions for a room name.

        Checks for similar existing rooms to maintain consistency.

        Args:
            room_name: Proposed room name

        Returns:
            List of similar existing room names
        """
        normalized = self.normalize_room_name(room_name)
        suggestions = []

        # Check if there's a known alias
        if normalized in ROOM_ALIASES:
            suggestions.append(ROOM_ALIASES[normalized])

        # Get existing rooms and check for similarity
        rooms = self.get_rooms()
        for room in rooms:
            existing = room["name"]

            # Check if names share common root
            if normalized in existing or existing in normalized:
                if existing not in suggestions:
                    suggestions.append(existing)

            # Check for word overlap
            normalized_words = set(normalized.split("_"))
            existing_words = set(existing.split("_"))
            if normalized_words & existing_words:  # Intersection
                if existing not in suggestions:
                    suggestions.append(existing)

        return suggestions

    def validate_room_name(self, room_name: str) -> dict[str, Any]:
        """
        Validate a room name for consistency.

        Args:
            room_name: Proposed room name

        Returns:
            Validation result with potential issues
        """
        normalized = self.normalize_room_name(room_name)
        result = {
            "normalized": normalized,
            "valid": True,
            "similar_existing": None,
            "warnings": [],
        }

        # Check for known aliases
        if normalized in ROOM_ALIASES:
            result["similar_existing"] = ROOM_ALIASES[normalized]
            result["warnings"].append(
                f"'{room_name}' is often used for '{ROOM_ALIASES[normalized]}'"
            )

        # Check for similar existing rooms
        suggestions = self.get_naming_suggestions(room_name)
        if suggestions and normalized not in suggestions:
            result["similar_existing"] = suggestions
            result["warnings"].append(f"Similar rooms exist: {', '.join(suggestions)}")

        return result

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with counts and breakdowns
        """
        with self._get_cursor() as cursor:
            # Total devices
            cursor.execute("SELECT COUNT(*) as count FROM devices")
            total_devices = cursor.fetchone()["count"]

            # Assigned devices
            cursor.execute("SELECT COUNT(*) as count FROM devices WHERE room_name IS NOT NULL")
            assigned_devices = cursor.fetchone()["count"]

            # Devices by type
            cursor.execute("""
                SELECT device_type, COUNT(*) as count
                FROM devices
                GROUP BY device_type
            """)
            devices_by_type = {row["device_type"]: row["count"] for row in cursor.fetchall()}

            # Total rooms
            cursor.execute("SELECT COUNT(*) as count FROM rooms")
            total_rooms = cursor.fetchone()["count"]

            # Total zones
            cursor.execute("SELECT COUNT(*) as count FROM zones")
            total_zones = cursor.fetchone()["count"]

            return {
                "total_devices": total_devices,
                "assigned_devices": assigned_devices,
                "unassigned_devices": total_devices - assigned_devices,
                "total_rooms": total_rooms,
                "total_zones": total_zones,
                "devices_by_type": devices_by_type,
            }

    # =========================================================================
    # HA Synchronization
    # =========================================================================

    def sync_from_ha(self, ha_client) -> list[dict[str, Any]]:
        """
        Synchronize devices from Home Assistant.

        Adds new devices found in HA to the registry.

        Args:
            ha_client: HomeAssistantClient instance

        Returns:
            List of newly added device dicts
        """
        new_devices = []
        states = ha_client.get_all_states()

        for state in states:
            entity_id = state.get("entity_id", "")

            # Skip if already registered
            if self.get_device_by_entity_id(entity_id):
                continue

            # Determine device type from entity_id prefix
            device_type = self._get_device_type_from_entity_id(entity_id)
            if device_type is None:
                continue  # Skip unsupported types

            friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)

            try:
                device_id = self.register_device(
                    entity_id=entity_id,
                    device_type=device_type,
                    friendly_name=friendly_name,
                )

                device = self.get_device(device_id)
                if device:
                    new_devices.append(device)
                    logger.info(f"Synced new device from HA: {entity_id}")

            except ValueError as error:
                logger.warning(f"Could not sync device {entity_id}: {error}")

        return new_devices

    def _get_device_type_from_entity_id(self, entity_id: str) -> DeviceType | None:
        """
        Determine device type from entity ID prefix.

        Args:
            entity_id: Home Assistant entity ID

        Returns:
            DeviceType or None if not supported
        """
        if not entity_id or "." not in entity_id:
            return None

        prefix = entity_id.split(".")[0]

        type_mapping = {
            "light": DeviceType.LIGHT,
            "switch": DeviceType.SWITCH,
            "sensor": DeviceType.SENSOR,
            "binary_sensor": DeviceType.BINARY_SENSOR,
            "cover": DeviceType.COVER,
            "climate": DeviceType.CLIMATE,
            "media_player": DeviceType.MEDIA_PLAYER,
            "vacuum": DeviceType.VACUUM,
            "fan": DeviceType.FAN,
            "lock": DeviceType.LOCK,
            "camera": DeviceType.CAMERA,
            "scene": DeviceType.SCENE,
            "script": DeviceType.SCRIPT,
            "automation": DeviceType.AUTOMATION,
        }

        return type_mapping.get(prefix, DeviceType.OTHER)


# Singleton instance
_device_registry: DeviceRegistry | None = None


def get_device_registry() -> DeviceRegistry:
    """Get the singleton DeviceRegistry instance."""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
    return _device_registry
