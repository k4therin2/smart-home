"""
Unit tests for smart plug control tools.

Tests plug on/off control, status monitoring, power monitoring,
and safety checks for high-power devices.
Part of WP-7.1: Smart Plug Control.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any


# =============================================================================
# Test Data
# =============================================================================

MOCK_PLUG_STATE_ON = {
    "entity_id": "switch.living_room_lamp",
    "state": "on",
    "attributes": {
        "friendly_name": "Living Room Lamp",
        "device_class": "outlet",
        "current_power_w": 60.5,
        "today_energy_kwh": 0.25,
    },
}

MOCK_PLUG_STATE_OFF = {
    "entity_id": "switch.bedroom_fan",
    "state": "off",
    "attributes": {
        "friendly_name": "Bedroom Fan",
        "device_class": "outlet",
        "current_power_w": 0,
        "today_energy_kwh": 1.2,
    },
}

MOCK_HIGH_POWER_PLUG = {
    "entity_id": "switch.space_heater",
    "state": "off",
    "attributes": {
        "friendly_name": "Space Heater",
        "device_class": "outlet",
        "current_power_w": 0,
        "today_energy_kwh": 5.5,
    },
}

MOCK_PLUG_WITHOUT_POWER = {
    "entity_id": "switch.garage_light",
    "state": "on",
    "attributes": {
        "friendly_name": "Garage Light",
        "device_class": "outlet",
    },
}

MOCK_ALL_PLUGS = [
    MOCK_PLUG_STATE_ON,
    MOCK_PLUG_STATE_OFF,
    MOCK_HIGH_POWER_PLUG,
    MOCK_PLUG_WITHOUT_POWER,
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_ha_client():
    """Create a mock Home Assistant client."""
    with patch("tools.plugs.get_ha_client") as mock_get_client:
        client = Mock()
        mock_get_client.return_value = client
        yield client


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    with patch("tools.plugs.get_plug_entities") as mock_get_plugs, \
         patch("tools.plugs.HIGH_POWER_DEVICES") as mock_high_power:
        mock_get_plugs.return_value = [
            "switch.living_room_lamp",
            "switch.bedroom_fan",
            "switch.space_heater",
            "switch.garage_light",
        ]
        mock_high_power.__iter__ = Mock(return_value=iter(["heater", "oven", "toaster"]))
        mock_high_power.__contains__ = lambda self, x: x in ["heater", "oven", "toaster"]
        yield {
            "get_plug_entities": mock_get_plugs,
            "HIGH_POWER_DEVICES": mock_high_power,
        }


# =============================================================================
# Control Plug Tests
# =============================================================================

class TestControlPlug:
    """Tests for the control_plug function."""

    def test_turn_on_plug_success(self, mock_ha_client):
        """Successfully turns on a plug."""
        mock_ha_client.call_service.return_value = True
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_OFF

        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.bedroom_fan", action="on")

        assert result["success"] is True
        assert result["action"] == "on"
        assert result["entity_id"] == "switch.bedroom_fan"
        mock_ha_client.call_service.assert_called_once_with(
            "switch", "turn_on", {"entity_id": "switch.bedroom_fan"}
        )

    def test_turn_off_plug_success(self, mock_ha_client):
        """Successfully turns off a plug."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.living_room_lamp", action="off")

        assert result["success"] is True
        assert result["action"] == "off"
        mock_ha_client.call_service.assert_called_once_with(
            "switch", "turn_off", {"entity_id": "switch.living_room_lamp"}
        )

    def test_toggle_plug_success(self, mock_ha_client):
        """Successfully toggles a plug."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.garage_light", action="toggle")

        assert result["success"] is True
        assert result["action"] == "toggle"
        mock_ha_client.call_service.assert_called_once_with(
            "switch", "toggle", {"entity_id": "switch.garage_light"}
        )

    def test_invalid_action_returns_error(self, mock_ha_client):
        """Returns error for invalid action."""
        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.bedroom_fan", action="invalid")

        assert result["success"] is False
        assert "error" in result
        assert "available_actions" in result

    def test_invalid_entity_format_returns_error(self, mock_ha_client):
        """Returns error for invalid entity ID format."""
        from tools.plugs import control_plug
        result = control_plug(entity_id="light.bedroom", action="on")

        assert result["success"] is False
        assert "error" in result
        assert "switch." in result["error"].lower() or "invalid" in result["error"].lower()

    def test_ha_client_failure_returns_error(self, mock_ha_client):
        """Returns error when HA client fails."""
        mock_ha_client.call_service.return_value = False

        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.bedroom_fan", action="on")

        assert result["success"] is False

    def test_exception_handling(self, mock_ha_client):
        """Handles exceptions gracefully."""
        mock_ha_client.call_service.side_effect = Exception("Connection error")

        from tools.plugs import control_plug
        result = control_plug(entity_id="switch.bedroom_fan", action="on")

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# High Power Device Safety Tests
# =============================================================================

class TestHighPowerSafety:
    """Tests for safety checks on high-power devices."""

    def test_heater_requires_confirmation(self, mock_ha_client):
        """High-power devices like heaters require safety confirmation."""
        from tools.plugs import control_plug
        result = control_plug(
            entity_id="switch.space_heater",
            action="on",
            confirm_high_power=False
        )

        assert result["success"] is False
        assert "safety" in result.get("error", "").lower() or "confirm" in result.get("error", "").lower()
        mock_ha_client.call_service.assert_not_called()

    def test_heater_turns_on_with_confirmation(self, mock_ha_client):
        """High-power devices turn on when confirmed."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import control_plug
        result = control_plug(
            entity_id="switch.space_heater",
            action="on",
            confirm_high_power=True
        )

        assert result["success"] is True
        assert result.get("high_power_confirmed") is True

    def test_oven_requires_confirmation(self, mock_ha_client):
        """Oven plugs require safety confirmation."""
        from tools.plugs import control_plug
        result = control_plug(
            entity_id="switch.kitchen_oven",
            action="on",
            confirm_high_power=False
        )

        assert result["success"] is False
        mock_ha_client.call_service.assert_not_called()

    def test_turning_off_high_power_does_not_require_confirmation(self, mock_ha_client):
        """Turning OFF high-power devices doesn't require confirmation."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import control_plug
        result = control_plug(
            entity_id="switch.space_heater",
            action="off",
            confirm_high_power=False
        )

        assert result["success"] is True
        mock_ha_client.call_service.assert_called_once()


# =============================================================================
# Get Plug Status Tests
# =============================================================================

class TestGetPlugStatus:
    """Tests for the get_plug_status function."""

    def test_get_status_on_plug(self, mock_ha_client):
        """Gets status of an on plug."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_ON

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.living_room_lamp")

        assert result["success"] is True
        assert result["state"] == "on"
        assert result["entity_id"] == "switch.living_room_lamp"
        assert result["friendly_name"] == "Living Room Lamp"

    def test_get_status_off_plug(self, mock_ha_client):
        """Gets status of an off plug."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_OFF

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.bedroom_fan")

        assert result["success"] is True
        assert result["state"] == "off"

    def test_get_status_includes_power_monitoring(self, mock_ha_client):
        """Status includes power monitoring data when available."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_ON

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.living_room_lamp")

        assert result["success"] is True
        assert result.get("current_power_w") == 60.5
        assert result.get("today_energy_kwh") == 0.25

    def test_get_status_without_power_monitoring(self, mock_ha_client):
        """Status works for plugs without power monitoring."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_WITHOUT_POWER

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.garage_light")

        assert result["success"] is True
        assert result["state"] == "on"
        assert result.get("current_power_w") is None

    def test_get_status_entity_not_found(self, mock_ha_client):
        """Returns error when entity not found."""
        mock_ha_client.get_state.return_value = None

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.nonexistent")

        assert result["success"] is False
        assert "error" in result

    def test_get_status_includes_description(self, mock_ha_client):
        """Status includes human-readable description."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_ON

        from tools.plugs import get_plug_status
        result = get_plug_status(entity_id="switch.living_room_lamp")

        assert "state_description" in result
        assert "on" in result["state_description"].lower()


