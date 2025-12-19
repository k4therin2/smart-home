"""
Unit tests for OnboardingAgent.

Tests device onboarding workflow, light identification,
voice input processing, and Hue bridge sync.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Will import once created
# from src.onboarding_agent import OnboardingAgent, OnboardingState, OnboardingSession


class TestOnboardingAgentInitialization:
    """Tests for OnboardingAgent initialization."""

    def test_create_agent_with_default_path(self, onboarding_agent):
        """Agent should initialize with default database path."""
        assert onboarding_agent is not None
        assert onboarding_agent.db_path.endswith(".db")

    def test_create_agent_with_custom_path(self, temp_db_path):
        """Agent should accept custom database path."""
        from src.onboarding_agent import OnboardingAgent
        agent = OnboardingAgent(db_path=temp_db_path)
        assert agent.db_path == temp_db_path

    def test_database_tables_created(self, onboarding_agent):
        """Database should create required tables on init."""
        conn = sqlite3.connect(onboarding_agent.db_path)
        cursor = conn.cursor()

        # Check onboarding_sessions table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='onboarding_sessions'"
        )
        assert cursor.fetchone() is not None

        # Check light_identifications table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='light_identifications'"
        )
        assert cursor.fetchone() is not None

        conn.close()


class TestOnboardingSessionManagement:
    """Tests for onboarding session CRUD operations."""

    def test_start_new_session(self, onboarding_agent):
        """Should start a new onboarding session."""
        session = onboarding_agent.start_session()

        assert session is not None
        assert session["session_id"] is not None
        assert session["state"] == "discovering"
        assert session["total_lights"] >= 0

    def test_get_current_session(self, onboarding_agent):
        """Should retrieve current active session."""
        onboarding_agent.start_session()
        session = onboarding_agent.get_current_session()

        assert session is not None
        assert session["state"] in ["discovering", "identifying", "mapping", "confirming", "applying"]

    def test_get_session_when_none_active(self, onboarding_agent):
        """Should return None when no session active."""
        session = onboarding_agent.get_current_session()
        assert session is None

    def test_cancel_session(self, onboarding_agent):
        """Should cancel active session."""
        onboarding_agent.start_session()
        result = onboarding_agent.cancel_session()

        assert result is True
        assert onboarding_agent.get_current_session() is None

    def test_cannot_start_session_when_one_active(self, onboarding_agent):
        """Should not allow multiple active sessions."""
        onboarding_agent.start_session()

        with pytest.raises(ValueError):
            onboarding_agent.start_session()

    def test_complete_session(self, onboarding_agent):
        """Should mark session as completed."""
        onboarding_agent.start_session()
        result = onboarding_agent.complete_session()

        assert result is True
        # Session should be marked complete, not active
        active = onboarding_agent.get_current_session()
        assert active is None


class TestLightDiscovery:
    """Tests for discovering unassigned lights."""

    def test_discover_lights(self, onboarding_agent, mock_device_registry):
        """Should discover unassigned light devices."""
        mock_device_registry.get_unassigned_devices.return_value = [
            {"entity_id": "light.living_room_1", "friendly_name": "Living Room Light 1"},
            {"entity_id": "light.bedroom_1", "friendly_name": "Bedroom Light 1"},
        ]

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            lights = onboarding_agent.discover_unassigned_lights()

        assert len(lights) == 2
        assert lights[0]["entity_id"] == "light.living_room_1"

    def test_discover_lights_filters_non_lights(self, onboarding_agent, mock_device_registry):
        """Should only return light devices."""
        mock_device_registry.get_unassigned_devices.return_value = [
            {"entity_id": "light.test", "type": "light"},
            {"entity_id": "switch.test", "type": "switch"},
        ]

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            lights = onboarding_agent.discover_unassigned_lights()

        # Should filter to only lights
        assert all(l["entity_id"].startswith("light.") for l in lights)

    def test_discover_lights_empty(self, onboarding_agent, mock_device_registry):
        """Should handle no unassigned lights."""
        mock_device_registry.get_unassigned_devices.return_value = []

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            lights = onboarding_agent.discover_unassigned_lights()

        assert lights == []


class TestColorAssignment:
    """Tests for assigning unique colors to lights."""

    def test_assign_colors_to_lights(self, onboarding_agent):
        """Should assign unique colors to each light."""
        lights = [
            {"entity_id": "light.one"},
            {"entity_id": "light.two"},
            {"entity_id": "light.three"},
        ]

        assignments = onboarding_agent.assign_identification_colors(lights)

        assert len(assignments) == 3
        colors = [a["color_name"] for a in assignments]
        # All colors should be unique
        assert len(set(colors)) == 3

    def test_get_available_colors(self, onboarding_agent):
        """Should return list of distinct colors for identification."""
        colors = onboarding_agent.get_identification_colors()

        assert len(colors) >= 10  # At least 10 distinct colors
        for color in colors:
            assert "name" in color
            assert "rgb" in color
            assert len(color["rgb"]) == 3

    def test_colors_are_distinct(self, onboarding_agent):
        """Colors should be visually distinct (not similar hues)."""
        colors = onboarding_agent.get_identification_colors()

        # Check no duplicate RGB values
        rgb_tuples = [tuple(c["rgb"]) for c in colors]
        assert len(set(rgb_tuples)) == len(rgb_tuples)


class TestLightIdentificationSequence:
    """Tests for the light identification visual sequence."""

    def test_turn_on_identification_lights(self, onboarding_agent, mock_ha_client):
        """Should turn on all lights with assigned colors."""
        mock_ha_client.turn_on_light.return_value = True
        assignments = [
            {"entity_id": "light.one", "color_name": "red", "rgb": [255, 0, 0]},
            {"entity_id": "light.two", "color_name": "blue", "rgb": [0, 0, 255]},
        ]

        with patch.object(onboarding_agent, '_get_ha_client', return_value=mock_ha_client):
            result = onboarding_agent.turn_on_identification_lights(assignments)

        assert result is True
        assert mock_ha_client.turn_on_light.call_count == 2

    def test_turn_off_all_lights(self, onboarding_agent, mock_ha_client):
        """Should turn off all identification lights."""
        mock_ha_client.turn_off_light.return_value = True

        with patch.object(onboarding_agent, '_get_ha_client', return_value=mock_ha_client):
            result = onboarding_agent.turn_off_all_onboarding_lights()

        assert result is True

    def test_flash_single_light(self, onboarding_agent, mock_ha_client):
        """Should flash a single light for confirmation."""
        mock_ha_client.turn_on_light.return_value = True
        mock_ha_client.turn_off_light.return_value = True

        with patch.object(onboarding_agent, '_get_ha_client', return_value=mock_ha_client):
            result = onboarding_agent.flash_light("light.test", times=3)

        assert result is True


class TestRoomMapping:
    """Tests for mapping colors/lights to rooms via voice."""

    def test_record_room_mapping(self, onboarding_agent):
        """Should record room assignment for a light."""
        onboarding_agent.start_session()

        result = onboarding_agent.record_room_mapping(
            entity_id="light.test",
            color_name="red",
            room_name="living room"
        )

        assert result is True

    def test_get_pending_mappings(self, onboarding_agent):
        """Should return lights not yet mapped."""
        session = onboarding_agent.start_session()
        # Mock some lights in session
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
            {"entity_id": "light.two", "color_name": "blue"},
        ])

        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        pending = onboarding_agent.get_pending_mappings()
        assert len(pending) == 1
        assert pending[0]["entity_id"] == "light.two"

    def test_get_completed_mappings(self, onboarding_agent):
        """Should return all completed mappings."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        completed = onboarding_agent.get_completed_mappings()
        assert len(completed) == 1
        assert completed[0]["room_name"] == "bedroom"

    def test_parse_room_from_voice(self, onboarding_agent):
        """Should parse room name from natural language input."""
        test_cases = [
            ("that's in the living room", "living_room"),
            ("red is bedroom", "bedroom"),
            ("kitchen", "kitchen"),
            ("the blue one is in the office", "office"),
        ]

        for voice_input, expected_room in test_cases:
            room = onboarding_agent.parse_room_from_voice(voice_input)
            assert room == expected_room, f"Failed for: {voice_input}"


