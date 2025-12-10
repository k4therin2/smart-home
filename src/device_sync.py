"""
Smart Home Assistant - Device Sync Utility

Synchronizes devices between Home Assistant and local registry.
Handles discovery, registration, and state tracking.
"""

from typing import Dict, List, Optional

from src.logging_config import get_logger, LogContext
from src.homeassistant import (
    HomeAssistantClient,
    HomeAssistantError,
    get_client,
)
from src.database import (
    register_device,
    get_all_devices,
    delete_device,
    record_device_state,
)

logger = get_logger(__name__)

# Device domains we care about
SUPPORTED_DOMAINS = [
    "light",
    "switch",
    "sensor",
    "binary_sensor",
    "climate",
    "cover",      # blinds, shades
    "vacuum",
    "media_player",
    "scene",
]


def extract_device_info(entity_state: dict) -> dict:
    """
    Extract device information from Home Assistant entity state.

    Args:
        entity_state: Entity state dict from HA API

    Returns:
        Dict with normalized device information
    """
    entity_id = entity_state.get("entity_id", "")
    attributes = entity_state.get("attributes", {})

    # Extract domain from entity_id (e.g., "light" from "light.living_room")
    domain = entity_id.split(".")[0] if "." in entity_id else "unknown"

    return {
        "entity_id": entity_id,
        "device_type": domain,
        "friendly_name": attributes.get("friendly_name"),
        "manufacturer": attributes.get("manufacturer"),
        "model": attributes.get("model"),
        "capabilities": extract_capabilities(domain, attributes),
        "metadata": {
            "supported_features": attributes.get("supported_features"),
            "device_class": attributes.get("device_class"),
            "unit_of_measurement": attributes.get("unit_of_measurement"),
        },
    }


def extract_capabilities(domain: str, attributes: dict) -> list[str]:
    """
    Extract device capabilities based on domain and attributes.

    Args:
        domain: Entity domain
        attributes: Entity attributes

    Returns:
        List of capability strings
    """
    capabilities = []

    if domain == "light":
        if "brightness" in attributes or attributes.get("supported_features", 0) & 1:
            capabilities.append("brightness")
        if "color_temp" in attributes or "color_temp_kelvin" in attributes:
            capabilities.append("color_temp")
        if "rgb_color" in attributes or "hs_color" in attributes:
            capabilities.append("color")
        if "effect_list" in attributes:
            capabilities.append("effects")

    elif domain == "climate":
        if "temperature" in attributes:
            capabilities.append("temperature")
        if "hvac_modes" in attributes:
            capabilities.extend(attributes.get("hvac_modes", []))
        if "fan_modes" in attributes:
            capabilities.append("fan_control")

    elif domain == "cover":
        if attributes.get("supported_features", 0) & 4:
            capabilities.append("position")
        if attributes.get("supported_features", 0) & 16:
            capabilities.append("tilt")

    elif domain == "vacuum":
        capabilities.extend(["start", "stop", "return_home"])
        if attributes.get("fan_speed_list"):
            capabilities.append("fan_speed")

    elif domain == "media_player":
        features = attributes.get("supported_features", 0)
        if features & 1:
            capabilities.append("pause")
        if features & 2:
            capabilities.append("seek")
        if features & 4:
            capabilities.append("volume")
        if features & 8:
            capabilities.append("mute")

    return capabilities


def infer_room_from_entity(entity_id: str, friendly_name: Optional[str]) -> Optional[str]:
    """
    Attempt to infer room from entity ID or friendly name.

    Args:
        entity_id: Entity ID string
        friendly_name: Friendly name if available

    Returns:
        Inferred room name or None
    """
    # Common room patterns
    room_patterns = [
        "living_room", "living room", "lounge",
        "bedroom", "bed room", "master",
        "kitchen",
        "bathroom", "bath room", "restroom",
        "office", "study",
        "dining", "dining_room",
        "garage",
        "basement",
        "hallway", "hall",
        "porch", "patio",
        "guest",
    ]

    # Check entity_id
    entity_lower = entity_id.lower()
    for room in room_patterns:
        if room.replace(" ", "_") in entity_lower or room.replace("_", " ") in entity_lower:
            return room.replace(" ", "_")

    # Check friendly name
    if friendly_name:
        name_lower = friendly_name.lower()
        for room in room_patterns:
            if room in name_lower:
                return room.replace(" ", "_")

    return None


