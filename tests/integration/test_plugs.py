"""
Integration tests for smart plug voice command handling.

Tests end-to-end scenarios for plug control via the agent system,
including natural language command processing and tool execution.
Part of WP-7.1: Smart Plug Control.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


# =============================================================================
# Test Data for Integration Tests
# =============================================================================

MOCK_ALL_STATES = [
    {
        "entity_id": "switch.living_room_lamp",
        "state": "on",
        "attributes": {
            "friendly_name": "Living Room Lamp",
            "device_class": "outlet",
            "current_power_w": 60.5,
            "today_energy_kwh": 0.25,
        },
    },
    {
        "entity_id": "switch.bedroom_fan",
        "state": "off",
        "attributes": {
            "friendly_name": "Bedroom Fan",
            "device_class": "outlet",
        },
    },
    {
        "entity_id": "switch.kitchen_toaster",
        "state": "off",
        "attributes": {
            "friendly_name": "Kitchen Toaster",
            "device_class": "outlet",
        },
    },
    {
        "entity_id": "switch.space_heater",
        "state": "off",
        "attributes": {
            "friendly_name": "Space Heater",
            "device_class": "outlet",
            "current_power_w": 0,
        },
    },
    {
        "entity_id": "light.living_room",  # Not a plug - should be filtered
        "state": "on",
        "attributes": {"friendly_name": "Living Room Light"},
    },
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_ha_client():
    """Create a mock Home Assistant client for integration tests."""
    with patch("tools.plugs.get_ha_client") as mock_get_client:
        client = Mock()
        mock_get_client.return_value = client

        # Set up default returns
        client.get_all_states.return_value = MOCK_ALL_STATES
        client.call_service.return_value = True

        def mock_get_state(entity_id):
            for state in MOCK_ALL_STATES:
                if state["entity_id"] == entity_id:
                    return state
            return None

        client.get_state = mock_get_state

        yield client


# =============================================================================
# Voice Command Integration Tests
# =============================================================================

class TestVoiceCommandIntegration:
    """Tests simulating voice command flows."""

    def test_turn_on_lamp_command(self, mock_ha_client):
        """Voice command: 'turn on the living room lamp'"""
        from tools.plugs import execute_plug_tool

        # Simulates what agent would call after NL processing
        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.living_room_lamp",
            "action": "on"
        })

        assert result["success"] is True
        assert result["action"] == "on"
        mock_ha_client.call_service.assert_called_once_with(
            "switch", "turn_on", {"entity_id": "switch.living_room_lamp"}
        )

    def test_turn_off_fan_command(self, mock_ha_client):
        """Voice command: 'turn off the bedroom fan'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.bedroom_fan",
            "action": "off"
        })

        assert result["success"] is True
        assert result["action"] == "off"

    def test_toggle_command(self, mock_ha_client):
        """Voice command: 'toggle the lamp'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("toggle_plug", {
            "entity_id": "switch.living_room_lamp"
        })

        assert result["success"] is True

    def test_status_query(self, mock_ha_client):
        """Voice command: 'is the living room lamp on?'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("get_plug_status", {
            "entity_id": "switch.living_room_lamp"
        })

        assert result["success"] is True
        assert result["state"] == "on"
        assert "Living Room Lamp" in result["friendly_name"]

    def test_list_all_plugs_query(self, mock_ha_client):
        """Voice command: 'what plugs do I have?'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("list_plugs", {})

        assert result["success"] is True
        assert result["count"] == 4  # 4 switches in mock data
        # Should not include the light entity
        entity_ids = [p["entity_id"] for p in result["plugs"]]
        assert "light.living_room" not in entity_ids

    def test_power_usage_query(self, mock_ha_client):
        """Voice command: 'how much power is the lamp using?'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("get_power_usage", {
            "entity_id": "switch.living_room_lamp"
        })

        assert result["success"] is True
        assert result["current_power_w"] == 60.5
        assert result["today_energy_kwh"] == 0.25


# =============================================================================
# Safety Integration Tests
# =============================================================================

