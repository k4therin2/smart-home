"""
Smart Home Assistant - Blinds Control Tools

Tools for controlling Hapadif smart blinds through Home Assistant.
Uses the Tuya integration via the Hapadif Smart Bridge Hub (MH100).

The blinds appear as 'cover' entities in Home Assistant with support for:
- Open/close/stop commands
- Position control (0-100%)
- Tilt control (if supported by hardware)

References:
- https://www.home-assistant.io/integrations/tuya/
- https://www.home-assistant.io/integrations/cover/
"""

from typing import Any

from src.config import ROOM_ENTITY_MAP, get_blinds_entities
from src.ha_client import get_ha_client
from src.utils import send_health_alert, setup_logging


logger = setup_logging("tools.blinds")

# Track consecutive errors to avoid alert spam
_consecutive_blinds_errors = 0
_BLINDS_ERROR_ALERT_THRESHOLD = 2  # Alert after N consecutive errors per room
_rooms_with_errors: set[str] = set()


def _handle_blinds_error(error: Exception, room: str, entity_id: str, action: str) -> None:
    """
    Handle blinds control errors with rate-limited alerting.

    Args:
        error: The exception that occurred
        room: Room name
        entity_id: Blinds entity ID
        action: Action that failed
    """
    global _consecutive_blinds_errors

    _consecutive_blinds_errors += 1
    error_msg = str(error)
    logger.error(f"Blinds control error in {room}: {error_msg}")

    # Only alert once per room until it recovers
    if room not in _rooms_with_errors:
        _rooms_with_errors.add(room)
        send_health_alert(
            title="Blind Motor Error",
            message=f"Unable to control blinds in *{room}*: {error_msg}",
            severity="warning",
            component="blinds",
            details={
                "room": room,
                "entity_id": entity_id,
                "action": action,
                "error": error_msg[:200],
            },
        )


def _clear_blinds_error(room: str) -> None:
    """Clear error state for a room after successful operation."""
    global _consecutive_blinds_errors
    if room in _rooms_with_errors:
        _rooms_with_errors.discard(room)
        send_health_alert(
            title="Blinds Recovered",
            message=f"Blinds in *{room}* are responding normally",
            severity="info",
            component="blinds",
        )
    if _consecutive_blinds_errors > 0:
        _consecutive_blinds_errors -= 1


