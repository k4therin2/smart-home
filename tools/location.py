"""
Smart Home Assistant - Location-Aware Command Tools

Agent tools for managing user location, voice puck registration, and location inference.
Part of WP-5.3: Location-Aware Commands.
"""

from typing import Any

from src.location_manager import LocationManager
from src.utils import setup_logging


logger = setup_logging("tools.location")

# Singleton instance
_location_manager: LocationManager | None = None


def get_location_manager() -> LocationManager:
    """Get or create the singleton LocationManager instance."""
    global _location_manager
    if _location_manager is None:
        _location_manager = LocationManager()
    return _location_manager


# Tool definitions for Claude
LOCATION_TOOLS = [
    {
        "name": "get_user_location",
        "description": """Get the user's current location (room).

Uses the priority chain:
1. Explicit room parameter (if provided in command)
2. Current tracked location (from recent voice puck activity)
3. Default location (if configured)

Returns the effective room or None if unknown.

Examples:
- "where am I" -> (no parameters)
- "what room am I in" -> (no parameters)
- "get my location" -> (no parameters)

Use this to determine context before executing room-based commands.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_user_location",
        "description": """Manually set the user's current location.

Use when the user explicitly says which room they're in,
or when they move to a different room.

Examples:
- "I'm in the bedroom" -> room='bedroom'
- "I'm going to the kitchen" -> room='kitchen'
- "I moved to the living room" -> room='living_room'

This updates the tracked location for context-aware commands.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name (e.g., 'bedroom', 'living room', 'kitchen', 'office')",
                }
            },
            "required": ["room"],
        },
    },
    {
        "name": "get_room_from_voice_context",
        "description": """Infer the user's room from voice puck context.

Called automatically when processing voice commands from HA webhook.
Uses the device_id from the voice context to look up the registered
voice puck's room assignment.

Examples:
- (Called by voice handler) -> context={'device_id': 'puck_living_001'}

Returns the room where the voice puck is located, or None if unknown.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Voice puck device ID from HA webhook context",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "register_voice_puck",
        "description": """Register a voice puck device with its room location.

Used during setup to map voice puck device IDs to rooms.
This enables automatic location inference from voice commands.

Examples:
- "register the living room voice puck" -> room='living_room'
- "the bedroom puck is device xyz123" -> device_id='xyz123', room='bedroom'

The device_id must match the device_id in HA webhook context.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Voice puck device ID from Home Assistant",
                },
                "room": {"type": "string", "description": "Room where the puck is located"},
                "display_name": {
                    "type": "string",
                    "description": "Human-readable name for the puck (optional)",
                },
            },
            "required": ["device_id", "room"],
        },
    },
    {
        "name": "list_voice_pucks",
        "description": """List all registered voice pucks and their room assignments.

Shows all voice pucks configured for location tracking.

Examples:
- "show my voice pucks" -> (no parameters)
- "list voice devices" -> (no parameters)
- "what pucks are registered" -> (no parameters)

Returns list of pucks with their device IDs and room assignments.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_default_location",
        "description": """Set the default/fallback room location.

Used when location cannot be determined from voice context or tracking.
This is the "home base" room.

Examples:
- "set my default room to living room" -> room='living_room'
- "my default location is the bedroom" -> room='bedroom'

The default is used only when no other location info is available.""",
        "input_schema": {
            "type": "object",
            "properties": {"room": {"type": "string", "description": "Default room name"}},
            "required": ["room"],
        },
    },
    {
        "name": "get_location_history",
        "description": """Get recent location history.

Shows where the user has been recently, useful for understanding
movement patterns or debugging location tracking.

Examples:
- "where have I been" -> (no parameters)
- "show my location history" -> limit=10
- "last 5 locations" -> limit=5

Returns chronological list of recent locations.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
    {
        "name": "clear_user_location",
        "description": """Clear the user's tracked location.

Removes the current location tracking, useful when leaving home
or when location is no longer valid.

Examples:
- "forget my location" -> (no parameters)
- "clear my location" -> (no parameters)
- "I'm leaving" -> (no parameters)

After clearing, location will fall back to default if set.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def get_user_location() -> dict[str, Any]:
    """
    Get the user's effective current location.

    Returns:
        Result dictionary with location info
    """
    try:
        manager = get_location_manager()

        effective_location = manager.get_effective_location()
        location_info = manager.get_user_location_info()
        is_stale = manager.is_location_stale()
        default_location = manager.get_default_location()

        if effective_location:
            source = "current"
            if not location_info or is_stale:
                source = "default"

            return {
                "success": True,
                "room": effective_location,
                "source": source,
                "is_stale": is_stale,
                "default_location": default_location,
                "message": f"You are in the {effective_location.replace('_', ' ')}.",
            }
        else:
            return {
                "success": True,
                "room": None,
                "source": None,
                "is_stale": True,
                "default_location": default_location,
                "message": "I don't know your current location. Which room are you in?",
            }

    except Exception as error:
        logger.error(f"Error getting user location: {error}")
        return {"success": False, "error": str(error)}


def set_user_location(room: str) -> dict[str, Any]:
    """
    Set the user's current location.

    Args:
        room: Room name

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_location_manager()

        # Validate room
        if not manager.is_valid_room(room):
            resolved = manager.resolve_room_alias(room)
            return {
                "success": False,
                "error": f"Unknown room: {room}. Did you mean '{resolved}'?",
            }

        manager.set_user_location(room, source="manual")
        resolved_room = manager.resolve_room_alias(room)

        return {
            "success": True,
            "room": resolved_room,
            "message": f"Got it, you're in the {resolved_room.replace('_', ' ')}.",
        }

    except Exception as error:
        logger.error(f"Error setting user location: {error}")
        return {"success": False, "error": str(error)}


def get_room_from_voice_context(device_id: str) -> dict[str, Any]:
    """
    Get room from voice puck device ID.

    Args:
        device_id: Voice puck device ID from HA webhook

    Returns:
        Result dictionary with room info
    """
    try:
        manager = get_location_manager()

        room = manager.get_room_from_puck(device_id)

        if room:
            # Also update user location from puck activity
            manager.record_puck_activity(device_id)

            return {
                "success": True,
                "room": room,
                "device_id": device_id,
                "message": f"Voice command from {room.replace('_', ' ')} puck.",
            }
        else:
            return {
                "success": True,
                "room": None,
                "device_id": device_id,
                "message": f"Voice puck {device_id} is not registered. Use register_voice_puck to set it up.",
            }

    except Exception as error:
        logger.error(f"Error getting room from context: {error}")
        return {"success": False, "error": str(error)}


def register_voice_puck(
    device_id: str,
    room: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """
    Register a voice puck with room assignment.

    Args:
        device_id: Voice puck device ID
        room: Room where puck is located
        display_name: Optional friendly name

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_location_manager()

        # Validate room (warn but allow unknown rooms for flexibility)
        resolved_room = manager.resolve_room_alias(room)

        if not display_name:
            display_name = f"{resolved_room.replace('_', ' ').title()} Voice Puck"

        manager.register_voice_puck(device_id, resolved_room, display_name)

        return {
            "success": True,
            "device_id": device_id,
            "room": resolved_room,
            "display_name": display_name,
            "message": f"Registered '{display_name}' in {resolved_room.replace('_', ' ')}.",
        }

    except Exception as error:
        logger.error(f"Error registering voice puck: {error}")
        return {"success": False, "error": str(error)}


def list_voice_pucks() -> dict[str, Any]:
    """
    List all registered voice pucks.

    Returns:
        Result dictionary with pucks
    """
    try:
        manager = get_location_manager()

        pucks = manager.list_voice_pucks()

        if not pucks:
            return {
                "success": True,
                "pucks": [],
                "count": 0,
                "message": "No voice pucks registered. Use register_voice_puck to add them.",
            }

        formatted = []
        lines = [f"Registered voice pucks ({len(pucks)}):"]

        for puck in pucks:
            formatted.append(
                {
                    "device_id": puck["device_id"],
                    "room": puck["room_name"],
                    "display_name": puck.get("display_name"),
                }
            )
            lines.append(
                f"- {puck.get('display_name', puck['device_id'])} in {puck['room_name'].replace('_', ' ')}"
            )

        return {
            "success": True,
            "pucks": formatted,
            "count": len(pucks),
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error listing voice pucks: {error}")
        return {"success": False, "error": str(error)}


def set_default_location(room: str) -> dict[str, Any]:
    """
    Set the default/fallback location.

    Args:
        room: Default room name

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_location_manager()

        resolved_room = manager.resolve_room_alias(room)
        manager.set_default_location(resolved_room)

        return {
            "success": True,
            "room": resolved_room,
            "message": f"Default location set to {resolved_room.replace('_', ' ')}.",
        }

    except Exception as error:
        logger.error(f"Error setting default location: {error}")
        return {"success": False, "error": str(error)}


def get_location_history(limit: int = 10) -> dict[str, Any]:
    """
    Get recent location history.

    Args:
        limit: Maximum entries to return

    Returns:
        Result dictionary with history
    """
    try:
        manager = get_location_manager()

        history = manager.get_location_history(limit=limit)

        if not history:
            return {
                "success": True,
                "history": [],
                "count": 0,
                "message": "No location history recorded yet.",
            }

        formatted = []
        lines = [f"Recent locations ({len(history)}):"]

        for entry in history:
            formatted.append(
                {
                    "room": entry["room_name"],
                    "source": entry["source"],
                    "timestamp": entry["timestamp"],
                }
            )
            lines.append(
                f"- {entry['room_name'].replace('_', ' ')} ({entry['source']}) at {entry['timestamp']}"
            )

        return {
            "success": True,
            "history": formatted,
            "count": len(history),
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error getting location history: {error}")
        return {"success": False, "error": str(error)}


def clear_user_location() -> dict[str, Any]:
    """
    Clear the user's tracked location.

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_location_manager()

        manager.clear_user_location()

        default = manager.get_default_location()
        if default:
            return {
                "success": True,
                "message": f"Location cleared. Will use default ({default.replace('_', ' ')}) for context.",
            }
        else:
            return {
                "success": True,
                "message": "Location cleared. I'll ask which room you're in when needed.",
            }

    except Exception as error:
        logger.error(f"Error clearing location: {error}")
        return {"success": False, "error": str(error)}


def execute_location_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a location tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing location tool: {tool_name}")

    if tool_name == "get_user_location":
        return get_user_location()

    elif tool_name == "set_user_location":
        return set_user_location(
            room=tool_input.get("room", ""),
        )

    elif tool_name == "get_room_from_voice_context":
        return get_room_from_voice_context(
            device_id=tool_input.get("device_id", ""),
        )

    elif tool_name == "register_voice_puck":
        return register_voice_puck(
            device_id=tool_input.get("device_id", ""),
            room=tool_input.get("room", ""),
            display_name=tool_input.get("display_name"),
        )

    elif tool_name == "list_voice_pucks":
        return list_voice_pucks()

    elif tool_name == "set_default_location":
        return set_default_location(
            room=tool_input.get("room", ""),
        )

    elif tool_name == "get_location_history":
        return get_location_history(
            limit=tool_input.get("limit", 10),
        )

    elif tool_name == "clear_user_location":
        return clear_user_location()

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
