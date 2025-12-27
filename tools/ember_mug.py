"""
Smart Home Assistant - Ember Mug Control Tools

Tools for controlling Ember Mug via Home Assistant.
Uses the hass-ember-mug-component custom integration.

Requires setup:
1. Install hass-ember-mug-component from HACS
2. Put Ember Mug in pairing mode
3. Home Assistant will auto-detect and configure the device

Entity types created by the integration:
- number.ember_mug_*_target_temperature - For setting target temp
- sensor.ember_mug_*_current_temperature - For reading current temp
- sensor.ember_mug_*_battery_level - Battery info
- sensor.ember_mug_*_liquid_level - Liquid presence
- sensor.ember_mug_*_state - Device state (empty, filling, heating, etc.)

References:
- https://github.com/sopelj/hass-ember-mug-component
- https://pypi.org/project/python-ember-mug/
"""

from typing import Any

from src.ha_client import get_ha_client
from src.utils import setup_logging


logger = setup_logging("tools.ember_mug")

# Temperature limits for safety
MIN_TEMP_F = 120  # Minimum target temperature
MAX_TEMP_F = 145  # Maximum target temperature (device limit)
DEFAULT_TEMP_F = 135  # Default temperature if not specified

# Ember Mug entity patterns
EMBER_MUG_PATTERNS = [
    "ember_mug",
    "ember_cup",
    "ember_tumbler",
    "ember_travel_mug",
]

