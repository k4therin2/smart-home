"""
Device Sync Integration Tests

Tests device synchronization between Home Assistant and local database.
Follows integration testing philosophy: tests real interactions, mocks only at boundaries.

Test Strategy:
- Mock Home Assistant API responses (external boundary)
- Use in-memory database (real database operations)
- Test actual device_sync.py logic
- Test capability extraction, room inference, sync statistics
"""

import json
import pytest
import responses

from src.device_sync import (
    sync_devices_from_ha,
    extract_device_info,
    extract_capabilities,
    infer_room_from_entity,
    sync_single_device,
    remove_stale_devices,
    get_device_summary,
)
from src.database import get_all_devices, get_device
from src.homeassistant import HomeAssistantClient


# =============================================================================
# Full Device Sync Tests
# =============================================================================

def test_sync_devices_from_ha(mock_ha_api, test_db):
    """Test syncing all devices from Home Assistant to local database."""
    # Create sample HA states
    ha_states = [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Light",
                "brightness": 255,
                "color_temp": 370,
                "supported_color_modes": ["color_temp"],
            },
        },
        {
            "entity_id": "switch.office_fan",
            "state": "off",
            "attributes": {
                "friendly_name": "Office Fan",
            },
        },
        {
            "entity_id": "climate.bedroom",
            "state": "heat",
            "attributes": {
                "friendly_name": "Bedroom Thermostat",
                "temperature": 22,
                "hvac_modes": ["heat", "cool", "auto", "off"],
            },
        },
    ]

    # Mock HA API get_states response
    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    # Create client and sync
    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    stats = sync_devices_from_ha(client=client)

    # Verify statistics
    assert stats["total_discovered"] == 3
    assert stats["new_devices"] == 3
    assert stats["updated_devices"] == 0
    assert stats["by_domain"]["light"] == 1
    assert stats["by_domain"]["switch"] == 1
    assert stats["by_domain"]["climate"] == 1

    # Verify devices were registered
    devices = get_all_devices()
    assert len(devices) == 3

    # Check light device
    light = get_device("light.living_room")
    assert light is not None
    assert light["friendly_name"] == "Living Room Light"
    assert light["device_type"] == "light"
    assert light["room"] == "living_room"  # Inferred from entity_id


def test_new_device_detection(mock_ha_api, test_db):
    """Test that new devices are correctly identified and counted."""
    from src.database import register_device

    # Pre-register one device
    register_device(
        entity_id="light.existing",
        device_type="light",
        friendly_name="Existing Light",
        room="bedroom",
    )

    # Mock HA response with existing + new devices
    ha_states = [
        {
            "entity_id": "light.existing",
            "state": "on",
            "attributes": {"friendly_name": "Existing Light"},
        },
        {
            "entity_id": "light.new_device",
            "state": "off",
            "attributes": {"friendly_name": "New Device"},
        },
    ]

    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    stats = sync_devices_from_ha(client=client)

    # Should detect 1 new, 1 updated
    assert stats["total_discovered"] == 2
    assert stats["new_devices"] == 1
    assert stats["updated_devices"] == 1


def test_updated_device_detection(mock_ha_api, test_db):
    """Test that existing devices are updated when synced again."""
    from src.database import register_device

    # Pre-register device with old info
    register_device(
        entity_id="light.living_room",
        device_type="light",
        friendly_name="Old Name",
        room="bedroom",
    )

    # Mock HA response with updated device
    ha_states = [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "New Name",
                "brightness": 200,
            },
        },
    ]

    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    stats = sync_devices_from_ha(client=client)

    # Should be counted as updated
    assert stats["new_devices"] == 0
    assert stats["updated_devices"] == 1

    # Verify update
    device = get_device("light.living_room")
    assert device["friendly_name"] == "New Name"


def test_sync_statistics(mock_ha_api, test_db):
    """Test that sync statistics are accurately tracked."""
    ha_states = [
        {"entity_id": "light.room1", "state": "on", "attributes": {"friendly_name": "Room 1"}},
        {"entity_id": "light.room2", "state": "on", "attributes": {"friendly_name": "Room 2"}},
        {"entity_id": "switch.device1", "state": "off", "attributes": {"friendly_name": "Device 1"}},
        {"entity_id": "sensor.temp", "state": "22", "attributes": {"friendly_name": "Temperature"}},
        {"entity_id": "binary_sensor.motion", "state": "off", "attributes": {"friendly_name": "Motion"}},
    ]

    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    stats = sync_devices_from_ha(client=client)

    assert stats["total_discovered"] == 5
    assert stats["by_domain"]["light"] == 2
    assert stats["by_domain"]["switch"] == 1
    assert stats["by_domain"]["sensor"] == 1
    assert stats["by_domain"]["binary_sensor"] == 1