# =============================================================================
# List Plugs Tests
# =============================================================================

class TestListPlugs:
    """Tests for the list_plugs function."""

    def test_list_all_plugs(self, mock_ha_client):
        """Lists all switch entities that are plugs."""
        mock_ha_client.get_all_states.return_value = MOCK_ALL_PLUGS

        from tools.plugs import list_plugs
        result = list_plugs()

        assert result["success"] is True
        assert "plugs" in result
        assert len(result["plugs"]) == 4
        assert result["count"] == 4

    def test_list_plugs_filters_by_device_class(self, mock_ha_client):
        """Filters to only include plug/outlet device class."""
        all_switches = MOCK_ALL_PLUGS + [
            {
                "entity_id": "switch.automation_enable",
                "state": "on",
                "attributes": {
                    "friendly_name": "Automation Enable",
                    "device_class": "switch",  # Not outlet
                },
            }
        ]
        mock_ha_client.get_all_states.return_value = all_switches

        from tools.plugs import list_plugs
        result = list_plugs(filter_device_class="outlet")

        assert result["success"] is True
        # Should filter out the automation_enable switch
        for plug in result["plugs"]:
            assert plug.get("device_class") != "switch" or "outlet" in plug.get("entity_id", "")

    def test_list_plugs_includes_state(self, mock_ha_client):
        """Listed plugs include their current state."""
        mock_ha_client.get_all_states.return_value = MOCK_ALL_PLUGS

        from tools.plugs import list_plugs
        result = list_plugs()

        assert result["success"] is True
        for plug in result["plugs"]:
            assert "state" in plug
            assert plug["state"] in ["on", "off", "unavailable", "unknown"]

    def test_list_plugs_empty(self, mock_ha_client):
        """Returns empty list when no plugs found."""
        mock_ha_client.get_all_states.return_value = []

        from tools.plugs import list_plugs
        result = list_plugs()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["plugs"] == []


