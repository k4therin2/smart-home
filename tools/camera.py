"""
Smart Home Assistant - Ring Camera Control Tools

Tools for monitoring Ring cameras (doorbell and indoor) through Home Assistant.
Supports listing cameras, capturing snapshots, and checking house status.

Ring cameras are integrated via the Home Assistant Ring integration which provides:
- camera.xyz_live_view - Real-time camera feed
- camera.xyz_last_recording - Last recorded video (requires Ring Protect)
- binary_sensor.xyz_motion - Motion detection
- binary_sensor.xyz_ding - Doorbell events
- sensor.xyz_battery - Battery level
- sensor.xyz_wifi_signal - WiFi signal strength

References:
- https://www.home-assistant.io/integrations/ring/

Part of WP-9.2: Ring Camera Integration
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config import DATA_DIR
from src.ha_client import get_ha_client
from src.utils import setup_logging

logger = setup_logging("tools.camera")


# =============================================================================
# Camera Registry - Tracks camera locations (user moves cameras around)
# =============================================================================

class CameraRegistry:
    """
    Registry for tracking camera positions/locations.

    Since Ring cameras (especially indoor ones) are frequently moved,
    this registry helps the system understand where each camera is currently
    positioned in the home.
    """

    def __init__(self):
        self.registry_file = Path(DATA_DIR) / "camera_registry.json"
        self._cache = None

    def _load(self) -> dict:
        """Load registry from file."""
        if self._cache is not None:
            return self._cache

        if self.registry_file.exists():
            with open(self.registry_file, "r") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

        return self._cache

    def _save(self) -> None:
        """Save registry to file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, "w") as f:
            json.dump(self._cache, f, indent=2)

    def set_camera_location(
        self,
        entity_id: str,
        location: str,
        description: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Register or update a camera's location.

        Args:
            entity_id: Camera entity ID
            location: Room or area name (e.g., "living room", "front porch")
            description: Optional description (e.g., "Corner by the TV")

        Returns:
            Result dictionary
        """
        registry = self._load()

        registry[entity_id] = {
            "location": location,
            "description": description,
            "updated_at": datetime.now().isoformat(),
        }

        self._cache = registry
        self._save()

        logger.info(f"Registered camera {entity_id} at {location}")
        return {
            "success": True,
            "entity_id": entity_id,
            "location": location,
            "message": f"Camera registered at {location}"
        }

    def get_camera_location(self, entity_id: str) -> Optional[dict]:
        """
        Get a camera's registered location.

        Args:
            entity_id: Camera entity ID

        Returns:
            Location dict or None if not registered
        """
        registry = self._load()
        return registry.get(entity_id)

    def list_cameras(self) -> list[dict]:
        """
        List all registered cameras with their locations.

        Returns:
            List of camera registration dicts
        """
        registry = self._load()
        return [
            {"entity_id": entity_id, **data}
            for entity_id, data in registry.items()
        ]

    def remove_camera(self, entity_id: str) -> dict[str, Any]:
        """
        Remove a camera from the registry.

        Args:
            entity_id: Camera entity ID

        Returns:
            Result dictionary
        """
        registry = self._load()

        if entity_id in registry:
            del registry[entity_id]
            self._cache = registry
            self._save()
            return {"success": True, "message": f"Removed {entity_id}"}

        return {"success": False, "error": f"Camera {entity_id} not registered"}


# Global registry instance
_camera_registry = None


def get_camera_registry() -> CameraRegistry:
    """Get the camera registry singleton."""
    global _camera_registry
    if _camera_registry is None:
        _camera_registry = CameraRegistry()
    return _camera_registry


# =============================================================================
# Tool Definitions for the LLM
# =============================================================================

CAMERA_TOOLS = [
    {
        "name": "list_cameras",
        "description": """List all available Ring cameras connected to Home Assistant.

Returns camera entity IDs, friendly names, and current states.
Use this to discover which cameras are available before taking snapshots.

Examples:
- "what cameras do I have?" -> list_cameras
- "show me my security cameras" -> list_cameras
- "which cameras are online?" -> list_cameras""",
        "input_schema": {
            "type": "object",
            "properties": {
                "live_view_only": {
                    "type": "boolean",
                    "description": "If true, only return live view cameras (not last_recording)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_camera_status",
        "description": """Get detailed status of a specific camera including:
- Current state (idle, recording, streaming, unavailable)
- Related sensors (motion, battery, WiFi signal)
- Camera location (if registered)

Examples:
- "is the front door camera working?" -> entity_id="camera.front_door_live_view"
- "check the living room camera" -> entity_id="camera.living_room_live_view"
- "what's the battery on the doorbell?" -> entity_id="camera.front_door_live_view\"""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Camera entity ID (e.g., camera.front_door_live_view)"
                },
                "include_sensors": {
                    "type": "boolean",
                    "description": "Include related sensors (motion, battery, WiFi)"
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "get_camera_snapshot",
        "description": """Take a snapshot from a Ring camera.

Returns the snapshot image as base64-encoded data.
Optionally saves the snapshot to a file.

Note: Ring cameras have limitations on snapshot frequency.
The image may be cached for a few seconds.

Examples:
- "take a picture from the front door" -> entity_id="camera.front_door_live_view"
- "show me what the living room camera sees" -> entity_id="camera.living_room_live_view"
- "capture the front porch camera" -> entity_id="camera.front_porch_live_view\"""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Camera entity ID (e.g., camera.front_door_live_view)"
                },
                "save_to": {
                    "type": "string",
                    "description": "Optional file path to save the snapshot"
                }
            },
            "required": ["entity_id"]
        }
    },
    {
        "name": "check_house_status",
        "description": """Check overall house security status across all cameras.

Returns:
- Which cameras are online/offline
- Any motion detected
- Any doorbell rings
- Overall status (all_clear / activity_detected / issues_found)

Use this for a quick overview of home security.

Examples:
- "is everything okay at home?" -> check_house_status
- "check the security cameras" -> check_house_status
- "are there any problems with the cameras?" -> check_house_status""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "register_camera_location",
        "description": """Register or update a camera's physical location in the home.

Ring indoor cameras are often moved around. Use this to track
where a camera is currently positioned so the system can provide
context-aware responses.

Examples:
- "the living room camera is now in the bedroom" -> entity_id, location="bedroom"
- "I moved the indoor cam to watch the back door" -> entity_id, location="back door\"""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Camera entity ID"
                },
                "location": {
                    "type": "string",
                    "description": "Room or area name (e.g., 'living room', 'front porch')"
                },
                "description": {
                    "type": "string",
                    "description": "Optional description (e.g., 'Corner by the TV')"
                }
            },
            "required": ["entity_id", "location"]
        }
    }
]


# =============================================================================
# Camera Functions
# =============================================================================

def list_cameras(live_view_only: bool = False) -> dict[str, Any]:
    """
    List all available cameras from Home Assistant.

    Args:
        live_view_only: If True, only return live_view cameras (not last_recording)

    Returns:
        Dictionary with list of cameras and their states
    """
    ha_client = get_ha_client()

    try:
        all_states = ha_client.get_states()

        cameras = []
        for entity in all_states:
            entity_id = entity.get("entity_id", "")

            # Only include camera entities
            if not entity_id.startswith("camera."):
                continue

            # Optionally filter out last_recording entities
            if live_view_only and "last_recording" in entity_id:
                continue

            attributes = entity.get("attributes", {})
            camera_info = {
                "entity_id": entity_id,
                "friendly_name": attributes.get("friendly_name", entity_id),
                "state": entity.get("state"),
                "device_class": attributes.get("device_class"),
            }

            # Add registered location if available
            registry = get_camera_registry()
            location_info = registry.get_camera_location(entity_id)
            if location_info:
                camera_info["location"] = location_info.get("location")

            cameras.append(camera_info)

        if not cameras:
            return {
                "success": True,
                "cameras": [],
                "message": "No cameras found in Home Assistant"
            }

        logger.info(f"Found {len(cameras)} cameras")
        return {
            "success": True,
            "cameras": cameras,
            "count": len(cameras)
        }

    except Exception as error:
        logger.error(f"Error listing cameras: {error}")
        return {"success": False, "error": str(error)}


def get_camera_status(
    entity_id: str,
    include_sensors: bool = False
) -> dict[str, Any]:
    """
    Get detailed status of a specific camera.

    Args:
        entity_id: Camera entity ID
        include_sensors: Include related sensors (motion, battery, WiFi)

    Returns:
        Camera status dictionary
    """
    ha_client = get_ha_client()

    try:
        state = ha_client.get_state(entity_id)

        if not state:
            return {
                "success": False,
                "error": f"Camera not found: {entity_id}"
            }

        attributes = state.get("attributes", {})

        result = {
            "success": True,
            "entity_id": entity_id,
            "state": state.get("state"),
            "friendly_name": attributes.get("friendly_name"),
            "device_class": attributes.get("device_class"),
            "model": attributes.get("model"),
        }

        # Add registered location
        registry = get_camera_registry()
        location_info = registry.get_camera_location(entity_id)
        if location_info:
            result["location"] = location_info.get("location")
            result["location_description"] = location_info.get("description")

        # Include related sensors if requested
        if include_sensors:
            # Extract base name for related entities
            # e.g., camera.front_door_live_view -> front_door
            base_name = entity_id.replace("camera.", "").replace("_live_view", "")

            all_states = ha_client.get_states()
            related_sensors = {}

            for entity in all_states:
                eid = entity.get("entity_id", "")

                if base_name in eid:
                    if "motion" in eid:
                        related_sensors["motion_detected"] = entity.get("state") == "on"
                    elif "ding" in eid:
                        related_sensors["ding_detected"] = entity.get("state") == "on"
                    elif "battery" in eid:
                        related_sensors["battery_level"] = entity.get("state")
                    elif "wifi" in eid or "signal" in eid:
                        related_sensors["wifi_signal"] = entity.get("state")

            if related_sensors:
                result["related_sensors"] = related_sensors
                # Also add motion_detected at top level for convenience
                if "motion_detected" in related_sensors:
                    result["motion_detected"] = related_sensors["motion_detected"]

        return result

    except Exception as error:
        logger.error(f"Error getting camera status: {error}")
        return {"success": False, "error": str(error)}


def get_camera_snapshot(
    entity_id: str,
    save_to: Optional[str] = None
) -> dict[str, Any]:
    """
    Take a snapshot from a camera.

    Args:
        entity_id: Camera entity ID
        save_to: Optional file path to save the snapshot

    Returns:
        Dictionary with base64 image data or error
    """
    ha_client = get_ha_client()

    try:
        # First check if camera is available
        state = ha_client.get_state(entity_id)

        if not state:
            return {
                "success": False,
                "error": f"Camera not found: {entity_id}"
            }

        if state.get("state") == "unavailable":
            return {
                "success": False,
                "error": f"Camera is unavailable: {entity_id}"
            }

        # Get snapshot from HA
        # The ha_client should have a get_camera_snapshot method
        image_bytes = ha_client.get_camera_snapshot(entity_id)

        if not image_bytes:
            return {
                "success": False,
                "error": "Failed to get camera snapshot"
            }

        # Encode as base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        result = {
            "success": True,
            "entity_id": entity_id,
            "image_base64": image_base64,
            "timestamp": datetime.now().isoformat(),
        }

        # Save to file if requested
        if save_to:
            output_path = Path(save_to)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            result["saved_to"] = str(output_path)
            logger.info(f"Saved snapshot to {output_path}")

        logger.info(f"Captured snapshot from {entity_id}")
        return result

    except Exception as error:
        logger.error(f"Error getting camera snapshot: {error}")
        return {"success": False, "error": str(error)}


def check_house_status() -> dict[str, Any]:
    """
    Check overall house security status across all cameras.

    Returns:
        Status dictionary with camera overview
    """
    ha_client = get_ha_client()

    try:
        all_states = ha_client.get_states()

        cameras_online = 0
        cameras_offline = 0
        cameras_recording = 0
        active_cameras = []
        motion_detected = []
        dings_detected = []
        issues = []

        for entity in all_states:
            entity_id = entity.get("entity_id", "")
            state = entity.get("state")
            attributes = entity.get("attributes", {})

            # Check camera entities
            if entity_id.startswith("camera."):
                # Skip last_recording entities
                if "last_recording" in entity_id:
                    continue

                if state == "unavailable":
                    cameras_offline += 1
                    issues.append(f"{attributes.get('friendly_name', entity_id)} is offline")
                elif state == "recording":
                    cameras_recording += 1
                    cameras_online += 1
                    active_cameras.append(attributes.get("friendly_name", entity_id))
                else:
                    cameras_online += 1

            # Check motion sensors
            elif "motion" in entity_id and entity_id.startswith("binary_sensor."):
                if state == "on":
                    friendly_name = attributes.get("friendly_name", entity_id)
                    motion_detected.append(friendly_name)
                    active_cameras.append(friendly_name.replace(" Motion", ""))

            # Check doorbell dings
            elif "ding" in entity_id and entity_id.startswith("binary_sensor."):
                if state == "on":
                    dings_detected.append(attributes.get("friendly_name", entity_id))

        # Determine overall status
        if issues:
            status = "issues_found"
        elif motion_detected or dings_detected:
            status = "activity_detected"
        else:
            status = "all_clear"

        result = {
            "success": True,
            "status": status,
            "cameras_online": cameras_online,
            "cameras_offline": cameras_offline,
            "cameras_recording": cameras_recording,
        }

        if active_cameras:
            result["active_cameras"] = list(set(active_cameras))

        if motion_detected:
            result["motion_detected"] = motion_detected

        if dings_detected:
            result["dings_detected"] = dings_detected

        if issues:
            result["issues"] = issues

        # Generate summary message
        if status == "all_clear":
            result["message"] = f"All {cameras_online} cameras online, no activity detected"
        elif status == "activity_detected":
            activities = []
            if motion_detected:
                activities.append(f"motion at {', '.join(motion_detected)}")
            if dings_detected:
                activities.append(f"doorbell at {', '.join(dings_detected)}")
            result["message"] = f"Activity detected: {'; '.join(activities)}"
        else:
            result["message"] = f"Issues found: {'; '.join(issues)}"

        logger.info(f"House status check: {status}")
        return result

    except Exception as error:
        logger.error(f"Error checking house status: {error}")
        return {"success": False, "error": str(error)}


def register_camera_location(
    entity_id: str,
    location: str,
    description: Optional[str] = None
) -> dict[str, Any]:
    """
    Register or update a camera's physical location.

    Args:
        entity_id: Camera entity ID
        location: Room or area name
        description: Optional description

    Returns:
        Result dictionary
    """
    registry = get_camera_registry()
    return registry.set_camera_location(entity_id, location, description)


# =============================================================================
# Tool Execution Entry Point
# =============================================================================

def execute_camera_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a camera tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing camera tool: {tool_name}")

    if tool_name == "list_cameras":
        return list_cameras(
            live_view_only=tool_input.get("live_view_only", False)
        )

    elif tool_name == "get_camera_status":
        return get_camera_status(
            entity_id=tool_input.get("entity_id", ""),
            include_sensors=tool_input.get("include_sensors", False)
        )

    elif tool_name == "get_camera_snapshot":
        return get_camera_snapshot(
            entity_id=tool_input.get("entity_id", ""),
            save_to=tool_input.get("save_to")
        )

    elif tool_name == "check_house_status":
        return check_house_status()

    elif tool_name == "register_camera_location":
        return register_camera_location(
            entity_id=tool_input.get("entity_id", ""),
            location=tool_input.get("location", ""),
            description=tool_input.get("description")
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