def test_domain_filtering(mock_ha_api, test_db):
    """Test that domain filtering correctly limits which entities are synced."""
    ha_states = [
        {"entity_id": "light.room1", "state": "on", "attributes": {"friendly_name": "Light 1"}},
        {"entity_id": "switch.device1", "state": "off", "attributes": {"friendly_name": "Switch 1"}},
        {"entity_id": "automation.test", "state": "on", "attributes": {"friendly_name": "Automation"}},
    ]

    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )

    # Sync only lights
    stats = sync_devices_from_ha(client=client, domains=["light"])

    assert stats["total_discovered"] == 1
    assert stats["by_domain"]["light"] == 1
    assert "switch" not in stats["by_domain"]

    # Verify only light was registered
    devices = get_all_devices()
    assert len(devices) == 1
    assert devices[0]["entity_id"] == "light.room1"


# =============================================================================
# Capability Extraction Tests
# =============================================================================

def test_capability_extraction_light():
    """Test capability extraction for light entities."""
    # Light with brightness and color temp
    capabilities = extract_capabilities("light", {
        "brightness": 200,
        "color_temp": 370,
    })
    assert "brightness" in capabilities
    assert "color_temp" in capabilities

    # Light with RGB color
    capabilities = extract_capabilities("light", {
        "rgb_color": [255, 128, 64],
    })
    assert "color" in capabilities

    # Light with effects
    capabilities = extract_capabilities("light", {
        "effect_list": ["colorloop", "random"],
    })
    assert "effects" in capabilities

    # Basic light with no special features
    capabilities = extract_capabilities("light", {})
    # Should still work, just no special capabilities
    assert isinstance(capabilities, list)


def test_capability_extraction_climate():
    """Test capability extraction for climate/thermostat entities."""
    capabilities = extract_capabilities("climate", {
        "temperature": 22,
        "hvac_modes": ["heat", "cool", "auto", "off"],
        "fan_modes": ["auto", "low", "medium", "high"],
    })

    assert "temperature" in capabilities
    assert "heat" in capabilities
    assert "cool" in capabilities
    assert "auto" in capabilities
    assert "off" in capabilities
    assert "fan_control" in capabilities


def test_capability_extraction_media_player():
    """Test capability extraction for media player entities."""
    # Media player with various features
    # Bits: pause=1, seek=2, volume=4, mute=8
    capabilities = extract_capabilities("media_player", {
        "supported_features": 15,  # All features: 1+2+4+8
    })

    assert "pause" in capabilities
    assert "seek" in capabilities
    assert "volume" in capabilities
    assert "mute" in capabilities

    # Media player with only volume
    capabilities = extract_capabilities("media_player", {
        "supported_features": 4,  # Only volume
    })

    assert "volume" in capabilities
    assert "pause" not in capabilities


# =============================================================================
# Room Inference Tests
# =============================================================================

def test_room_inference_from_entity_id():
    """Test room inference from entity ID patterns."""
    # Test various patterns
    assert infer_room_from_entity("light.living_room", None) == "living_room"
    assert infer_room_from_entity("switch.bedroom_fan", None) == "bedroom"
    assert infer_room_from_entity("climate.kitchen_thermostat", None) == "kitchen"
    assert infer_room_from_entity("sensor.bathroom_humidity", None) == "bathroom"
    assert infer_room_from_entity("light.office_desk", None) == "office"

    # Test with spaces converted to underscores
    assert infer_room_from_entity("light.dining_room_chandelier", None) == "dining_room"

    # No room pattern
    assert infer_room_from_entity("light.lamp_1", None) is None


def test_room_inference_from_friendly_name():
    """Test room inference from friendly name when entity_id doesn't match."""
    # Entity ID has no room, but friendly name does
    assert infer_room_from_entity(
        "light.hue_lamp_1",
        "Living Room Lamp"
    ) == "living_room"

    assert infer_room_from_entity(
        "switch.plug_1",
        "Bedroom Fan"
    ) == "bedroom"

    assert infer_room_from_entity(
        "sensor.temp_sensor_1",
        "Kitchen Temperature"
    ) == "kitchen"

    # Neither has room pattern
    assert infer_room_from_entity("light.lamp_1", "Main Lamp") is None


