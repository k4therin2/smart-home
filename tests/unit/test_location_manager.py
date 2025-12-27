"""Unit tests for LocationManager class.

Tests location tracking, voice puck inference, and room context management
following TDD workflow.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestLocationManagerInitialization:
    """Tests for LocationManager initialization and database setup."""

    def test_init_creates_database_tables(self):
        """LocationManager should create required database tables on init."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check voice_pucks table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='voice_pucks'")
            assert cursor.fetchone() is not None

            # Check user_locations table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_locations'")
            assert cursor.fetchone() is not None

            conn.close()

    def test_init_with_default_db_path(self):
        """LocationManager should use default database path if not specified."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.location_manager.DATA_DIR', Path(tmpdir)):
                manager = LocationManager()
                assert manager.db_path is not None

    def test_init_creates_data_directory(self):
        """LocationManager should create data directory if it doesn't exist."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "test.db")
            manager = LocationManager(db_path=db_path)
            assert os.path.exists(os.path.dirname(db_path))


class TestVoicePuckRegistration:
    """Tests for registering voice pucks and their room assignments."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            yield manager

    def test_register_voice_puck(self, manager):
        """Should register a voice puck with its device_id and room."""
        result = manager.register_voice_puck(
            device_id="puck_living_room_001",
            room_name="living_room",
            display_name="Living Room Puck"
        )

        assert result is True
        puck = manager.get_voice_puck("puck_living_room_001")
        assert puck is not None
        assert puck["room_name"] == "living_room"
        assert puck["display_name"] == "Living Room Puck"

    def test_register_voice_puck_normalizes_room_name(self, manager):
        """Should normalize room name to snake_case."""
        manager.register_voice_puck(
            device_id="puck_001",
            room_name="Living Room",
            display_name="Test Puck"
        )

        puck = manager.get_voice_puck("puck_001")
        assert puck["room_name"] == "living_room"

    def test_register_voice_puck_with_alias(self, manager):
        """Should resolve room aliases to canonical names."""
        manager.register_voice_puck(
            device_id="puck_001",
            room_name="lounge",  # alias for living_room
            display_name="Test Puck"
        )

        puck = manager.get_voice_puck("puck_001")
        assert puck["room_name"] == "living_room"

    def test_update_voice_puck_room(self, manager):
        """Should allow updating a puck's room assignment."""
        manager.register_voice_puck(
            device_id="puck_001",
            room_name="living_room",
            display_name="Test Puck"
        )

        result = manager.update_voice_puck_room("puck_001", "bedroom")
        assert result is True

        puck = manager.get_voice_puck("puck_001")
        assert puck["room_name"] == "bedroom"

    def test_get_nonexistent_voice_puck(self, manager):
        """Should return None for non-existent puck."""
        puck = manager.get_voice_puck("nonexistent")
        assert puck is None

    def test_list_voice_pucks(self, manager):
        """Should list all registered voice pucks."""
        manager.register_voice_puck("puck_001", "living_room", "Living Puck")
        manager.register_voice_puck("puck_002", "bedroom", "Bedroom Puck")

        pucks = manager.list_voice_pucks()
        assert len(pucks) == 2

        room_names = [p["room_name"] for p in pucks]
        assert "living_room" in room_names
        assert "bedroom" in room_names

    def test_delete_voice_puck(self, manager):
        """Should delete a voice puck registration."""
        manager.register_voice_puck("puck_001", "living_room", "Test Puck")

        result = manager.delete_voice_puck("puck_001")
        assert result is True

        puck = manager.get_voice_puck("puck_001")
        assert puck is None


