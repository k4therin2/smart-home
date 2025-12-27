"""
Integration tests for Device Organization feature.

Tests the complete workflow from device discovery to organization.
Part of WP-5.2: Device Organization Assistant.
"""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock, patch

from src.device_registry import DeviceRegistry, DeviceType
from src.device_organizer import DeviceOrganizer, OrganizationPlan
from tools.devices import (
    list_devices,
    suggest_room,
    assign_device_to_room,
    rename_device,
    organize_devices,
    get_organization_status,
    list_rooms,
    create_room,
    execute_device_tool,
)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        yield Path(temp_file.name)
    Path(temp_file.name).unlink(missing_ok=True)


@pytest.fixture
def registry(temp_db):
    """Create a DeviceRegistry with temporary database."""
    return DeviceRegistry(database_path=temp_db)


@pytest.fixture
def organizer(registry):
    """Create a DeviceOrganizer with the test registry."""
    return DeviceOrganizer(registry=registry)


@pytest.fixture
def populated_registry(registry):
    """Registry with sample devices."""
    registry.register_device(
        entity_id="light.living_room_ceiling",
        device_type=DeviceType.LIGHT,
        friendly_name="Living Room Ceiling Light",
        room_name="living_room",
    )
    registry.register_device(
        entity_id="light.bedroom_lamp",
        device_type=DeviceType.LIGHT,
        friendly_name="Bedroom Lamp",
        room_name="bedroom",
    )
    registry.register_device(
        entity_id="light.unassigned_bulb",
        device_type=DeviceType.LIGHT,
        friendly_name="Smart Bulb",
    )
    registry.register_device(
        entity_id="switch.kitchen_coffee",
        device_type=DeviceType.SWITCH,
        friendly_name="Kitchen Coffee Maker",
    )
    return registry


# =============================================================================
# End-to-End Workflow Tests
# =============================================================================

