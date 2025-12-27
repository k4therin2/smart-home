"""
Smart Home Assistant - Light Control Tools

Tools for controlling Philips Hue lights through Home Assistant.
Includes basic controls and integration with the Hue specialist agent.
"""

from typing import Any

from src.config import (
    ROOM_ENTITY_MAP,
    VIBE_PRESETS,
    get_room_entity,
)
from src.ha_client import get_ha_client
from src.utils import setup_logging


logger = setup_logging("tools.lights")

# Common color name to RGB mapping
COLOR_NAME_TO_RGB = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "violet": (238, 130, 238),
    "pink": (255, 192, 203),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "white": (255, 255, 255),
    "warm white": (255, 244, 229),
    "cool white": (255, 255, 255),
    "lime": (0, 255, 0),
    "teal": (0, 128, 128),
    "lavender": (230, 230, 250),
    "coral": (255, 127, 80),
    "salmon": (250, 128, 114),
    "turquoise": (64, 224, 208),
    "gold": (255, 215, 0),
    "navy": (0, 0, 128),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "aqua": (0, 255, 255),
    "indigo": (75, 0, 130),
}


# Tool definitions for Claude
LIGHT_TOOLS = [
    {
        "name": "set_room_ambiance",
        "description": """Set the ambiance of a room's lights. Use this for any lighting request.

For specific settings: provide brightness (0-100) and/or color_temp_kelvin (2200-6500).
For color requests: provide a color name like 'blue', 'red', 'green', 'purple', 'pink', 'orange', 'cyan'.
For vibe requests: provide a vibe like 'cozy', 'focus', 'romantic', 'movie', 'energetic'.
For on/off: use action='on' or action='off'.

Examples:
- "turn on living room lights" -> action='on', room='living room'
- "dim the bedroom to 30%" -> action='set', room='bedroom', brightness=30
- "make kitchen cozy" -> action='set', room='kitchen', vibe='cozy'
- "turn living room to warm white" -> action='set', room='living room', color_temp_kelvin=2700
- "turn office to blue" -> action='set', room='office', color='blue'
- "make bedroom purple" -> action='set', room='bedroom', color='purple'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name: living room, bedroom, kitchen, office, upstairs, downstairs, garage, staircase",
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "set"],
                    "description": "on=turn on, off=turn off, set=adjust settings",
                },
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Brightness percentage (0-100)",
                },
                "color": {
                    "type": "string",
                    "description": "Color name: red, green, blue, yellow, orange, purple, pink, cyan, magenta, teal, lavender, coral, turquoise, gold, navy, indigo",
                },
                "color_temp_kelvin": {
                    "type": "integer",
                    "minimum": 2200,
                    "maximum": 6500,
                    "description": "Color temperature (white light): 2700=warm, 4000=neutral, 5000=cool, 6500=daylight. Do NOT use for colors like blue/red/green - use color parameter instead.",
                },
                "vibe": {
                    "type": "string",
                    "description": "Vibe preset: cozy, relaxed, focus, energetic, romantic, movie, reading, morning, evening, night",
                },
                "transition": {
                    "type": "number",
                    "description": "Transition time in seconds (default: 0.5)",
                },
            },
            "required": ["room", "action"],
        },
    },
    {
        "name": "get_light_status",
        "description": "Get the current status of lights in a room. Returns on/off state, brightness, and color temperature.",
        "input_schema": {
            "type": "object",
            "properties": {"room": {"type": "string", "description": "Room name to check"}},
            "required": ["room"],
        },
    },
    {
        "name": "activate_hue_scene",
        "description": """Activate a Philips Hue dynamic scene. Use this for requests like "arctic aurora", "tropical twilight", "under the sea", etc.

Dynamic scenes have colors that shift over time for ambient lighting. Set dynamic=true for movement.
Speed controls how fast colors change (0=slow, 100=fast). Default is 50.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room where the scene should be activated",
                },
                "scene_name": {
                    "type": "string",
                    "description": "Scene name like 'arctic_aurora', 'tropical_twilight', 'savanna_sunset'",
                },
                "dynamic": {
                    "type": "boolean",
                    "description": "Enable dynamic mode (colors shift over time)",
                    "default": True,
                },
                "speed": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Speed of color transitions (0-100)",
                    "default": 50,
                },
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Overall scene brightness",
                },
            },
            "required": ["room", "scene_name"],
        },
    },
    {
        "name": "list_available_rooms",
        "description": "List all rooms that can be controlled.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def set_room_ambiance(
    room: str,
    action: str,
    brightness: int | None = None,
    color: str | None = None,
    color_temp_kelvin: int | None = None,
    vibe: str | None = None,
    transition: float = 0.5,
) -> dict[str, Any]:
    """
    Set the ambiance of lights in a room.

    Args:
        room: Room name
        action: 'on', 'off', or 'set'
        brightness: Brightness percentage (0-100)
        color: Color name (e.g., 'blue', 'red', 'purple')
        color_temp_kelvin: Color temperature in Kelvin
        vibe: Vibe preset name
        transition: Transition time in seconds

    Returns:
        Result dictionary with success status and details
    """
    entity_id = get_room_entity(room)

    if not entity_id:
        available = list(ROOM_ENTITY_MAP.keys())
        return {"success": False, "error": f"Unknown room: {room}", "available_rooms": available}

    # Convert color name to RGB if specified
    rgb_color = None
    if color:
        color_lower = color.lower().strip()
        if color_lower in COLOR_NAME_TO_RGB:
            rgb_color = COLOR_NAME_TO_RGB[color_lower]
            logger.info(f"Converted color '{color}' to RGB: {rgb_color}")
        else:
            logger.warning(f"Unknown color '{color}', ignoring")

    # Apply vibe preset if specified
    if vibe:
        vibe_lower = vibe.lower()
        if vibe_lower in VIBE_PRESETS:
            preset = VIBE_PRESETS[vibe_lower]
            if brightness is None:
                brightness = preset.get("brightness")
            if color_temp_kelvin is None and rgb_color is None:
                color_temp_kelvin = preset.get("color_temp_kelvin")
            logger.info(
                f"Applied vibe '{vibe}': brightness={brightness}, color_temp={color_temp_kelvin}K"
            )
        else:
            logger.warning(f"Unknown vibe '{vibe}', using explicit settings")

    ha_client = get_ha_client()

    try:
        if action == "off":
            success = ha_client.turn_off_light(entity_id, transition=transition)
            return {"success": success, "action": "off", "room": room, "entity_id": entity_id}

        elif action in ("on", "set"):
            # Don't pass color_temp if we're using RGB color
            effective_color_temp = None if rgb_color else color_temp_kelvin

            success = ha_client.turn_on_light(
                entity_id=entity_id,
                brightness_pct=brightness,
                color_temp_kelvin=effective_color_temp,
                rgb_color=rgb_color,
                transition=transition,
            )

            result = {"success": success, "action": action, "room": room, "entity_id": entity_id}

            if brightness is not None:
                result["brightness"] = brightness
            if rgb_color is not None:
                result["color"] = color
                result["rgb_color"] = rgb_color
            if color_temp_kelvin is not None and rgb_color is None:
                result["color_temp_kelvin"] = color_temp_kelvin
            if vibe:
                result["vibe_applied"] = vibe

            return result

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as error:
        logger.error(f"Error setting room ambiance: {error}")
        return {"success": False, "error": str(error)}


