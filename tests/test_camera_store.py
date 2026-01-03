"""
Tests for src/camera_store.py - Camera Observation Storage

Tests SQLite database operations for camera events, image file management,
query methods for voice commands, and cleanup/retention policies.

WP-11.2: Storage System (SQLite + Image Retention)
"""

import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# =============================================================================
# Camera Store Fixtures
# =============================================================================


@pytest.fixture
def camera_store(temp_data_dir, monkeypatch):
    """
    Create an isolated camera observation store for testing.

    Uses temp directory for both database and images.
    """
    db_path = temp_data_dir / "test_camera_observations.db"
    images_dir = temp_data_dir / "camera_images"

    # Patch module-level paths
    monkeypatch.setattr("src.camera_store.CAMERA_DB_PATH", db_path)
    monkeypatch.setattr("src.camera_store.CAMERA_IMAGES_DIR", images_dir)

    # Import and initialize
    from src.camera_store import CameraObservationStore, initialize_database

    initialize_database()
    store = CameraObservationStore(db_path=db_path, images_dir=images_dir)

    yield store


@pytest.fixture
def sample_image_data():
    """Sample image bytes for testing."""
    # Minimal valid JPEG header for testing
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100


@pytest.fixture
def sample_observations():
    """Sample observation data for testing."""
    now = datetime.now()
    return [
        {
            "camera_id": "camera.front_door_live_view",
            "timestamp": now - timedelta(hours=1),
            "objects_detected": ["person", "cat"],
            "llm_description": "A person walking by the front door with a cat following behind.",
            "confidence": 0.95,
            "motion_triggered": True,
        },
        {
            "camera_id": "camera.living_room_live_view",
            "timestamp": now - timedelta(hours=2),
            "objects_detected": ["cat"],
            "llm_description": "Cat sleeping on the couch.",
            "confidence": 0.88,
            "motion_triggered": False,
        },
        {
            "camera_id": "camera.front_door_live_view",
            "timestamp": now - timedelta(hours=3),
            "objects_detected": ["dog", "person"],
            "llm_description": "Person walking the dog past the front door.",
            "confidence": 0.92,
            "motion_triggered": True,
        },
        {
            "camera_id": "camera.living_room_live_view",
            "timestamp": now - timedelta(days=2),
            "objects_detected": ["cat", "toy"],
            "llm_description": "Cat playing with a toy mouse.",
            "confidence": 0.85,
            "motion_triggered": True,
        },
    ]


# =============================================================================
# Database Initialization Tests
# =============================================================================


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""

    def test_database_file_created(self, camera_store, temp_data_dir):
        """Database file should be created on initialization."""
        db_path = temp_data_dir / "test_camera_observations.db"
        assert db_path.exists()

    def test_camera_events_table_exists(self, camera_store):
        """Camera events table should exist after initialization."""
        with camera_store._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='camera_events'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_indexes_created(self, camera_store):
        """Required indexes should exist."""
        with camera_store._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_camera%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            assert "idx_camera_events_timestamp" in indexes
            assert "idx_camera_events_camera_id" in indexes
            assert "idx_camera_events_camera_timestamp" in indexes

    def test_images_directory_created(self, camera_store):
        """Images directory should be created on initialization."""
        assert camera_store.images_dir.exists()
        assert camera_store.images_dir.is_dir()


# =============================================================================
# CRUD Operations Tests
# =============================================================================


class TestAddObservation:
    """Test adding camera observations."""

    def test_add_observation_minimal(self, camera_store):
        """Should add observation with minimal data."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test_camera",
        )

        assert obs_id is not None
        assert obs_id > 0

        # Verify it was stored
        obs = camera_store.get_observation(obs_id)
        assert obs is not None
        assert obs["camera_id"] == "camera.test_camera"

    def test_add_observation_full(self, camera_store, sample_image_data):
        """Should add observation with all fields."""
        timestamp = datetime.now()

        obs_id = camera_store.add_observation(
            camera_id="camera.front_door",
            timestamp=timestamp,
            image_data=sample_image_data,
            objects_detected=["person", "cat"],
            llm_description="A person with a cat at the door.",
            confidence=0.95,
            motion_triggered=True,
            processing_time_ms=250,
            metadata={"model": "yolov8", "resolution": "1920x1080"},
        )

        obs = camera_store.get_observation(obs_id)

        assert obs["camera_id"] == "camera.front_door"
        assert obs["objects_detected"] == ["person", "cat"]
        assert obs["llm_description"] == "A person with a cat at the door."
        assert obs["confidence"] == 0.95
        assert obs["motion_triggered"] == 1  # SQLite stores as int
        assert obs["processing_time_ms"] == 250
        assert obs["metadata"]["model"] == "yolov8"
        assert obs["image_path"] is not None

    def test_add_observation_saves_image(self, camera_store, sample_image_data):
        """Should save image file when image_data provided."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test_camera",
            image_data=sample_image_data,
        )

        obs = camera_store.get_observation(obs_id)
        image_path = Path(obs["image_path"])

        assert image_path.exists()
        assert image_path.read_bytes() == sample_image_data

    def test_add_observation_default_timestamp(self, camera_store):
        """Should use current time if timestamp not provided."""
        before = datetime.now()
        obs_id = camera_store.add_observation(camera_id="camera.test")
        after = datetime.now()

        obs = camera_store.get_observation(obs_id)
        obs_time = datetime.fromisoformat(obs["timestamp"])

        assert before <= obs_time <= after


