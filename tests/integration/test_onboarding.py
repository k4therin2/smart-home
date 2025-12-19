"""Integration tests for device onboarding tools.

Tests the full workflow from starting onboarding to applying mappings.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from tools.onboarding import (
    ONBOARDING_TOOLS,
    execute_onboarding_tool,
    start_device_onboarding,
    identify_light_room,
    get_onboarding_progress,
    list_pending_lights,
    apply_onboarding_mappings,
    cancel_onboarding,
    resume_onboarding,
    show_identification_lights,
    get_onboarding_summary,
    sync_rooms_to_hue,
)
from src.onboarding_agent import OnboardingAgent


@pytest.fixture
def mock_ha_client():
    """Mock Home Assistant client."""
    with patch("src.onboarding_agent.get_ha_client") as mock:
        client = Mock()
        client.get_states.return_value = [
            {"entity_id": "light.living_room_1", "attributes": {"friendly_name": "Living Room Light 1"}},
            {"entity_id": "light.bedroom_1", "attributes": {"friendly_name": "Bedroom Light 1"}},
            {"entity_id": "light.kitchen_1", "attributes": {"friendly_name": "Kitchen Light 1"}},
        ]
        client.call_service.return_value = True
        mock.return_value = client
        yield client


@pytest.fixture
def mock_device_registry():
    """Mock device registry."""
    with patch("src.onboarding_agent.get_device_registry") as mock:
        registry = Mock()
        registry.get_device.return_value = None  # No existing assignments
        registry.update_device.return_value = True
        # Mock unassigned devices - these are lights without room assignments
        registry.get_unassigned_devices.return_value = [
            {"entity_id": "light.living_room_1", "friendly_name": "Living Room Light 1"},
            {"entity_id": "light.bedroom_1", "friendly_name": "Bedroom Light 1"},
            {"entity_id": "light.kitchen_1", "friendly_name": "Kitchen Light 1"},
        ]
        registry.get_devices_by_type.return_value = [
            {"entity_id": "light.living_room_1", "friendly_name": "Living Room Light 1"},
            {"entity_id": "light.bedroom_1", "friendly_name": "Bedroom Light 1"},
            {"entity_id": "light.kitchen_1", "friendly_name": "Kitchen Light 1"},
        ]
        mock.return_value = registry
        yield registry


@pytest.fixture
def fresh_onboarding_agent(mock_ha_client, mock_device_registry, tmp_path):
    """Create a fresh onboarding agent for each test."""
    # Reset singleton
    import src.onboarding_agent
    src.onboarding_agent._onboarding_agent = None

    # Create agent with temp db path
    agent = OnboardingAgent(db_path=str(tmp_path / "test_onboarding.db"))
    yield agent

    # Clean up
    src.onboarding_agent._onboarding_agent = None


@pytest.fixture
def onboarding_tools_mock(fresh_onboarding_agent):
    """Setup mocks for tools module."""
    with patch("tools.onboarding.get_onboarding_agent") as mock:
        mock.return_value = fresh_onboarding_agent
        yield fresh_onboarding_agent


class TestToolDefinitions:
    """Test tool definitions are valid."""

    def test_all_tools_have_required_fields(self):
        """All tools should have name, description, input_schema."""
        for tool in ONBOARDING_TOOLS:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing description"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing input_schema"

    def test_tool_names_are_unique(self):
        """Tool names should be unique."""
        names = [tool["name"] for tool in ONBOARDING_TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_expected_tools_exist(self):
        """Verify all expected tools exist."""
        expected = [
            "start_device_onboarding",
            "identify_light_room",
            "get_onboarding_progress",
            "list_pending_lights",
            "apply_onboarding_mappings",
            "cancel_onboarding",
            "resume_onboarding",
            "show_identification_lights",
            "get_onboarding_summary",
            "sync_rooms_to_hue",
        ]
        actual = [tool["name"] for tool in ONBOARDING_TOOLS]
        for name in expected:
            assert name in actual, f"Missing expected tool: {name}"


class TestExecuteOnboardingTool:
    """Test the tool dispatcher."""

    def test_unknown_tool_returns_error(self):
        """Unknown tool should return error."""
        result = execute_onboarding_tool("unknown_tool", {})
        assert result["success"] is False
        assert "Unknown" in result["error"]

    def test_start_device_onboarding_dispatch(self, onboarding_tools_mock):
        """Dispatcher should route start_device_onboarding correctly."""
        result = execute_onboarding_tool("start_device_onboarding", {"skip_organized": True})
        # Will return no lights found since mock returns lights with rooms
        assert "success" in result

    def test_identify_light_room_dispatch(self, onboarding_tools_mock):
        """Dispatcher should route identify_light_room correctly."""
        result = execute_onboarding_tool("identify_light_room", {
            "color_name": "red",
            "room_name": "living room"
        })
        # Will fail because no session active
        assert result["success"] is False
        assert "No onboarding session" in result["error"]


class TestFullOnboardingWorkflow:
    """Test complete onboarding workflow."""

    def test_start_session_with_lights(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Starting onboarding should discover lights and assign colors."""
        # Mock device registry to return no room for any light
        mock_device_registry.get_device.return_value = None

        result = start_device_onboarding(skip_organized=True)

        assert result["success"] is True
        assert result["total_lights"] == 3
        assert "session_id" in result
        assert len(result["lights"]) == 3

        # Each light should have a unique color
        colors = [l["color_name"] for l in result["lights"]]
        assert len(colors) == len(set(colors))

    def test_identify_lights_workflow(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Full workflow: start -> identify -> apply."""
        mock_device_registry.get_device.return_value = None

        # Start session
        start_result = start_device_onboarding()
        assert start_result["success"] is True

        # Get the colors assigned
        lights = start_result["lights"]

        # Identify each light
        rooms = ["living room", "bedroom", "kitchen"]
        for i, light in enumerate(lights):
            result = identify_light_room(light["color_name"], rooms[i])
            assert result["success"] is True
            assert result["room"] is not None

        # Check progress
        progress = get_onboarding_progress()
        assert progress["success"] is True
        assert progress["completed"] == 3
        assert progress["is_complete"] is True

        # Apply mappings
        apply_result = apply_onboarding_mappings()
        assert apply_result["success"] is True
        assert apply_result["applied"] == 3

    def test_cancel_workflow(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Test cancelling an onboarding session."""
        mock_device_registry.get_device.return_value = None

        # Start session
        start_result = start_device_onboarding()
        assert start_result["success"] is True

        # Cancel
        cancel_result = cancel_onboarding()
        assert cancel_result["success"] is True

        # Verify session is gone
        progress = get_onboarding_progress()
        assert progress["success"] is False
        assert "No onboarding session" in progress["error"]

    def test_resume_workflow(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Test resuming a partially completed session."""
        mock_device_registry.get_device.return_value = None

        # Start session
        start_result = start_device_onboarding()
        assert start_result["success"] is True
        lights = start_result["lights"]

        # Identify one light
        identify_light_room(lights[0]["color_name"], "living room")

        # Resume
        resume_result = resume_onboarding()
        assert resume_result["success"] is True
        assert resume_result["progress"]["completed"] == 1
        assert resume_result["progress"]["remaining"] == 2


class TestNoSessionErrors:
    """Test error handling when no session is active."""

    def test_identify_without_session(self, onboarding_tools_mock):
        """Identifying without active session should fail."""
        result = identify_light_room("red", "living room")
        assert result["success"] is False
        assert "No onboarding session" in result["error"]

    def test_progress_without_session(self, onboarding_tools_mock):
        """Getting progress without active session should fail."""
        result = get_onboarding_progress()
        assert result["success"] is False

    def test_pending_without_session(self, onboarding_tools_mock):
        """Listing pending without active session should fail."""
        result = list_pending_lights()
        assert result["success"] is False

    def test_apply_without_session(self, onboarding_tools_mock):
        """Applying without active session should fail."""
        result = apply_onboarding_mappings()
        assert result["success"] is False

    def test_show_lights_without_session(self, onboarding_tools_mock):
        """Showing lights without active session should fail."""
        result = show_identification_lights()
        assert result["success"] is False

    def test_summary_without_session(self, onboarding_tools_mock):
        """Getting summary without active session should fail."""
        result = get_onboarding_summary()
        assert result["success"] is False


class TestInvalidColorHandling:
    """Test handling of invalid color names."""

    def test_invalid_color_in_identify(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Using invalid color should return error with available colors."""
        mock_device_registry.get_device.return_value = None

        # Start session
        start_device_onboarding()

        # Try invalid color
        result = identify_light_room("invalid_color", "living room")
        assert result["success"] is False
        assert "No light with color" in result["error"]
        assert "Available colors" in result["error"]


class TestDuplicateSessionPrevention:
    """Test that duplicate sessions are prevented."""

    def test_cannot_start_duplicate_session(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Starting a session while one is active should fail."""
        mock_device_registry.get_device.return_value = None

        # Start first session
        result1 = start_device_onboarding()
        assert result1["success"] is True

        # Try to start another
        result2 = start_device_onboarding()
        assert result2["success"] is False
        assert "already active" in result2["error"]


class TestProgressTracking:
    """Test progress tracking during onboarding."""

    def test_progress_updates_correctly(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Progress should update as lights are identified."""
        mock_device_registry.get_device.return_value = None

        start_result = start_device_onboarding()
        lights = start_result["lights"]

        # Initial progress
        progress = get_onboarding_progress()
        assert progress["completed"] == 0
        assert progress["total"] == 3
        assert progress["percentage"] == 0

        # Identify one light
        identify_light_room(lights[0]["color_name"], "room1")
        progress = get_onboarding_progress()
        assert progress["completed"] == 1
        assert progress["percentage"] == pytest.approx(33.33, rel=0.1)

        # Identify second light
        identify_light_room(lights[1]["color_name"], "room2")
        progress = get_onboarding_progress()
        assert progress["completed"] == 2
        assert progress["percentage"] == pytest.approx(66.67, rel=0.1)


class TestOnboardingSummary:
    """Test onboarding summary generation."""

    def test_summary_shows_completed_and_pending(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Summary should show both completed and pending mappings."""
        mock_device_registry.get_device.return_value = None

        start_result = start_device_onboarding()
        lights = start_result["lights"]

        # Identify one light
        identify_light_room(lights[0]["color_name"], "living room")

        # Get summary
        summary = get_onboarding_summary()
        assert summary["success"] is True
        assert summary["completed_count"] == 1
        assert summary["pending_count"] == 2
        # Room name is normalized to underscore format (living_room)
        assert "living_room" in summary["summary"].lower()


class TestSyncToHue:
    """Test Hue bridge sync functionality."""

    def test_sync_requires_mappings(self, onboarding_tools_mock):
        """Sync should fail if no mappings exist."""
        result = sync_rooms_to_hue()
        assert result["success"] is False
        assert "No mappings" in result["error"]

    def test_sync_after_apply(self, onboarding_tools_mock, mock_ha_client, mock_device_registry):
        """Sync should work after applying mappings."""
        mock_device_registry.get_device.return_value = None

        # Complete a session
        start_result = start_device_onboarding()
        for light in start_result["lights"]:
            identify_light_room(light["color_name"], f"room_{light['color_name']}")

        # DON'T apply mappings - sync while session is still active
        # The agent should have completed mappings available

        # Mock the sync method on the agent
        onboarding_tools_mock.sync_to_hue_bridge = Mock(return_value={"success": True, "synced": 3})

        result = sync_rooms_to_hue()
        assert result["success"] is True
        assert result["synced"] == 3


class TestAgentIntegration:
    """Test integration with agent.py dispatcher."""

    def test_tools_registered_in_agent(self):
        """Onboarding tools should be registered in agent."""
        from agent import TOOLS

        onboarding_names = [tool["name"] for tool in ONBOARDING_TOOLS]
        agent_tool_names = [tool["name"] for tool in TOOLS]

        for name in onboarding_names:
            assert name in agent_tool_names, f"Tool {name} not in agent TOOLS"

    def test_execute_tool_dispatcher(self):
        """Agent execute_tool should dispatch to onboarding tools."""
        from agent import execute_tool

        # This will fail because no session, but it proves dispatch works
        result = execute_tool("get_onboarding_progress", {})
        result_dict = json.loads(result)

        assert "success" in result_dict
        assert result_dict["success"] is False
        assert "No onboarding session" in result_dict["error"]


class TestCancelWithoutSession:
    """Test cancel behavior when no session exists."""

    def test_cancel_without_session_succeeds(self, onboarding_tools_mock):
        """Cancelling when no session exists should still succeed."""
        result = cancel_onboarding()
        assert result["success"] is True
        assert "No active" in result["message"]


class TestResumeWithoutSession:
    """Test resume behavior when no session exists."""

    def test_resume_without_session_fails(self, onboarding_tools_mock):
        """Resuming when no session exists should fail gracefully."""
        result = resume_onboarding()
        assert result["success"] is False
        assert "No onboarding session to resume" in result["error"]
