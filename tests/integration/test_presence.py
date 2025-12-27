"""
Integration tests for presence detection system.

Tests the full flow from agent tools to PresenceManager.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from tools.presence import (
    PRESENCE_TOOLS,
    execute_presence_tool,
    get_presence_status,
    set_presence_mode,
    get_presence_history,
    register_presence_tracker,
    list_presence_trackers,
    predict_departure,
    predict_arrival,
    get_presence_settings,
    set_vacuum_delay,
    discover_ha_trackers,
    sync_presence_from_ha,
)


class TestPresenceToolDefinitions:
    """Tests for presence tool definitions."""

    def test_all_tools_have_required_fields(self):
        """Each tool should have name, description, and input_schema."""
        for tool in PRESENCE_TOOLS:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool missing description: {tool.get('name')}"
            assert "input_schema" in tool, f"Tool missing input_schema: {tool.get('name')}"

    def test_tool_count(self):
        """Should have 11 presence tools."""
        assert len(PRESENCE_TOOLS) == 11

    def test_tool_names(self):
        """Should have expected tool names."""
        expected_tools = [
            "get_presence_status",
            "set_presence_mode",
            "get_presence_history",
            "register_presence_tracker",
            "list_presence_trackers",
            "predict_departure",
            "predict_arrival",
            "get_presence_settings",
            "set_vacuum_delay",
            "discover_ha_trackers",
            "sync_presence_from_ha",
        ]
        tool_names = [t["name"] for t in PRESENCE_TOOLS]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestGetPresenceStatus:
    """Tests for get_presence_status tool."""

    def test_get_initial_status(self, mock_presence_manager):
        """Should return unknown status initially."""
        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = get_presence_status()

        assert result["success"] is True
        assert result["state"] == "unknown"
        assert "message" in result

    def test_get_status_after_set(self, mock_presence_manager):
        """Should return current status after setting."""
        mock_presence_manager.get_presence_state.return_value = {
            "state": "home",
            "source": "manual",
            "confidence": 1.0,
            "updated_at": datetime.now().isoformat()
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = get_presence_status()

        assert result["success"] is True
        assert result["state"] == "home"
        assert result["confidence"] == 1.0

    def test_execute_via_dispatcher(self, mock_presence_manager):
        """Should work via execute_presence_tool dispatcher."""
        mock_presence_manager.get_presence_state.return_value = {
            "state": "away",
            "source": "router",
            "confidence": 0.95,
            "updated_at": datetime.now().isoformat()
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = execute_presence_tool("get_presence_status", {})

        assert result["success"] is True
        assert result["state"] == "away"


class TestSetPresenceMode:
    """Tests for set_presence_mode tool."""

    def test_set_home(self, mock_presence_manager):
        """Should set presence to home."""
        mock_presence_manager.manual_set_presence.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = set_presence_mode("home")

        assert result["success"] is True
        assert result["state"] == "home"
        mock_presence_manager.manual_set_presence.assert_called_once_with("home", None)

    def test_set_away(self, mock_presence_manager):
        """Should set presence to away."""
        mock_presence_manager.manual_set_presence.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = set_presence_mode("away")

        assert result["success"] is True
        assert result["state"] == "away"

    def test_set_with_duration(self, mock_presence_manager):
        """Should set presence with duration."""
        mock_presence_manager.manual_set_presence.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = set_presence_mode("away", duration_minutes=60)

        assert result["success"] is True
        assert result["duration_minutes"] == 60
        mock_presence_manager.manual_set_presence.assert_called_once_with("away", 60)

    def test_invalid_state(self, mock_presence_manager):
        """Should reject invalid state."""
        mock_presence_manager.manual_set_presence.side_effect = ValueError("Invalid state")

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = set_presence_mode("invalid")

        assert result["success"] is False
        assert "error" in result

    def test_execute_via_dispatcher(self, mock_presence_manager):
        """Should work via execute_presence_tool dispatcher."""
        mock_presence_manager.manual_set_presence.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = execute_presence_tool("set_presence_mode", {"state": "leaving"})

        assert result["success"] is True
        assert result["state"] == "leaving"


class TestGetPresenceHistory:
    """Tests for get_presence_history tool."""

    def test_get_empty_history(self, mock_presence_manager):
        """Should return empty list initially."""
        mock_presence_manager.get_presence_history.return_value = []

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = get_presence_history()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["history"] == []

    def test_get_history_with_limit(self, mock_presence_manager):
        """Should respect limit parameter."""
        mock_presence_manager.get_presence_history.return_value = [
            {"state": "home", "source": "manual", "timestamp": "2025-12-19T10:00:00"},
            {"state": "away", "source": "router", "timestamp": "2025-12-19T08:00:00"},
        ]

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = get_presence_history(limit=5)

        assert result["success"] is True
        assert result["count"] == 2
        mock_presence_manager.get_presence_history.assert_called_once_with(limit=5)


class TestRegisterPresenceTracker:
    """Tests for register_presence_tracker tool."""

    def test_register_gps_tracker(self, mock_presence_manager):
        """Should register GPS tracker."""
        mock_presence_manager.register_device_tracker.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = register_presence_tracker(
                entity_id="device_tracker.phone",
                source_type="gps",
                display_name="Katherine's Phone"
            )

        assert result["success"] is True
        assert result["entity_id"] == "device_tracker.phone"
        assert result["source_type"] == "gps"

    def test_register_router_tracker(self, mock_presence_manager):
        """Should register router tracker."""
        mock_presence_manager.register_device_tracker.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = register_presence_tracker(
                entity_id="device_tracker.router",
                source_type="router"
            )

        assert result["success"] is True
        assert result["source_type"] == "router"


class TestListPresenceTrackers:
    """Tests for list_presence_trackers tool."""

    def test_list_empty(self, mock_presence_manager):
        """Should return empty list when no trackers."""
        mock_presence_manager.list_device_trackers.return_value = []

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = list_presence_trackers()

        assert result["success"] is True
        assert result["count"] == 0

    def test_list_multiple_trackers(self, mock_presence_manager):
        """Should list all registered trackers."""
        mock_presence_manager.list_device_trackers.return_value = [
            {"entity_id": "device_tracker.phone", "source_type": "gps", "enabled": True},
            {"entity_id": "device_tracker.router", "source_type": "router", "enabled": True},
        ]

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = list_presence_trackers()

        assert result["success"] is True
        assert result["count"] == 2


class TestPredictDeparture:
    """Tests for predict_departure tool."""

    def test_predict_with_data(self, mock_presence_manager):
        """Should predict departure time when data available."""
        mock_presence_manager.predict_departure.return_value = {
            "hour": 8,
            "minute": 30,
            "confidence": 0.85,
            "data_points": 5
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = predict_departure(day_of_week=1)

        assert result["success"] is True
        assert result["hour"] == 8
        assert result["minute"] == 30
        assert result["day"] == "Tuesday"

    def test_predict_without_data(self, mock_presence_manager):
        """Should handle insufficient data."""
        mock_presence_manager.predict_departure.return_value = None

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = predict_departure(day_of_week=0)

        assert result["success"] is True
        assert result["prediction"] is None
        assert "Not enough data" in result["message"]

    def test_predict_default_day(self, mock_presence_manager):
        """Should use today's day if not specified."""
        mock_presence_manager.predict_departure.return_value = None

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = predict_departure()

        assert result["success"] is True
        # Should have called with today's weekday
        mock_presence_manager.predict_departure.assert_called_once()