class TestRoomNormalization:
    """Tests for room name normalization."""

    def test_normalize_room_name(self, onboarding_agent):
        """Should normalize room names to snake_case."""
        test_cases = [
            ("Living Room", "living_room"),
            ("BEDROOM", "bedroom"),
            ("  kitchen  ", "kitchen"),
            ("home office", "home_office"),
        ]

        for input_name, expected in test_cases:
            result = onboarding_agent.normalize_room_name(input_name)
            assert result == expected

    def test_resolve_room_alias(self, onboarding_agent):
        """Should resolve room aliases."""
        test_cases = [
            ("lounge", "living_room"),
            ("master bedroom", "bedroom"),
            ("study", "office"),
            ("unknown room", "unknown_room"),  # No alias, just normalize
        ]

        for alias, expected in test_cases:
            result = onboarding_agent.resolve_room_alias(alias)
            assert result == expected


class TestApplyMappings:
    """Tests for applying room mappings to device registry."""

    def test_apply_all_mappings(self, onboarding_agent, mock_device_registry):
        """Should apply all mappings to device registry."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
            {"entity_id": "light.two", "color_name": "blue"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")
        onboarding_agent.record_room_mapping("light.two", "blue", "kitchen")

        mock_device_registry.move_device_to_room.return_value = True

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            result = onboarding_agent.apply_mappings()

        assert result["success"] is True
        assert result["applied"] == 2
        assert mock_device_registry.move_device_to_room.call_count == 2

    def test_apply_mappings_creates_missing_rooms(self, onboarding_agent, mock_device_registry):
        """Should create rooms that don't exist."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "new room")

        mock_device_registry.create_room.return_value = True
        mock_device_registry.get_room.return_value = None
        mock_device_registry.move_device_to_room.return_value = True

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            result = onboarding_agent.apply_mappings()

        assert result["success"] is True
        mock_device_registry.create_room.assert_called()


