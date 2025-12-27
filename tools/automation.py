"""
Smart Home Assistant - Automation Tools

Agent tools for creating and managing home automations via natural language.
Part of WP-4.2: Simple Automation Creation.
"""

import re
from typing import Any

from src.automation_manager import VALID_DAYS, get_automation_manager
from src.utils import setup_logging


logger = setup_logging("tools.automation")

# Tool definitions for Claude
AUTOMATION_TOOLS = [
    {
        "name": "create_automation",
        "description": """Create a new home automation rule.

Supports two types of automations:
1. Time-based: "Do X at time Y" - triggers at specific times
2. State-based: "When X happens, do Y" - triggers on entity state changes

Examples:
- "Turn on warm lights at 8pm every day" -> time trigger, agent command
- "Turn off all lights at 11pm on weekdays" -> time trigger, days filter
- "Start vacuum when I leave home" -> state trigger (presence)
- "Turn on porch light at sunset" -> time trigger (special time)

The LLM should parse the natural language request and extract:
- trigger_type: 'time' or 'state'
- trigger_config: time and days, or entity and state conditions
- action_command: the action to perform (as natural language for the agent)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short name for the automation (e.g., 'Evening lights', 'Goodbye vacuum')",
                },
                "trigger_type": {
                    "type": "string",
                    "enum": ["time", "state"],
                    "description": "Type of trigger: 'time' for scheduled, 'state' for event-based",
                },
                "trigger_time": {
                    "type": "string",
                    "description": "For time triggers: time in HH:MM format (24-hour) or special values like 'sunset', 'sunrise'",
                },
                "trigger_days": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    },
                    "description": "Days of week for time triggers (default: all days)",
                },
                "trigger_entity": {
                    "type": "string",
                    "description": "For state triggers: entity_id to watch (e.g., 'person.katherine', 'binary_sensor.door')",
                },
                "trigger_from_state": {
                    "type": "string",
                    "description": "For state triggers: state to transition FROM (optional)",
                },
                "trigger_to_state": {
                    "type": "string",
                    "description": "For state triggers: state to transition TO",
                },
                "action_command": {
                    "type": "string",
                    "description": "Natural language command to execute (e.g., 'turn living room to warm yellow at 80%')",
                },
            },
            "required": ["name", "trigger_type", "action_command"],
        },
    },
    {
        "name": "list_automations",
        "description": """View all configured automations.

Shows automation name, trigger type, schedule/conditions, and enabled status.
Can filter to show only enabled automations or by trigger type.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "enabled_only": {
                    "type": "boolean",
                    "description": "Only show enabled automations",
                    "default": False,
                },
                "trigger_type": {
                    "type": "string",
                    "enum": ["time", "state"],
                    "description": "Filter by trigger type",
                },
            },
            "required": [],
        },
    },
    {
        "name": "toggle_automation",
        "description": """Enable or disable an automation.

Examples:
- "disable the evening lights automation"
- "turn on the goodbye vacuum automation"
- "pause my morning routine"

Can match by automation name (fuzzy) or ID.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "automation_id": {"type": "integer", "description": "Automation ID (if known)"},
                "name_match": {
                    "type": "string",
                    "description": "Text to match against automation name",
                },
            },
            "required": [],
        },
    },
    {
        "name": "delete_automation",
        "description": """Delete an automation permanently.

Examples:
- "remove the evening lights automation"
- "delete the vacuum automation"

Can match by automation name (fuzzy) or ID.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "automation_id": {"type": "integer", "description": "Automation ID (if known)"},
                "name_match": {
                    "type": "string",
                    "description": "Text to match against automation name",
                },
            },
            "required": [],
        },
    },
    {
        "name": "update_automation",
        "description": """Modify an existing automation.

Can update the name, trigger time/days, or action command.

Examples:
- "change evening lights to 9pm instead of 8pm"
- "update the vacuum automation to run on weekdays only"
- "rename morning routine to wake up lights" """,
        "input_schema": {
            "type": "object",
            "properties": {
                "automation_id": {"type": "integer", "description": "Automation ID (if known)"},
                "name_match": {
                    "type": "string",
                    "description": "Text to match against automation name",
                },
                "new_name": {"type": "string", "description": "New name for the automation"},
                "new_time": {"type": "string", "description": "New trigger time (HH:MM format)"},
                "new_days": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New days of week",
                },
                "new_action": {"type": "string", "description": "New action command"},
            },
            "required": [],
        },
    },
]