class TestGetObservation:
    """Test retrieving observations."""

    def test_get_existing_observation(self, camera_store):
        """Should return observation by ID."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            llm_description="Test description",
        )

        result = camera_store.get_observation(obs_id)

        assert result is not None
        assert result["id"] == obs_id
        assert result["llm_description"] == "Test description"

    def test_get_nonexistent_observation(self, camera_store):
        """Should return None for nonexistent ID."""
        result = camera_store.get_observation(99999)
        assert result is None

    def test_get_observation_parses_json(self, camera_store):
        """Should parse JSON fields correctly."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            objects_detected=["cat", "dog"],
            metadata={"key": "value"},
        )

        result = camera_store.get_observation(obs_id)

        assert isinstance(result["objects_detected"], list)
        assert "cat" in result["objects_detected"]
        assert isinstance(result["metadata"], dict)
        assert result["metadata"]["key"] == "value"


class TestGetObservations:
    """Test querying multiple observations."""

    def test_get_all_observations(self, camera_store, sample_observations):
        """Should return all observations."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.get_observations()

        assert len(results) == len(sample_observations)

    def test_get_observations_filter_camera(self, camera_store, sample_observations):
        """Should filter by camera ID."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.get_observations(
            camera_id="camera.front_door_live_view"
        )

        assert len(results) == 2
        for obs in results:
            assert obs["camera_id"] == "camera.front_door_live_view"

    def test_get_observations_filter_time_range(self, camera_store, sample_observations):
        """Should filter by time range."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Get observations from last 4 hours
        start = datetime.now() - timedelta(hours=4)
        end = datetime.now()

        results = camera_store.get_observations(
            start_time=start,
            end_time=end,
        )

        # Should get the 3 recent ones (1h, 2h, 3h ago)
        assert len(results) == 3

    def test_get_observations_motion_only(self, camera_store, sample_observations):
        """Should filter motion-triggered only."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.get_observations(motion_only=True)

        assert len(results) == 3  # 3 out of 4 are motion triggered
        for obs in results:
            assert obs["motion_triggered"] == 1

    def test_get_observations_limit(self, camera_store, sample_observations):
        """Should respect limit parameter."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.get_observations(limit=2)

        assert len(results) == 2

    def test_get_observations_offset(self, camera_store, sample_observations):
        """Should respect offset parameter."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        all_results = camera_store.get_observations()
        offset_results = camera_store.get_observations(offset=2)

        assert len(offset_results) == len(all_results) - 2


class TestDeleteObservation:
    """Test deleting observations."""

    def test_delete_observation(self, camera_store):
        """Should delete observation by ID."""
        obs_id = camera_store.add_observation(camera_id="camera.test")

        result = camera_store.delete_observation(obs_id)

        assert result is True
        assert camera_store.get_observation(obs_id) is None

    def test_delete_observation_with_image(self, camera_store, sample_image_data):
        """Should delete associated image file."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            image_data=sample_image_data,
        )

        obs = camera_store.get_observation(obs_id)
        image_path = Path(obs["image_path"])
        assert image_path.exists()

        camera_store.delete_observation(obs_id)

        assert not image_path.exists()

    def test_delete_nonexistent_observation(self, camera_store):
        """Should return False for nonexistent ID."""
        result = camera_store.delete_observation(99999)
        assert result is False


class TestUpdateObservation:
    """Test updating observations."""

    def test_update_description(self, camera_store):
        """Should update LLM description."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            llm_description="Original",
        )

        result = camera_store.update_observation(
            obs_id, llm_description="Updated description"
        )

        assert result is True
        obs = camera_store.get_observation(obs_id)
        assert obs["llm_description"] == "Updated description"

    def test_update_objects(self, camera_store):
        """Should update objects detected."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            objects_detected=["cat"],
        )

        camera_store.update_observation(
            obs_id, objects_detected=["cat", "dog", "person"]
        )

        obs = camera_store.get_observation(obs_id)
        assert obs["objects_detected"] == ["cat", "dog", "person"]

    def test_update_confidence(self, camera_store):
        """Should update confidence score."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            confidence=0.5,
        )

        camera_store.update_observation(obs_id, confidence=0.95)

        obs = camera_store.get_observation(obs_id)
        assert obs["confidence"] == 0.95

    def test_update_no_changes(self, camera_store):
        """Should return False when no updates provided."""
        obs_id = camera_store.add_observation(camera_id="camera.test")
        result = camera_store.update_observation(obs_id)
        assert result is False