class TestLocationInference:
    """Tests for inferring user location from voice pucks."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database and registered pucks."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)

            # Register some pucks
            manager.register_voice_puck("puck_living", "living_room", "Living Room Puck")
            manager.register_voice_puck("puck_bedroom", "bedroom", "Bedroom Puck")
            manager.register_voice_puck("puck_kitchen", "kitchen", "Kitchen Puck")

            yield manager

    def test_infer_room_from_puck(self, manager):
        """Should return room name for registered puck device_id."""
        room = manager.get_room_from_puck("puck_living")
        assert room == "living_room"

    def test_infer_room_from_unknown_puck(self, manager):
        """Should return None for unknown puck."""
        room = manager.get_room_from_puck("unknown_puck")
        assert room is None

    def test_infer_room_from_context(self, manager):
        """Should extract room from HA webhook context with device_id."""
        context = {
            "device_id": "puck_bedroom",
            "language": "en",
            "conversation_id": "conv_123"
        }

        room = manager.get_room_from_context(context)
        assert room == "bedroom"

    def test_infer_room_from_context_no_device_id(self, manager):
        """Should return None if context has no device_id."""
        context = {
            "language": "en",
            "conversation_id": "conv_123"
        }

        room = manager.get_room_from_context(context)
        assert room is None

    def test_infer_room_from_empty_context(self, manager):
        """Should return None for empty context."""
        room = manager.get_room_from_context({})
        assert room is None

    def test_infer_room_from_none_context(self, manager):
        """Should return None for None context."""
        room = manager.get_room_from_context(None)
        assert room is None


class TestUserLocationTracking:
    """Tests for tracking and managing user's current location."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            manager.register_voice_puck("puck_living", "living_room", "Living Room Puck")
            yield manager

    def test_set_user_location(self, manager):
        """Should set user's current location."""
        result = manager.set_user_location("living_room")
        assert result is True

        location = manager.get_user_location()
        assert location == "living_room"

    def test_set_user_location_normalizes_room_name(self, manager):
        """Should normalize room name when setting location."""
        manager.set_user_location("Living Room")

        location = manager.get_user_location()
        assert location == "living_room"

    def test_update_user_location(self, manager):
        """Should update user's location when they move."""
        manager.set_user_location("living_room")
        manager.set_user_location("bedroom")

        location = manager.get_user_location()
        assert location == "bedroom"

    def test_get_user_location_when_not_set(self, manager):
        """Should return None if location never set."""
        location = manager.get_user_location()
        assert location is None

    def test_set_location_from_puck_activity(self, manager):
        """Should update location when puck is used."""
        manager.record_puck_activity("puck_living")

        location = manager.get_user_location()
        assert location == "living_room"

    def test_location_timestamp_tracked(self, manager):
        """Should track when location was last updated."""
        manager.set_user_location("living_room")

        location_info = manager.get_user_location_info()
        assert location_info is not None
        assert "room_name" in location_info
        assert "updated_at" in location_info
        assert location_info["room_name"] == "living_room"

    def test_clear_user_location(self, manager):
        """Should allow clearing user's location."""
        manager.set_user_location("living_room")
        manager.clear_user_location()

        location = manager.get_user_location()
        assert location is None


class TestLocationHistory:
    """Tests for location history tracking."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            manager.register_voice_puck("puck_living", "living_room", "Living Room")
            manager.register_voice_puck("puck_bedroom", "bedroom", "Bedroom")
            yield manager

    def test_location_history_recorded(self, manager):
        """Should record location changes in history."""
        manager.set_user_location("living_room")
        manager.set_user_location("bedroom")
        manager.set_user_location("kitchen")

        history = manager.get_location_history(limit=10)
        assert len(history) >= 3

        rooms = [h["room_name"] for h in history]
        assert "living_room" in rooms
        assert "bedroom" in rooms
        assert "kitchen" in rooms

    def test_location_history_limit(self, manager):
        """Should respect history limit parameter."""
        for room in ["living_room", "bedroom", "kitchen", "office", "bathroom"]:
            manager.set_user_location(room)

        history = manager.get_location_history(limit=3)
        assert len(history) == 3

    def test_location_history_ordered_recent_first(self, manager):
        """Should order history with most recent first."""
        manager.set_user_location("living_room")
        manager.set_user_location("bedroom")

        history = manager.get_location_history(limit=2)
        assert history[0]["room_name"] == "bedroom"
        assert history[1]["room_name"] == "living_room"


class TestDefaultLocation:
    """Tests for default/fallback location configuration."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            yield manager

    def test_set_default_location(self, manager):
        """Should allow setting a default fallback location."""
        result = manager.set_default_location("living_room")
        assert result is True

        default = manager.get_default_location()
        assert default == "living_room"

    def test_get_effective_location_uses_current(self, manager):
        """Should prefer current location over default."""
        manager.set_default_location("living_room")
        manager.set_user_location("bedroom")

        location = manager.get_effective_location()
        assert location == "bedroom"

    def test_get_effective_location_falls_back_to_default(self, manager):
        """Should use default when no current location set."""
        manager.set_default_location("living_room")

        location = manager.get_effective_location()
        assert location == "living_room"

    def test_get_effective_location_returns_none_if_nothing_set(self, manager):
        """Should return None if no location info available."""
        location = manager.get_effective_location()
        assert location is None

    def test_get_effective_location_with_explicit_override(self, manager):
        """Should allow explicit room override."""
        manager.set_default_location("living_room")
        manager.set_user_location("bedroom")

        location = manager.get_effective_location(explicit_room="kitchen")
        assert location == "kitchen"


