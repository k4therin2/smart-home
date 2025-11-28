"""
Philips Hue lighting control via Home Assistant API
"""

import os
import requests
from typing import Optional


def kelvin_to_mireds(kelvin: int) -> int:
    """
    Convert color temperature from Kelvin to mireds (used by Hue lights).

    Args:
        kelvin: Color temperature in Kelvin (2000-6500)

    Returns:
        Color temperature in mireds
    """
    return round(1000000 / kelvin)


def set_room_ambiance(
    room: str,
    color_temp_kelvin: int,
    brightness_pct: int,
    description: Optional[str] = None
) -> dict:
    """
    Set lighting ambiance for a room based on mood/description.

    Args:
        room: Room name (e.g., 'living_room', 'bedroom')
        color_temp_kelvin: Color temperature in Kelvin (2000-6500)
        brightness_pct: Brightness percentage (0-100)
        description: What this ambiance represents (e.g., 'fire', 'ocean')

    Returns:
        Dictionary with status and response details
    """
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    ha_token = os.getenv("HA_TOKEN")

    if not ha_token:
        return {
            "success": False,
            "error": "HA_TOKEN not set in environment variables"
        }

    # Convert kelvin to mireds for Hue
    mireds = kelvin_to_mireds(color_temp_kelvin)

    # Clamp values to valid ranges
    mireds = max(153, min(500, mireds))  # Hue range: ~2000K-6500K
    brightness_pct = max(0, min(100, brightness_pct))

    # Map room names to Home Assistant entity IDs
    # TODO: Make this dynamic by querying HA for lights in an area
    room_entity_map = {
        "living_room": "light.living_room",
        "bedroom": "light.bedroom",
        "kitchen": "light.kitchen",
        "office": "light.office",
    }

    entity_id = room_entity_map.get(room.lower().replace(" ", "_"))

    if not entity_id:
        return {
            "success": False,
            "error": f"Unknown room: {room}. Available rooms: {', '.join(room_entity_map.keys())}"
        }

    # Prepare the API call to Home Assistant
    url = f"{ha_url}/api/services/light/turn_on"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    data = {
        "entity_id": entity_id,
        "color_temp": mireds,
        "brightness_pct": brightness_pct
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()

        return {
            "success": True,
            "room": room,
            "entity_id": entity_id,
            "color_temp_kelvin": color_temp_kelvin,
            "color_temp_mireds": mireds,
            "brightness_pct": brightness_pct,
            "description": description or "custom",
            "message": f"Set {room} to {description or 'ambiance'}: {color_temp_kelvin}K, {brightness_pct}% brightness"
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to communicate with Home Assistant: {str(e)}"
        }


def get_available_rooms() -> dict:
    """
    Query Home Assistant for available lights/rooms.

    Returns:
        Dictionary with available rooms and their entity IDs
    """
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    ha_token = os.getenv("HA_TOKEN")

    if not ha_token:
        return {
            "success": False,
            "error": "HA_TOKEN not set in environment variables"
        }

    url = f"{ha_url}/api/states"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Filter for light entities
        states = response.json()
        lights = [
            {
                "entity_id": entity["entity_id"],
                "name": entity.get("attributes", {}).get("friendly_name", entity["entity_id"]),
                "state": entity["state"]
            }
            for entity in states
            if entity["entity_id"].startswith("light.")
        ]

        return {
            "success": True,
            "lights": lights,
            "count": len(lights)
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to query Home Assistant: {str(e)}"
        }


def apply_fire_flicker(room: str, duration_seconds: int = 15) -> dict:
    """
    Apply a realistic fire flickering effect to a room.

    This function consults a specialist Hue agent to plan the flicker sequence,
    then executes it asynchronously.

    Args:
        room: Room name (e.g., 'living_room')
        duration_seconds: How long the flicker effect should run (default 15s)

    Returns:
        Dictionary with status and flicker plan details
    """
    import time
    import threading
    from .hue_specialist import get_hue_specialist

    # Get the specialist agent to plan the effect
    specialist = get_hue_specialist()

    try:
        flicker_plan = specialist.plan_fire_flicker(room, duration_seconds)

        if not flicker_plan:
            return {
                "success": False,
                "error": "Specialist agent failed to create flicker plan"
            }

        # Execute flicker plan in background thread
        def execute_flicker():
            """Execute the flicker sequence."""
            for step in flicker_plan:
                time.sleep(step.get("delay_seconds", 0))

                # Call set_room_ambiance with this step's parameters
                set_room_ambiance(
                    room=room,
                    color_temp_kelvin=step["color_temp_kelvin"],
                    brightness_pct=step["brightness_pct"],
                    description=f"fire_flicker_step"
                )

        # Start flicker in background
        flicker_thread = threading.Thread(target=execute_flicker, daemon=True)
        flicker_thread.start()

        return {
            "success": True,
            "room": room,
            "duration_seconds": duration_seconds,
            "num_steps": len(flicker_plan),
            "message": f"Started fire flicker effect in {room} ({len(flicker_plan)} steps over {duration_seconds}s)",
            "flicker_plan": flicker_plan
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to apply fire flicker: {str(e)}"
        }
