"""Integration tests for Location-Aware Commands.

Tests the full flow from voice puck registration through location inference
and context-aware command execution.
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestLocationToolsIntegration:
    """Tests for location tools integration with agent."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    @pytest.fixture
    def location_manager(self, temp_db):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager
        return LocationManager(db_path=temp_db)

    @pytest.fixture
    def mock_location_manager(self, temp_db):
        """Create a patched location manager for tools."""
        from src.location_manager import LocationManager
        manager = LocationManager(db_path=temp_db)

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                yield manager


class TestVoicePuckWorkflow:
    """Tests for the voice puck registration and location inference workflow."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    def test_register_and_infer_location(self, temp_db):
        """Should register a puck and infer location from it."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)

        # Register a puck
        manager.register_voice_puck(
            device_id="puck_living_room_001",
            room_name="living_room",
            display_name="Living Room Puck"
        )

        # Simulate webhook context
        context = {
            "device_id": "puck_living_room_001",
            "language": "en",
            "conversation_id": "conv_123"
        }

        # Infer room from context
        room = manager.get_room_from_context(context)
        assert room == "living_room"

    def test_puck_activity_updates_user_location(self, temp_db):
        """Recording puck activity should update user location."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)

        # Register pucks
        manager.register_voice_puck("puck_1", "living_room", "Living Puck")
        manager.register_voice_puck("puck_2", "bedroom", "Bedroom Puck")

        # Record activity from living room puck
        manager.record_puck_activity("puck_1")
        assert manager.get_user_location() == "living_room"

        # Record activity from bedroom puck (user moved)
        manager.record_puck_activity("puck_2")
        assert manager.get_user_location() == "bedroom"

    def test_location_history_tracks_movements(self, temp_db):
        """Location history should track room movements."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)

        # Move through rooms
        manager.set_user_location("living_room")
        manager.set_user_location("kitchen")
        manager.set_user_location("bedroom")

        history = manager.get_location_history(limit=10)
        rooms = [h["room_name"] for h in history]

        assert "living_room" in rooms
        assert "kitchen" in rooms
        assert "bedroom" in rooms


class TestLocationToolExecution:
    """Tests for executing location tools via the tools module."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    def test_execute_set_user_location(self, temp_db):
        """Should execute set_user_location tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool, get_location_manager

        manager = LocationManager(db_path=temp_db)

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("set_user_location", {"room": "living_room"})

                assert result["success"] is True
                assert result["room"] == "living_room"
                assert "living room" in result["message"].lower()

    def test_execute_get_user_location(self, temp_db):
        """Should execute get_user_location tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.set_user_location("bedroom")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("get_user_location", {})

                assert result["success"] is True
                assert result["room"] == "bedroom"

    def test_execute_register_voice_puck(self, temp_db):
        """Should execute register_voice_puck tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("register_voice_puck", {
                    "device_id": "puck_123",
                    "room": "kitchen"
                })

                assert result["success"] is True
                assert result["device_id"] == "puck_123"
                assert result["room"] == "kitchen"

    def test_execute_list_voice_pucks(self, temp_db):
        """Should execute list_voice_pucks tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.register_voice_puck("puck_1", "living_room", "Living Puck")
        manager.register_voice_puck("puck_2", "bedroom", "Bedroom Puck")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("list_voice_pucks", {})

                assert result["success"] is True
                assert result["count"] == 2
                assert len(result["pucks"]) == 2

    def test_execute_get_room_from_voice_context(self, temp_db):
        """Should execute get_room_from_voice_context tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.register_voice_puck("puck_office", "office", "Office Puck")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("get_room_from_voice_context", {
                    "device_id": "puck_office"
                })

                assert result["success"] is True
                assert result["room"] == "office"

    def test_execute_set_default_location(self, temp_db):
        """Should execute set_default_location tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("set_default_location", {"room": "living_room"})

                assert result["success"] is True
                assert manager.get_default_location() == "living_room"

    def test_execute_clear_user_location(self, temp_db):
        """Should execute clear_user_location tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.set_user_location("bedroom")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("clear_user_location", {})

                assert result["success"] is True
                assert manager.get_user_location() is None

    def test_execute_get_location_history(self, temp_db):
        """Should execute get_location_history tool."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.set_user_location("living_room")
        manager.set_user_location("kitchen")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("get_location_history", {"limit": 5})

                assert result["success"] is True
                assert result["count"] >= 2


class TestEffectiveLocationLogic:
    """Tests for the effective location priority chain."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    def test_explicit_room_takes_priority(self, temp_db):
        """Explicit room should take priority over tracked location."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.set_default_location("living_room")
        manager.set_user_location("bedroom")

        # Explicit room overrides everything
        effective = manager.get_effective_location(explicit_room="kitchen")
        assert effective == "kitchen"

    def test_current_location_over_default(self, temp_db):
        """Current tracked location should take priority over default."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.set_default_location("living_room")
        manager.set_user_location("bedroom")

        effective = manager.get_effective_location()
        assert effective == "bedroom"

    def test_default_when_no_current(self, temp_db):
        """Default location should be used when no current location."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.set_default_location("living_room")

        effective = manager.get_effective_location()
        assert effective == "living_room"

    def test_none_when_nothing_set(self, temp_db):
        """Should return None when no location info available."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)

        effective = manager.get_effective_location()
        assert effective is None