def _parse_time(time_str: str) -> str | None:
    """
    Parse a time string into HH:MM format.

    Args:
        time_str: Time string (e.g., '8pm', '20:00', '8:30pm')

    Returns:
        Time in HH:MM format or None if invalid
    """
    if not time_str:
        return None

    time_str = time_str.lower().strip()

    # Already in HH:MM format
    if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_str):
        # Pad hour if needed
        parts = time_str.split(":")
        return f"{int(parts[0]):02d}:{parts[1]}"

    # Parse Xpm, Xam, X:XXpm, X:XXam
    match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return None


def _parse_days(days_input: list[str] | None) -> list[str]:
    """
    Parse and validate days of week.

    Args:
        days_input: List of day abbreviations or special values

    Returns:
        List of valid day abbreviations
    """
    if not days_input:
        return VALID_DAYS.copy()

    result = []
    for day in days_input:
        day_lower = day.lower().strip()

        # Handle special values
        if day_lower == "weekdays":
            result.extend(["mon", "tue", "wed", "thu", "fri"])
        elif day_lower == "weekends":
            result.extend(["sat", "sun"])
        elif day_lower in VALID_DAYS:
            result.append(day_lower)
        # Handle full day names
        elif day_lower.startswith("mon"):
            result.append("mon")
        elif day_lower.startswith("tue"):
            result.append("tue")
        elif day_lower.startswith("wed"):
            result.append("wed")
        elif day_lower.startswith("thu"):
            result.append("thu")
        elif day_lower.startswith("fri"):
            result.append("fri")
        elif day_lower.startswith("sat"):
            result.append("sat")
        elif day_lower.startswith("sun"):
            result.append("sun")

    # Remove duplicates while preserving order
    seen = set()
    return [day for day in result if not (day in seen or seen.add(day))]


def _format_automation(automation: dict) -> str:
    """Format an automation for display."""
    status = "enabled" if automation["enabled"] else "disabled"
    trigger_config = automation["trigger_config"]
    action_config = automation["action_config"]

    # Format trigger description
    if automation["trigger_type"] == "time":
        time_str = trigger_config.get("time", "?")
        days = trigger_config.get("days", VALID_DAYS)
        if set(days) == set(VALID_DAYS):
            days_str = "daily"
        elif set(days) == {"mon", "tue", "wed", "thu", "fri"}:
            days_str = "weekdays"
        elif set(days) == {"sat", "sun"}:
            days_str = "weekends"
        else:
            days_str = ", ".join(days)
        trigger_str = f"at {time_str} ({days_str})"
    else:
        entity = trigger_config.get("entity_id", "?")
        to_state = trigger_config.get("to_state", "?")
        trigger_str = f"when {entity} becomes {to_state}"

    # Format action
    action_str = action_config.get("command", "?")

    return f"[{status}] {automation['name']}: {trigger_str} -> {action_str}"


def _find_automation_by_name(name_match: str) -> dict | None:
    """Find automation by fuzzy name match."""
    manager = get_automation_manager()
    automations = manager.get_automations()

    name_lower = name_match.lower()
    for automation in automations:
        if name_lower in automation["name"].lower():
            return automation

    return None