# Tool definitions for Claude
EMBER_MUG_TOOLS = [
    {
        "name": "set_mug_temperature",
        "description": """Set the target temperature for the Ember Mug.

Temperature must be between 120°F and 145°F (device limits).
Common temperatures:
- Hot coffee: 135-145°F
- Warm latte: 130-135°F
- Drinking temperature: 125-130°F

Examples:
- "heat up my ember mug to 140" -> target_temp=140
- "set my mug to 135 degrees" -> target_temp=135
- "warm up my coffee" -> target_temp=135 (default)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_temp": {
                    "type": "number",
                    "description": f"Target temperature in Fahrenheit ({MIN_TEMP_F}-{MAX_TEMP_F}°F). Default is {DEFAULT_TEMP_F}°F.",
                },
                "entity_id": {
                    "type": "string",
                    "description": "Specific Ember Mug entity ID (optional). If not provided, uses the first detected mug.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_mug_status",
        "description": """Get the current status of the Ember Mug.

Returns:
- Current temperature
- Target temperature
- Liquid level (empty, low, medium, full)
- Battery level
- Device state (heating, cooling, idle, empty, etc.)

Examples:
- "what temperature is my mug?"
- "is my coffee hot?"
- "ember mug status"
- "how much battery does my mug have?"
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Specific Ember Mug entity ID (optional). If not provided, uses the first detected mug.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "list_ember_mugs",
        "description": """List all Ember Mugs detected by Home Assistant.

Returns information about each mug including:
- Device name
- Current temperature
- Target temperature
- Battery level
- Connection status

Useful when you have multiple Ember devices.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _find_ember_mugs() -> list[dict[str, Any]]:
    """
    Find all Ember Mug entities in Home Assistant.

    Returns:
        List of entity info dicts with entity_id and attributes
    """
    ha_client = get_ha_client()
    all_states = ha_client.get_all_states()

    mugs = []
    for state in all_states:
        entity_id = state.get("entity_id", "").lower()
        # Check if this is an Ember Mug entity
        for pattern in EMBER_MUG_PATTERNS:
            if pattern in entity_id:
                mugs.append(state)
                break

    return mugs


def _get_mug_base_id(entity_id: str) -> str:
    """
    Extract the base entity ID from an Ember Mug entity.

    For example, "sensor.ember_mug_abc123_current_temperature"
    becomes "ember_mug_abc123"

    Args:
        entity_id: Full entity ID

    Returns:
        Base device identifier
    """
    # Remove domain prefix
    name = entity_id.split(".", 1)[-1]

    # Remove common suffixes
    suffixes = [
        "_target_temperature",
        "_current_temperature",
        "_battery_level",
        "_liquid_level",
        "_state",
        "_mug_name",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    return name


def _find_related_entities(base_id: str, all_states: list[dict]) -> dict[str, Any]:
    """
    Find all entities related to a specific Ember Mug.

    Args:
        base_id: Base identifier (e.g., "ember_mug_abc123")
        all_states: List of all HA states

    Returns:
        Dict mapping entity type to state info
    """
    related = {}
    for state in all_states:
        entity_id = state.get("entity_id", "").lower()
        if base_id in entity_id:
            # Identify entity type
            if "target_temperature" in entity_id:
                related["target_temp"] = state
            elif "current_temperature" in entity_id:
                related["current_temp"] = state
            elif "battery" in entity_id:
                related["battery"] = state
            elif "liquid_level" in entity_id:
                related["liquid"] = state
            elif "_state" in entity_id:
                related["state"] = state

    return related


def set_mug_temperature(
    target_temp: float | None = None, entity_id: str | None = None
) -> dict[str, Any]:
    """
    Set the target temperature for an Ember Mug.

    Args:
        target_temp: Target temperature in Fahrenheit (120-145)
        entity_id: Specific mug entity ID (optional)

    Returns:
        Result dictionary with success status
    """
    # Default temperature
    if target_temp is None:
        target_temp = DEFAULT_TEMP_F

    # Validate temperature
    if target_temp < MIN_TEMP_F:
        return {
            "success": False,
            "error": f"Temperature {target_temp}°F is too low. Minimum is {MIN_TEMP_F}°F.",
        }
    if target_temp > MAX_TEMP_F:
        return {
            "success": False,
            "error": f"Temperature {target_temp}°F is too high. Maximum is {MAX_TEMP_F}°F.",
        }

    ha_client = get_ha_client()

    # Find the mug
    if entity_id:
        # Verify entity exists
        state = ha_client.get_state(entity_id)
        if not state:
            return {"success": False, "error": f"Entity {entity_id} not found"}
    else:
        # Find any Ember Mug target_temperature entity
        all_states = ha_client.get_all_states()
        target_entities = [
            s
            for s in all_states
            if "target_temperature" in s.get("entity_id", "").lower()
            and any(p in s.get("entity_id", "").lower() for p in EMBER_MUG_PATTERNS)
        ]

        if not target_entities:
            return {
                "success": False,
                "error": "No Ember Mug found. Make sure the hass-ember-mug-component is installed and the mug is connected.",
                "setup_instructions": [
                    "1. Install hass-ember-mug-component from HACS",
                    "2. Put your Ember Mug in pairing mode",
                    "3. Home Assistant should auto-detect it",
                    "4. Try this command again once setup is complete",
                ],
            }

        entity_id = target_entities[0]["entity_id"]

    # Call the number.set_value service
    try:
        logger.info(f"Setting Ember Mug temperature to {target_temp}°F via {entity_id}")

        success = ha_client.call_service(
            domain="number",
            service="set_value",
            service_data={"value": target_temp},
            target={"entity_id": entity_id},
        )

        if success:
            return {
                "success": True,
                "message": f"Set Ember Mug target temperature to {target_temp}°F",
                "entity_id": entity_id,
                "target_temp": target_temp,
            }
        else:
            return {
                "success": False,
                "error": "Failed to set temperature. Check Home Assistant logs.",
            }
    except Exception as error:
        logger.error(f"Error setting mug temperature: {error}")
        return {"success": False, "error": str(error)}


def get_mug_status(entity_id: str | None = None) -> dict[str, Any]:
    """
    Get the current status of an Ember Mug.

    Args:
        entity_id: Specific mug entity ID (optional)

    Returns:
        Status dictionary with all mug information
    """
    ha_client = get_ha_client()
    all_states = ha_client.get_all_states()

    # Find Ember Mug entities
    mug_entities = [
        s
        for s in all_states
        if any(p in s.get("entity_id", "").lower() for p in EMBER_MUG_PATTERNS)
    ]

    if not mug_entities:
        return {
            "success": False,
            "error": "No Ember Mug found. Make sure the hass-ember-mug-component is installed and the mug is connected.",
            "setup_instructions": [
                "1. Install hass-ember-mug-component from HACS",
                "2. Put your Ember Mug in pairing mode",
                "3. Home Assistant should auto-detect it",
            ],
        }

    # If entity_id specified, find its base ID
    if entity_id:
        base_id = _get_mug_base_id(entity_id)
    else:
        # Use first mug found
        base_id = _get_mug_base_id(mug_entities[0]["entity_id"])

    # Get all related entities
    related = _find_related_entities(base_id, all_states)

    # Build status response
    status = {
        "success": True,
        "mug_id": base_id,
    }

    if "current_temp" in related:
        temp_state = related["current_temp"]
        status["current_temperature"] = {
            "value": temp_state.get("state"),
            "unit": temp_state.get("attributes", {}).get("unit_of_measurement", "°F"),
        }

    if "target_temp" in related:
        temp_state = related["target_temp"]
        status["target_temperature"] = {
            "value": temp_state.get("state"),
            "unit": temp_state.get("attributes", {}).get("unit_of_measurement", "°F"),
        }

    if "battery" in related:
        bat_state = related["battery"]
        status["battery"] = {
            "level": bat_state.get("state"),
            "unit": bat_state.get("attributes", {}).get("unit_of_measurement", "%"),
        }

    if "liquid" in related:
        status["liquid_level"] = related["liquid"].get("state")

    if "state" in related:
        status["device_state"] = related["state"].get("state")

    # Generate human-readable summary
    current_temp = status.get("current_temperature", {}).get("value", "unknown")
    target_temp = status.get("target_temperature", {}).get("value", "unknown")
    device_state = status.get("device_state", "unknown")

    status["summary"] = f"Mug is {device_state}. Current: {current_temp}°F, Target: {target_temp}°F"

    return status


def list_ember_mugs() -> dict[str, Any]:
    """
    List all Ember Mugs connected to Home Assistant.

    Returns:
        List of mugs with their status
    """
    ha_client = get_ha_client()
    all_states = ha_client.get_all_states()

    # Find all unique mug base IDs
    mug_base_ids = set()
    for state in all_states:
        entity_id = state.get("entity_id", "").lower()
        if any(p in entity_id for p in EMBER_MUG_PATTERNS):
            base_id = _get_mug_base_id(entity_id)
            mug_base_ids.add(base_id)

    if not mug_base_ids:
        return {
            "success": False,
            "error": "No Ember Mugs found",
            "mugs": [],
            "setup_instructions": [
                "1. Install hass-ember-mug-component from HACS",
                "2. Put your Ember Mug in pairing mode",
                "3. Home Assistant should auto-detect it",
            ],
        }

    # Get status for each mug
    mugs = []
    for base_id in mug_base_ids:
        related = _find_related_entities(base_id, all_states)

        mug_info = {
            "id": base_id,
        }

        if "current_temp" in related:
            mug_info["current_temp"] = related["current_temp"].get("state")
        if "target_temp" in related:
            mug_info["target_temp"] = related["target_temp"].get("state")
        if "battery" in related:
            mug_info["battery"] = related["battery"].get("state")
        if "state" in related:
            mug_info["state"] = related["state"].get("state")

        mugs.append(mug_info)

    return {"success": True, "count": len(mugs), "mugs": mugs}


def execute_ember_mug_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute an Ember Mug tool by name.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    tool_map = {
        "set_mug_temperature": set_mug_temperature,
        "get_mug_status": get_mug_status,
        "list_ember_mugs": list_ember_mugs,
    }

    if tool_name not in tool_map:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}",
            "available_tools": list(tool_map.keys()),
        }

    try:
        return tool_map[tool_name](**tool_input)
    except TypeError as error:
        return {"success": False, "error": f"Invalid parameters: {error}"}
    except Exception as error:
        logger.error(f"Error executing {tool_name}: {error}")
        return {"success": False, "error": str(error)}
