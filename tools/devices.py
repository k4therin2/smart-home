"""
Smart Home Assistant - Device Organization Tools

Agent tools for managing device organization, room assignments, and naming.
Part of WP-5.2: Device Organization Assistant.
"""

from typing import Any

from src.device_organizer import get_device_organizer
from src.device_registry import DeviceType, get_device_registry
from src.utils import setup_logging


logger = setup_logging("tools.devices")

# Tool definitions for Claude
DEVICE_TOOLS = [
    {
        "name": "list_devices",
        "description": """List registered devices in the smart home system.

Can filter by:
- room: Show only devices in a specific room
- type: Show only specific device types (light, switch, sensor, etc.)
- unassigned: Show only devices without room assignments

Examples:
- "show all devices" -> (no filters)
- "what devices are in the bedroom" -> room='bedroom'
- "list all lights" -> device_type='light'
- "show unassigned devices" -> unassigned=true

Returns device names, types, and room assignments.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Filter by room name (e.g., 'bedroom', 'kitchen')",
                },
                "device_type": {
                    "type": "string",
                    "description": "Filter by device type (light, switch, sensor, cover, climate, media_player, vacuum)",
                    "enum": [
                        "light",
                        "switch",
                        "sensor",
                        "cover",
                        "climate",
                        "media_player",
                        "vacuum",
                        "fan",
                        "lock",
                        "camera",
                    ],
                },
                "unassigned": {
                    "type": "boolean",
                    "description": "Show only devices without room assignment",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "suggest_room",
        "description": """Get room assignment suggestions for a device.

Uses device name and type to suggest appropriate room placements.

Examples:
- "where should the bedroom lamp go" -> device_name='bedroom lamp'
- "suggest room for the new light" -> entity_id='light.new_light'

Returns suggested rooms with confidence levels.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {"type": "string", "description": "Device friendly name to look up"},
                "entity_id": {"type": "string", "description": "Home Assistant entity ID"},
            },
            "required": [],
        },
    },
    {
        "name": "assign_device_to_room",
        "description": """Assign a device to a room.

Examples:
- "put the floor lamp in the living room" -> device_name='floor lamp', room='living_room'
- "move bedroom light to office" -> device_name='bedroom light', room='office'

Creates the room if it doesn't exist.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {"type": "string", "description": "Device friendly name to assign"},
                "entity_id": {"type": "string", "description": "Home Assistant entity ID"},
                "room": {
                    "type": "string",
                    "description": "Room name to assign to (e.g., 'bedroom', 'kitchen')",
                },
            },
            "required": ["room"],
        },
    },
    {
        "name": "rename_device",
        "description": """Rename a device to a more friendly name.

Examples:
- "rename hue_ambiance_1 to Desk Lamp" -> device_name='hue_ambiance_1', new_name='Desk Lamp'
- "call the bedroom light Main Light" -> device_name='bedroom light', new_name='Main Light'

Updates the device's friendly name in the registry.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Current device name or entity ID",
                },
                "new_name": {"type": "string", "description": "New friendly name for the device"},
            },
            "required": ["device_name", "new_name"],
        },
    },
    {
        "name": "organize_devices",
        "description": """Auto-organize unassigned devices into rooms.

Creates an organization plan based on device names and types,
then applies it to assign devices to appropriate rooms.

Examples:
- "organize all devices" -> auto_apply=true
- "suggest organization for new devices" -> auto_apply=false

Returns the organization plan with applied changes.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "auto_apply": {
                    "type": "boolean",
                    "description": "Automatically apply suggestions (true) or just show plan (false)",
                    "default": False,
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence for auto-apply (0.0-1.0)",
                    "default": 0.7,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_organization_status",
        "description": """Get the current organization status of devices.

Shows:
- Total devices and how many are organized
- Device count by room
- Recommendations for improving organization

Examples:
- "how organized are my devices"
- "show device organization status"
- "what needs organizing"

Returns organization statistics and recommendations.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sync_devices_from_ha",
        "description": """Sync new devices from Home Assistant.

Discovers devices in Home Assistant that aren't yet in the registry
and adds them for organization.

Examples:
- "discover new devices"
- "sync devices from home assistant"
- "find new devices"

Returns list of newly discovered devices.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_rooms",
        "description": """List all rooms in the smart home.

Shows room names, zones, and device counts.

Examples:
- "what rooms do I have"
- "show all rooms"
- "list rooms and their devices"

Returns room list with device counts.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "include_empty": {
                    "type": "boolean",
                    "description": "Include rooms with no devices",
                    "default": True,
                }
            },
            "required": [],
        },
    },
    {
        "name": "create_room",
        "description": """Create a new room in the smart home.

Examples:
- "create a guest room" -> name='guest_room'
- "add a nursery to upstairs" -> name='nursery', zone='upstairs'

Returns the created room details.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Room name (e.g., 'guest_room', 'nursery')",
                },
                "display_name": {
                    "type": "string",
                    "description": "Human-readable name (e.g., 'Guest Room')",
                },
                "zone": {
                    "type": "string",
                    "description": "Optional zone (e.g., 'upstairs', 'main_floor')",
                },
            },
            "required": ["name"],
        },
    },
]


def _find_device(
    device_name: str | None = None,
    entity_id: str | None = None,
) -> dict | None:
    """Find a device by name or entity_id."""
    registry = get_device_registry()

    if entity_id:
        return registry.get_device_by_entity_id(entity_id)

    if device_name:
        # Search by friendly name
        devices = registry.get_all_devices()
        device_name_lower = device_name.lower()

        # Exact match first
        for device in devices:
            if device.get("friendly_name", "").lower() == device_name_lower:
                return device

        # Partial match
        for device in devices:
            if device_name_lower in device.get("friendly_name", "").lower():
                return device
            if device_name_lower in device.get("entity_id", "").lower():
                return device

    return None


def list_devices(
    room: str | None = None,
    device_type: str | None = None,
    unassigned: bool = False,
) -> dict[str, Any]:
    """
    List devices with optional filtering.

    Args:
        room: Filter by room name
        device_type: Filter by device type
        unassigned: Show only unassigned devices

    Returns:
        Result dictionary with devices
    """
    try:
        registry = get_device_registry()

        if unassigned:
            devices = registry.get_unassigned_devices()
        elif room:
            devices = registry.get_devices_by_room(room)
        elif device_type:
            try:
                dtype = DeviceType(device_type)
                devices = registry.get_devices_by_type(dtype)
            except ValueError:
                return {"success": False, "error": f"Unknown device type: {device_type}"}
        else:
            devices = registry.get_all_devices()

        # Format output
        formatted = []
        for device in devices:
            formatted.append(
                {
                    "name": device.get("friendly_name"),
                    "entity_id": device.get("entity_id"),
                    "type": device.get("device_type"),
                    "room": device.get("room_name") or "Unassigned",
                }
            )

        # Create message
        if room:
            message = f"Found {len(devices)} device(s) in {room}:"
        elif device_type:
            message = f"Found {len(devices)} {device_type}(s):"
        elif unassigned:
            message = f"Found {len(devices)} unassigned device(s):"
        else:
            message = f"Found {len(devices)} device(s) total:"

        if formatted:
            lines = [message]
            for device in formatted:
                lines.append(f"- {device['name']} ({device['type']}) in {device['room']}")
            message = "\n".join(lines)
        else:
            message = "No devices found matching the criteria."

        return {
            "success": True,
            "devices": formatted,
            "count": len(devices),
            "message": message,
        }

    except Exception as error:
        logger.error(f"Error listing devices: {error}")
        return {"success": False, "error": str(error)}


def suggest_room(
    device_name: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """
    Get room suggestions for a device.

    Args:
        device_name: Device friendly name
        entity_id: Home Assistant entity ID

    Returns:
        Result dictionary with suggestions
    """
    try:
        device = _find_device(device_name, entity_id)
        if not device:
            return {"success": False, "error": f"Device not found: {device_name or entity_id}"}

        organizer = get_device_organizer()
        suggestions = organizer.suggest_room(device["id"])

        if not suggestions:
            return {
                "success": True,
                "suggestions": [],
                "message": f"No room suggestions for '{device.get('friendly_name')}'. Please specify a room manually.",
            }

        formatted = []
        for suggestion in suggestions[:3]:
            formatted.append(
                {
                    "room": suggestion.room_name,
                    "confidence": round(suggestion.confidence * 100),
                    "reason": suggestion.reason,
                }
            )

        message = f"Room suggestions for '{device.get('friendly_name')}':\n"
        for idx, suggestion in enumerate(formatted, 1):
            message += f"{idx}. {suggestion['room']} ({suggestion['confidence']}% confident) - {suggestion['reason']}\n"

        return {
            "success": True,
            "device": device.get("friendly_name"),
            "suggestions": formatted,
            "message": message.strip(),
        }

    except Exception as error:
        logger.error(f"Error suggesting room: {error}")
        return {"success": False, "error": str(error)}


def assign_device_to_room(
    room: str,
    device_name: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """
    Assign a device to a room.

    Args:
        room: Room name
        device_name: Device friendly name
        entity_id: Home Assistant entity ID

    Returns:
        Result dictionary with success status
    """
    try:
        device = _find_device(device_name, entity_id)
        if not device:
            return {"success": False, "error": f"Device not found: {device_name or entity_id}"}

        registry = get_device_registry()
        success = registry.move_device_to_room(device["id"], room)

        if success:
            return {
                "success": True,
                "device": device.get("friendly_name"),
                "room": room,
                "message": f"Moved '{device.get('friendly_name')}' to {room}.",
            }
        else:
            return {"success": False, "error": "Failed to move device"}

    except Exception as error:
        logger.error(f"Error assigning device: {error}")
        return {"success": False, "error": str(error)}


def rename_device(
    device_name: str,
    new_name: str,
) -> dict[str, Any]:
    """
    Rename a device.

    Args:
        device_name: Current device name or entity ID
        new_name: New friendly name

    Returns:
        Result dictionary with success status
    """
    try:
        device = _find_device(device_name)
        if not device:
            return {"success": False, "error": f"Device not found: {device_name}"}

        registry = get_device_registry()
        success = registry.rename_device(device["id"], new_name)

        if success:
            return {
                "success": True,
                "old_name": device.get("friendly_name"),
                "new_name": new_name,
                "message": f"Renamed '{device.get('friendly_name')}' to '{new_name}'.",
            }
        else:
            return {"success": False, "error": "Failed to rename device"}

    except Exception as error:
        logger.error(f"Error renaming device: {error}")
        return {"success": False, "error": str(error)}


def organize_devices(
    auto_apply: bool = False,
    min_confidence: float = 0.7,
) -> dict[str, Any]:
    """
    Create and optionally apply an organization plan.

    Args:
        auto_apply: Apply suggestions automatically
        min_confidence: Minimum confidence for auto-apply

    Returns:
        Result dictionary with plan and results
    """
    try:
        organizer = get_device_organizer()
        plan = organizer.create_organization_plan()

        if not plan.assignments:
            return {
                "success": True,
                "message": "All devices are already organized!",
                "plan": [],
            }

        formatted_plan = []
        for assignment in plan.assignments:
            formatted_plan.append(
                {
                    "device": assignment.get("friendly_name"),
                    "entity_id": assignment.get("entity_id"),
                    "suggested_room": assignment.get("suggested_room"),
                    "confidence": round(assignment.get("confidence", 0) * 100),
                    "reason": assignment.get("reason"),
                }
            )

        if auto_apply:
            results = organizer.apply_organization_plan(plan, min_confidence=min_confidence)

            applied_count = len(results["applied"])
            skipped_count = len(results["skipped"])

            message = f"Organization complete! Applied {applied_count} assignment(s)."
            if skipped_count:
                message += f" Skipped {skipped_count} (low confidence)."

            return {
                "success": True,
                "plan": formatted_plan,
                "applied": applied_count,
                "skipped": skipped_count,
                "message": message,
            }
        else:
            lines = [f"Organization plan for {len(formatted_plan)} device(s):"]
            for item in formatted_plan:
                lines.append(
                    f"- {item['device']} → {item['suggested_room']} "
                    f"({item['confidence']}% - {item['reason']})"
                )
            lines.append("\nUse auto_apply=true to apply this plan.")

            return {
                "success": True,
                "plan": formatted_plan,
                "applied": 0,
                "message": "\n".join(lines),
            }

    except Exception as error:
        logger.error(f"Error organizing devices: {error}")
        return {"success": False, "error": str(error)}


def get_organization_status() -> dict[str, Any]:
    """
    Get organization status and recommendations.

    Returns:
        Result dictionary with status and recommendations
    """
    try:
        organizer = get_device_organizer()
        status = organizer.get_organization_status()
        room_summary = organizer.get_room_summary()
        recommendations = organizer.get_recommendations()

        lines = [
            "Device Organization Status:",
            f"- Total devices: {status['total_devices']}",
            f"- Organized: {status['organized_devices']} ({status['organization_percentage']}%)",
            f"- Unorganized: {status['unorganized_devices']}",
            f"- Total rooms: {status['total_rooms']}",
            "",
            "Devices by room:",
        ]

        for room_name, info in room_summary.items():
            if info["device_count"] > 0:
                lines.append(f"- {info['display_name']}: {info['device_count']} device(s)")

        if recommendations:
            lines.extend(["", "Recommendations:"])
            for rec in recommendations[:3]:
                lines.append(f"- {rec['message']}")

        return {
            "success": True,
            "status": status,
            "room_summary": room_summary,
            "recommendations": recommendations,
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error getting status: {error}")
        return {"success": False, "error": str(error)}


def sync_devices_from_ha() -> dict[str, Any]:
    """
    Sync devices from Home Assistant.

    Returns:
        Result dictionary with new devices
    """
    try:
        from src.ha_client import get_ha_client

        registry = get_device_registry()
        ha_client = get_ha_client()

        new_devices = registry.sync_from_ha(ha_client)

        if not new_devices:
            return {
                "success": True,
                "new_devices": [],
                "count": 0,
                "message": "No new devices found in Home Assistant.",
            }

        formatted = []
        for device in new_devices:
            formatted.append(
                {
                    "name": device.get("friendly_name"),
                    "entity_id": device.get("entity_id"),
                    "type": device.get("device_type"),
                }
            )

        lines = [f"Discovered {len(new_devices)} new device(s):"]
        for device in formatted:
            lines.append(f"- {device['name']} ({device['type']})")

        return {
            "success": True,
            "new_devices": formatted,
            "count": len(new_devices),
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error syncing devices: {error}")
        return {"success": False, "error": str(error)}


def list_rooms(include_empty: bool = True) -> dict[str, Any]:
    """
    List all rooms.

    Args:
        include_empty: Include rooms with no devices

    Returns:
        Result dictionary with rooms
    """
    try:
        organizer = get_device_organizer()
        room_summary = organizer.get_room_summary()

        rooms = []
        for room_name, info in room_summary.items():
            if not include_empty and info["device_count"] == 0:
                continue
            rooms.append(
                {
                    "name": room_name,
                    "display_name": info["display_name"],
                    "zone": info.get("zone"),
                    "device_count": info["device_count"],
                }
            )

        lines = [f"Rooms ({len(rooms)}):"]
        for room in sorted(rooms, key=lambda r: r["display_name"]):
            zone_str = f" ({room['zone']})" if room["zone"] else ""
            lines.append(f"- {room['display_name']}{zone_str}: {room['device_count']} device(s)")

        return {
            "success": True,
            "rooms": rooms,
            "count": len(rooms),
            "message": "\n".join(lines),
        }

    except Exception as error:
        logger.error(f"Error listing rooms: {error}")
        return {"success": False, "error": str(error)}


def create_room(
    name: str,
    display_name: str | None = None,
    zone: str | None = None,
) -> dict[str, Any]:
    """
    Create a new room.

    Args:
        name: Room identifier
        display_name: Human-readable name
        zone: Optional zone assignment

    Returns:
        Result dictionary with created room
    """
    try:
        registry = get_device_registry()

        if not display_name:
            display_name = name.replace("_", " ").title()

        success = registry.create_room(
            name=name,
            display_name=display_name,
            zone_name=zone,
        )

        if success:
            return {
                "success": True,
                "room": {
                    "name": registry.normalize_room_name(name),
                    "display_name": display_name,
                    "zone": zone,
                },
                "message": f"Created room '{display_name}'.",
            }
        else:
            return {"success": False, "error": f"Room '{name}' already exists"}

    except Exception as error:
        logger.error(f"Error creating room: {error}")
        return {"success": False, "error": str(error)}


def execute_device_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a device organization tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing device tool: {tool_name}")

    if tool_name == "list_devices":
        return list_devices(
            room=tool_input.get("room"),
            device_type=tool_input.get("device_type"),
            unassigned=tool_input.get("unassigned", False),
        )

    elif tool_name == "suggest_room":
        return suggest_room(
            device_name=tool_input.get("device_name"),
            entity_id=tool_input.get("entity_id"),
        )

    elif tool_name == "assign_device_to_room":
        return assign_device_to_room(
            room=tool_input.get("room", ""),
            device_name=tool_input.get("device_name"),
            entity_id=tool_input.get("entity_id"),
        )

    elif tool_name == "rename_device":
        return rename_device(
            device_name=tool_input.get("device_name", ""),
            new_name=tool_input.get("new_name", ""),
        )

    elif tool_name == "organize_devices":
        return organize_devices(
            auto_apply=tool_input.get("auto_apply", False),
            min_confidence=tool_input.get("min_confidence", 0.7),
        )

    elif tool_name == "get_organization_status":
        return get_organization_status()

    elif tool_name == "sync_devices_from_ha":
        return sync_devices_from_ha()

    elif tool_name == "list_rooms":
        return list_rooms(
            include_empty=tool_input.get("include_empty", True),
        )

    elif tool_name == "create_room":
        return create_room(
            name=tool_input.get("name", ""),
            display_name=tool_input.get("display_name"),
            zone=tool_input.get("zone"),
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