class TestRoomAliasResolution:
    """Tests for room alias and name normalization."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    def test_alias_resolution_in_puck_registration(self, temp_db):
        """Should resolve aliases when registering pucks."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.register_voice_puck("puck_1", "lounge", "Lounge Puck")  # alias

        puck = manager.get_voice_puck("puck_1")
        assert puck["room_name"] == "living_room"  # canonical name

    def test_alias_resolution_in_user_location(self, temp_db):
        """Should resolve aliases when setting user location."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.set_user_location("front room")  # alias

        location = manager.get_user_location()
        assert location == "living_room"  # canonical name

    def test_name_normalization(self, temp_db):
        """Should normalize room names to snake_case."""
        from src.location_manager import LocationManager

        manager = LocationManager(db_path=temp_db)
        manager.set_user_location("Living Room")  # Title Case

        location = manager.get_user_location()
        assert location == "living_room"  # snake_case


class TestAgentIntegration:
    """Tests for integration with the main agent."""

    def test_location_tools_in_agent_tools(self):
        """Location tools should be included in agent's tool list."""
        from agent import TOOLS

        tool_names = [tool["name"] for tool in TOOLS]

        assert "get_user_location" in tool_names
        assert "set_user_location" in tool_names
        assert "register_voice_puck" in tool_names

    def test_execute_tool_dispatches_location_tools(self):
        """Agent execute_tool should dispatch location tools correctly."""
        from agent import execute_tool
        import json

        # Mock the location manager
        with patch('tools.location.get_location_manager') as mock_get:
            mock_manager = MagicMock()
            mock_manager.get_effective_location.return_value = "living_room"
            mock_manager.get_user_location_info.return_value = {"room_name": "living_room"}
            mock_manager.is_location_stale.return_value = False
            mock_manager.get_default_location.return_value = None
            mock_get.return_value = mock_manager

            result = execute_tool("get_user_location", {})
            result_dict = json.loads(result)

            assert result_dict["success"] is True
            assert result_dict["room"] == "living_room"


class TestVoiceHandlerLocationIntegration:
    """Tests for voice handler using location context."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_locations.db")
            yield db_path

    def test_voice_context_provides_room(self, temp_db):
        """Voice handler should be able to get room from context."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)
        manager.register_voice_puck("puck_kitchen_001", "kitchen", "Kitchen Puck")

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("get_room_from_voice_context", {
                    "device_id": "puck_kitchen_001"
                })

                assert result["success"] is True
                assert result["room"] == "kitchen"

                # Should also update user location
                assert manager.get_user_location() == "kitchen"

    def test_unknown_puck_returns_none(self, temp_db):
        """Unknown puck should return None for room."""
        from src.location_manager import LocationManager
        from tools.location import execute_location_tool

        manager = LocationManager(db_path=temp_db)

        with patch('tools.location._location_manager', manager):
            with patch('tools.location.get_location_manager', return_value=manager):
                result = execute_location_tool("get_room_from_voice_context", {
                    "device_id": "unknown_puck"
                })

                assert result["success"] is True
                assert result["room"] is None