class TestHueBridgeSync:
    """Tests for syncing room assignments to Hue bridge."""

    def test_sync_to_hue_bridge(self, onboarding_agent):
        """Should sync room assignments to Hue bridge API."""
        mappings = [
            {"entity_id": "light.hue_1", "room_name": "bedroom"},
            {"entity_id": "light.hue_2", "room_name": "bedroom"},
        ]

        with patch.object(onboarding_agent, '_sync_hue_room') as mock_sync:
            mock_sync.return_value = True
            result = onboarding_agent.sync_to_hue_bridge(mappings)

        assert result["success"] is True

    def test_skip_non_hue_lights(self, onboarding_agent):
        """Should skip lights that aren't Hue devices."""
        mappings = [
            {"entity_id": "light.hue_1", "room_name": "bedroom", "is_hue": True},
            {"entity_id": "light.non_hue", "room_name": "kitchen", "is_hue": False},
        ]

        with patch.object(onboarding_agent, '_sync_hue_room') as mock_sync:
            mock_sync.return_value = True
            result = onboarding_agent.sync_to_hue_bridge(mappings)

        # Should only sync Hue lights
        assert mock_sync.call_count <= 1

    def test_handle_hue_api_error(self, onboarding_agent):
        """Should handle Hue API errors gracefully."""
        mappings = [
            {"entity_id": "light.hue_1", "room_name": "bedroom", "is_hue": True},
        ]

        with patch.object(onboarding_agent, '_sync_hue_room') as mock_sync:
            mock_sync.side_effect = Exception("API error")
            result = onboarding_agent.sync_to_hue_bridge(mappings)

        assert result["success"] is False
        assert "error" in result


class TestProgressTracking:
    """Tests for onboarding progress tracking."""

    def test_get_progress(self, onboarding_agent):
        """Should return progress as X of Y."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
            {"entity_id": "light.two", "color_name": "blue"},
            {"entity_id": "light.three", "color_name": "green"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        progress = onboarding_agent.get_progress()

        assert progress["completed"] == 1
        assert progress["total"] == 3
        assert progress["remaining"] == 2
        assert progress["percentage"] == pytest.approx(33.33, rel=0.1)

    def test_is_complete(self, onboarding_agent):
        """Should detect when all lights are mapped."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        assert onboarding_agent.is_mapping_complete() is True

    def test_is_not_complete(self, onboarding_agent):
        """Should detect when lights remain unmapped."""
        onboarding_agent.start_session()
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
            {"entity_id": "light.two", "color_name": "blue"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        assert onboarding_agent.is_mapping_complete() is False


class TestSessionResume:
    """Tests for resuming interrupted sessions."""

    def test_resume_session(self, onboarding_agent):
        """Should resume an interrupted session."""
        session = onboarding_agent.start_session()
        session_id = session["session_id"]
        onboarding_agent._set_session_lights([
            {"entity_id": "light.one", "color_name": "red"},
            {"entity_id": "light.two", "color_name": "blue"},
        ])
        onboarding_agent.record_room_mapping("light.one", "red", "bedroom")

        # Simulate interruption (clear in-memory state)
        onboarding_agent._clear_memory_state()

        # Resume
        resumed = onboarding_agent.resume_session(session_id)

        assert resumed is not None
        progress = onboarding_agent.get_progress()
        assert progress["completed"] == 1

    def test_resume_nonexistent_session(self, onboarding_agent):
        """Should handle resuming non-existent session."""
        with pytest.raises(ValueError):
            onboarding_agent.resume_session("fake-session-id")


class TestSkipAlreadyOrganized:
    """Tests for skipping already-organized lights."""

    def test_skip_organized_lights(self, onboarding_agent, mock_device_registry):
        """Should skip lights already assigned to rooms."""
        mock_device_registry.get_unassigned_devices.return_value = [
            {"entity_id": "light.unassigned"},
        ]
        mock_device_registry.get_devices_by_room.return_value = [
            {"entity_id": "light.assigned", "room_name": "bedroom"},
        ]

        with patch.object(onboarding_agent, '_get_device_registry', return_value=mock_device_registry):
            session = onboarding_agent.start_session(skip_organized=True)

        # Should only include unassigned lights
        assert session["total_lights"] == 1


# Fixtures

@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def onboarding_agent(temp_db_path):
    """Create an OnboardingAgent instance for testing."""
    from src.onboarding_agent import OnboardingAgent
    agent = OnboardingAgent(db_path=temp_db_path)
    return agent


@pytest.fixture
def mock_device_registry():
    """Create a mock DeviceRegistry."""
    registry = MagicMock()
    registry.get_unassigned_devices.return_value = []
    registry.move_device_to_room.return_value = True
    registry.create_room.return_value = True
    registry.get_room.return_value = {"name": "test_room"}
    return registry


@pytest.fixture
def mock_ha_client():
    """Create a mock HomeAssistantClient."""
    client = MagicMock()
    client.turn_on_light.return_value = True
    client.turn_off_light.return_value = True
    client.get_state.return_value = {"state": "on"}
    return client