# =============================================================================
# Voice Command Query Tests
# =============================================================================


class TestQueryByObject:
    """Test object-based queries for voice commands."""

    def test_query_by_single_object(self, camera_store, sample_observations):
        """Should find observations containing specific object."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.query_by_object("cat")

        assert len(results) == 3  # 3 observations have cat

    def test_query_by_object_case_insensitive(self, camera_store):
        """Object queries are case-insensitive (SQLite LIKE default)."""
        camera_store.add_observation(
            camera_id="camera.test",
            objects_detected=["Cat"],
        )

        # Both should find the observation (LIKE is case-insensitive in SQLite)
        results = camera_store.query_by_object("Cat")
        assert len(results) == 1

        results = camera_store.query_by_object("cat")
        assert len(results) == 1

    def test_query_by_object_with_time_filter(self, camera_store, sample_observations):
        """Should filter by object and time."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Only get cats in last 3 hours
        start = datetime.now() - timedelta(hours=3)
        results = camera_store.query_by_object("cat", start_time=start)

        # Only 2 cat observations in last 3 hours
        assert len(results) == 2

    def test_query_by_object_with_camera_filter(self, camera_store, sample_observations):
        """Should filter by object and camera."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.query_by_object(
            "cat", camera_id="camera.living_room_live_view"
        )

        assert len(results) == 2


class TestActivitySummary:
    """Test activity summary generation."""

    def test_activity_summary_counts(self, camera_store, sample_observations):
        """Should return correct event counts."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Default is last 24h, 4th observation is 2 days old
        summary = camera_store.get_activity_summary()

        assert summary["total_events"] == 3  # 3 in last 24h
        assert summary["motion_events"] == 2  # 2 motion events in last 24h

    def test_activity_summary_object_counts(self, camera_store, sample_observations):
        """Should count objects correctly."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Query all time to include all observations
        start = datetime.now() - timedelta(days=30)
        summary = camera_store.get_activity_summary(start_time=start)

        assert "cat" in summary["objects_detected"]
        assert summary["objects_detected"]["cat"] == 3
        assert summary["objects_detected"]["person"] == 2

    def test_activity_summary_top_objects(self, camera_store, sample_observations):
        """Should return top objects sorted by count."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Query all time
        start = datetime.now() - timedelta(days=30)
        summary = camera_store.get_activity_summary(start_time=start)

        top = summary["top_objects"]
        assert len(top) > 0
        # Cat should be first (3 occurrences)
        assert top[0][0] == "cat"
        assert top[0][1] == 3

    def test_activity_summary_time_filter(self, camera_store, sample_observations):
        """Should respect time range filter."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # Last 90 minutes - should only get the 1 observation from 1h ago
        start = datetime.now() - timedelta(minutes=90)
        summary = camera_store.get_activity_summary(start_time=start)

        assert summary["total_events"] == 1


class TestRecentDescriptions:
    """Test getting recent LLM descriptions."""

    def test_get_recent_descriptions(self, camera_store, sample_observations):
        """Should return observations with descriptions."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        # 4th observation is 2 days old, outside 24h window
        results = camera_store.get_recent_descriptions(hours=24)

        assert len(results) == 3  # 3 in last 24h
        for obs in results:
            assert obs["llm_description"] is not None

    def test_get_recent_descriptions_excludes_null(self, camera_store):
        """Should not return observations without descriptions."""
        camera_store.add_observation(camera_id="camera.test")  # No description
        camera_store.add_observation(
            camera_id="camera.test",
            llm_description="Has description",
        )

        results = camera_store.get_recent_descriptions()

        assert len(results) == 1

    def test_get_recent_descriptions_limit(self, camera_store, sample_observations):
        """Should respect limit parameter."""
        for obs in sample_observations:
            camera_store.add_observation(**obs)

        results = camera_store.get_recent_descriptions(limit=2)

        assert len(results) == 2


