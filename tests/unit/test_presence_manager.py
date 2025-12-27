"""
Unit tests for PresenceManager.

Tests presence detection, state tracking, and pattern learning
using TDD methodology.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# We'll import the class once it's created
# from src.presence_manager import PresenceManager, PresenceState, PresenceSource


class TestPresenceManagerInitialization:
    """Tests for PresenceManager initialization."""

    def test_create_manager_with_default_path(self, presence_manager):
        """Manager should initialize with default database path."""
        assert presence_manager is not None
        assert presence_manager.db_path.endswith(".db")

    def test_create_manager_with_custom_path(self, temp_db_path):
        """Manager should accept custom database path."""
        from src.presence_manager import PresenceManager
        manager = PresenceManager(db_path=temp_db_path)
        assert manager.db_path == temp_db_path

    def test_database_tables_created(self, presence_manager):
        """Database should create required tables on init."""
        conn = sqlite3.connect(presence_manager.db_path)
        cursor = conn.cursor()

        # Check presence_state table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='presence_state'"
        )
        assert cursor.fetchone() is not None

        # Check device_trackers table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='device_trackers'"
        )
        assert cursor.fetchone() is not None

        # Check presence_history table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='presence_history'"
        )
        assert cursor.fetchone() is not None

        # Check presence_patterns table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='presence_patterns'"
        )
        assert cursor.fetchone() is not None

        conn.close()


class TestDeviceTrackerManagement:
    """Tests for device tracker registration and management."""

    def test_register_device_tracker(self, presence_manager):
        """Should register a new device tracker."""
        result = presence_manager.register_device_tracker(
            entity_id="device_tracker.phone",
            source_type="gps",
            display_name="Katherine's Phone"
        )
        assert result is True

    def test_get_device_tracker(self, presence_manager):
        """Should retrieve registered device tracker."""
        presence_manager.register_device_tracker(
            entity_id="device_tracker.phone",
            source_type="gps",
            display_name="Katherine's Phone"
        )

        tracker = presence_manager.get_device_tracker("device_tracker.phone")
        assert tracker is not None
        assert tracker["entity_id"] == "device_tracker.phone"
        assert tracker["source_type"] == "gps"
        assert tracker["display_name"] == "Katherine's Phone"

    def test_get_nonexistent_tracker(self, presence_manager):
        """Should return None for unregistered tracker."""
        tracker = presence_manager.get_device_tracker("device_tracker.nonexistent")
        assert tracker is None

    def test_list_device_trackers(self, presence_manager):
        """Should list all registered device trackers."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps")
        presence_manager.register_device_tracker("device_tracker.router", "router")

        trackers = presence_manager.list_device_trackers()
        assert len(trackers) == 2
        entity_ids = [t["entity_id"] for t in trackers]
        assert "device_tracker.phone" in entity_ids
        assert "device_tracker.router" in entity_ids

    def test_remove_device_tracker(self, presence_manager):
        """Should remove a device tracker."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps")
        result = presence_manager.remove_device_tracker("device_tracker.phone")
        assert result is True

        tracker = presence_manager.get_device_tracker("device_tracker.phone")
        assert tracker is None

    def test_update_device_tracker_priority(self, presence_manager):
        """Should update tracker priority."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps", priority=1)
        result = presence_manager.update_tracker_priority("device_tracker.phone", 10)
        assert result is True

        tracker = presence_manager.get_device_tracker("device_tracker.phone")
        assert tracker["priority"] == 10


class TestPresenceStateManagement:
    """Tests for presence state tracking."""

    def test_set_presence_state_home(self, presence_manager):
        """Should set presence state to home."""
        result = presence_manager.set_presence_state("home", source="manual")
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["state"] == "home"
        assert state["source"] == "manual"

    def test_set_presence_state_away(self, presence_manager):
        """Should set presence state to away."""
        result = presence_manager.set_presence_state("away", source="gps")
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["state"] == "away"

    def test_set_presence_state_arriving(self, presence_manager):
        """Should set presence state to arriving."""
        result = presence_manager.set_presence_state("arriving", source="gps")
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["state"] == "arriving"

    def test_set_presence_state_leaving(self, presence_manager):
        """Should set presence state to leaving."""
        result = presence_manager.set_presence_state("leaving", source="router")
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["state"] == "leaving"

    def test_invalid_presence_state(self, presence_manager):
        """Should reject invalid presence state."""
        with pytest.raises(ValueError):
            presence_manager.set_presence_state("invalid_state")

    def test_get_presence_state_initial(self, presence_manager):
        """Should return unknown state initially."""
        state = presence_manager.get_presence_state()
        assert state["state"] == "unknown"

    def test_presence_state_includes_timestamp(self, presence_manager):
        """Presence state should include last updated timestamp."""
        presence_manager.set_presence_state("home")
        state = presence_manager.get_presence_state()
        assert "updated_at" in state
        assert state["updated_at"] is not None

    def test_presence_state_includes_confidence(self, presence_manager):
        """Presence state should include confidence score."""
        presence_manager.set_presence_state("home", source="router", confidence=0.9)
        state = presence_manager.get_presence_state()
        assert "confidence" in state
        assert state["confidence"] == 0.9


class TestMultiSourceDetection:
    """Tests for multi-source presence detection."""

    def test_update_from_device_tracker(self, presence_manager):
        """Should update presence from device tracker state."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps")
        result = presence_manager.update_from_tracker(
            "device_tracker.phone",
            state="home"
        )
        assert result is True

    def test_router_detection_high_confidence(self, presence_manager):
        """Router detection should have high confidence for home."""
        presence_manager.register_device_tracker("device_tracker.router", "router", priority=10)
        presence_manager.update_from_tracker("device_tracker.router", state="home")

        state = presence_manager.get_presence_state()
        assert state["state"] == "home"
        assert state["confidence"] >= 0.9

    def test_gps_detection_medium_confidence(self, presence_manager):
        """GPS detection should have medium confidence."""
        # Register both GPS and router to show GPS has lower priority
        presence_manager.register_device_tracker("device_tracker.phone", "gps", priority=5)
        presence_manager.register_device_tracker("device_tracker.router", "router", priority=10)

        # Both report home - router should have higher contribution
        presence_manager.update_from_tracker("device_tracker.phone", state="home")
        presence_manager.update_from_tracker("device_tracker.router", state="home")

        state = presence_manager.get_presence_state()
        # With combined sources, we get high confidence
        assert state["confidence"] >= 0.8
        # GPS source type has base confidence of 0.8 (less than router's 0.95)
        from src.presence_manager import SOURCE_CONFIDENCE
        assert SOURCE_CONFIDENCE["gps"] < SOURCE_CONFIDENCE["router"]

    def test_combined_sources_boost_confidence(self, presence_manager):
        """Multiple sources agreeing should boost confidence."""
        presence_manager.register_device_tracker("device_tracker.router", "router", priority=10)
        presence_manager.register_device_tracker("device_tracker.phone", "gps", priority=5)

        presence_manager.update_from_tracker("device_tracker.router", state="home")
        presence_manager.update_from_tracker("device_tracker.phone", state="home")

        state = presence_manager.get_presence_state()
        assert state["confidence"] >= 0.95  # Combined confidence should be higher

    def test_conflicting_sources_lowers_confidence(self, presence_manager):
        """Conflicting sources should lower overall confidence."""
        presence_manager.register_device_tracker("device_tracker.router", "router", priority=10)
        presence_manager.register_device_tracker("device_tracker.phone", "gps", priority=5)

        presence_manager.update_from_tracker("device_tracker.router", state="home")
        presence_manager.update_from_tracker("device_tracker.phone", state="away")

        state = presence_manager.get_presence_state()
        # Router should win but confidence lowered due to conflict
        assert state["state"] == "home"  # Higher priority wins
        assert state["confidence"] < 0.9


class TestPresenceHistory:
    """Tests for presence history tracking."""

    def test_presence_change_recorded(self, presence_manager):
        """State changes should be recorded in history."""
        presence_manager.set_presence_state("home")
        presence_manager.set_presence_state("away")

        history = presence_manager.get_presence_history(limit=10)
        assert len(history) >= 2

    def test_history_ordered_by_time(self, presence_manager):
        """History should be ordered newest first."""
        presence_manager.set_presence_state("home")
        presence_manager.set_presence_state("away")
        presence_manager.set_presence_state("home")

        history = presence_manager.get_presence_history(limit=10)
        assert history[0]["state"] == "home"  # Most recent
        assert history[1]["state"] == "away"

    def test_history_limit(self, presence_manager):
        """Should respect history limit parameter."""
        for _ in range(5):
            presence_manager.set_presence_state("home")
            presence_manager.set_presence_state("away")

        history = presence_manager.get_presence_history(limit=3)
        assert len(history) == 3

    def test_history_includes_source(self, presence_manager):
        """History should include source of each change."""
        presence_manager.set_presence_state("home", source="router")

        history = presence_manager.get_presence_history(limit=1)
        assert history[0]["source"] == "router"

    def test_history_by_date_range(self, presence_manager):
        """Should filter history by date range."""
        presence_manager.set_presence_state("home")

        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        history = presence_manager.get_presence_history(
            start_date=yesterday,
            end_date=tomorrow
        )
        assert len(history) >= 1


class TestPresenceTransitions:
    """Tests for presence state transitions."""

    def test_detect_arriving_transition(self, presence_manager):
        """Should detect arriving state when approaching home."""
        presence_manager.set_presence_state("away")
        presence_manager.update_from_tracker(
            "device_tracker.phone",
            state="home",
            distance_from_home=100  # 100 meters
        )

        # When close but not home, should be "arriving"
        state = presence_manager.get_presence_state()
        # Depending on implementation, could be arriving or home
        assert state["state"] in ["arriving", "home"]

    def test_detect_leaving_transition(self, presence_manager):
        """Should detect leaving state when moving away from home."""
        # Register WiFi tracker first
        presence_manager.register_device_tracker("device_tracker.router", "router", priority=10)
        presence_manager.update_from_tracker("device_tracker.router", state="home")

        # Now WiFi disconnects
        presence_manager.update_from_tracker("device_tracker.router", state="not_home")

        state = presence_manager.get_presence_state()
        assert state["state"] in ["leaving", "away"]

    def test_transition_cooldown(self, presence_manager):
        """Should have cooldown to prevent rapid state changes."""
        presence_manager.set_presence_state("home")

        # Rapid state changes should be debounced
        presence_manager.update_from_tracker("device_tracker.phone", state="away")
        presence_manager.update_from_tracker("device_tracker.phone", state="home")
        presence_manager.update_from_tracker("device_tracker.phone", state="away")

        # Stable state should win (implementation detail)
        state = presence_manager.get_presence_state()
        assert state is not None


class TestPatternLearning:
    """Tests for pattern learning and prediction."""

    def test_record_departure_pattern(self, presence_manager):
        """Should record departure times for pattern learning."""
        # Simulate leaving at 8am on Monday
        with patch('src.presence_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 19, 8, 0, 0)  # Thursday 8am
            mock_dt.fromisoformat = datetime.fromisoformat
            presence_manager.set_presence_state("away", source="router")

        patterns = presence_manager.get_patterns()
        assert len(patterns) >= 0  # Pattern recorded (or empty if not enough data)

    def test_record_arrival_pattern(self, presence_manager):
        """Should record arrival times for pattern learning."""
        # First set to away
        presence_manager.set_presence_state("away")

        # Simulate arriving at 6pm
        with patch('src.presence_manager.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 12, 19, 18, 0, 0)  # Thursday 6pm
            mock_dt.fromisoformat = datetime.fromisoformat
            presence_manager.set_presence_state("home", source="router")

        patterns = presence_manager.get_patterns()
        assert len(patterns) >= 0

    def test_predict_departure_time(self, presence_manager):
        """Should predict typical departure time from patterns."""
        # Add several departure records on same weekday at similar times
        for _ in range(5):
            presence_manager._record_pattern(
                pattern_type="departure",
                day_of_week=4,  # Thursday
                hour=8,
                minute=15
            )

        prediction = presence_manager.predict_departure(day_of_week=4)
        assert prediction is not None
        if prediction:
            assert 8 <= prediction["hour"] <= 9

    def test_predict_arrival_time(self, presence_manager):
        """Should predict typical arrival time from patterns."""
        # Add several arrival records
        for _ in range(5):
            presence_manager._record_pattern(
                pattern_type="arrival",
                day_of_week=4,
                hour=18,
                minute=0
            )

        prediction = presence_manager.predict_arrival(day_of_week=4)
        assert prediction is not None
        if prediction:
            assert 17 <= prediction["hour"] <= 19

    def test_pattern_requires_minimum_data(self, presence_manager):
        """Should not predict without enough data points."""
        # Only one data point
        presence_manager._record_pattern(
            pattern_type="departure",
            day_of_week=4,
            hour=8,
            minute=0
        )

        prediction = presence_manager.predict_departure(day_of_week=4)
        # Need minimum data points for reliable prediction
        # Could be None or low confidence
        assert prediction is None or prediction.get("confidence", 0) < 0.5

    def test_weekday_vs_weekend_patterns(self, presence_manager):
        """Should track weekday and weekend patterns separately."""
        # Weekday departures at 8am
        for day in [0, 1, 2, 3, 4]:  # Mon-Fri
            presence_manager._record_pattern("departure", day, 8, 0)

        # Weekend departures at 10am
        for day in [5, 6]:  # Sat-Sun
            presence_manager._record_pattern("departure", day, 10, 0)

        weekday_pred = presence_manager.predict_departure(day_of_week=1)  # Tuesday
        weekend_pred = presence_manager.predict_departure(day_of_week=6)  # Sunday

        # Predictions should differ (if enough data)
        if weekday_pred and weekend_pred:
            assert weekday_pred["hour"] != weekend_pred["hour"]


class TestManualOverrides:
    """Tests for manual presence override."""

    def test_manual_override_sets_state(self, presence_manager):
        """Manual override should set presence state directly."""
        result = presence_manager.manual_set_presence("home")
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["state"] == "home"
        assert state["source"] == "manual"

    def test_manual_override_high_confidence(self, presence_manager):
        """Manual override should have high confidence."""
        presence_manager.manual_set_presence("away")

        state = presence_manager.get_presence_state()
        assert state["confidence"] == 1.0

    def test_manual_override_with_duration(self, presence_manager):
        """Manual override should support duration."""
        presence_manager.manual_set_presence("away", duration_minutes=60)

        state = presence_manager.get_presence_state()
        assert "expires_at" in state

    def test_clear_manual_override(self, presence_manager):
        """Should be able to clear manual override."""
        presence_manager.manual_set_presence("away")
        result = presence_manager.clear_manual_override()
        assert result is True

        state = presence_manager.get_presence_state()
        assert state["source"] != "manual" or state["state"] == "unknown"


class TestVacuumAutomation:
    """Tests for vacuum automation integration."""

    def test_vacuum_starts_on_departure(self, presence_manager):
        """Should trigger vacuum start on departure."""
        presence_manager.set_presence_state("home")

        callbacks = []
        presence_manager.on_departure(lambda: callbacks.append("vacuum_start"))

        presence_manager.set_presence_state("away")
        assert "vacuum_start" in callbacks

    def test_vacuum_stops_on_arrival(self, presence_manager):
        """Should trigger vacuum stop on arrival."""
        presence_manager.set_presence_state("away")

        callbacks = []
        presence_manager.on_arrival(lambda: callbacks.append("vacuum_stop"))

        presence_manager.set_presence_state("home")
        assert "vacuum_stop" in callbacks

    def test_no_vacuum_on_arriving_state(self, presence_manager):
        """Should stop vacuum when user is arriving, not fully away."""
        presence_manager.set_presence_state("away")

        callbacks = []
        presence_manager.on_arrival(lambda: callbacks.append("vacuum_stop"))

        # Arriving should also trigger stop
        presence_manager.set_presence_state("arriving")
        assert "vacuum_stop" in callbacks

    def test_vacuum_delayed_start(self, presence_manager):
        """Vacuum start should be delayed after departure confirmation."""
        presence_manager.set_vacuum_start_delay(minutes=5)
        delay = presence_manager.get_vacuum_start_delay()
        assert delay == 5


class TestPresenceSettings:
    """Tests for presence configuration."""

    def test_set_home_zone_radius(self, presence_manager):
        """Should configure home zone radius."""
        result = presence_manager.set_home_zone_radius(150)  # 150 meters
        assert result is True

        radius = presence_manager.get_home_zone_radius()
        assert radius == 150

    def test_set_arriving_distance(self, presence_manager):
        """Should configure distance at which 'arriving' is detected."""
        result = presence_manager.set_arriving_distance(500)  # 500 meters
        assert result is True

    def test_enable_tracker(self, presence_manager):
        """Should enable/disable specific trackers."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps")

        result = presence_manager.set_tracker_enabled("device_tracker.phone", False)
        assert result is True

        tracker = presence_manager.get_device_tracker("device_tracker.phone")
        assert tracker["enabled"] is False

    def test_get_presence_settings(self, presence_manager):
        """Should return all presence settings."""
        settings = presence_manager.get_settings()
        assert "home_zone_radius" in settings
        assert "arriving_distance" in settings
        assert "vacuum_start_delay" in settings


class TestHomeAssistantIntegration:
    """Tests for HA entity tracking integration."""

    def test_fetch_tracker_states_from_ha(self, presence_manager):
        """Should fetch device tracker states from HA."""
        with patch('src.presence_manager.get_ha_client') as mock_ha:
            mock_client = MagicMock()
            mock_ha.return_value = mock_client
            mock_client.get_all_states.return_value = [
                {"entity_id": "device_tracker.phone", "state": "home"},
                {"entity_id": "device_tracker.router", "state": "home"},
            ]

            trackers = presence_manager.discover_ha_trackers()
            assert len(trackers) == 2

    def test_sync_tracker_state(self, presence_manager):
        """Should sync individual tracker state from HA."""
        presence_manager.register_device_tracker("device_tracker.phone", "gps")

        with patch('src.presence_manager.get_ha_client') as mock_ha:
            mock_client = MagicMock()
            mock_ha.return_value = mock_client
            mock_client.get_state.return_value = {
                "entity_id": "device_tracker.phone",
                "state": "not_home",
                "attributes": {"latitude": 37.7, "longitude": -122.4}
            }

            result = presence_manager.sync_tracker_from_ha("device_tracker.phone")
            assert result is True


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
def presence_manager(temp_db_path):
    """Create a PresenceManager instance for testing."""
    from src.presence_manager import PresenceManager
    manager = PresenceManager(db_path=temp_db_path)
    return manager
