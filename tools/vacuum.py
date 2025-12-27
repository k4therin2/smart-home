"""
Smart Home Assistant - Vacuum Control Tools

Tools for controlling the Dreame L10s vacuum through Home Assistant.
Uses the Tasshack/dreame-vacuum HACS integration.

References:
- https://github.com/Tasshack/dreame-vacuum
- Standard HA vacuum services: start, stop, pause, return_to_base, locate
- Dreame-specific: dreame_vacuum.vacuum_clean_segment for room cleaning
"""

from typing import Any

from src.config import get_vacuum_entity
from src.ha_client import get_ha_client
from src.utils import send_health_alert, setup_logging


logger = setup_logging("tools.vacuum")

# Track if we've already alerted for current error state
_last_alerted_error_state: str | None = None


def _check_vacuum_error_alert(error_state: str, entity_id: str, vacuum_state: str) -> None:
    """
    Check vacuum error state and send alert if new error detected.

    Only alerts once per unique error state to avoid spam.

    Args:
        error_state: Error description from vacuum attributes
        entity_id: Vacuum entity ID
        vacuum_state: Current vacuum state
    """
    global _last_alerted_error_state

    # Don't re-alert for the same error
    if error_state == _last_alerted_error_state:
        return

    _last_alerted_error_state = error_state

    # Common vacuum error types for severity classification
    critical_errors = ["stuck", "cliff", "wheel", "bin", "brush", "filter"]
    is_critical = any(keyword in error_state.lower() for keyword in critical_errors)

    send_health_alert(
        title="Vacuum Error Detected",
        message=f"Robot vacuum reports error: *{error_state}*",
        severity="critical" if is_critical else "warning",
        component="vacuum",
        details={
            "entity_id": entity_id,
            "error": error_state,
            "state": vacuum_state,
            "action": "Check vacuum and clear obstruction if needed",
        },
    )


def _clear_vacuum_error_state() -> None:
    """Clear the tracked error state when vacuum is operating normally."""
    global _last_alerted_error_state
    if _last_alerted_error_state is not None:
        # Send recovery alert
        send_health_alert(
            title="Vacuum Error Cleared",
            message="Robot vacuum is operating normally again",
            severity="info",
            component="vacuum",
        )
        _last_alerted_error_state = None