def get_light_status(room: str) -> dict[str, Any]:
    """
    Get the current status of lights in a room.

    Args:
        room: Room name

    Returns:
        Status dictionary
    """
    entity_id = get_room_entity(room)

    if not entity_id:
        return {"success": False, "error": f"Unknown room: {room}"}

    ha_client = get_ha_client()
    state = ha_client.get_light_state(entity_id)

    if not state:
        return {"success": False, "error": f"Could not get state for {entity_id}", "room": room}

    # Convert brightness from 0-255 to 0-100 if present
    brightness_raw = state.get("brightness")
    brightness_pct = None
    if brightness_raw is not None:
        brightness_pct = round((brightness_raw / 255) * 100)

    # Convert mireds to Kelvin if present
    color_temp_mireds = state.get("color_temp")
    color_temp_kelvin = None
    if color_temp_mireds is not None:
        color_temp_kelvin = round(1000000 / color_temp_mireds)

    return {
        "success": True,
        "room": room,
        "entity_id": entity_id,
        "state": state.get("state"),
        "is_on": state.get("state") == "on",
        "brightness_pct": brightness_pct,
        "color_temp_kelvin": color_temp_kelvin,
        "rgb_color": state.get("rgb_color"),
        "friendly_name": state.get("friendly_name"),
    }


def activate_hue_scene(
    room: str, scene_name: str, dynamic: bool = True, speed: int = 50, brightness: int | None = None
) -> dict[str, Any]:
    """
    Activate a Philips Hue scene.

    Args:
        room: Room name
        scene_name: Scene name (e.g., 'arctic_aurora')
        dynamic: Enable dynamic mode
        speed: Color transition speed (0-100)
        brightness: Scene brightness

    Returns:
        Result dictionary
    """
    # Construct scene entity ID
    # Format: scene.{room}_{scene_name}
    room_normalized = room.lower().replace(" ", "_")
    scene_normalized = scene_name.lower().replace(" ", "_")
    scene_entity_id = f"scene.{room_normalized}_{scene_normalized}"

    logger.info(f"Activating Hue scene: {scene_entity_id} (dynamic={dynamic}, speed={speed})")

    ha_client = get_ha_client()

    try:
        success = ha_client.activate_hue_scene(
            scene_entity_id=scene_entity_id, dynamic=dynamic, speed=speed, brightness=brightness
        )

        return {
            "success": success,
            "scene": scene_name,
            "room": room,
            "scene_entity_id": scene_entity_id,
            "dynamic": dynamic,
            "speed": speed,
            "brightness": brightness,
        }

    except Exception as error:
        logger.error(f"Error activating Hue scene: {error}")
        return {"success": False, "error": str(error), "scene_entity_id": scene_entity_id}


def list_available_rooms() -> dict[str, Any]:
    """List all available rooms."""
    rooms = []
    for room_key, room_config in ROOM_ENTITY_MAP.items():
        rooms.append(
            {
                "name": room_key.replace("_", " "),
                "entity_id": room_config.get("default_light"),
                "light_count": len(room_config.get("lights", [])),
            }
        )

    return {"success": True, "rooms": rooms, "count": len(rooms)}


def execute_light_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a light tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing light tool: {tool_name}")

    if tool_name == "set_room_ambiance":
        return set_room_ambiance(
            room=tool_input.get("room", ""),
            action=tool_input.get("action", "on"),
            brightness=tool_input.get("brightness"),
            color=tool_input.get("color"),
            color_temp_kelvin=tool_input.get("color_temp_kelvin"),
            vibe=tool_input.get("vibe"),
            transition=tool_input.get("transition", 0.5),
        )

    elif tool_name == "get_light_status":
        return get_light_status(room=tool_input.get("room", ""))

    elif tool_name == "activate_hue_scene":
        return activate_hue_scene(
            room=tool_input.get("room", ""),
            scene_name=tool_input.get("scene_name", ""),
            dynamic=tool_input.get("dynamic", True),
            speed=tool_input.get("speed", 50),
            brightness=tool_input.get("brightness"),
        )

    elif tool_name == "list_available_rooms":
        return list_available_rooms()

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
