"""
Onboarding Agent - Device organization via color identification.

This module manages the device onboarding workflow:
- Discover unassigned lights
- Assign unique colors for visual identification
- Collect room assignments via voice
- Apply mappings to device registry
- Optionally sync to Philips Hue bridge
"""

import sqlite3
import threading
import logging
import uuid
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from enum import Enum

from src.config import DATA_DIR, ROOM_ALIASES
from src.ha_client import get_ha_client
from src.device_registry import get_device_registry


logger = logging.getLogger(__name__)


class OnboardingState(str, Enum):
    """Onboarding session states."""
    DISCOVERING = "discovering"
    IDENTIFYING = "identifying"
    MAPPING = "mapping"
    CONFIRMING = "confirming"
    APPLYING = "applying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Distinct colors for light identification
# Using colors that are visually distinct, including for color-blind users
IDENTIFICATION_COLORS = [
    {"name": "red", "rgb": [255, 0, 0]},
    {"name": "blue", "rgb": [0, 0, 255]},
    {"name": "green", "rgb": [0, 255, 0]},
    {"name": "yellow", "rgb": [255, 255, 0]},
    {"name": "purple", "rgb": [128, 0, 128]},
    {"name": "orange", "rgb": [255, 165, 0]},
    {"name": "cyan", "rgb": [0, 255, 255]},
    {"name": "pink", "rgb": [255, 105, 180]},
    {"name": "white", "rgb": [255, 255, 255]},
    {"name": "lime", "rgb": [0, 255, 128]},
    {"name": "magenta", "rgb": [255, 0, 255]},
    {"name": "teal", "rgb": [0, 128, 128]},
    {"name": "gold", "rgb": [255, 215, 0]},
    {"name": "coral", "rgb": [255, 127, 80]},
    {"name": "lavender", "rgb": [230, 230, 250]},
]