# =============================================================================
# Stale Device Removal Tests
# =============================================================================

def test_remove_stale_devices(mock_ha_api, test_db):
    """Test removal of devices that no longer exist in Home Assistant."""
    from src.database import register_device

    # Register some local devices
    register_device(
        entity_id="light.still_exists",
        device_type="light",
        friendly_name="Still Here",
    )
    register_device(
        entity_id="light.removed_device",
        device_type="light",
        friendly_name="Was Removed",
    )

    # Mock HA response - only one device exists now
    ha_states = [
        {
            "entity_id": "light.still_exists",
            "state": "on",
            "attributes": {"friendly_name": "Still Here"},
        },
    ]

    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=ha_states,
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    removed = remove_stale_devices(client=client)

    # Should have removed the stale device
    assert len(removed) == 1
    assert "light.removed_device" in removed

    # Verify it's gone from database
    devices = get_all_devices()
    assert len(devices) == 1
    assert devices[0]["entity_id"] == "light.still_exists"


# =============================================================================
# Single Device Sync Tests
# =============================================================================

def test_sync_single_device(mock_ha_api, test_db):
    """Test syncing a single device from Home Assistant."""
    # Mock HA response for single device
    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states/light.bedroom",
        json={
            "entity_id": "light.bedroom",
            "state": "on",
            "attributes": {
                "friendly_name": "Bedroom Light",
                "brightness": 180,
                "color_temp": 400,
            },
        },
        status=200,
    )

    client = HomeAssistantClient(
        base_url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    device_info = sync_single_device("light.bedroom", client=client)

    # Verify return value
    assert device_info is not None
    assert device_info["entity_id"] == "light.bedroom"
    assert device_info["friendly_name"] == "Bedroom Light"
    assert device_info["room"] == "bedroom"

    # Verify it was registered
    device = get_device("light.bedroom")
    assert device is not None
    assert device["friendly_name"] == "Bedroom Light"


# =============================================================================
# Device Summary Tests
# =============================================================================

def test_get_device_summary(test_db):
    """Test getting a summary of registered devices."""
    from src.database import register_device

    # Register various devices
    register_device(
        entity_id="light.living_room_1",
        device_type="light",
        room="living_room",
    )
    register_device(
        entity_id="light.living_room_2",
        device_type="light",
        room="living_room",
    )
    register_device(
        entity_id="light.bedroom",
        device_type="light",
        room="bedroom",
    )
    register_device(
        entity_id="switch.kitchen_fan",
        device_type="switch",
        room="kitchen",
    )
    register_device(
        entity_id="sensor.outdoor_temp",
        device_type="sensor",
        room=None,  # No room
    )

    summary = get_device_summary()

    # Check total
    assert summary["total"] == 5

    # Check by type
    assert summary["by_type"]["light"] == 3
    assert summary["by_type"]["switch"] == 1
    assert summary["by_type"]["sensor"] == 1

    # Check by room
    assert summary["by_room"]["living_room"] == 2
    assert summary["by_room"]["bedroom"] == 1
    assert summary["by_room"]["kitchen"] == 1
    assert summary["by_room"]["unassigned"] == 1


# =============================================================================
# Device Info Extraction Tests
# =============================================================================

def test_extract_device_info_basic():
    """Test basic device info extraction from entity state."""
    state = {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room Light",
            "manufacturer": "Philips",
            "model": "Hue White A19",
            "brightness": 255,
            "color_temp": 370,
        },
    }

    info = extract_device_info(state)

    assert info["entity_id"] == "light.living_room"
    assert info["device_type"] == "light"
    assert info["friendly_name"] == "Living Room Light"
    assert info["manufacturer"] == "Philips"
    assert info["model"] == "Hue White A19"
    assert "brightness" in info["capabilities"]
    assert "color_temp" in info["capabilities"]


def test_extract_device_info_metadata():
    """Test that metadata is properly extracted."""
    state = {
        "entity_id": "sensor.temperature",
        "state": "22",
        "attributes": {
            "friendly_name": "Temperature Sensor",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "supported_features": 0,
        },
    }

    info = extract_device_info(state)

    assert info["metadata"]["device_class"] == "temperature"
    assert info["metadata"]["unit_of_measurement"] == "°C"
    assert info["metadata"]["supported_features"] == 0
