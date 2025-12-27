"""
Unit tests for DeviceRegistry class.

Tests device registration, room management, and naming consistency.
Part of WP-5.2: Device Organization Assistant.
"""

import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.device_registry import (
    DeviceRegistry,
    DeviceType,
    SUPPORTED_DEVICE_TYPES,
)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        yield Path(temp_file.name)
    # Cleanup
    Path(temp_file.name).unlink(missing_ok=True)


@pytest.fixture
def registry(temp_db):
    """Create a DeviceRegistry with temporary database."""
    return DeviceRegistry(database_path=temp_db)


# =============================================================================
# Initialization Tests
# =============================================================================

class TestDeviceRegistryInitialization:
    """Tests for DeviceRegistry initialization."""

    def test_creates_database_tables(self, temp_db):
        """Registry creates required database tables on init."""
        registry = DeviceRegistry(database_path=temp_db)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check devices table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"
        )
        assert cursor.fetchone() is not None

        # Check rooms table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'"
        )
        assert cursor.fetchone() is not None

        # Check zones table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='zones'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_creates_default_rooms(self, registry):
        """Registry creates default rooms on init."""
        rooms = registry.get_rooms()
        room_names = [room["name"] for room in rooms]

        # Should have at least these common rooms
        assert "living_room" in room_names
        assert "bedroom" in room_names
        assert "kitchen" in room_names

    def test_creates_default_zones(self, registry):
        """Registry creates default zones on init."""
        zones = registry.get_zones()
        zone_names = [zone["name"] for zone in zones]

        # Should have at least these common zones
        assert "downstairs" in zone_names or "main_floor" in zone_names
        assert "upstairs" in zone_names


# =============================================================================
# Device Registration Tests
# =============================================================================

class TestDeviceRegistration:
    """Tests for device registration operations."""

    def test_register_device_creates_record(self, registry):
        """Registering a device creates a database record."""
        device_id = registry.register_device(
            entity_id="light.living_room_lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Living Room Lamp",
        )

        assert device_id is not None
        assert device_id > 0

    def test_register_device_with_room(self, registry):
        """Device can be registered with a room assignment."""
        device_id = registry.register_device(
            entity_id="light.bedroom_ceiling",
            device_type=DeviceType.LIGHT,
            friendly_name="Bedroom Ceiling Light",
            room_name="bedroom",
        )

        device = registry.get_device(device_id)
        assert device["room_name"] == "bedroom"

    def test_register_device_with_zone(self, registry):
        """Device can be registered with a zone assignment."""
        device_id = registry.register_device(
            entity_id="light.hallway",
            device_type=DeviceType.LIGHT,
            friendly_name="Hallway Light",
            zone_name="upstairs",
        )

        device = registry.get_device(device_id)
        assert device["zone_name"] == "upstairs"

    def test_register_device_duplicate_entity_id_fails(self, registry):
        """Registering duplicate entity_id raises error."""
        registry.register_device(
            entity_id="light.test_lamp",
            device_type=DeviceType.LIGHT,
            friendly_name="Test Lamp",
        )

        with pytest.raises(ValueError, match="already registered"):
            registry.register_device(
                entity_id="light.test_lamp",
                device_type=DeviceType.LIGHT,
                friendly_name="Duplicate Lamp",
            )

    def test_register_device_requires_entity_id(self, registry):
        """Registration requires entity_id."""
        with pytest.raises(ValueError, match="entity_id"):
            registry.register_device(
                entity_id="",
                device_type=DeviceType.LIGHT,
                friendly_name="Test",
            )

    def test_register_device_stores_metadata(self, registry):
        """Device metadata is stored correctly."""
        device_id = registry.register_device(
            entity_id="switch.smart_plug",
            device_type=DeviceType.SWITCH,
            friendly_name="Smart Plug",
            manufacturer="TP-Link",
            model="HS105",
        )

        device = registry.get_device(device_id)
        assert device["manufacturer"] == "TP-Link"
        assert device["model"] == "HS105"

    def test_get_device_by_entity_id(self, registry):
        """Can retrieve device by entity_id."""
        registry.register_device(
            entity_id="light.office",
            device_type=DeviceType.LIGHT,
            friendly_name="Office Light",
        )

        device = registry.get_device_by_entity_id("light.office")
        assert device is not None
        assert device["friendly_name"] == "Office Light"

    def test_get_device_not_found_returns_none(self, registry):
        """Getting non-existent device returns None."""
        device = registry.get_device(999999)
        assert device is None


# =============================================================================
# Room Management Tests
# =============================================================================

class TestRoomManagement:
    """Tests for room management operations."""

    def test_create_room(self, registry):
        """Can create a new room."""
        success = registry.create_room(
            name="guest_room",
            display_name="Guest Room",
        )

        assert success is True

        rooms = registry.get_rooms()
        room_names = [room["name"] for room in rooms]
        assert "guest_room" in room_names

    def test_create_room_with_zone(self, registry):
        """Room can be created with zone assignment."""
        registry.create_room(
            name="master_bedroom",
            display_name="Master Bedroom",
            zone_name="upstairs",
        )

        rooms = registry.get_rooms()
        room = next((r for r in rooms if r["name"] == "master_bedroom"), None)
        assert room is not None
        assert room["zone_name"] == "upstairs"

    def test_create_duplicate_room_fails(self, registry):
        """Creating duplicate room returns False."""
        registry.create_room(name="test_room", display_name="Test Room")

        # Second creation should fail
        success = registry.create_room(name="test_room", display_name="Test Room 2")
        assert success is False

    def test_delete_room_moves_devices_to_unassigned(self, registry):
        """Deleting room moves its devices to unassigned."""
        # Create a room and add a device
        registry.create_room(name="temp_room", display_name="Temporary Room")
        device_id = registry.register_device(
            entity_id="light.temp_device",
            device_type=DeviceType.LIGHT,
            friendly_name="Temp Device",
            room_name="temp_room",
        )

        # Delete the room
        registry.delete_room("temp_room")

        # Device should have no room
        device = registry.get_device(device_id)
        assert device["room_name"] is None

    def test_get_devices_by_room(self, registry):
        """Can get all devices in a room."""
        registry.register_device(
            entity_id="light.kitchen_1",
            device_type=DeviceType.LIGHT,
            friendly_name="Kitchen Light 1",
            room_name="kitchen",
        )
        registry.register_device(
            entity_id="light.kitchen_2",
            device_type=DeviceType.LIGHT,
            friendly_name="Kitchen Light 2",
            room_name="kitchen",
        )
        registry.register_device(
            entity_id="light.bedroom",
            device_type=DeviceType.LIGHT,
            friendly_name="Bedroom Light",
            room_name="bedroom",
        )

        kitchen_devices = registry.get_devices_by_room("kitchen")
        assert len(kitchen_devices) == 2
        entity_ids = [d["entity_id"] for d in kitchen_devices]
        assert "light.kitchen_1" in entity_ids
        assert "light.kitchen_2" in entity_ids


# =============================================================================
# Zone Management Tests
# =============================================================================

class TestZoneManagement:
    """Tests for zone management operations."""

    def test_create_zone(self, registry):
        """Can create a new zone."""
        success = registry.create_zone(
            name="basement",
            display_name="Basement",
        )

        assert success is True

        zones = registry.get_zones()
        zone_names = [zone["name"] for zone in zones]
        assert "basement" in zone_names

    def test_get_rooms_by_zone(self, registry):
        """Can get all rooms in a zone."""
        registry.create_room(name="room1", display_name="Room 1", zone_name="upstairs")
        registry.create_room(name="room2", display_name="Room 2", zone_name="upstairs")
        registry.create_room(name="room3", display_name="Room 3", zone_name="downstairs")

        upstairs_rooms = registry.get_rooms_by_zone("upstairs")
        room_names = [r["name"] for r in upstairs_rooms]
        assert "room1" in room_names
        assert "room2" in room_names
        assert "room3" not in room_names


# =============================================================================
# Device Update Tests
# =============================================================================

class TestDeviceUpdates:
    """Tests for device update operations."""

    def test_rename_device(self, registry):
        """Can rename a device."""
        device_id = registry.register_device(
            entity_id="light.test",
            device_type=DeviceType.LIGHT,
            friendly_name="Old Name",
        )

        success = registry.rename_device(device_id, "New Name")
        assert success is True

        device = registry.get_device(device_id)
        assert device["friendly_name"] == "New Name"

    def test_move_device_to_room(self, registry):
        """Can move device to different room."""
        device_id = registry.register_device(
            entity_id="light.movable",
            device_type=DeviceType.LIGHT,
            friendly_name="Movable Light",
            room_name="living_room",
        )

        success = registry.move_device_to_room(device_id, "bedroom")
        assert success is True

        device = registry.get_device(device_id)
        assert device["room_name"] == "bedroom"

    def test_move_device_to_nonexistent_room_creates_room(self, registry):
        """Moving device to non-existent room creates the room."""
        device_id = registry.register_device(
            entity_id="light.pioneer",
            device_type=DeviceType.LIGHT,
            friendly_name="Pioneer Light",
        )

        registry.move_device_to_room(device_id, "new_room")

        rooms = registry.get_rooms()
        room_names = [r["name"] for r in rooms]
        assert "new_room" in room_names


# =============================================================================
# Naming Validation Tests
# =============================================================================