# Tool definitions for Claude
BLINDS_TOOLS = [
    {
        "name": "control_blinds",
        "description": """Control smart blinds in a room. Supports:
- open: Fully open the blinds
- close: Fully close the blinds
- stop: Stop blinds movement
- set_position: Set blinds to specific position (0=closed, 100=open)

Examples:
- "open the bedroom blinds" -> room='bedroom', action='open'
- "close living room blinds" -> room='living room', action='close'
- "set office blinds to 50%" -> room='office', action='set_position', position=50
- "lower the blinds halfway" -> action='set_position', position=50
- "stop the blinds" -> action='stop'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name where blinds should be controlled",
                },
                "action": {
                    "type": "string",
                    "enum": ["open", "close", "stop", "set_position"],
                    "description": "The blinds control action",
                },
                "position": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Position percentage (0=fully closed, 100=fully open). Required for set_position action.",
                },
            },
            "required": ["room", "action"],
        },
    },
    {
        "name": "get_blinds_status",
        "description": """Get the current status of blinds in a room. Returns:
- Current position (0-100%)
- State (open, closed, opening, closing)
- Tilt position if supported

Use this to check blinds position before adjusting.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {"type": "string", "description": "Room name to check blinds status"}
            },
            "required": ["room"],
        },
    },
    {
        "name": "set_blinds_for_scene",
        "description": """Set blinds position based on a lighting scene or time of day.
Coordinates blinds with ambient lighting needs.

Available scenes:
- morning: Open blinds fully for natural light
- day: Blinds at 75% for balanced light
- evening: Blinds at 25% for privacy with some light
- night: Close blinds fully for privacy
- movie: Close blinds for dark room
- work: Blinds at 50% to reduce screen glare

Examples:
- "set blinds for movie night" -> scene='movie'
- "morning blinds" -> scene='morning'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name (optional - applies to all rooms if omitted)",
                },
                "scene": {
                    "type": "string",
                    "enum": ["morning", "day", "evening", "night", "movie", "work"],
                    "description": "Scene preset for blinds position",
                },
            },
            "required": ["scene"],
        },
    },
    {
        "name": "list_rooms_with_blinds",
        "description": "List all rooms that have smart blinds configured.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# Scene presets for blinds positions
BLINDS_SCENE_PRESETS = {
    "morning": 100,  # Fully open
    "day": 75,  # Mostly open
    "evening": 25,  # Mostly closed
    "night": 0,  # Fully closed
    "movie": 0,  # Fully closed
    "work": 50,  # Half open (reduce glare)
}


def control_blinds(room: str, action: str, position: int | None = None) -> dict[str, Any]:
    """
    Control blinds in a room.

    Args:
        room: Room name
        action: Control action (open, close, stop, set_position)
        position: Position percentage for set_position action

    Returns:
        Result dictionary with success status
    """
    entity_id = get_blinds_entities(room)
    if not entity_id:
        available_rooms = [r for r in ROOM_ENTITY_MAP if ROOM_ENTITY_MAP[r].get("blinds")]
        return {
            "success": False,
            "error": f"No blinds found in room: {room}",
            "available_rooms": available_rooms
            if available_rooms
            else "No rooms with blinds configured",
        }

    ha_client = get_ha_client()

    # Map actions to Home Assistant services
    service_map = {
        "open": ("cover", "open_cover"),
        "close": ("cover", "close_cover"),
        "stop": ("cover", "stop_cover"),
        "set_position": ("cover", "set_cover_position"),
    }

    if action not in service_map:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": list(service_map.keys()),
        }

    domain, service = service_map[action]
    service_data = {"entity_id": entity_id}

    # Add position for set_position action
    if action == "set_position":
        if position is None:
            return {"success": False, "error": "Position required for set_position action"}
        service_data["position"] = max(0, min(100, position))

    try:
        logger.info(
            f"Blinds control: {action} on {entity_id}"
            + (f" to {position}%" if position is not None else "")
        )
        success = ha_client.call_service(domain, service, service_data)

        if success:
            _clear_blinds_error(room)

        result = {
            "success": success,
            "action": action,
            "room": room,
            "entity_id": entity_id,
        }
        if position is not None:
            result["position"] = position

        return result

    except Exception as error:
        _handle_blinds_error(error, room, entity_id, action)
        return {"success": False, "error": str(error)}


def get_blinds_status(room: str) -> dict[str, Any]:
    """
    Get the current status of blinds in a room.

    Args:
        room: Room name

    Returns:
        Status dictionary with position and state
    """
    entity_id = get_blinds_entities(room)
    if not entity_id:
        return {"success": False, "error": f"No blinds found in room: {room}"}

    ha_client = get_ha_client()

    try:
        state = ha_client.get_state(entity_id)
        if not state:
            return {"success": False, "error": f"Could not get state for {entity_id}"}

        attributes = state.get("attributes", {})
        current_position = attributes.get("current_position")

        result = {
            "success": True,
            "room": room,
            "entity_id": entity_id,
            "state": state.get("state"),
            "position": current_position,
            "friendly_name": attributes.get("friendly_name"),
        }

        # Add tilt if supported
        if "current_tilt_position" in attributes:
            result["tilt_position"] = attributes.get("current_tilt_position")

        # Interpret position for natural language
        if current_position is not None:
            if current_position == 0:
                result["position_description"] = "fully closed"
            elif current_position == 100:
                result["position_description"] = "fully open"
            elif current_position < 25:
                result["position_description"] = "mostly closed"
            elif current_position < 75:
                result["position_description"] = "partially open"
            else:
                result["position_description"] = "mostly open"

        return result

    except Exception as error:
        logger.error(f"Error getting blinds status: {error}")
        return {"success": False, "error": str(error)}


def set_blinds_for_scene(scene: str, room: str | None = None) -> dict[str, Any]:
    """
    Set blinds position based on a scene preset.

    Args:
        scene: Scene name (morning, day, evening, night, movie, work)
        room: Optional room name (all rooms if omitted)

    Returns:
        Result dictionary
    """
    if scene not in BLINDS_SCENE_PRESETS:
        return {
            "success": False,
            "error": f"Unknown scene: {scene}",
            "available_scenes": list(BLINDS_SCENE_PRESETS.keys()),
        }

    position = BLINDS_SCENE_PRESETS[scene]

    # If room specified, just set that room
    if room:
        result = control_blinds(room, "set_position", position)
        result["scene"] = scene
        return result

    # Otherwise, set all rooms with blinds
    rooms_with_blinds = [r for r in ROOM_ENTITY_MAP if ROOM_ENTITY_MAP[r].get("blinds")]

    if not rooms_with_blinds:
        return {"success": False, "error": "No rooms with blinds configured"}

    results = []
    all_success = True

    for room_name in rooms_with_blinds:
        result = control_blinds(room_name, "set_position", position)
        results.append({"room": room_name, "success": result.get("success", False)})
        if not result.get("success"):
            all_success = False

    return {
        "success": all_success,
        "scene": scene,
        "position": position,
        "rooms": results,
        "message": f"Set {len(rooms_with_blinds)} room(s) to {scene} mode ({position}% open)",
    }


def list_rooms_with_blinds() -> dict[str, Any]:
    """List all rooms that have smart blinds configured."""
    rooms = []
    for room_key, room_config in ROOM_ENTITY_MAP.items():
        if room_config.get("blinds"):
            rooms.append(
                {
                    "name": room_key.replace("_", " "),
                    "entity_id": room_config.get("blinds"),
                }
            )

    return {
        "success": True,
        "rooms": rooms,
        "count": len(rooms),
        "message": f"{len(rooms)} room(s) have smart blinds"
        if rooms
        else "No rooms with blinds configured",
    }


def execute_blinds_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a blinds tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing blinds tool: {tool_name}")

    if tool_name == "control_blinds":
        return control_blinds(
            room=tool_input.get("room", ""),
            action=tool_input.get("action", ""),
            position=tool_input.get("position"),
        )

    elif tool_name == "get_blinds_status":
        return get_blinds_status(room=tool_input.get("room", ""))

    elif tool_name == "set_blinds_for_scene":
        return set_blinds_for_scene(scene=tool_input.get("scene", ""), room=tool_input.get("room"))

    elif tool_name == "list_rooms_with_blinds":
        return list_rooms_with_blinds()

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