class TestDeviceOrganizationWorkflow:
    """End-to-end tests for device organization workflow."""

    def test_complete_organization_workflow(self, populated_registry):
        """Test full workflow: discover -> suggest -> assign."""
        organizer = DeviceOrganizer(registry=populated_registry)

        # 1. Get unassigned devices
        unassigned = populated_registry.get_unassigned_devices()
        assert len(unassigned) == 2

        # 2. Get suggestions for first unassigned device
        coffee_maker = next(
            d for d in unassigned
            if "coffee" in d["friendly_name"].lower()
        )
        suggestions = organizer.suggest_room(coffee_maker["id"])
        assert any(s.room_name == "kitchen" for s in suggestions)

        # 3. Create organization plan
        # Only devices with room hints get suggestions (Kitchen Coffee Maker has "kitchen" in name)
        plan = organizer.create_organization_plan()
        assert len(plan.assignments) >= 1  # At least the kitchen device

        # 4. Apply organization plan
        results = organizer.apply_organization_plan(plan, min_confidence=0.5)

        # At least the kitchen coffee maker should be organized
        applied_devices = [a["entity_id"] for a in results["applied"]]
        assert "switch.kitchen_coffee" in applied_devices

    def test_tool_based_workflow(self, temp_db, mocker):
        """Test workflow using agent tools."""
        # Create fresh registry and patch the singleton
        registry = DeviceRegistry(database_path=temp_db)
        mocker.patch("tools.devices.get_device_registry", return_value=registry)
        mocker.patch("src.device_organizer.get_device_registry", return_value=registry)

        organizer = DeviceOrganizer(registry=registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        # 1. Create a room
        result = create_room(name="test_room", display_name="Test Room")
        assert result["success"] is True

        # 2. Register a device manually (simulating sync)
        registry.register_device(
            entity_id="light.test_device",
            device_type=DeviceType.LIGHT,
            friendly_name="Test Light",
        )

        # 3. List unassigned devices
        result = list_devices(unassigned=True)
        assert result["success"] is True
        assert result["count"] >= 1

        # 4. Assign device to room
        result = assign_device_to_room(
            device_name="Test Light",
            room="test_room",
        )
        assert result["success"] is True

        # 5. Verify assignment
        device = registry.get_device_by_entity_id("light.test_device")
        assert device["room_name"] == "test_room"


# =============================================================================
# Tool Integration Tests
# =============================================================================

class TestDeviceToolIntegration:
    """Integration tests for device tools."""

    def test_list_devices_tool(self, populated_registry, mocker):
        """list_devices tool returns correct devices."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        # All devices
        result = list_devices()
        assert result["success"] is True
        assert result["count"] == 4

        # By room
        result = list_devices(room="living_room")
        assert result["count"] == 1
        assert "Living Room" in result["message"]

        # Unassigned
        result = list_devices(unassigned=True)
        assert result["count"] == 2

        # By type
        result = list_devices(device_type="light")
        assert result["count"] == 3

    def test_suggest_room_tool(self, populated_registry, mocker):
        """suggest_room tool returns appropriate suggestions."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        result = suggest_room(device_name="Kitchen Coffee Maker")
        assert result["success"] is True
        assert len(result["suggestions"]) > 0

        # Should suggest kitchen based on name
        rooms = [s["room"] for s in result["suggestions"]]
        assert "kitchen" in rooms

    def test_assign_device_to_room_tool(self, populated_registry, mocker):
        """assign_device_to_room tool moves devices correctly."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        # Move unassigned device to kitchen
        result = assign_device_to_room(
            device_name="Kitchen Coffee Maker",
            room="kitchen",
        )
        assert result["success"] is True
        assert result["room"] == "kitchen"

        # Verify in registry
        device = populated_registry.get_device_by_entity_id("switch.kitchen_coffee")
        assert device["room_name"] == "kitchen"

    def test_rename_device_tool(self, populated_registry, mocker):
        """rename_device tool updates friendly name."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        result = rename_device(
            device_name="Smart Bulb",
            new_name="Office Desk Lamp",
        )
        assert result["success"] is True
        assert result["new_name"] == "Office Desk Lamp"

        # Verify in registry
        device = populated_registry.get_device_by_entity_id("light.unassigned_bulb")
        assert device["friendly_name"] == "Office Desk Lamp"

    def test_organize_devices_tool_preview(self, populated_registry, mocker):
        """organize_devices tool creates plan without applying."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        result = organize_devices(auto_apply=False)
        assert result["success"] is True
        assert result["applied"] == 0
        # Only devices with room hints in their name get suggestions
        assert len(result["plan"]) >= 1  # At least kitchen coffee maker

    def test_organize_devices_tool_auto_apply(self, populated_registry, mocker):
        """organize_devices tool applies plan when auto_apply=True."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        # High confidence threshold
        result = organize_devices(auto_apply=True, min_confidence=0.5)
        assert result["success"] is True

        # Should have applied at least the kitchen device
        assert result["applied"] >= 1

    def test_get_organization_status_tool(self, populated_registry, mocker):
        """get_organization_status tool returns correct statistics."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        result = get_organization_status()
        assert result["success"] is True
        assert result["status"]["total_devices"] == 4
        assert result["status"]["organized_devices"] == 2
        assert result["status"]["unorganized_devices"] == 2

    def test_list_rooms_tool(self, populated_registry, mocker):
        """list_rooms tool returns all rooms."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        result = list_rooms()
        assert result["success"] is True
        assert result["count"] >= 2  # At least living_room and bedroom

        room_names = [r["name"] for r in result["rooms"]]
        assert "living_room" in room_names
        assert "bedroom" in room_names

    def test_create_room_tool(self, registry, mocker):
        """create_room tool creates new rooms."""
        mocker.patch("tools.devices.get_device_registry", return_value=registry)

        result = create_room(
            name="game_room",
            display_name="Game Room",
            zone="basement",
        )
        assert result["success"] is True
        assert result["room"]["name"] == "game_room"

        # Verify in registry
        rooms = registry.get_rooms()
        room_names = [r["name"] for r in rooms]
        assert "game_room" in room_names