# =============================================================================
# Image File Management Tests
# =============================================================================


class TestImageStorage:
    """Test image file storage and retrieval."""

    def test_image_directory_structure(self, camera_store, sample_image_data):
        """Should organize images by camera and date."""
        timestamp = datetime(2025, 12, 27, 14, 30, 45)

        camera_store.add_observation(
            camera_id="camera.front_door",
            timestamp=timestamp,
            image_data=sample_image_data,
        )

        expected_dir = (
            camera_store.images_dir / "camera_front_door" / "2025-12-27"
        )
        assert expected_dir.exists()

        # Check a file was created in the directory
        files = list(expected_dir.glob("*.jpg"))
        assert len(files) == 1

    def test_get_image_returns_data(self, camera_store, sample_image_data):
        """Should retrieve image data by observation ID."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            image_data=sample_image_data,
        )

        image_data = camera_store.get_image(obs_id)

        assert image_data == sample_image_data

    def test_get_image_missing_observation(self, camera_store):
        """Should return None for nonexistent observation."""
        result = camera_store.get_image(99999)
        assert result is None

    def test_get_image_no_image_path(self, camera_store):
        """Should return None for observation without image."""
        obs_id = camera_store.add_observation(camera_id="camera.test")
        result = camera_store.get_image(obs_id)
        assert result is None


# =============================================================================
# Retention and Cleanup Tests
# =============================================================================


class TestCleanupOldImages:
    """Test image retention and cleanup."""

    def test_cleanup_removes_old_directories(self, camera_store, sample_image_data):
        """Should remove directories older than retention period."""
        # Create old image (20 days ago)
        old_timestamp = datetime.now() - timedelta(days=20)
        camera_store.add_observation(
            camera_id="camera.test",
            timestamp=old_timestamp,
            image_data=sample_image_data,
        )

        # Create recent image
        camera_store.add_observation(
            camera_id="camera.test",
            image_data=sample_image_data,
        )

        result = camera_store.cleanup_old_images()

        assert result["deleted_files"] == 1
        assert result["deleted_records"] == 1

    def test_cleanup_preserves_recent_images(self, camera_store, sample_image_data):
        """Should not remove images within retention period."""
        # Create image from 5 days ago (within 14-day default)
        recent_timestamp = datetime.now() - timedelta(days=5)
        camera_store.add_observation(
            camera_id="camera.test",
            timestamp=recent_timestamp,
            image_data=sample_image_data,
        )

        result = camera_store.cleanup_old_images()

        assert result["deleted_files"] == 0

    def test_cleanup_dry_run(self, camera_store, sample_image_data):
        """Dry run should not actually delete files."""
        old_timestamp = datetime.now() - timedelta(days=20)
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            timestamp=old_timestamp,
            image_data=sample_image_data,
        )

        obs = camera_store.get_observation(obs_id)
        image_path = Path(obs["image_path"])

        result = camera_store.cleanup_old_images(dry_run=True)

        assert result["dry_run"] is True
        assert result["deleted_files"] == 1
        # But file should still exist
        assert image_path.exists()

    def test_cleanup_deletes_database_records(self, camera_store):
        """Should delete old database records too."""
        old_timestamp = datetime.now() - timedelta(days=20)
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            timestamp=old_timestamp,
        )

        camera_store.cleanup_old_images()

        assert camera_store.get_observation(obs_id) is None


# =============================================================================
# Disk Space Monitoring Tests
# =============================================================================


class TestStorageStats:
    """Test storage statistics."""

    def test_storage_stats_counts_files(self, camera_store, sample_image_data):
        """Should count image files correctly."""
        for _ in range(3):
            camera_store.add_observation(
                camera_id="camera.test",
                image_data=sample_image_data,
            )

        stats = camera_store.get_storage_stats()

        assert stats["image_files"] == 3
        assert stats["image_bytes"] > 0

    def test_storage_stats_includes_database(self, camera_store):
        """Should include database size."""
        camera_store.add_observation(camera_id="camera.test")

        stats = camera_store.get_storage_stats()

        assert stats["database_bytes"] > 0

    def test_storage_stats_disk_usage(self, camera_store):
        """Should include disk usage info."""
        stats = camera_store.get_storage_stats()

        assert stats["disk_total_bytes"] > 0
        assert stats["disk_used_bytes"] > 0
        assert stats["disk_free_bytes"] > 0
        assert 0 <= stats["disk_used_percent"] <= 100

    def test_storage_stats_alert_status_ok(self, camera_store):
        """Should show ok status when plenty of space."""
        stats = camera_store.get_storage_stats()
        # Temp directory should have plenty of space
        assert stats["alert_status"] == "ok"


class TestDiskSpaceAlert:
    """Test disk space alerting."""

    def test_no_alert_when_ok(self, camera_store):
        """Should return None when disk space is fine."""
        alert = camera_store.check_disk_space_alert()
        assert alert is None

    def test_alert_when_warning(self, camera_store, monkeypatch):
        """Should return warning alert when threshold exceeded."""
        # Mock disk_usage to return high usage
        def mock_disk_usage(path):
            return (100 * 1024**3, 85 * 1024**3, 15 * 1024**3)  # 85% used

        monkeypatch.setattr(shutil, "disk_usage", mock_disk_usage)

        alert = camera_store.check_disk_space_alert()

        assert alert is not None
        assert alert["severity"] == "warning"

    def test_alert_when_critical(self, camera_store, monkeypatch):
        """Should return critical alert when critically low."""
        def mock_disk_usage(path):
            return (100 * 1024**3, 95 * 1024**3, 5 * 1024**3)  # 95% used

        monkeypatch.setattr(shutil, "disk_usage", mock_disk_usage)

        alert = camera_store.check_disk_space_alert()

        assert alert is not None
        assert alert["severity"] == "critical"


# =============================================================================
# Module-Level Convenience Functions Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_add_camera_observation(self, camera_store, monkeypatch, temp_data_dir):
        """Should work through convenience function."""
        from src import camera_store as cs_module

        # Reset global store
        cs_module._store = camera_store

        obs_id = cs_module.add_camera_observation(
            camera_id="camera.test",
            llm_description="Test via convenience function",
        )

        assert obs_id > 0

    def test_query_camera_by_object(self, camera_store, monkeypatch, sample_observations):
        """Should work through convenience function."""
        from src import camera_store as cs_module

        for obs in sample_observations:
            camera_store.add_observation(**obs)

        cs_module._store = camera_store

        results = cs_module.query_camera_by_object("cat")
        assert len(results) == 3

    def test_get_camera_activity_summary(self, camera_store, monkeypatch, sample_observations):
        """Should work through convenience function."""
        from src import camera_store as cs_module

        for obs in sample_observations:
            camera_store.add_observation(**obs)

        cs_module._store = camera_store

        # Default is last 24h, 4th observation is 2 days old
        summary = cs_module.get_camera_activity_summary()
        assert summary["total_events"] == 3


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_special_characters_in_camera_id(self, camera_store, sample_image_data):
        """Should handle special characters in camera ID."""
        obs_id = camera_store.add_observation(
            camera_id="camera.front_door_live_view/special",
            image_data=sample_image_data,
        )

        obs = camera_store.get_observation(obs_id)
        assert obs is not None
        # Image should be saved with sanitized path
        assert Path(obs["image_path"]).exists()

    def test_empty_objects_list(self, camera_store):
        """Should handle empty objects list."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            objects_detected=[],
        )

        obs = camera_store.get_observation(obs_id)
        # Empty list stored as JSON "[]", parsed back as empty list
        assert obs["objects_detected"] == [] or obs["objects_detected"] is None

    def test_unicode_in_description(self, camera_store):
        """Should handle unicode in descriptions."""
        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            llm_description="Cat sleeping on the couch 🐱 très mignon",
        )

        obs = camera_store.get_observation(obs_id)
        assert "🐱" in obs["llm_description"]
        assert "très" in obs["llm_description"]

    def test_very_long_description(self, camera_store):
        """Should handle very long descriptions."""
        long_desc = "This is a very long description. " * 1000

        obs_id = camera_store.add_observation(
            camera_id="camera.test",
            llm_description=long_desc,
        )

        obs = camera_store.get_observation(obs_id)
        assert obs["llm_description"] == long_desc

    def test_concurrent_access(self, camera_store):
        """Should handle concurrent database access."""
        import threading

        results = []
        errors = []

        def add_observation(thread_id):
            try:
                obs_id = camera_store.add_observation(
                    camera_id=f"camera.thread_{thread_id}",
                )
                results.append(obs_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_observation, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs
