"""
Tests for Camera Voice Query Support (WP-11.5)

Voice queries for camera observations:
- "what has the cat been up to today"
- "did I get any packages delivered"
- "who was at the front door this morning"
- "when did Sophie go outside"

Tests cover:
- Time range parsing (today, yesterday, this morning, etc.)
- Object filtering (cat, dog, person, package, etc.)
- Query execution against camera_store
- Summary generation from LLM descriptions
- Voice response formatting
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.camera_store import CameraObservationStore


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_camera_store(tmp_path):
    """Create a mock camera store with test data."""
    db_path = tmp_path / "camera_test.db"
    images_dir = tmp_path / "images"
    store = CameraObservationStore(
        db_path=db_path, images_dir=images_dir, retention_days=14
    )

    # Initialize the database schema first
    with store._get_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                camera_id TEXT NOT NULL,
                image_path TEXT,
                objects_detected TEXT,
                llm_description TEXT,
                confidence REAL,
                motion_triggered BOOLEAN DEFAULT FALSE,
                processing_time_ms INTEGER,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Add test observations
    now = datetime.now()

    # Add test observations for different objects at different times
    store.add_observation(
        camera_id="camera.living_room",
        timestamp=now - timedelta(hours=2),
        objects_detected=["cat"],
        llm_description="A gray cat is sitting on the couch looking out the window.",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.living_room",
        timestamp=now - timedelta(hours=5),
        objects_detected=["cat", "person"],
        llm_description="A person is petting the gray cat on the floor near the TV.",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.front_door",
        timestamp=now - timedelta(hours=3),
        objects_detected=["person", "package"],
        llm_description="A delivery person is placing a package at the front door.",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.front_door",
        timestamp=now - timedelta(hours=1),
        objects_detected=["person"],
        llm_description="A woman is entering through the front door.",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.backyard",
        timestamp=now - timedelta(hours=4),
        objects_detected=["dog"],
        llm_description="A brown dog named Sophie is running in the backyard chasing a ball.",
        motion_triggered=True,
    )

    store.add_observation(
        camera_id="camera.backyard",
        timestamp=now - timedelta(hours=6),
        objects_detected=["dog", "person"],
        llm_description="Sophie the dog is being let outside by a person.",
        motion_triggered=True,
    )

    return store


# =============================================================================
# Time Range Parsing Tests
# =============================================================================


class TestTimeRangeParsing:
    """Tests for parsing natural language time ranges."""

    def test_parse_today(self):
        """Parse 'today' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("today")

        now = datetime.now()
        assert start.date() == now.date()
        assert start.hour == 0
        assert start.minute == 0
        assert end.date() == now.date()

    def test_parse_yesterday(self):
        """Parse 'yesterday' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("yesterday")

        yesterday = datetime.now() - timedelta(days=1)
        assert start.date() == yesterday.date()
        assert end.date() == yesterday.date()

    def test_parse_this_morning(self):
        """Parse 'this morning' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("this morning")

        now = datetime.now()
        assert start.date() == now.date()
        assert start.hour == 0
        assert end.hour <= 12

    def test_parse_this_afternoon(self):
        """Parse 'this afternoon' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("this afternoon")

        now = datetime.now()
        # If it's early morning (before noon), afternoon refers to yesterday
        if now.hour < 12:
            yesterday = now - timedelta(days=1)
            assert start.date() == yesterday.date()
        else:
            assert start.date() == now.date()
        assert start.hour >= 12

    def test_parse_this_evening(self):
        """Parse 'this evening' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("this evening")

        now = datetime.now()
        # If it's before evening, refers to yesterday evening
        if now.hour < 17:
            yesterday = now - timedelta(days=1)
            assert start.date() == yesterday.date()
        else:
            assert start.date() == now.date()
        assert start.hour >= 17

    def test_parse_last_hour(self):
        """Parse 'last hour' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("last hour")

        now = datetime.now()
        assert (now - start).total_seconds() <= 3700  # ~1 hour with buffer

    def test_parse_last_n_hours(self):
        """Parse 'last 3 hours' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("last 3 hours")

        now = datetime.now()
        diff_seconds = (now - start).total_seconds()
        assert diff_seconds <= 3 * 3600 + 100  # ~3 hours with buffer

    def test_parse_this_week(self):
        """Parse 'this week' time range."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("this week")

        now = datetime.now()
        # Start should be Monday of this week
        assert start.weekday() == 0
        assert end.date() == now.date()

    def test_parse_default_today(self):
        """Default to today when no time specified."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("")

        now = datetime.now()
        assert start.date() == now.date()

    def test_parse_specific_date(self):
        """Parse specific date reference."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("on December 25th")

        # Should handle relative date parsing
        assert start.month == 12
        assert start.day == 25


# =============================================================================
# Object Type Normalization Tests
# =============================================================================


class TestObjectTypeNormalization:
    """Tests for normalizing object type queries."""

    def test_normalize_cat(self):
        """Normalize cat-related terms."""
        from tools.camera_query import normalize_object_type

        assert normalize_object_type("cat") == "cat"
        assert normalize_object_type("kitty") == "cat"
        assert normalize_object_type("kitten") == "cat"
        assert normalize_object_type("the cat") == "cat"

    def test_normalize_dog(self):
        """Normalize dog-related terms."""
        from tools.camera_query import normalize_object_type

        assert normalize_object_type("dog") == "dog"
        assert normalize_object_type("puppy") == "dog"
        assert normalize_object_type("doggy") == "dog"
        assert normalize_object_type("Sophie") == "dog"  # Named pet

    def test_normalize_person(self):
        """Normalize person-related terms."""
        from tools.camera_query import normalize_object_type

        assert normalize_object_type("person") == "person"
        assert normalize_object_type("someone") == "person"
        assert normalize_object_type("anyone") == "person"
        assert normalize_object_type("somebody") == "person"

    def test_normalize_package(self):
        """Normalize package-related terms."""
        from tools.camera_query import normalize_object_type

        assert normalize_object_type("package") == "package"
        assert normalize_object_type("delivery") == "package"
        assert normalize_object_type("parcel") == "package"
        assert normalize_object_type("packages") == "package"

    def test_normalize_vehicle(self):
        """Normalize vehicle-related terms."""
        from tools.camera_query import normalize_object_type

        assert normalize_object_type("car") == "vehicle"
        assert normalize_object_type("truck") == "vehicle"
        assert normalize_object_type("vehicle") == "vehicle"


# =============================================================================
# Query Parsing Tests
# =============================================================================


class TestQueryParsing:
    """Tests for parsing natural language camera queries."""

    def test_parse_cat_query(self):
        """Parse 'what has the cat been up to today'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("what has the cat been up to today")

        assert result["object_type"] == "cat"
        assert result["time_range"] is not None

    def test_parse_package_query(self):
        """Parse 'did I get any packages delivered'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("did I get any packages delivered")

        assert result["object_type"] == "package"

    def test_parse_front_door_query(self):
        """Parse 'who was at the front door this morning'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("who was at the front door this morning")

        assert result["object_type"] == "person"
        assert "morning" in result.get("time_context", "") or result.get("time_range") is not None
        assert result.get("camera_filter") == "front_door" or "front_door" in result.get("camera_hint", "")

    def test_parse_dog_outdoors_query(self):
        """Parse 'when did Sophie go outside'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("when did Sophie go outside")

        assert result["object_type"] == "dog"

    def test_parse_anyone_home_query(self):
        """Parse 'has anyone been home today'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("has anyone been home today")

        assert result["object_type"] == "person"

    def test_parse_motion_query(self):
        """Parse 'any activity in the living room'."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("any activity in the living room")

        # Activity queries should return all objects or motion events
        assert result.get("camera_filter") == "living_room" or "living_room" in result.get("camera_hint", "")


# =============================================================================
# Query Execution Tests
# =============================================================================


class TestQueryExecution:
    """Tests for executing camera queries against the store."""

    def test_query_cat_today(self, mock_camera_store):
        """Query for cat observations today."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="cat",
            time_range="today",
        )

        assert result["success"] is True
        assert len(result["observations"]) >= 1
        assert all("cat" in obs["objects_detected"] for obs in result["observations"])

    def test_query_package_delivery(self, mock_camera_store):
        """Query for package deliveries."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="package",
            time_range="today",
        )

        assert result["success"] is True
        assert len(result["observations"]) >= 1
        assert any("package" in obs["objects_detected"] for obs in result["observations"])

    def test_query_dog_outdoors(self, mock_camera_store):
        """Query for dog going outside."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="dog",
            camera_filter="backyard",
            time_range="today",
        )

        assert result["success"] is True
        assert len(result["observations"]) >= 1

    def test_query_front_door_visitors(self, mock_camera_store):
        """Query for visitors at front door."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="person",
            camera_filter="front_door",
            time_range="today",
        )

        assert result["success"] is True
        assert len(result["observations"]) >= 1

    def test_query_no_results(self, mock_camera_store):
        """Query with no matching results."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="vehicle",
            time_range="today",
        )

        assert result["success"] is True
        assert len(result["observations"]) == 0

    def test_query_with_limit(self, mock_camera_store):
        """Query with result limit."""
        from tools.camera_query import execute_camera_query

        result = execute_camera_query(
            store=mock_camera_store,
            object_type="person",
            time_range="today",
            limit=2,
        )

        assert result["success"] is True
        assert len(result["observations"]) <= 2


# =============================================================================
# Summary Generation Tests
# =============================================================================


class TestSummaryGeneration:
    """Tests for generating voice-friendly summaries."""

    def test_generate_cat_summary(self, mock_camera_store):
        """Generate summary for cat observations."""
        from tools.camera_query import generate_activity_summary

        observations = mock_camera_store.query_by_object("cat")

        summary = generate_activity_summary(
            observations=observations,
            object_type="cat",
            time_range="today",
        )

        assert isinstance(summary, str)
        assert len(summary) > 0
        # Summary should mention the cat and activities
        summary_lower = summary.lower()
        assert "cat" in summary_lower or "seen" in summary_lower

    def test_generate_package_summary(self, mock_camera_store):
        """Generate summary for package deliveries."""
        from tools.camera_query import generate_activity_summary

        observations = mock_camera_store.query_by_object("package")

        summary = generate_activity_summary(
            observations=observations,
            object_type="package",
            time_range="today",
        )

        assert isinstance(summary, str)
        assert "package" in summary.lower() or "deliver" in summary.lower()

    def test_generate_no_results_summary(self):
        """Generate summary when no observations found."""
        from tools.camera_query import generate_activity_summary

        summary = generate_activity_summary(
            observations=[],
            object_type="cat",
            time_range="today",
        )

        assert isinstance(summary, str)
        assert "no" in summary.lower() or "didn't" in summary.lower() or "not" in summary.lower()

    def test_summary_includes_times(self, mock_camera_store):
        """Summary includes approximate times."""
        from tools.camera_query import generate_activity_summary

        observations = mock_camera_store.query_by_object("cat")

        summary = generate_activity_summary(
            observations=observations,
            object_type="cat",
            time_range="today",
        )

        # Should mention times like "2 hours ago" or specific times
        time_indicators = ["hour", "minute", "am", "pm", "ago", "at"]
        assert any(ind in summary.lower() for ind in time_indicators)

    def test_summary_mentions_locations(self, mock_camera_store):
        """Summary mentions camera locations."""
        from tools.camera_query import generate_activity_summary

        observations = mock_camera_store.query_by_object("cat")

        summary = generate_activity_summary(
            observations=observations,
            object_type="cat",
            time_range="today",
        )

        # Should mention room names
        location_indicators = ["living room", "room", "front", "back", "camera"]
        assert any(ind in summary.lower() for ind in location_indicators)


# =============================================================================
# Voice Response Formatting Tests
# =============================================================================


class TestVoiceResponseFormatting:
    """Tests for formatting responses for voice output."""

    def test_format_for_voice_short(self):
        """Format short response for voice."""
        from tools.camera_query import format_for_voice

        response = format_for_voice(
            "The cat was seen at 2pm in the living room.",
            max_length=100,
        )

        assert len(response) <= 100
        assert response.endswith(".")

    def test_format_for_voice_truncation(self):
        """Truncate long response appropriately."""
        from tools.camera_query import format_for_voice

        long_summary = (
            "The cat was seen 5 times today. "
            "At 8am it was in the kitchen eating breakfast. "
            "At 10am it was on the couch sleeping. "
            "At 12pm it was chasing a toy. "
            "At 2pm it was by the window watching birds. "
            "At 4pm it was back on the couch sleeping again."
        )

        response = format_for_voice(long_summary, max_length=100)

        assert len(response) <= 100

    def test_format_includes_count(self, mock_camera_store):
        """Response includes observation count when many results."""
        from tools.camera_query import format_for_voice, generate_activity_summary

        observations = mock_camera_store.query_by_object("cat")

        summary = generate_activity_summary(
            observations=observations,
            object_type="cat",
            time_range="today",
        )

        # If multiple observations, should mention count
        if len(observations) > 1:
            assert any(str(len(observations)) in summary or "times" in summary.lower() for _ in [1])

    def test_format_natural_language(self):
        """Response uses natural language."""
        from tools.camera_query import format_for_voice

        response = format_for_voice(
            "The cat was seen 3 times: 8am in kitchen, 2pm on couch, 6pm by food bowl"
        )

        # Should be readable natural language
        assert not response.startswith("{")  # Not JSON
        assert not response.startswith("[")  # Not array


# =============================================================================
# Tool Integration Tests
# =============================================================================


class TestCameraQueryTool:
    """Tests for the camera query tool integration."""

    def test_tool_definition_exists(self):
        """Camera query tool is defined."""
        from tools.camera_query import CAMERA_QUERY_TOOLS

        tool_names = [t["name"] for t in CAMERA_QUERY_TOOLS]
        assert "query_camera_activity" in tool_names

    def test_tool_has_required_schema(self):
        """Tool has required input schema."""
        from tools.camera_query import CAMERA_QUERY_TOOLS

        query_tool = next(t for t in CAMERA_QUERY_TOOLS if t["name"] == "query_camera_activity")

        assert "input_schema" in query_tool
        assert "properties" in query_tool["input_schema"]
        assert "query" in query_tool["input_schema"]["properties"]

    def test_execute_tool_query(self, mock_camera_store):
        """Execute camera query tool."""
        from tools.camera_query import execute_camera_query_tool

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = execute_camera_query_tool(
                tool_name="query_camera_activity",
                tool_input={"query": "what has the cat been up to today"},
            )

        assert result["success"] is True
        assert "response" in result

    def test_execute_tool_invalid_name(self):
        """Handle invalid tool name."""
        from tools.camera_query import execute_camera_query_tool

        result = execute_camera_query_tool(
            tool_name="invalid_tool",
            tool_input={},
        )

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# End-to-End Voice Query Tests
# =============================================================================


class TestEndToEndVoiceQueries:
    """End-to-end tests for voice queries."""

    def test_cat_activity_voice_query(self, mock_camera_store):
        """E2E: 'what has the cat been up to today'."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = handle_voice_query("what has the cat been up to today")

        assert result["success"] is True
        assert "response" in result
        assert "cat" in result["response"].lower()

    def test_package_delivery_voice_query(self, mock_camera_store):
        """E2E: 'did I get any packages delivered'."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = handle_voice_query("did I get any packages delivered")

        assert result["success"] is True
        assert "response" in result

    def test_front_door_voice_query(self, mock_camera_store):
        """E2E: 'who was at the front door this morning'."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = handle_voice_query("who was at the front door this morning")

        assert result["success"] is True
        assert "response" in result

    def test_dog_outdoor_voice_query(self, mock_camera_store):
        """E2E: 'when did Sophie go outside'."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = handle_voice_query("when did Sophie go outside")

        assert result["success"] is True
        assert "response" in result

    def test_activity_summary_voice_query(self, mock_camera_store):
        """E2E: 'what activity was there today'."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", return_value=mock_camera_store):
            result = handle_voice_query("what activity was there today")

        assert result["success"] is True
        assert "response" in result

    def test_error_handling(self):
        """E2E: Handle errors gracefully."""
        from tools.camera_query import handle_voice_query

        with patch("tools.camera_query.get_camera_store", side_effect=Exception("DB error")):
            result = handle_voice_query("what has the cat been up to")

        assert result["success"] is False
        assert "error" in result


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_query(self):
        """Handle empty query."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("")

        # Should return default or error
        assert result is not None

    def test_ambiguous_query(self):
        """Handle ambiguous query."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("what happened")

        # Should handle gracefully
        assert result is not None

    def test_future_time_reference(self):
        """Handle future time reference."""
        from tools.camera_query import parse_time_range

        # "tomorrow" should either be handled or default to today
        start, end = parse_time_range("tomorrow")

        # Should not crash, may return today or empty range
        assert start is not None

    def test_very_old_time_reference(self):
        """Handle very old time reference."""
        from tools.camera_query import parse_time_range

        start, end = parse_time_range("last month")

        # Should handle but may limit to retention period
        assert start is not None

    def test_multiple_objects_in_query(self):
        """Handle query mentioning multiple objects."""
        from tools.camera_query import parse_camera_query

        result = parse_camera_query("did the cat or dog go outside")

        # Should extract at least one object type
        assert result.get("object_type") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