class TestPredictArrival:
    """Tests for predict_arrival tool."""

    def test_predict_with_data(self, mock_presence_manager):
        """Should predict arrival time when data available."""
        mock_presence_manager.predict_arrival.return_value = {
            "hour": 18,
            "minute": 0,
            "confidence": 0.9,
            "data_points": 10
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = predict_arrival(day_of_week=4)

        assert result["success"] is True
        assert result["hour"] == 18
        assert result["day"] == "Friday"


class TestGetPresenceSettings:
    """Tests for get_presence_settings tool."""

    def test_get_default_settings(self, mock_presence_manager):
        """Should return all presence settings."""
        mock_presence_manager.get_settings.return_value = {
            "home_zone_radius": 100,
            "arriving_distance": 500,
            "vacuum_start_delay": 5
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = get_presence_settings()

        assert result["success"] is True
        assert result["settings"]["home_zone_radius"] == 100
        assert result["settings"]["vacuum_start_delay"] == 5


class TestSetVacuumDelay:
    """Tests for set_vacuum_delay tool."""

    def test_set_delay(self, mock_presence_manager):
        """Should set vacuum start delay."""
        mock_presence_manager.set_vacuum_start_delay.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = set_vacuum_delay(minutes=10)

        assert result["success"] is True
        assert result["delay_minutes"] == 10
        mock_presence_manager.set_vacuum_start_delay.assert_called_once_with(10)


class TestDiscoverHaTrackers:
    """Tests for discover_ha_trackers tool."""

    def test_discover_trackers(self, mock_presence_manager):
        """Should discover HA device trackers."""
        mock_presence_manager.discover_ha_trackers.return_value = [
            {"entity_id": "device_tracker.phone", "state": "home"},
            {"entity_id": "device_tracker.tablet", "state": "not_home"},
        ]

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = discover_ha_trackers()

        assert result["success"] is True
        assert result["count"] == 2


class TestSyncPresenceFromHa:
    """Tests for sync_presence_from_ha tool."""

    def test_sync_all_trackers(self, mock_presence_manager):
        """Should sync all enabled trackers."""
        mock_presence_manager.list_device_trackers.return_value = [
            {"entity_id": "device_tracker.phone", "enabled": True},
            {"entity_id": "device_tracker.router", "enabled": True},
        ]
        mock_presence_manager.sync_tracker_from_ha.return_value = True
        mock_presence_manager.get_presence_state.return_value = {
            "state": "home",
            "confidence": 0.95
        }

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            result = sync_presence_from_ha()

        assert result["success"] is True
        assert result["trackers_synced"] == 2
        assert result["current_state"] == "home"


class TestExecutePresenceTool:
    """Tests for the execute_presence_tool dispatcher."""

    def test_unknown_tool(self):
        """Should handle unknown tool name."""
        result = execute_presence_tool("unknown_tool", {})
        assert result["success"] is False
        assert "Unknown" in result["error"]

    def test_all_tools_dispatched(self, mock_presence_manager):
        """Each tool should be dispatchable."""
        # Set up mock returns
        mock_presence_manager.get_presence_state.return_value = {"state": "unknown", "source": "unknown", "confidence": 0.5}
        mock_presence_manager.manual_set_presence.return_value = True
        mock_presence_manager.get_presence_history.return_value = []
        mock_presence_manager.register_device_tracker.return_value = True
        mock_presence_manager.list_device_trackers.return_value = []
        mock_presence_manager.predict_departure.return_value = None
        mock_presence_manager.predict_arrival.return_value = None
        mock_presence_manager.get_settings.return_value = {"home_zone_radius": 100, "arriving_distance": 500, "vacuum_start_delay": 5}
        mock_presence_manager.set_vacuum_start_delay.return_value = True
        mock_presence_manager.discover_ha_trackers.return_value = []
        mock_presence_manager.sync_tracker_from_ha.return_value = True

        with patch('tools.presence.get_presence_manager', return_value=mock_presence_manager):
            for tool in PRESENCE_TOOLS:
                tool_name = tool["name"]
                # Build minimum required input
                tool_input = {}
                required = tool["input_schema"].get("required", [])
                props = tool["input_schema"].get("properties", {})

                for req in required:
                    if props.get(req, {}).get("type") == "string":
                        if req == "state":
                            tool_input[req] = "home"
                        elif req == "entity_id":
                            tool_input[req] = "device_tracker.test"
                        elif req == "source_type":
                            tool_input[req] = "gps"
                        else:
                            tool_input[req] = "test"
                    elif props.get(req, {}).get("type") == "integer":
                        tool_input[req] = 5

                result = execute_presence_tool(tool_name, tool_input)
                assert "error" not in result or result.get("success") is False, \
                    f"Tool {tool_name} returned unexpected error: {result}"


# Fixtures

@pytest.fixture
def mock_presence_manager():
    """Create a mock PresenceManager."""
    manager = MagicMock()
    manager.get_presence_state.return_value = {
        "state": "unknown",
        "source": "unknown",
        "confidence": 0.5,
        "updated_at": None
    }
    return manager