# =============================================================================
# Toggle Plug Tests
# =============================================================================

class TestTogglePlug:
    """Tests for the toggle_plug function."""

    def test_toggle_plug(self, mock_ha_client):
        """Toggles plug state."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import toggle_plug
        result = toggle_plug(entity_id="switch.bedroom_fan")

        assert result["success"] is True
        mock_ha_client.call_service.assert_called_once_with(
            "switch", "toggle", {"entity_id": "switch.bedroom_fan"}
        )

    def test_toggle_high_power_requires_confirmation(self, mock_ha_client):
        """Toggling high-power devices to ON requires confirmation."""
        mock_ha_client.get_state.return_value = MOCK_HIGH_POWER_PLUG  # Currently off

        from tools.plugs import toggle_plug
        result = toggle_plug(entity_id="switch.space_heater", confirm_high_power=False)

        assert result["success"] is False
        assert "confirm" in result.get("error", "").lower() or "safety" in result.get("error", "").lower()


# =============================================================================
# Power Monitoring Tests
# =============================================================================

class TestPowerMonitoring:
    """Tests for power monitoring features."""

    def test_get_power_usage(self, mock_ha_client):
        """Gets current power usage for a plug."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_ON

        from tools.plugs import get_power_usage
        result = get_power_usage(entity_id="switch.living_room_lamp")

        assert result["success"] is True
        assert result["current_power_w"] == 60.5
        assert result["today_energy_kwh"] == 0.25

    def test_get_power_usage_not_supported(self, mock_ha_client):
        """Returns appropriate message when power monitoring not supported."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_WITHOUT_POWER

        from tools.plugs import get_power_usage
        result = get_power_usage(entity_id="switch.garage_light")

        assert result["success"] is True
        assert result.get("power_monitoring_available") is False


# =============================================================================
# Execute Tool Tests
# =============================================================================

class TestExecutePlugTool:
    """Tests for the execute_plug_tool dispatcher function."""

    def test_execute_control_plug(self, mock_ha_client):
        """Dispatches control_plug correctly."""
        mock_ha_client.call_service.return_value = True

        from tools.plugs import execute_plug_tool
        result = execute_plug_tool(
            "control_plug",
            {"entity_id": "switch.bedroom_fan", "action": "on"}
        )

        assert result["success"] is True
        assert result["action"] == "on"

    def test_execute_get_plug_status(self, mock_ha_client):
        """Dispatches get_plug_status correctly."""
        mock_ha_client.get_state.return_value = MOCK_PLUG_STATE_ON

        from tools.plugs import execute_plug_tool
        result = execute_plug_tool(
            "get_plug_status",
            {"entity_id": "switch.living_room_lamp"}
        )

        assert result["success"] is True
        assert result["state"] == "on"

    def test_execute_list_plugs(self, mock_ha_client):
        """Dispatches list_plugs correctly."""
        mock_ha_client.get_all_states.return_value = MOCK_ALL_PLUGS

        from tools.plugs import execute_plug_tool
        result = execute_plug_tool("list_plugs", {})

        assert result["success"] is True
        assert "plugs" in result

    def test_execute_unknown_tool(self, mock_ha_client):
        """Returns error for unknown tool."""
        from tools.plugs import execute_plug_tool
        result = execute_plug_tool("unknown_tool", {})

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Tool Definitions Tests
# =============================================================================

class TestToolDefinitions:
    """Tests for PLUGS_TOOLS definitions."""

    def test_plugs_tools_exists(self):
        """PLUGS_TOOLS list exists and is not empty."""
        from tools.plugs import PLUGS_TOOLS

        assert isinstance(PLUGS_TOOLS, list)
        assert len(PLUGS_TOOLS) > 0

    def test_all_tools_have_required_fields(self):
        """All tools have name, description, and input_schema."""
        from tools.plugs import PLUGS_TOOLS

        for tool in PLUGS_TOOLS:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing description"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing input_schema"

    def test_tool_names_are_unique(self):
        """All tool names are unique."""
        from tools.plugs import PLUGS_TOOLS

        names = [tool["name"] for tool in PLUGS_TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_control_plug_tool_defined(self):
        """control_plug tool is properly defined."""
        from tools.plugs import PLUGS_TOOLS

        control_tool = next((t for t in PLUGS_TOOLS if t["name"] == "control_plug"), None)
        assert control_tool is not None
        assert "entity_id" in str(control_tool["input_schema"])
        assert "action" in str(control_tool["input_schema"])

    def test_get_plug_status_tool_defined(self):
        """get_plug_status tool is properly defined."""
        from tools.plugs import PLUGS_TOOLS

        status_tool = next((t for t in PLUGS_TOOLS if t["name"] == "get_plug_status"), None)
        assert status_tool is not None

    def test_list_plugs_tool_defined(self):
        """list_plugs tool is properly defined."""
        from tools.plugs import PLUGS_TOOLS

        list_tool = next((t for t in PLUGS_TOOLS if t["name"] == "list_plugs"), None)
        assert list_tool is not None