def create_automation(
    name: str,
    trigger_type: str,
    action_command: str,
    trigger_time: str | None = None,
    trigger_days: list[str] | None = None,
    trigger_entity: str | None = None,
    trigger_from_state: str | None = None,
    trigger_to_state: str | None = None,
) -> dict[str, Any]:
    """
    Create a new automation.

    Args:
        name: Name for the automation
        trigger_type: 'time' or 'state'
        action_command: Natural language command to execute
        trigger_time: Time in HH:MM or natural format (for time triggers)
        trigger_days: Days of week (for time triggers)
        trigger_entity: Entity ID (for state triggers)
        trigger_from_state: State to transition from (for state triggers)
        trigger_to_state: State to transition to (for state triggers)

    Returns:
        Result dictionary with success status
    """
    if not name or not name.strip():
        return {"success": False, "error": "Name cannot be empty"}

    if not action_command or not action_command.strip():
        return {"success": False, "error": "Action command cannot be empty"}

    try:
        manager = get_automation_manager()

        # Build trigger config based on type
        if trigger_type == "time":
            parsed_time = _parse_time(trigger_time)
            if not parsed_time:
                return {
                    "success": False,
                    "error": f"Invalid time format: {trigger_time}. Use HH:MM or '8pm' format.",
                }

            trigger_config = {
                "type": "time",
                "time": parsed_time,
                "days": _parse_days(trigger_days),
            }
        elif trigger_type == "state":
            if not trigger_entity:
                return {"success": False, "error": "State triggers require trigger_entity"}
            if not trigger_to_state:
                return {"success": False, "error": "State triggers require trigger_to_state"}

            trigger_config = {
                "type": "state",
                "entity_id": trigger_entity,
                "to_state": trigger_to_state,
            }
            if trigger_from_state:
                trigger_config["from_state"] = trigger_from_state
        else:
            return {"success": False, "error": f"Invalid trigger_type: {trigger_type}"}

        # Build action config
        action_config = {"type": "agent_command", "command": action_command.strip()}

        automation_id = manager.create_automation(
            name=name.strip(),
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            action_type="agent_command",
            action_config=action_config,
        )

        logger.info(f"Created automation '{name}': {trigger_type} -> {action_command}")

        # Format confirmation message
        if trigger_type == "time":
            days = trigger_config.get("days", VALID_DAYS)
            if set(days) == set(VALID_DAYS):
                days_str = "every day"
            elif set(days) == {"mon", "tue", "wed", "thu", "fri"}:
                days_str = "on weekdays"
            elif set(days) == {"sat", "sun"}:
                days_str = "on weekends"
            else:
                days_str = f"on {', '.join(days)}"

            message = f"Created automation '{name}': at {trigger_config['time']} {days_str}, I'll {action_command}."
        else:
            message = f"Created automation '{name}': when {trigger_entity} becomes {trigger_to_state}, I'll {action_command}."

        return {"success": True, "automation_id": automation_id, "name": name, "message": message}

    except Exception as error:
        logger.error(f"Error creating automation: {error}")
        return {"success": False, "error": str(error)}


def list_automations(
    enabled_only: bool = False,
    trigger_type: str | None = None,
) -> dict[str, Any]:
    """
    List all automations.

    Args:
        enabled_only: Only return enabled automations
        trigger_type: Filter by trigger type

    Returns:
        Result dictionary with automations list
    """
    try:
        manager = get_automation_manager()
        automations = manager.get_automations(enabled_only=enabled_only, trigger_type=trigger_type)

        if not automations:
            return {
                "success": True,
                "automations": [],
                "count": 0,
                "message": "No automations configured yet.",
            }

        lines = ["Your automations:"]
        for automation in automations:
            lines.append(f"- {_format_automation(automation)}")

        stats = manager.get_stats()
        lines.append(
            f"\nTotal: {stats['total']} ({stats['enabled']} enabled, {stats['disabled']} disabled)"
        )

        return {
            "success": True,
            "automations": automations,
            "count": len(automations),
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error listing automations: {error}")
        return {"success": False, "error": str(error)}


def toggle_automation(
    automation_id: int | None = None,
    name_match: str | None = None,
) -> dict[str, Any]:
    """
    Toggle automation enabled/disabled.

    Args:
        automation_id: Automation ID (if known)
        name_match: Text to match against name

    Returns:
        Result dictionary with success status
    """
    if not automation_id and not name_match:
        return {"success": False, "error": "Either automation_id or name_match is required"}

    try:
        manager = get_automation_manager()

        if name_match and not automation_id:
            automation = _find_automation_by_name(name_match)
            if not automation:
                return {"success": False, "error": f"No automation found matching '{name_match}'"}
            automation_id = automation["id"]

        # Get current state before toggling
        current = manager.get_automation(automation_id)
        if not current:
            return {"success": False, "error": f"Automation {automation_id} not found"}

        success = manager.toggle_automation(automation_id)
        if success:
            new_state = "disabled" if current["enabled"] else "enabled"
            return {
                "success": True,
                "automation_id": automation_id,
                "message": f"{new_state.capitalize()} automation '{current['name']}'.",
            }
        else:
            return {"success": False, "error": f"Failed to toggle automation {automation_id}"}

    except Exception as error:
        logger.error(f"Error toggling automation: {error}")
        return {"success": False, "error": str(error)}


def delete_automation(
    automation_id: int | None = None,
    name_match: str | None = None,
) -> dict[str, Any]:
    """
    Delete an automation.

    Args:
        automation_id: Automation ID (if known)
        name_match: Text to match against name

    Returns:
        Result dictionary with success status
    """
    if not automation_id and not name_match:
        return {"success": False, "error": "Either automation_id or name_match is required"}

    try:
        manager = get_automation_manager()

        if name_match and not automation_id:
            automation = _find_automation_by_name(name_match)
            if not automation:
                return {"success": False, "error": f"No automation found matching '{name_match}'"}
            automation_id = automation["id"]
            name = automation["name"]
        else:
            current = manager.get_automation(automation_id)
            name = current["name"] if current else f"#{automation_id}"

        success = manager.delete_automation(automation_id)
        if success:
            return {"success": True, "message": f"Deleted automation '{name}'."}
        else:
            return {"success": False, "error": f"Automation {automation_id} not found"}

    except Exception as error:
        logger.error(f"Error deleting automation: {error}")
        return {"success": False, "error": str(error)}


def update_automation(
    automation_id: int | None = None,
    name_match: str | None = None,
    new_name: str | None = None,
    new_time: str | None = None,
    new_days: list[str] | None = None,
    new_action: str | None = None,
) -> dict[str, Any]:
    """
    Update an existing automation.

    Args:
        automation_id: Automation ID (if known)
        name_match: Text to match against name
        new_name: New name for the automation
        new_time: New trigger time
        new_days: New days of week
        new_action: New action command

    Returns:
        Result dictionary with success status
    """
    if not automation_id and not name_match:
        return {"success": False, "error": "Either automation_id or name_match is required"}

    if not any([new_name, new_time, new_days, new_action]):
        return {"success": False, "error": "At least one update field is required"}

    try:
        manager = get_automation_manager()

        if name_match and not automation_id:
            automation = _find_automation_by_name(name_match)
            if not automation:
                return {"success": False, "error": f"No automation found matching '{name_match}'"}
            automation_id = automation["id"]
        else:
            automation = manager.get_automation(automation_id)
            if not automation:
                return {"success": False, "error": f"Automation {automation_id} not found"}

        updates = {}

        if new_name:
            updates["name"] = new_name

        if new_time or new_days:
            trigger_config = automation["trigger_config"].copy()
            if new_time:
                parsed_time = _parse_time(new_time)
                if not parsed_time:
                    return {"success": False, "error": f"Invalid time format: {new_time}"}
                trigger_config["time"] = parsed_time
            if new_days:
                trigger_config["days"] = _parse_days(new_days)
            updates["trigger_config"] = trigger_config

        if new_action:
            action_config = automation["action_config"].copy()
            action_config["command"] = new_action
            updates["action_config"] = action_config

        success = manager.update_automation(automation_id, **updates)
        if success:
            changes = []
            if new_name:
                changes.append(f"name to '{new_name}'")
            if new_time:
                changes.append(f"time to {_parse_time(new_time)}")
            if new_days:
                changes.append(f"days to {', '.join(_parse_days(new_days))}")
            if new_action:
                changes.append(f"action to '{new_action}'")

            return {
                "success": True,
                "automation_id": automation_id,
                "message": f"Updated automation '{automation['name']}': changed {', '.join(changes)}.",
            }
        else:
            return {"success": False, "error": f"Failed to update automation {automation_id}"}

    except Exception as error:
        logger.error(f"Error updating automation: {error}")
        return {"success": False, "error": str(error)}


def execute_automation_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute an automation tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing automation tool: {tool_name}")

    if tool_name == "create_automation":
        return create_automation(
            name=tool_input.get("name", ""),
            trigger_type=tool_input.get("trigger_type", "time"),
            action_command=tool_input.get("action_command", ""),
            trigger_time=tool_input.get("trigger_time"),
            trigger_days=tool_input.get("trigger_days"),
            trigger_entity=tool_input.get("trigger_entity"),
            trigger_from_state=tool_input.get("trigger_from_state"),
            trigger_to_state=tool_input.get("trigger_to_state"),
        )

    elif tool_name == "list_automations":
        return list_automations(
            enabled_only=tool_input.get("enabled_only", False),
            trigger_type=tool_input.get("trigger_type"),
        )

    elif tool_name == "toggle_automation":
        return toggle_automation(
            automation_id=tool_input.get("automation_id"),
            name_match=tool_input.get("name_match"),
        )

    elif tool_name == "delete_automation":
        return delete_automation(
            automation_id=tool_input.get("automation_id"),
            name_match=tool_input.get("name_match"),
        )

    elif tool_name == "update_automation":
        return update_automation(
            automation_id=tool_input.get("automation_id"),
            name_match=tool_input.get("name_match"),
            new_name=tool_input.get("new_name"),
            new_time=tool_input.get("new_time"),
            new_days=tool_input.get("new_days"),
            new_action=tool_input.get("new_action"),
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