class OnboardingAgent:
    """
    Manages the device onboarding workflow.

    Features:
    - Discover unassigned lights from device registry
    - Assign unique colors for visual identification
    - Process voice input for room assignments
    - Apply mappings to device registry
    - Optional sync to Philips Hue bridge
    - Progress tracking and session resume
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
    ):
        """
        Initialize the OnboardingAgent.

        Args:
            db_path: Path to SQLite database. Defaults to DATA_DIR/onboarding.db
        """
        if db_path is None:
            db_path = str(DATA_DIR / "onboarding.db")

        self.db_path = db_path
        self._lock = threading.Lock()

        # In-memory session state
        self._current_session: Optional[Dict[str, Any]] = None
        self._session_lights: List[Dict[str, Any]] = []
        self._mappings: Dict[str, str] = {}  # entity_id -> room_name

        # Ensure parent directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(f"OnboardingAgent initialized with database at {self.db_path}")

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

            # Onboarding sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS onboarding_sessions (
                    session_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'discovering',
                    total_lights INTEGER DEFAULT 0,
                    completed_mappings INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)

            # Light identifications (color assignments)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS light_identifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    color_name TEXT NOT NULL,
                    rgb TEXT NOT NULL,
                    room_name TEXT,
                    mapped_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES onboarding_sessions(session_id)
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_light_identifications_session
                ON light_identifications(session_id)
            """)

            conn.commit()

    # ========== Device Registry Integration ==========

    def _get_device_registry(self):
        """Get the device registry singleton."""
        return get_device_registry()

    def _get_ha_client(self):
        """Get the Home Assistant client singleton."""
        return get_ha_client()

    # ========== Session Management ==========

    def start_session(self, skip_organized: bool = True) -> Dict[str, Any]:
        """
        Start a new onboarding session.

        Args:
            skip_organized: If True, skip lights already assigned to rooms

        Returns:
            Session info dict

        Raises:
            ValueError: If a session is already active
        """
        # Check for existing active session
        if self.get_current_session() is not None:
            raise ValueError("An onboarding session is already active. Cancel or complete it first.")

        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Discover lights
        lights = self.discover_unassigned_lights() if skip_organized else self._discover_all_lights()

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO onboarding_sessions
                    (session_id, state, total_lights, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, OnboardingState.DISCOVERING.value, len(lights), now, now))
                conn.commit()

        # Set in-memory state
        self._current_session = {
            "session_id": session_id,
            "state": OnboardingState.DISCOVERING.value,
            "total_lights": len(lights),
            "completed_mappings": 0,
            "created_at": now,
        }
        self._session_lights = []
        self._mappings = {}

        # Assign colors to lights
        if lights:
            color_assignments = self.assign_identification_colors(lights)
            self._session_lights = color_assignments
            self._save_light_identifications(session_id, color_assignments)
            self._update_session_state(OnboardingState.IDENTIFYING)

        logger.info(f"Started onboarding session {session_id} with {len(lights)} lights")
        return self._current_session

    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the current active session.

        Returns:
            Session dict or None if no active session
        """
        if self._current_session and self._current_session.get("state") not in [
            OnboardingState.COMPLETED.value,
            OnboardingState.CANCELLED.value
        ]:
            return self._current_session

        # Check database for incomplete session
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM onboarding_sessions
                WHERE state NOT IN (?, ?)
                ORDER BY created_at DESC
                LIMIT 1
            """, (OnboardingState.COMPLETED.value, OnboardingState.CANCELLED.value))
            row = cursor.fetchone()

            if row:
                self._current_session = dict(row)
                return self._current_session

        return None

    def cancel_session(self) -> bool:
        """
        Cancel the current session.

        Returns:
            True if session was cancelled
        """
        session = self.get_current_session()
        if not session:
            return False

        session_id = session["session_id"]

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE onboarding_sessions
                    SET state = ?, updated_at = ?
                    WHERE session_id = ?
                """, (OnboardingState.CANCELLED.value, datetime.now().isoformat(), session_id))
                conn.commit()

        # Clear in-memory state
        self._current_session = None
        self._session_lights = []
        self._mappings = {}

        logger.info(f"Cancelled onboarding session {session_id}")
        return True

    def complete_session(self) -> bool:
        """
        Mark session as completed.

        Returns:
            True if session was completed
        """
        session = self.get_current_session()
        if not session:
            return False

        session_id = session["session_id"]
        now = datetime.now().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE onboarding_sessions
                    SET state = ?, updated_at = ?, completed_at = ?
                    WHERE session_id = ?
                """, (OnboardingState.COMPLETED.value, now, now, session_id))
                conn.commit()

        # Clear in-memory state
        self._current_session = None
        self._session_lights = []
        self._mappings = {}

        logger.info(f"Completed onboarding session {session_id}")
        return True

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        """
        Resume an interrupted session.

        Args:
            session_id: ID of session to resume

        Returns:
            Session dict

        Raises:
            ValueError: If session doesn't exist
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM onboarding_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"Session {session_id} not found")

            self._current_session = dict(row)

            # Load light identifications
            cursor.execute(
                "SELECT * FROM light_identifications WHERE session_id = ?",
                (session_id,)
            )
            lights = []
            for light_row in cursor.fetchall():
                light = dict(light_row)
                lights.append({
                    "entity_id": light["entity_id"],
                    "color_name": light["color_name"],
                    "rgb": eval(light["rgb"]),  # Parse stored list
                    "room_name": light.get("room_name"),
                })
                if light.get("room_name"):
                    self._mappings[light["entity_id"]] = light["room_name"]

            self._session_lights = lights

        logger.info(f"Resumed onboarding session {session_id}")
        return self._current_session

    def _update_session_state(self, state: OnboardingState):
        """Update session state in database and memory."""
        if not self._current_session:
            return

        session_id = self._current_session["session_id"]

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE onboarding_sessions
                    SET state = ?, updated_at = ?
                    WHERE session_id = ?
                """, (state.value, datetime.now().isoformat(), session_id))
                conn.commit()

        self._current_session["state"] = state.value

    def _set_session_lights(self, lights: List[Dict[str, Any]]):
        """Set lights for current session (for testing)."""
        self._session_lights = lights

    def _clear_memory_state(self):
        """Clear in-memory state (for testing resume)."""
        self._current_session = None
        self._session_lights = []
        # Keep mappings in database

    # ========== Light Discovery ==========

    def discover_unassigned_lights(self) -> List[Dict[str, Any]]:
        """
        Discover unassigned light devices.

        Returns:
            List of unassigned light entities
        """
        try:
            registry = self._get_device_registry()
            devices = registry.get_unassigned_devices()

            # Filter to only light entities
            lights = [d for d in devices if d.get("entity_id", "").startswith("light.")]
            return lights
        except Exception as error:
            logger.error(f"Error discovering lights: {error}")
            return []

    def _discover_all_lights(self) -> List[Dict[str, Any]]:
        """Discover all light devices (for full re-onboarding)."""
        try:
            registry = self._get_device_registry()
            devices = registry.get_devices_by_type("light")
            return list(devices)
        except Exception as error:
            logger.error(f"Error discovering all lights: {error}")
            return []

    # ========== Color Assignment ==========

    def get_identification_colors(self) -> List[Dict[str, Any]]:
        """
        Get list of identification colors.

        Returns:
            List of color dicts with name and rgb
        """
        return IDENTIFICATION_COLORS.copy()

    def assign_identification_colors(
        self,
        lights: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Assign unique colors to each light.

        Args:
            lights: List of light entities

        Returns:
            List of assignments with entity_id, color_name, rgb
        """
        colors = self.get_identification_colors()
        assignments = []

        for i, light in enumerate(lights):
            color = colors[i % len(colors)]  # Cycle if more lights than colors
            assignments.append({
                "entity_id": light.get("entity_id"),
                "friendly_name": light.get("friendly_name", light.get("entity_id")),
                "color_name": color["name"],
                "rgb": color["rgb"],
            })

        return assignments

    def _save_light_identifications(
        self,
        session_id: str,
        assignments: List[Dict[str, Any]]
    ):
        """Save light identifications to database."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for assignment in assignments:
                    cursor.execute("""
                        INSERT INTO light_identifications
                        (session_id, entity_id, color_name, rgb)
                        VALUES (?, ?, ?, ?)
                    """, (
                        session_id,
                        assignment["entity_id"],
                        assignment["color_name"],
                        str(assignment["rgb"])
                    ))
                conn.commit()

    # ========== Light Control ==========

    def turn_on_identification_lights(
        self,
        assignments: List[Dict[str, Any]]
    ) -> bool:
        """
        Turn on all lights with their assigned colors.

        Args:
            assignments: List of color assignments

        Returns:
            True if all lights turned on successfully
        """
        try:
            ha_client = self._get_ha_client()
            success = True

            for assignment in assignments:
                entity_id = assignment["entity_id"]
                rgb = assignment["rgb"]

                result = ha_client.turn_on_light(
                    entity_id=entity_id,
                    rgb_color=tuple(rgb),
                    brightness_pct=100
                )
                if not result:
                    success = False
                    logger.warning(f"Failed to turn on {entity_id}")

            return success
        except Exception as error:
            logger.error(f"Error turning on lights: {error}")
            return False

    def turn_off_all_onboarding_lights(self) -> bool:
        """
        Turn off all lights in the current session.

        Returns:
            True if successful
        """
        try:
            ha_client = self._get_ha_client()

            for light in self._session_lights:
                ha_client.turn_off_light(light["entity_id"])

            return True
        except Exception as error:
            logger.error(f"Error turning off lights: {error}")
            return False

    def flash_light(self, entity_id: str, times: int = 3) -> bool:
        """
        Flash a light for confirmation.

        Args:
            entity_id: Light entity ID
            times: Number of flashes

        Returns:
            True if successful
        """
        try:
            ha_client = self._get_ha_client()

            for _ in range(times):
                ha_client.turn_off_light(entity_id)
                time.sleep(0.3)
                ha_client.turn_on_light(entity_id, brightness_pct=100)
                time.sleep(0.3)

            return True
        except Exception as error:
            logger.error(f"Error flashing light: {error}")
            return False

    # ========== Room Mapping ==========

    def record_room_mapping(
        self,
        entity_id: str,
        color_name: str,
        room_name: str
    ) -> bool:
        """
        Record a room assignment for a light.

        Args:
            entity_id: Light entity ID
            color_name: Color the light was showing
            room_name: Room the user specified

        Returns:
            True if recorded successfully
        """
        if not self._current_session:
            return False

        normalized_room = self.normalize_room_name(room_name)
        session_id = self._current_session["session_id"]
        now = datetime.now().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE light_identifications
                    SET room_name = ?, mapped_at = ?
                    WHERE session_id = ? AND entity_id = ?
                """, (normalized_room, now, session_id, entity_id))
                conn.commit()

        self._mappings[entity_id] = normalized_room

        # Update session progress
        self._update_session_progress()

        logger.debug(f"Recorded mapping: {entity_id} ({color_name}) -> {normalized_room}")
        return True

    def _update_session_progress(self):
        """Update session completed count."""
        if not self._current_session:
            return

        completed = len(self._mappings)
        session_id = self._current_session["session_id"]

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE onboarding_sessions
                    SET completed_mappings = ?, updated_at = ?
                    WHERE session_id = ?
                """, (completed, datetime.now().isoformat(), session_id))
                conn.commit()

        self._current_session["completed_mappings"] = completed

    def get_pending_mappings(self) -> List[Dict[str, Any]]:
        """
        Get lights not yet mapped.

        Returns:
            List of unmapped lights
        """
        return [
            light for light in self._session_lights
            if light["entity_id"] not in self._mappings
        ]

    def get_completed_mappings(self) -> List[Dict[str, Any]]:
        """
        Get all completed mappings.

        Returns:
            List of mapped lights with room assignments
        """
        mappings = []
        for light in self._session_lights:
            entity_id = light["entity_id"]
            if entity_id in self._mappings:
                mappings.append({
                    **light,
                    "room_name": self._mappings[entity_id]
                })
        return mappings

    def parse_room_from_voice(self, voice_input: str) -> str:
        """
        Parse room name from natural language input.

        Args:
            voice_input: User's voice input

        Returns:
            Normalized room name
        """
        text = voice_input.lower().strip()

        # Pattern: "[color] is [room]" or "[color] is in [room]"
        match = re.search(r"(?:\w+)\s+is\s+(?:in\s+)?(?:the\s+)?(.+)", text)
        if match:
            room = match.group(1).strip()
            return self.resolve_room_alias(room)

        # Pattern: "that's in the [room]" or "in the [room]"
        match = re.search(r"(?:that'?s?\s+)?(?:in\s+)?(?:the\s+)(.+)", text)
        if match:
            room = match.group(1).strip()
            return self.resolve_room_alias(room)

        # Pattern: "the [color] one is in [room]"
        match = re.search(r"the\s+\w+\s+(?:one\s+)?is\s+(?:in\s+)?(?:the\s+)?(.+)", text)
        if match:
            room = match.group(1).strip()
            return self.resolve_room_alias(room)

        # Fallback: assume entire input is room name
        return self.resolve_room_alias(text)

    # ========== Room Normalization ==========

    def normalize_room_name(self, room_name: str) -> str:
        """
        Normalize room name to snake_case.

        Args:
            room_name: Room name in any format

        Returns:
            Normalized room name
        """
        if not room_name:
            return ""

        # Strip and lowercase
        normalized = room_name.strip().lower()

        # Replace spaces with underscores
        normalized = normalized.replace(" ", "_")

        # Remove double underscores
        while "__" in normalized:
            normalized = normalized.replace("__", "_")

        return normalized

    def resolve_room_alias(self, room_name: str) -> str:
        """
        Resolve room alias to canonical name.

        Args:
            room_name: Room name or alias

        Returns:
            Canonical room name
        """
        if not room_name:
            return ""

        normalized = room_name.strip().lower()

        # Check aliases
        if normalized in ROOM_ALIASES:
            return ROOM_ALIASES[normalized]

        return self.normalize_room_name(room_name)

    # ========== Apply Mappings ==========

    def apply_mappings(self) -> Dict[str, Any]:
        """
        Apply all mappings to the device registry.

        Returns:
            Result dict with success, applied count, errors
        """
        if not self._current_session:
            return {"success": False, "error": "No active session"}

        self._update_session_state(OnboardingState.APPLYING)

        try:
            registry = self._get_device_registry()
            applied = 0
            errors = []

            for entity_id, room_name in self._mappings.items():
                try:
                    # Create room if it doesn't exist
                    existing_room = registry.get_room(room_name)
                    if not existing_room:
                        registry.create_room(room_name)

                    # Move device to room
                    result = registry.move_device_to_room(entity_id, room_name)
                    if result:
                        applied += 1
                    else:
                        errors.append(f"Failed to move {entity_id} to {room_name}")
                except Exception as error:
                    errors.append(f"Error with {entity_id}: {error}")

            return {
                "success": len(errors) == 0,
                "applied": applied,
                "errors": errors,
                "message": f"Applied {applied} room assignments"
            }

        except Exception as error:
            logger.error(f"Error applying mappings: {error}")
            return {"success": False, "error": str(error)}

    # ========== Hue Bridge Sync ==========

    def sync_to_hue_bridge(
        self,
        mappings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Sync room assignments to Philips Hue bridge.

        Args:
            mappings: List of mappings with entity_id, room_name, is_hue

        Returns:
            Result dict
        """
        try:
            # Filter to only Hue lights
            hue_mappings = [m for m in mappings if m.get("is_hue", True)]

            if not hue_mappings:
                return {"success": True, "synced": 0, "message": "No Hue lights to sync"}

            # Group by room
            rooms: Dict[str, List[str]] = {}
            for mapping in hue_mappings:
                room = mapping["room_name"]
                if room not in rooms:
                    rooms[room] = []
                rooms[room].append(mapping["entity_id"])

            # Sync each room
            synced = 0
            for room_name, light_ids in rooms.items():
                if self._sync_hue_room(room_name, light_ids):
                    synced += 1

            return {
                "success": True,
                "synced": synced,
                "message": f"Synced {synced} rooms to Hue bridge"
            }

        except Exception as error:
            logger.error(f"Error syncing to Hue bridge: {error}")
            return {"success": False, "error": str(error)}

    def _sync_hue_room(self, room_name: str, light_ids: List[str]) -> bool:
        """
        Sync a single room to Hue bridge.

        Args:
            room_name: Room name
            light_ids: List of light entity IDs

        Returns:
            True if successful
        """
        try:
            from src.hue_bridge import get_hue_bridge_client, HueBridgeError

            client = get_hue_bridge_client()

            if not client.is_configured():
                logger.warning("Hue bridge not configured - skipping sync")
                return False

            # Map HA entity IDs to Hue device IDs
            device_ids = []
            for entity_id in light_ids:
                device_id = client.get_device_id_from_ha_entity(entity_id)
                if device_id:
                    device_ids.append(device_id)
                else:
                    logger.warning(f"Could not find Hue device for {entity_id}")

            if not device_ids:
                logger.warning(f"No Hue devices found for room {room_name}")
                return False

            # Check if room exists
            existing_room = client.find_room_by_name(room_name)

            if existing_room:
                # Add devices to existing room
                client.add_devices_to_room(existing_room.id, device_ids)
                logger.info(f"Added {len(device_ids)} devices to existing room '{room_name}'")
            else:
                # Create new room
                client.create_room(room_name, device_ids)
                logger.info(f"Created room '{room_name}' with {len(device_ids)} devices")

            return True

        except ImportError:
            logger.error("hue_bridge module not available")
            return False
        except HueBridgeError as error:
            logger.error(f"Hue bridge sync error: {error}")
            return False
        except Exception as error:
            logger.error(f"Unexpected error syncing to Hue: {error}")
            return False

    # ========== Progress Tracking ==========

    def get_progress(self) -> Dict[str, Any]:
        """
        Get onboarding progress.

        Returns:
            Progress dict with completed, total, remaining, percentage
        """
        total = len(self._session_lights)
        completed = len(self._mappings)
        remaining = total - completed
        percentage = (completed / total * 100) if total > 0 else 0

        return {
            "completed": completed,
            "total": total,
            "remaining": remaining,
            "percentage": round(percentage, 2),
        }

    def is_mapping_complete(self) -> bool:
        """
        Check if all lights are mapped.

        Returns:
            True if all lights have room assignments
        """
        return len(self._mappings) >= len(self._session_lights)


# Singleton instance
_onboarding_agent: Optional[OnboardingAgent] = None


def get_onboarding_agent() -> OnboardingAgent:
    """Get or create the OnboardingAgent singleton."""
    global _onboarding_agent
    if _onboarding_agent is None:
        _onboarding_agent = OnboardingAgent()
    return _onboarding_agent
