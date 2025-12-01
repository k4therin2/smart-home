"""
Advanced lighting effects using Hue scenes and dynamic modes.

This module provides efficient, looping effects using Hue's built-in
capabilities rather than continuous API calls.
"""

import os
import requests
from typing import Optional, Dict, List
from config import ROOM_ENTITY_MAP


def get_hue_scenes(room: str) -> Dict:
    """
    Get available Hue scenes for a room.

    Args:
        room: Room name

    Returns:
        Dictionary with available scenes
    """
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    ha_token = os.getenv("HA_TOKEN")

    if not ha_token:
        return {"success": False, "error": "HA_TOKEN not set"}

    # Get entity ID from shared config
    entity_id = ROOM_ENTITY_MAP.get(room.lower().replace(" ", "_"))
    if not entity_id:
        return {"success": False, "error": f"Unknown room: {room}"}

    # Get room state to check available scenes
    url = f"{ha_url}/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {ha_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        scenes = data.get("attributes", {}).get("hue_scenes", [])

        return {
            "success": True,
            "room": room,
            "entity_id": entity_id,
            "available_scenes": scenes
        }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


def activate_dynamic_scene(
    room: str,
    scene_name: str,
    speed: Optional[int] = None,
    brightness_pct: Optional[int] = None
) -> Dict:
    """
    Activate a Hue scene with dynamic (looping) mode enabled.

    This uses the Hue bridge's built-in animation capabilities,
    so effects loop indefinitely WITHOUT continuous API calls.

    Args:
        room: Room name
        scene_name: Name of Hue scene (e.g., "Fire", "Nebula", "Arctic aurora")
        speed: Animation speed 0-100 (optional)
        brightness_pct: Override brightness 0-100 (optional)

    Returns:
        Dictionary with activation status
    """
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    ha_token = os.getenv("HA_TOKEN")

    if not ha_token:
        return {"success": False, "error": "HA_TOKEN not set"}

    # Get entity ID from shared config
    entity_id = ROOM_ENTITY_MAP.get(room.lower().replace(" ", "_"))
    if not entity_id:
        return {"success": False, "error": f"Unknown room: {room}"}

    # First, get available scenes for this room
    scenes_result = get_hue_scenes(room)
    if not scenes_result.get("success"):
        return scenes_result

    available_scenes = scenes_result["available_scenes"]

    # Find matching scene (case-insensitive partial match)
    scene_name_lower = scene_name.lower()
    matched_scene = None

    for scene in available_scenes:
        if scene_name_lower in scene.lower() or scene.lower() in scene_name_lower:
            matched_scene = scene
            break

    if not matched_scene:
        return {
            "success": False,
            "error": f"Scene '{scene_name}' not found. Available: {', '.join(available_scenes)}"
        }

    # Find the scene entity (format: scene.<room>_<scene_name>)
    # We need to query for scene entities
    url = f"{ha_url}/api/states"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        states = response.json()

        # Find scene entity that matches
        scene_entity_id = None
        for state in states:
            if state["entity_id"].startswith("scene."):
                friendly_name = state.get("attributes", {}).get("friendly_name", "")
                if matched_scene.lower() in friendly_name.lower():
                    scene_entity_id = state["entity_id"]
                    break

        if not scene_entity_id:
            # Fallback: construct likely entity ID
            # Hue scenes are usually scene.<room>_<scene_name_normalized>
            scene_slug = matched_scene.lower().replace(" ", "_").replace("'", "")
            room_slug = room.lower().replace(" ", "_")
            scene_entity_id = f"scene.{room_slug}_{scene_slug}"

        # Activate the scene with dynamic mode
        service_url = f"{ha_url}/api/services/hue/activate_scene"
        payload = {
            "entity_id": scene_entity_id,
            "dynamic": True  # Enable looping animation!
        }

        if speed is not None:
            payload["speed"] = max(0, min(100, speed))

        if brightness_pct is not None:
            payload["brightness"] = max(0, min(100, brightness_pct))

        response = requests.post(service_url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        return {
            "success": True,
            "room": room,
            "scene": matched_scene,
            "scene_entity_id": scene_entity_id,
            "dynamic": True,
            "speed": speed,
            "brightness_pct": brightness_pct,
            "message": f"Activated dynamic '{matched_scene}' scene in {room} (loops indefinitely)"
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to activate scene: {str(e)}"
        }


def apply_abstract_effect(description: str, room: str) -> Dict:
    """
    Apply an effect based on abstract description (e.g., "under the sea", "swamp").

    This function:
    1. Consults specialist agent to map description → Hue scene
    2. Activates the scene with dynamic mode for looping effect

    Args:
        description: Abstract description of desired atmosphere
        room: Room name

    Returns:
        Dictionary with activation status
    """
    from .hue_specialist import get_hue_specialist

    # Get available scenes for this room
    scenes_result = get_hue_scenes(room)
    if not scenes_result.get("success"):
        return scenes_result

    available_scenes = scenes_result["available_scenes"]

    if not available_scenes:
        return {
            "success": False,
            "error": f"No Hue scenes found for {room}"
        }

    # Ask specialist agent for recommendation
    specialist = get_hue_specialist()
    recommendation = specialist.recommend_scene(
        user_description=description,
        available_scenes=available_scenes
    )

    if not recommendation.get("success"):
        return recommendation

    # Activate the recommended scene
    result = activate_dynamic_scene(
        room=room,
        scene_name=recommendation["scene"],
        speed=recommendation.get("speed"),
        brightness_pct=recommendation.get("brightness")  # Note: changed from brightness_pct to brightness
    )

    if result.get("success"):
        result["specialist_reasoning"] = recommendation.get("reasoning")
        result["description"] = description

    return result
