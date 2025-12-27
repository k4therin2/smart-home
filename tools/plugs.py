"""
Smart Home Assistant - Smart Plug Control Tools

Tools for controlling smart plugs through Home Assistant.
Supports on/off control, power monitoring, and safety checks
for high-power devices like heaters and ovens.

Smart plugs appear as 'switch' entities in Home Assistant.

References:
- https://www.home-assistant.io/integrations/switch/
"""

from typing import Any

from src.ha_client import get_ha_client
from src.utils import setup_logging


logger = setup_logging("tools.plugs")

# High-power device keywords that require confirmation
# These devices could be dangerous if left on unattended
HIGH_POWER_DEVICES = frozenset(
    [
        "heater",
        "space_heater",
        "oven",
        "toaster",
        "toaster_oven",
        "iron",
        "curling_iron",
        "hair_dryer",
        "portable_heater",
    ]
)

# Tool definitions for Claude
PLUGS_TOOLS = [
    {
        "name": "control_plug",
        "description": """Control a smart plug. Supports:
- on: Turn the plug on
- off: Turn the plug off
- toggle: Toggle the plug state

For high-power devices (heaters, ovens, etc.), turning ON requires
explicit confirmation via confirm_high_power=true for safety.

Examples:
- "turn on the living room lamp" -> entity_id='switch.living_room_lamp', action='on'
- "turn off the bedroom fan" -> entity_id='switch.bedroom_fan', action='off'
- "toggle the garage light" -> entity_id='switch.garage_light', action='toggle'
- "turn on the space heater" -> entity_id='switch.space_heater', action='on', confirm_high_power=true""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Smart plug entity ID (must start with 'switch.')",
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "toggle"],
                    "description": "The plug control action",
                },
                "confirm_high_power": {
                    "type": "boolean",
                    "description": "Required confirmation for high-power devices (heaters, ovens). Set to true to confirm.",
                },
            },
            "required": ["entity_id", "action"],
        },
    },
    {
        "name": "get_plug_status",
        "description": """Get the current status of a smart plug. Returns:
- Current state (on/off)
- Power usage (if supported by hardware)
- Today's energy consumption (if supported)
- Friendly name

Use this to check if a plug is on or off before controlling it.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Smart plug entity ID (must start with 'switch.')",
                }
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "list_plugs",
        "description": """List all smart plugs in the system with their current state.
Optionally filter by device class (outlet vs switch).

Returns a list of all plugs with their:
- Entity ID
- Friendly name
- Current state (on/off)
- Power monitoring availability""",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter_device_class": {
                    "type": "string",
                    "enum": ["outlet", "switch", "all"],
                    "description": "Filter by device class. Default is 'all'.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "toggle_plug",
        "description": """Toggle a smart plug between on and off states.
If currently on, turns off. If currently off, turns on.

For high-power devices that are currently OFF, toggling ON
requires confirm_high_power=true for safety.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Smart plug entity ID (must start with 'switch.')",
                },
                "confirm_high_power": {
                    "type": "boolean",
                    "description": "Required confirmation for high-power devices when toggling to ON.",
                },
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "get_power_usage",
        "description": """Get power consumption data for a smart plug.
Returns current power draw in watts and today's energy usage in kWh.

Note: Power monitoring is only available on plugs with energy
monitoring capability (e.g., TP-Link Kasa, Shelly, etc.).""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Smart plug entity ID (must start with 'switch.')",
                }
            },
            "required": ["entity_id"],
        },
    },
]


def _is_high_power_device(entity_id: str) -> bool:
    """
    Check if the entity ID corresponds to a high-power device.

    Args:
        entity_id: The switch entity ID

    Returns:
        True if the device is high-power, False otherwise
    """
    entity_lower = entity_id.lower()
    for keyword in HIGH_POWER_DEVICES:
        if keyword in entity_lower:
            return True
    return False