# Tool definitions for Claude
VACUUM_TOOLS = [
    {
        "name": "control_vacuum",
        "description": """Control the robot vacuum cleaner. Supports:
- start: Start a full cleaning cycle
- stop: Stop cleaning immediately
- pause: Pause current cleaning (can resume later)
- resume: Resume paused cleaning
- return_home: Send vacuum back to charging dock
- locate: Make the vacuum beep to find it

Examples:
- "start the vacuum" -> action='start'
- "stop vacuuming" -> action='stop'
- "send the robot home" -> action='return_home'
- "pause cleaning" -> action='pause'
- "where's the vacuum?" -> action='locate'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["start", "stop", "pause", "resume", "return_home", "locate"],
                    "description": "The vacuum control action",
                }
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_vacuum_status",
        "description": """Get the current status of the robot vacuum. Returns:
- Current state (cleaning, docked, paused, idle, returning, error)
- Battery level
- Fan speed setting
- Cleaning statistics (area cleaned, time spent)
- Error state if any

Use this to check if the vacuum is busy, charging, or available.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_vacuum_fan_speed",
        "description": """Set the vacuum's suction power level.

Available modes:
- quiet: Low power, quieter operation
- standard: Normal balanced cleaning
- strong: Higher suction for deeper clean
- turbo: Maximum power for tough dirt

Higher power uses more battery but cleans more thoroughly.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "speed": {
                    "type": "string",
                    "enum": ["quiet", "standard", "strong", "turbo"],
                    "description": "Fan speed / suction power level",
                }
            },
            "required": ["speed"],
        },
    },
    {
        "name": "clean_rooms",
        "description": """Clean specific rooms only. Requires room names that match
the vacuum's room mapping in Home Assistant.

If room IDs are unknown, the vacuum will attempt to clean by room name.
The vacuum must have a valid map with room segments defined.

Examples:
- "vacuum the living room" -> rooms=['living room']
- "clean kitchen and bedroom" -> rooms=['kitchen', 'bedroom']""",
        "input_schema": {
            "type": "object",
            "properties": {
                "rooms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of room names to clean",
                },
                "repeat": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3,
                    "description": "Number of cleaning passes (default: 1)",
                },
            },
            "required": ["rooms"],
        },
    },
]


def control_vacuum(action: str) -> dict[str, Any]:
    """
    Control the robot vacuum.

    Args:
        action: Control action (start, stop, pause, resume, return_home, locate)

    Returns:
        Result dictionary with success status
    """
    entity_id = get_vacuum_entity()
    if not entity_id:
        return {
            "success": False,
            "error": "Vacuum entity not configured. Add VACUUM_ENTITY_ID to config.",
        }

    ha_client = get_ha_client()

    # Map actions to Home Assistant services
    service_map = {
        "start": ("vacuum", "start"),
        "stop": ("vacuum", "stop"),
        "pause": ("vacuum", "pause"),
        "resume": ("vacuum", "start"),  # Resume is just start again
        "return_home": ("vacuum", "return_to_base"),
        "locate": ("vacuum", "locate"),
    }

    if action not in service_map:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": list(service_map.keys()),
        }

    domain, service = service_map[action]
    service_data = {"entity_id": entity_id}

    try:
        logger.info(f"Vacuum control: {action} on {entity_id}")
        success = ha_client.call_service(domain, service, service_data)

        return {
            "success": success,
            "action": action,
            "entity_id": entity_id,
            "message": f"Vacuum {action} command sent" if success else f"Failed to {action} vacuum",
        }

    except Exception as error:
        logger.error(f"Error controlling vacuum: {error}")
        return {"success": False, "error": str(error)}


def get_vacuum_status() -> dict[str, Any]:
    """
    Get the current status of the robot vacuum.

    Returns:
        Status dictionary with state, battery, and cleaning info
    """
    entity_id = get_vacuum_entity()
    if not entity_id:
        return {"success": False, "error": "Vacuum entity not configured"}

    ha_client = get_ha_client()

    try:
        state = ha_client.get_state(entity_id)
        if not state:
            return {"success": False, "error": f"Could not get state for {entity_id}"}

        attributes = state.get("attributes", {})

        # Extract relevant vacuum attributes
        result = {
            "success": True,
            "entity_id": entity_id,
            "state": state.get("state"),
            "battery_level": attributes.get("battery_level"),
            "fan_speed": attributes.get("fan_speed"),
            "status": attributes.get("status"),
            "friendly_name": attributes.get("friendly_name"),
        }

        # Add cleaning statistics if available
        if "cleaned_area" in attributes:
            result["cleaned_area_sqm"] = attributes.get("cleaned_area")
        if "cleaning_time" in attributes:
            result["cleaning_time_minutes"] = attributes.get("cleaning_time")

        # Get current state first for error checking
        current_state = state.get("state", "unknown")

        # Add error info if present and send alert
        error_state = attributes.get("error")
        if error_state:
            result["error_state"] = error_state
            _check_vacuum_error_alert(error_state, entity_id, current_state)
        elif current_state not in ("error", "unknown"):
            # Vacuum is operating normally - clear any previous error state
            _clear_vacuum_error_state()

        # Interpret state for natural language
        state_descriptions = {
            "cleaning": "currently cleaning",
            "docked": "on the charging dock",
            "paused": "paused",
            "idle": "idle and ready",
            "returning": "returning to dock",
            "error": "in error state",
        }
        result["state_description"] = state_descriptions.get(current_state, current_state)

        # Check for error state (vacuum in error but no error message)
        if current_state == "error" and not error_state:
            _check_vacuum_error_alert("unknown error", entity_id, current_state)

        return result

    except Exception as error:
        logger.error(f"Error getting vacuum status: {error}")
        return {"success": False, "error": str(error)}


def set_vacuum_fan_speed(speed: str) -> dict[str, Any]:
    """
    Set the vacuum's fan speed / suction power.

    Args:
        speed: Fan speed level (quiet, standard, strong, turbo)

    Returns:
        Result dictionary
    """
    entity_id = get_vacuum_entity()
    if not entity_id:
        return {"success": False, "error": "Vacuum entity not configured"}

    # Dreame vacuum fan speed values
    # These may need adjustment based on the specific model
    speed_map = {
        "quiet": "Quiet",
        "standard": "Standard",
        "strong": "Strong",
        "turbo": "Turbo",
    }

    fan_speed_value = speed_map.get(speed.lower())
    if not fan_speed_value:
        return {
            "success": False,
            "error": f"Unknown speed: {speed}",
            "available_speeds": list(speed_map.keys()),
        }

    ha_client = get_ha_client()
    service_data = {"entity_id": entity_id, "fan_speed": fan_speed_value}

    try:
        logger.info(f"Setting vacuum fan speed to {fan_speed_value}")
        success = ha_client.call_service("vacuum", "set_fan_speed", service_data)

        return {"success": success, "fan_speed": speed, "entity_id": entity_id}

    except Exception as error:
        logger.error(f"Error setting vacuum fan speed: {error}")
        return {"success": False, "error": str(error)}


def clean_rooms(rooms: list[str], repeat: int = 1) -> dict[str, Any]:
    """
    Clean specific rooms.

    Args:
        rooms: List of room names to clean
        repeat: Number of cleaning passes (1-3)

    Returns:
        Result dictionary
    """
    entity_id = get_vacuum_entity()
    if not entity_id:
        return {"success": False, "error": "Vacuum entity not configured"}

    if not rooms:
        return {"success": False, "error": "No rooms specified"}

    ha_client = get_ha_client()

    # The Dreame integration uses segment IDs for room cleaning
    # We'll try both the dreame-specific service and standard segment cleaning
    # The segment IDs need to be mapped from room names - this may require
    # querying the vacuum's room map or configuration

    # Try the dreame_vacuum.vacuum_clean_segment service first
    service_data = {
        "entity_id": entity_id,
        "segments": rooms,  # Try room names first
        "repeats": max(1, min(3, repeat)),
    }

    try:
        logger.info(f"Cleaning rooms: {rooms} with {repeat} pass(es)")

        # Try dreame-specific service first
        success = ha_client.call_service("dreame_vacuum", "vacuum_clean_segment", service_data)

        if success:
            return {
                "success": True,
                "rooms": rooms,
                "repeat": repeat,
                "entity_id": entity_id,
                "message": f"Started cleaning {', '.join(rooms)}",
            }

        # Fall back to standard vacuum.send_command if dreame service fails
        logger.info("Dreame service not available, trying standard command")
        fallback_data = {
            "entity_id": entity_id,
            "command": "app_segment_clean",
            "params": {"segments": rooms, "repeat": repeat},
        }
        success = ha_client.call_service("vacuum", "send_command", fallback_data)

        return {
            "success": success,
            "rooms": rooms,
            "repeat": repeat,
            "entity_id": entity_id,
            "message": f"Started cleaning {', '.join(rooms)}"
            if success
            else "Failed to start room cleaning",
        }

    except Exception as error:
        logger.error(f"Error cleaning rooms: {error}")
        return {"success": False, "error": str(error)}


def execute_vacuum_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a vacuum tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing vacuum tool: {tool_name}")

    if tool_name == "control_vacuum":
        return control_vacuum(action=tool_input.get("action", ""))

    elif tool_name == "get_vacuum_status":
        return get_vacuum_status()

    elif tool_name == "set_vacuum_fan_speed":
        return set_vacuum_fan_speed(speed=tool_input.get("speed", ""))

    elif tool_name == "clean_rooms":
        return clean_rooms(rooms=tool_input.get("rooms", []), repeat=tool_input.get("repeat", 1))

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