def sync_devices_from_ha(
    client: Optional[HomeAssistantClient] = None,
    domains: Optional[List[str]] = None,
    infer_rooms: bool = True,
) -> Dict:
    """
    Sync devices from Home Assistant to local registry.

    Args:
        client: HA client (uses default if not provided)
        domains: List of domains to sync (defaults to SUPPORTED_DOMAINS)
        infer_rooms: Attempt to infer room from entity names

    Returns:
        Dict with sync statistics
    """
    if client is None:
        client = get_client()

    if domains is None:
        domains = SUPPORTED_DOMAINS

    stats = {
        "total_discovered": 0,
        "new_devices": 0,
        "updated_devices": 0,
        "by_domain": {},
    }

    with LogContext(logger, "Syncing devices from Home Assistant"):
        try:
            all_states = client.get_states()
        except HomeAssistantError as error:
            logger.error(f"Failed to fetch states from HA: {error}")
            raise

        # Get existing devices for comparison
        existing_entities = {device["entity_id"] for device in get_all_devices()}

        for state in all_states:
            entity_id = state.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else None

            if domain not in domains:
                continue

            stats["total_discovered"] += 1
            stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

            # Extract device info
            device_info = extract_device_info(state)

            # Infer room if requested
            if infer_rooms and not device_info.get("room"):
                device_info["room"] = infer_room_from_entity(
                    entity_id,
                    device_info.get("friendly_name")
                )

            # Register device
            is_new = entity_id not in existing_entities
            register_device(**device_info)

            if is_new:
                stats["new_devices"] += 1
                logger.debug(f"Registered new device: {entity_id}")
            else:
                stats["updated_devices"] += 1

            # Record current state
            record_device_state(
                entity_id=entity_id,
                state=state.get("state", "unknown"),
                attributes=state.get("attributes"),
            )

    logger.info(
        f"Device sync complete: {stats['total_discovered']} discovered, "
        f"{stats['new_devices']} new, {stats['updated_devices']} updated"
    )

    return stats


def sync_single_device(entity_id: str, client: Optional[HomeAssistantClient] = None) -> Optional[Dict]:
    """
    Sync a single device from Home Assistant.

    Args:
        entity_id: Entity ID to sync
        client: HA client (uses default if not provided)

    Returns:
        Device info dict or None if not found
    """
    if client is None:
        client = get_client()

    try:
        state = client.get_state(entity_id)
    except HomeAssistantError as error:
        logger.error(f"Failed to fetch state for {entity_id}: {error}")
        return None

    device_info = extract_device_info(state)
    device_info["room"] = infer_room_from_entity(
        entity_id,
        device_info.get("friendly_name")
    )

    register_device(**device_info)

    record_device_state(
        entity_id=entity_id,
        state=state.get("state", "unknown"),
        attributes=state.get("attributes"),
    )

    logger.info(f"Synced device: {entity_id}")
    return device_info


def remove_stale_devices(client: Optional[HomeAssistantClient] = None) -> List[str]:
    """
    Remove devices from local registry that no longer exist in HA.

    Args:
        client: HA client (uses default if not provided)

    Returns:
        List of removed entity IDs
    """
    if client is None:
        client = get_client()

    try:
        ha_states = client.get_states()
    except HomeAssistantError as error:
        logger.error(f"Failed to fetch states for stale device check: {error}")
        return []

    ha_entities = {state.get("entity_id") for state in ha_states}
    local_devices = get_all_devices()

    removed = []
    for device in local_devices:
        entity_id = device["entity_id"]
        if entity_id not in ha_entities:
            delete_device(entity_id)
            removed.append(entity_id)
            logger.info(f"Removed stale device: {entity_id}")

    return removed


def get_device_summary() -> dict:
    """
    Get a summary of devices in the local registry.

    Returns:
        Dict with device counts by type and room
    """
    devices = get_all_devices()

    summary = {
        "total": len(devices),
        "by_type": {},
        "by_room": {},
    }

    for device in devices:
        device_type = device.get("device_type", "unknown")
        room = device.get("room", "unassigned")

        summary["by_type"][device_type] = summary["by_type"].get(device_type, 0) + 1
        summary["by_room"][room] = summary["by_room"].get(room, 0) + 1

    return summary