class TestSafetyIntegration:
    """Tests for safety features in real-world scenarios."""

    def test_heater_safety_block(self, mock_ha_client):
        """Voice command: 'turn on the heater' - should require confirmation"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.space_heater",
            "action": "on"
        })

        assert result["success"] is False
        assert result.get("requires_confirmation") is True
        mock_ha_client.call_service.assert_not_called()

    def test_heater_with_confirmation(self, mock_ha_client):
        """Voice command: 'yes, turn on the heater'"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.space_heater",
            "action": "on",
            "confirm_high_power": True
        })

        assert result["success"] is True
        assert result.get("high_power_confirmed") is True
        mock_ha_client.call_service.assert_called_once()

    def test_toaster_requires_confirmation(self, mock_ha_client):
        """Voice command: 'turn on the toaster' - toaster is high-power"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.kitchen_toaster",
            "action": "on"
        })

        assert result["success"] is False
        assert "confirm" in result.get("error", "").lower()

    def test_turning_off_heater_no_confirmation(self, mock_ha_client):
        """Voice command: 'turn off the heater' - no confirmation needed"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.space_heater",
            "action": "off"
        })

        assert result["success"] is True
        mock_ha_client.call_service.assert_called_once()


# =============================================================================
# Error Handling Integration Tests
# =============================================================================

class TestErrorHandlingIntegration:
    """Tests for error scenarios in real-world usage."""

    def test_nonexistent_plug(self, mock_ha_client):
        """Voice command: 'turn on the garage fan' (doesn't exist)"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("get_plug_status", {
            "entity_id": "switch.garage_fan"
        })

        assert result["success"] is False
        assert "not exist" in result.get("error", "").lower() or "could not" in result.get("error", "").lower()

    def test_invalid_entity_type(self, mock_ha_client):
        """User tries to control a light as a plug"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "light.living_room",
            "action": "on"
        })

        assert result["success"] is False
        assert "switch" in result.get("error", "").lower()

    def test_ha_connection_failure(self, mock_ha_client):
        """Home Assistant connection fails"""
        mock_ha_client.call_service.side_effect = Exception("Connection refused")

        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.bedroom_fan",
            "action": "on"
        })

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Multi-Step Workflow Tests
# =============================================================================

class TestMultiStepWorkflows:
    """Tests for multi-step interaction workflows."""

    def test_check_then_control(self, mock_ha_client):
        """Workflow: check status, then turn on if off"""
        from tools.plugs import execute_plug_tool

        # Step 1: Check status
        status = execute_plug_tool("get_plug_status", {
            "entity_id": "switch.bedroom_fan"
        })
        assert status["success"] is True
        assert status["state"] == "off"

        # Step 2: Turn on since it's off
        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.bedroom_fan",
            "action": "on"
        })
        assert result["success"] is True

    def test_list_then_control(self, mock_ha_client):
        """Workflow: list plugs, then control one"""
        from tools.plugs import execute_plug_tool

        # Step 1: List all plugs
        list_result = execute_plug_tool("list_plugs", {})
        assert list_result["success"] is True
        assert list_result["count"] > 0

        # Step 2: Control the first one
        first_plug = list_result["plugs"][0]["entity_id"]
        result = execute_plug_tool("control_plug", {
            "entity_id": first_plug,
            "action": "off"
        })
        # May fail if high-power, but should at least process
        assert "entity_id" in result or "error" in result

    def test_power_monitoring_workflow(self, mock_ha_client):
        """Workflow: check power, then turn off if high"""
        from tools.plugs import execute_plug_tool

        # Step 1: Check power usage
        power = execute_plug_tool("get_power_usage", {
            "entity_id": "switch.living_room_lamp"
        })
        assert power["success"] is True
        assert power["current_power_w"] == 60.5

        # Step 2: Turn off to save power
        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.living_room_lamp",
            "action": "off"
        })
        assert result["success"] is True


# =============================================================================
# Filter Tests
# =============================================================================

class TestFiltering:
    """Tests for plug listing filters."""

    def test_filter_by_outlet(self, mock_ha_client):
        """Filter list to only outlet device class"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("list_plugs", {
            "filter_device_class": "outlet"
        })

        assert result["success"] is True
        for plug in result["plugs"]:
            assert plug.get("device_class") == "outlet"

    def test_filter_all(self, mock_ha_client):
        """Default filter returns all switches"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("list_plugs", {
            "filter_device_class": "all"
        })

        assert result["success"] is True
        assert result["count"] == 4


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_entity_id(self, mock_ha_client):
        """Empty entity ID should fail gracefully"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "",
            "action": "on"
        })

        assert result["success"] is False
        assert "error" in result

    def test_missing_action(self, mock_ha_client):
        """Missing action should fail gracefully"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("control_plug", {
            "entity_id": "switch.bedroom_fan",
            "action": ""
        })

        assert result["success"] is False

    def test_plug_without_power_monitoring(self, mock_ha_client):
        """Plugs without power monitoring should report it"""
        from tools.plugs import execute_plug_tool

        result = execute_plug_tool("get_power_usage", {
            "entity_id": "switch.bedroom_fan"
        })

        assert result["success"] is True
        assert result.get("power_monitoring_available") is False
