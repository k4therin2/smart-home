"""
Smart Home Assistant - Effects Module

High-level effect handling that coordinates between basic light controls
and the Hue specialist for abstract vibe requests.
"""

from typing import Any

from src.config import VIBE_PRESETS, get_room_entity, ROOM_ENTITY_MAP
from src.ha_client import get_ha_client
from src.utils import setup_logging
from tools.hue_specialist import interpret_vibe_request, HUE_SCENE_MAPPINGS

logger = setup_logging("tools.effects")


def apply_vibe(
    room: str,
    vibe_description: str,
    transition: float = 1.0
) -> dict[str, Any]:
    """
    Apply a vibe to a room based on an abstract description.

    This is the main entry point for abstract lighting requests like:
    - "make it cozy"
    - "set the mood for a movie"
    - "underwater vibes"
    - "like a campfire"

    Args:
        room: Room name
        vibe_description: Abstract vibe description
        transition: Transition time in seconds

    Returns:
        Result dictionary with success status and applied settings
    """
    entity_id = get_room_entity(room)
    if not entity_id:
        return {
            "success": False,
            "error": f"Unknown room: {room}",
            "available_rooms": list(ROOM_ENTITY_MAP.keys())
        }

    # Interpret the vibe description
    settings = interpret_vibe_request(vibe_description, room=room)

    logger.info(f"Applying vibe '{vibe_description}' to {room}: {settings}")

    ha_client = get_ha_client()

    try:
        if settings.get("type") == "scene":
            # Apply Hue scene
            room_normalized = room.lower().replace(" ", "_")
            scene_name = settings.get("scene_name", "")
            scene_entity_id = f"scene.{room_normalized}_{scene_name}"

            success = ha_client.activate_hue_scene(
                scene_entity_id=scene_entity_id,
                dynamic=settings.get("dynamic", True),
                speed=settings.get("speed", 50),
                brightness=settings.get("brightness")
            )

            return {
                "success": success,
                "room": room,
                "vibe": vibe_description,
                "type": "scene",
                "scene_name": scene_name,
                "scene_entity_id": scene_entity_id,
                "dynamic": settings.get("dynamic"),
                "speed": settings.get("speed"),
                "brightness": settings.get("brightness"),
                "source": settings.get("source")
            }

        else:
            # Apply basic light settings
            brightness = settings.get("brightness")
            color_temp = settings.get("color_temp_kelvin")

            success = ha_client.turn_on_light(
                entity_id=entity_id,
                brightness_pct=brightness,
                color_temp_kelvin=color_temp,
                transition=transition
            )

            return {
                "success": success,
                "room": room,
                "entity_id": entity_id,
                "vibe": vibe_description,
                "type": "basic",
                "brightness": brightness,
                "color_temp_kelvin": color_temp,
                "source": settings.get("source")
            }

    except Exception as error:
        logger.error(f"Error applying vibe: {error}")
        return {
            "success": False,
            "error": str(error),
            "room": room,
            "vibe": vibe_description
        }


def get_vibe_preview(vibe_description: str) -> dict[str, Any]:
    """
    Preview what settings would be applied for a vibe without executing.

    Args:
        vibe_description: Abstract vibe description

    Returns:
        Preview of settings that would be applied
    """
    settings = interpret_vibe_request(vibe_description)

    preview = {
        "vibe": vibe_description,
        "type": settings.get("type"),
        "source": settings.get("source")
    }

    if settings.get("type") == "scene":
        preview["scene_name"] = settings.get("scene_name")
        preview["dynamic"] = settings.get("dynamic")
        preview["speed"] = settings.get("speed")
        preview["brightness"] = settings.get("brightness")
    else:
        preview["brightness"] = settings.get("brightness")
        preview["color_temp_kelvin"] = settings.get("color_temp_kelvin")

    return preview


def list_vibes() -> dict[str, Any]:
    """
    List all available vibes and their settings.

    Returns:
        Dictionary of available vibes and scenes
    """
    return {
        "preset_vibes": {
            name: {
                "brightness": settings["brightness"],
                "color_temp_kelvin": settings["color_temp_kelvin"]
            }
            for name, settings in VIBE_PRESETS.items()
        },
        "scene_keywords": list(HUE_SCENE_MAPPINGS.keys()),
        "examples": [
            "cozy",
            "romantic",
            "focus",
            "movie",
            "under the sea",
            "northern lights",
            "fire",
            "party"
        ]
    }


def create_light_sequence(
    room: str,
    sequence: list[dict[str, Any]],
    loop: bool = False
) -> dict[str, Any]:
    """
    Create a sequence of light changes (for future implementation).

    This is a placeholder for future functionality where we could
    create custom light sequences/animations.

    Args:
        room: Room name
        sequence: List of settings to apply in order
        loop: Whether to loop the sequence

    Returns:
        Result dictionary
    """
    # Future implementation
    return {
        "success": False,
        "error": "Light sequences not yet implemented",
        "note": "This feature is planned for future development"
    }