class TestRoomNormalization:
    """Tests for room name normalization and alias resolution."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            yield manager

    def test_normalize_room_name_snake_case(self, manager):
        """Should convert to snake_case."""
        assert manager.normalize_room_name("Living Room") == "living_room"
        assert manager.normalize_room_name("Master Bedroom") == "master_bedroom"
        assert manager.normalize_room_name("home office") == "home_office"

    def test_normalize_room_name_preserves_snake_case(self, manager):
        """Should preserve already normalized names."""
        assert manager.normalize_room_name("living_room") == "living_room"
        assert manager.normalize_room_name("master_bedroom") == "master_bedroom"

    def test_normalize_room_name_strips_whitespace(self, manager):
        """Should strip leading/trailing whitespace."""
        assert manager.normalize_room_name("  living room  ") == "living_room"

    def test_resolve_room_alias(self, manager):
        """Should resolve common room aliases."""
        assert manager.resolve_room_alias("lounge") == "living_room"
        assert manager.resolve_room_alias("bed room") == "bedroom"
        assert manager.resolve_room_alias("front room") == "living_room"

    def test_resolve_room_alias_returns_normalized_if_no_alias(self, manager):
        """Should return normalized name if no alias match."""
        assert manager.resolve_room_alias("garage") == "garage"
        assert manager.resolve_room_alias("laundry room") == "laundry_room"


class TestLocationStaleTimeout:
    """Tests for stale location detection."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path, stale_timeout_minutes=30)
            yield manager

    def test_location_not_stale_when_recent(self, manager):
        """Should not consider location stale if recently set."""
        manager.set_user_location("living_room")

        is_stale = manager.is_location_stale()
        assert is_stale is False

    def test_location_stale_after_timeout(self, manager):
        """Should consider location stale after timeout period."""
        manager.set_user_location("living_room")

        # Manually adjust timestamp to simulate old location
        with manager._get_connection() as conn:
            old_time = datetime.now() - timedelta(minutes=60)
            conn.execute(
                "UPDATE user_locations SET updated_at = ?",
                (old_time.isoformat(),)
            )
            conn.commit()

        is_stale = manager.is_location_stale()
        assert is_stale is True

    def test_location_not_set_is_not_stale(self, manager):
        """Should return True (stale/unknown) if location never set."""
        is_stale = manager.is_location_stale()
        assert is_stale is True


class TestRoomValidation:
    """Tests for validating room names against known rooms."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            yield manager

    def test_is_valid_room(self, manager):
        """Should validate rooms against ROOM_ENTITY_MAP."""
        assert manager.is_valid_room("living_room") is True
        assert manager.is_valid_room("bedroom") is True
        assert manager.is_valid_room("kitchen") is True

    def test_is_invalid_room(self, manager):
        """Should reject unknown room names."""
        assert manager.is_valid_room("spaceship") is False
        assert manager.is_valid_room("moon_base") is False

    def test_is_valid_room_with_alias(self, manager):
        """Should validate aliases that resolve to valid rooms."""
        assert manager.is_valid_room("lounge") is True  # alias for living_room


class TestConcurrency:
    """Tests for thread safety and concurrent access."""

    @pytest.fixture
    def manager(self):
        """Create a LocationManager with temporary database."""
        from src.location_manager import LocationManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            manager = LocationManager(db_path=db_path)
            yield manager

    def test_concurrent_location_updates(self, manager):
        """Should handle concurrent location updates safely."""
        import threading

        rooms = ["living_room", "bedroom", "kitchen", "office", "bathroom"]
        errors = []

        def update_location(room):
            try:
                for _ in range(10):
                    manager.set_user_location(room)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=update_location, args=(room,)) for room in rooms]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        location = manager.get_user_location()
        assert location in rooms