# =============================================================================
# execute_device_tool Tests
# =============================================================================

class TestExecuteDeviceTool:
    """Tests for the tool dispatcher."""

    def test_execute_list_devices(self, populated_registry, mocker):
        """Dispatches list_devices correctly."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        result = execute_device_tool("list_devices", {"room": "living_room"})
        assert result["success"] is True
        assert result["count"] == 1

    def test_execute_suggest_room(self, populated_registry, mocker):
        """Dispatches suggest_room correctly."""
        mocker.patch("tools.devices.get_device_registry", return_value=populated_registry)

        organizer = DeviceOrganizer(registry=populated_registry)
        mocker.patch("tools.devices.get_device_organizer", return_value=organizer)

        result = execute_device_tool("suggest_room", {"device_name": "Kitchen Coffee Maker"})
        assert result["success"] is True

    def test_execute_unknown_tool(self):
        """Unknown tool returns error."""
        result = execute_device_tool("unknown_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]


# =============================================================================
# HA Sync Integration Tests
# =============================================================================

class TestHASyncIntegration:
    """Tests for Home Assistant synchronization."""

    def test_sync_from_ha_adds_new_devices(self, registry, mocker):
        """Syncing from HA adds devices to registry."""
        # Mock HA client
        mock_ha_client = Mock()
        mock_ha_client.get_all_states.return_value = [
            {
                "entity_id": "light.new_bulb",
                "state": "on",
                "attributes": {"friendly_name": "New Smart Bulb"},
            },
            {
                "entity_id": "switch.new_plug",
                "state": "off",
                "attributes": {"friendly_name": "New Smart Plug"},
            },
        ]

        mocker.patch("tools.devices.get_device_registry", return_value=registry)
        mocker.patch("src.ha_client.get_ha_client", return_value=mock_ha_client)

        new_devices = registry.sync_from_ha(mock_ha_client)
        assert len(new_devices) == 2

        # Verify devices in registry
        assert registry.get_device_by_entity_id("light.new_bulb") is not None
        assert registry.get_device_by_entity_id("switch.new_plug") is not None

    def test_sync_preserves_existing_assignments(self, registry, mocker):
        """Syncing doesn't overwrite existing device data."""
        # Register existing device with room assignment
        registry.register_device(
            entity_id="light.existing",
            device_type=DeviceType.LIGHT,
            friendly_name="Existing Light",
            room_name="bedroom",
        )

        # Mock HA returning same device
        mock_ha_client = Mock()
        mock_ha_client.get_all_states.return_value = [
            {
                "entity_id": "light.existing",
                "state": "on",
                "attributes": {"friendly_name": "Existing Light"},
            },
        ]

        new_devices = registry.sync_from_ha(mock_ha_client)

        # No new devices should be added
        assert len(new_devices) == 0

        # Room assignment should be preserved
        device = registry.get_device_by_entity_id("light.existing")
        assert device["room_name"] == "bedroom"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in device tools."""

    def test_suggest_room_nonexistent_device(self, registry, mocker):
        """suggest_room handles non-existent device gracefully."""
        mocker.patch("tools.devices.get_device_registry", return_value=registry)

        result = suggest_room(device_name="Nonexistent Device")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_assign_device_nonexistent(self, registry, mocker):
        """assign_device_to_room handles non-existent device."""
        mocker.patch("tools.devices.get_device_registry", return_value=registry)

        result = assign_device_to_room(
            device_name="Nonexistent",
            room="living_room",
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_rename_device_nonexistent(self, registry, mocker):
        """rename_device handles non-existent device."""
        mocker.patch("tools.devices.get_device_registry", return_value=registry)

        result = rename_device(
            device_name="Nonexistent",
            new_name="New Name",
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_list_devices_invalid_type(self, registry, mocker):
        """list_devices handles invalid device type."""
        mocker.patch("tools.devices.get_device_registry", return_value=registry)

        result = list_devices(device_type="invalid_type")
        assert result["success"] is False
        assert "Unknown device type" in result["error"]