def _validate_entity_id(entity_id: str) -> tuple[bool, str | None]:
    """
    Validate that the entity ID is a valid switch entity.

    Args:
        entity_id: The entity ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not entity_id:
        return False, "Entity ID is required"
    if not entity_id.startswith("switch."):
        return (
            False,
            f"Invalid entity ID format. Smart plugs must use 'switch.' prefix, got: {entity_id}",
        )
    return True, None


def control_plug(entity_id: str, action: str, confirm_high_power: bool = False) -> dict[str, Any]:
    """
    Control a smart plug (on/off/toggle).

    Args:
        entity_id: Smart plug entity ID (switch.*)
        action: Control action (on, off, toggle)
        confirm_high_power: Safety confirmation for high-power devices

    Returns:
        Result dictionary with success status
    """
    # Validate entity ID
    is_valid, error = _validate_entity_id(entity_id)
    if not is_valid:
        return {"success": False, "error": error}

    # Validate action
    valid_actions = ["on", "off", "toggle"]
    if action not in valid_actions:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
            "available_actions": valid_actions,
        }

    # Safety check for high-power devices (only when turning ON)
    is_high_power = _is_high_power_device(entity_id)
    if is_high_power and action in ["on", "toggle"] and not confirm_high_power:
        return {
            "success": False,
            "error": f"Safety confirmation required for high-power device. "
            f"Set confirm_high_power=true to proceed with turning on {entity_id}",
            "requires_confirmation": True,
            "device_type": "high_power",
        }

    ha_client = get_ha_client()

    # Map actions to Home Assistant services
    service_map = {
        "on": ("switch", "turn_on"),
        "off": ("switch", "turn_off"),
        "toggle": ("switch", "toggle"),
    }

    domain, service = service_map[action]
    service_data = {"entity_id": entity_id}

    try:
        logger.info(f"Plug control: {action} on {entity_id}")
        success = ha_client.call_service(domain, service, service_data)

        result = {
            "success": success,
            "action": action,
            "entity_id": entity_id,
        }

        if is_high_power and action in ["on", "toggle"]:
            result["high_power_confirmed"] = True
            result["warning"] = "High-power device activated. Remember to turn off when not in use."

        if not success:
            result["error"] = f"Failed to {action} plug: {entity_id}"

        return result

    except Exception as error:
        logger.error(f"Error controlling plug: {error}")
        return {"success": False, "error": str(error)}


def get_plug_status(entity_id: str) -> dict[str, Any]:
    """
    Get the current status of a smart plug.

    Args:
        entity_id: Smart plug entity ID

    Returns:
        Status dictionary with state and power info
    """
    # Validate entity ID
    is_valid, error = _validate_entity_id(entity_id)
    if not is_valid:
        return {"success": False, "error": error}

    ha_client = get_ha_client()

    try:
        state = ha_client.get_state(entity_id)
        if not state:
            return {
                "success": False,
                "error": f"Could not get state for {entity_id}. Entity may not exist.",
            }

        attributes = state.get("attributes", {})
        current_state = state.get("state", "unknown")

        result = {
            "success": True,
            "entity_id": entity_id,
            "state": current_state,
            "friendly_name": attributes.get("friendly_name"),
            "device_class": attributes.get("device_class"),
        }

        # Add power monitoring data if available
        if "current_power_w" in attributes:
            result["current_power_w"] = attributes.get("current_power_w")
        else:
            result["current_power_w"] = None

        if "today_energy_kwh" in attributes:
            result["today_energy_kwh"] = attributes.get("today_energy_kwh")

        # Human-readable state description
        state_descriptions = {
            "on": "currently on and active",
            "off": "currently off",
            "unavailable": "unavailable (device may be offline)",
            "unknown": "in unknown state",
        }
        result["state_description"] = state_descriptions.get(current_state, current_state)

        # Mark high-power devices
        if _is_high_power_device(entity_id):
            result["is_high_power_device"] = True

        return result

    except Exception as error:
        logger.error(f"Error getting plug status: {error}")
        return {"success": False, "error": str(error)}


def list_plugs(filter_device_class: str = "all") -> dict[str, Any]:
    """
    List all smart plugs in the system.

    Args:
        filter_device_class: Filter by device class ('outlet', 'switch', 'all')

    Returns:
        Dictionary with list of plugs and their states
    """
    ha_client = get_ha_client()

    try:
        all_states = ha_client.get_all_states()
        plugs = []

        for entity in all_states:
            entity_id = entity.get("entity_id", "")
            if not entity_id.startswith("switch."):
                continue

            attributes = entity.get("attributes", {})
            device_class = attributes.get("device_class", "switch")

            # Filter by device class if specified
            if filter_device_class != "all":
                if device_class != filter_device_class:
                    continue

            plug_info = {
                "entity_id": entity_id,
                "friendly_name": attributes.get("friendly_name", entity_id),
                "state": entity.get("state", "unknown"),
                "device_class": device_class,
            }

            # Add power monitoring availability
            plug_info["power_monitoring_available"] = "current_power_w" in attributes

            # Mark high-power devices
            if _is_high_power_device(entity_id):
                plug_info["is_high_power_device"] = True

            plugs.append(plug_info)

        return {
            "success": True,
            "plugs": plugs,
            "count": len(plugs),
            "filter": filter_device_class,
        }

    except Exception as error:
        logger.error(f"Error listing plugs: {error}")
        return {"success": False, "error": str(error), "plugs": [], "count": 0}


def toggle_plug(entity_id: str, confirm_high_power: bool = False) -> dict[str, Any]:
    """
    Toggle a smart plug's state.

    Args:
        entity_id: Smart plug entity ID
        confirm_high_power: Safety confirmation for high-power devices

    Returns:
        Result dictionary with success status
    """
    # Validate entity ID
    is_valid, error = _validate_entity_id(entity_id)
    if not is_valid:
        return {"success": False, "error": error}

    # For high-power devices, check current state to see if we're toggling to ON
    if _is_high_power_device(entity_id):
        ha_client = get_ha_client()
        state = ha_client.get_state(entity_id)
        if state and state.get("state") == "off" and not confirm_high_power:
            return {
                "success": False,
                "error": f"Safety confirmation required. Device is currently OFF. "
                f"Set confirm_high_power=true to toggle {entity_id} to ON.",
                "requires_confirmation": True,
                "current_state": "off",
                "device_type": "high_power",
            }

    # Use control_plug for the actual toggle
    return control_plug(entity_id, "toggle", confirm_high_power)


def get_power_usage(entity_id: str) -> dict[str, Any]:
    """
    Get power consumption data for a smart plug.

    Args:
        entity_id: Smart plug entity ID

    Returns:
        Dictionary with power usage information
    """
    # Validate entity ID
    is_valid, error = _validate_entity_id(entity_id)
    if not is_valid:
        return {"success": False, "error": error}

    ha_client = get_ha_client()

    try:
        state = ha_client.get_state(entity_id)
        if not state:
            return {
                "success": False,
                "error": f"Could not get state for {entity_id}. Entity may not exist.",
            }

        attributes = state.get("attributes", {})

        # Check if power monitoring is available
        has_power = "current_power_w" in attributes
        has_energy = "today_energy_kwh" in attributes

        result = {
            "success": True,
            "entity_id": entity_id,
            "power_monitoring_available": has_power or has_energy,
        }

        if has_power:
            result["current_power_w"] = attributes.get("current_power_w")

        if has_energy:
            result["today_energy_kwh"] = attributes.get("today_energy_kwh")

        # Additional energy attributes if available
        if "voltage" in attributes:
            result["voltage"] = attributes.get("voltage")
        if "current_a" in attributes:
            result["current_a"] = attributes.get("current_a")

        if not result["power_monitoring_available"]:
            result["message"] = "Power monitoring is not supported by this device"

        return result

    except Exception as error:
        logger.error(f"Error getting power usage: {error}")
        return {"success": False, "error": str(error)}


def execute_plug_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a plug tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing plug tool: {tool_name}")

    if tool_name == "control_plug":
        return control_plug(
            entity_id=tool_input.get("entity_id", ""),
            action=tool_input.get("action", ""),
            confirm_high_power=tool_input.get("confirm_high_power", False),
        )

    elif tool_name == "get_plug_status":
        return get_plug_status(entity_id=tool_input.get("entity_id", ""))

    elif tool_name == "list_plugs":
        return list_plugs(filter_device_class=tool_input.get("filter_device_class", "all"))

    elif tool_name == "toggle_plug":
        return toggle_plug(
            entity_id=tool_input.get("entity_id", ""),
            confirm_high_power=tool_input.get("confirm_high_power", False),
        )

    elif tool_name == "get_power_usage":
        return get_power_usage(entity_id=tool_input.get("entity_id", ""))

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