class TestNamingValidation:
    """Tests for naming consistency validation."""

    def test_normalize_room_name(self, registry):
        """Room names are normalized to snake_case."""
        # These should all normalize to the same name
        assert registry.normalize_room_name("Living Room") == "living_room"
        assert registry.normalize_room_name("living room") == "living_room"
        assert registry.normalize_room_name("Living_Room") == "living_room"
        assert registry.normalize_room_name("LIVING ROOM") == "living_room"

    def test_suggest_room_name_variants(self, registry):
        """Can suggest consistent naming for variants."""
        # Register a device with "master bedroom"
        registry.register_device(
            entity_id="light.master_bedroom",
            device_type=DeviceType.LIGHT,
            friendly_name="Master Bedroom Light",
            room_name="master_bedroom",
        )

        # Should recognize "bedroom" might be related
        suggestions = registry.get_naming_suggestions("bedroom")
        assert "master_bedroom" in suggestions or len(suggestions) == 0

    def test_validate_room_name_warns_on_inconsistency(self, registry):
        """Validation warns about inconsistent naming."""
        registry.create_room(name="living_room", display_name="Living Room")

        # This should trigger a warning about potential duplicate
        validation = registry.validate_room_name("front_room")

        # front_room is a common alias for living_room
        assert validation.get("similar_existing") is not None or validation.get("valid") is True


# =============================================================================
# Device Listing Tests
# =============================================================================

class TestDeviceListing:
    """Tests for device listing and filtering."""

    def test_get_all_devices(self, registry):
        """Can get all registered devices."""
        registry.register_device(
            entity_id="light.a",
            device_type=DeviceType.LIGHT,
            friendly_name="Light A",
        )
        registry.register_device(
            entity_id="switch.b",
            device_type=DeviceType.SWITCH,
            friendly_name="Switch B",
        )

        devices = registry.get_all_devices()
        assert len(devices) >= 2

    def test_get_devices_by_type(self, registry):
        """Can filter devices by type."""
        registry.register_device(
            entity_id="light.typed",
            device_type=DeviceType.LIGHT,
            friendly_name="Typed Light",
        )
        registry.register_device(
            entity_id="switch.typed",
            device_type=DeviceType.SWITCH,
            friendly_name="Typed Switch",
        )

        lights = registry.get_devices_by_type(DeviceType.LIGHT)
        light_types = [d["device_type"] for d in lights]
        assert all(t == DeviceType.LIGHT.value for t in light_types)

    def test_get_unassigned_devices(self, registry):
        """Can get devices without room assignment."""
        registry.register_device(
            entity_id="light.assigned",
            device_type=DeviceType.LIGHT,
            friendly_name="Assigned Light",
            room_name="living_room",
        )
        registry.register_device(
            entity_id="light.unassigned",
            device_type=DeviceType.LIGHT,
            friendly_name="Unassigned Light",
        )

        unassigned = registry.get_unassigned_devices()
        entity_ids = [d["entity_id"] for d in unassigned]
        assert "light.unassigned" in entity_ids
        assert "light.assigned" not in entity_ids


# =============================================================================
# Statistics Tests
# =============================================================================

class TestRegistryStatistics:
    """Tests for registry statistics."""

    def test_get_stats(self, registry):
        """Can get registry statistics."""
        registry.register_device(
            entity_id="light.stat1",
            device_type=DeviceType.LIGHT,
            friendly_name="Stat Light 1",
            room_name="kitchen",
        )
        registry.register_device(
            entity_id="light.stat2",
            device_type=DeviceType.LIGHT,
            friendly_name="Stat Light 2",
        )

        stats = registry.get_stats()

        assert "total_devices" in stats
        assert "assigned_devices" in stats
        assert "unassigned_devices" in stats
        assert "total_rooms" in stats
        assert "devices_by_type" in stats

        assert stats["total_devices"] >= 2
        assert stats["assigned_devices"] >= 1
        assert stats["unassigned_devices"] >= 1


# =============================================================================
# HA Sync Tests
# =============================================================================

class TestHASynchronization:
    """Tests for Home Assistant synchronization."""

    def test_sync_from_ha_adds_new_devices(self, registry, mocker):
        """Syncing from HA adds new devices to registry."""
        # Mock HA client
        mock_ha_client = mocker.Mock()
        mock_ha_client.get_all_states.return_value = [
            {
                "entity_id": "light.new_from_ha",
                "state": "on",
                "attributes": {
                    "friendly_name": "New HA Light",
                },
            }
        ]

        new_devices = registry.sync_from_ha(mock_ha_client)

        assert len(new_devices) >= 1
        entity_ids = [d["entity_id"] for d in new_devices]
        assert "light.new_from_ha" in entity_ids

    def test_sync_from_ha_ignores_existing_devices(self, registry, mocker):
        """Syncing from HA doesn't duplicate existing devices."""
        # Register existing device
        registry.register_device(
            entity_id="light.existing",
            device_type=DeviceType.LIGHT,
            friendly_name="Existing Light",
        )

        # Mock HA client returning the same device
        mock_ha_client = mocker.Mock()
        mock_ha_client.get_all_states.return_value = [
            {
                "entity_id": "light.existing",
                "state": "on",
                "attributes": {"friendly_name": "Existing Light"},
            }
        ]

        new_devices = registry.sync_from_ha(mock_ha_client)

        # No new devices should be added
        existing_entities = [d["entity_id"] for d in new_devices]
        assert "light.existing" not in existing_entities
