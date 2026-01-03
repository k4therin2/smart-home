"""
Tests for src/camera_scheduler.py - Camera Snapshot Scheduler

Tests rate limiting, hourly baseline capture, motion event handling,
and scheduler state management.

WP-11.3: Snapshot Scheduler with Motion-Trigger Optimization
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Scheduler Fixtures
# =============================================================================


@pytest.fixture
def scheduler_db(temp_data_dir, monkeypatch):
    """Set up scheduler database in temp directory."""
    db_path = temp_data_dir / "test_camera_scheduler.db"
    monkeypatch.setattr("src.camera_scheduler.SCHEDULER_DB_PATH", db_path)

    from src.camera_scheduler import _initialize_scheduler_db
    _initialize_scheduler_db()

    return db_path


@pytest.fixture
def camera_store(temp_data_dir, monkeypatch):
    """Create isolated camera store for testing."""
    db_path = temp_data_dir / "test_camera_observations.db"
    images_dir = temp_data_dir / "camera_images"

    monkeypatch.setattr("src.camera_store.CAMERA_DB_PATH", db_path)
    monkeypatch.setattr("src.camera_store.CAMERA_IMAGES_DIR", images_dir)

    from src.camera_store import CameraObservationStore, initialize_database
    initialize_database()

    return CameraObservationStore(db_path=db_path, images_dir=images_dir)


@pytest.fixture
def scheduler(scheduler_db, camera_store, monkeypatch):
    """Create scheduler with test configuration."""
    from src.camera_scheduler import CameraScheduler, SchedulerConfig

    config = SchedulerConfig(
        hourly_baseline_enabled=True,
        motion_trigger_enabled=True,
        max_llm_calls_per_hour=10,
    )

    scheduler = CameraScheduler(config=config, store=camera_store)
    return scheduler


@pytest.fixture
def rate_limiter():
    """Create isolated rate limiter for testing."""
    from src.camera_scheduler import RateLimiter
    return RateLimiter(max_calls=5, window_seconds=60)


@pytest.fixture
def mock_ha_cameras(monkeypatch):
    """Mock Home Assistant camera responses."""
    # Mock list_cameras
    def mock_list_cameras(live_view_only=False):
        return {
            "success": True,
            "cameras": [
                {
                    "entity_id": "camera.front_door_live_view",
                    "friendly_name": "Front Door",
                    "state": "idle",
                },
                {
                    "entity_id": "camera.living_room_live_view",
                    "friendly_name": "Living Room",
                    "state": "idle",
                },
                {
                    "entity_id": "camera.unavailable_cam",
                    "friendly_name": "Unavailable",
                    "state": "unavailable",
                },
            ],
            "count": 3,
        }

    # Mock get_camera_snapshot
    def mock_get_snapshot(entity_id):
        import base64
        fake_image = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
        return {
            "success": True,
            "entity_id": entity_id,
            "image_base64": base64.b64encode(fake_image).decode(),
            "timestamp": datetime.now().isoformat(),
        }

    monkeypatch.setattr("src.camera_scheduler.list_cameras", mock_list_cameras)
    monkeypatch.setattr("src.camera_scheduler.get_camera_snapshot", mock_get_snapshot)


# =============================================================================
# Rate Limiter Tests
# =============================================================================


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_can_call_initially(self, rate_limiter):
        """Should allow calls when under limit."""
        assert rate_limiter.can_call() is True

    def test_can_call_up_to_limit(self, rate_limiter):
        """Should allow calls up to the limit."""
        for _ in range(5):
            assert rate_limiter.can_call() is True
            rate_limiter.record_call()

        # Should be at limit now
        assert rate_limiter.can_call() is False

    def test_record_call_returns_success(self, rate_limiter):
        """Record call should return True when under limit."""
        result = rate_limiter.record_call()
        assert result is True

    def test_record_call_returns_false_at_limit(self, rate_limiter):
        """Record call should return False at limit."""
        for _ in range(5):
            rate_limiter.record_call()

        result = rate_limiter.record_call()
        assert result is False

    def test_get_remaining_calls(self, rate_limiter):
        """Should track remaining calls correctly."""
        assert rate_limiter.get_remaining_calls() == 5

        rate_limiter.record_call()
        assert rate_limiter.get_remaining_calls() == 4

        rate_limiter.record_call()
        rate_limiter.record_call()
        assert rate_limiter.get_remaining_calls() == 2

    def test_trigger_backoff(self, rate_limiter):
        """Should implement exponential backoff."""
        backoff1 = rate_limiter.trigger_backoff()
        assert backoff1 == 60  # Base backoff

        backoff2 = rate_limiter.trigger_backoff()
        assert backoff2 == 120  # Doubled

        backoff3 = rate_limiter.trigger_backoff()
        assert backoff3 == 240  # Doubled again

    def test_backoff_max_limit(self, rate_limiter):
        """Backoff should cap at maximum."""
        # Trigger many backoffs
        for _ in range(10):
            backoff = rate_limiter.trigger_backoff()

        assert backoff <= 900  # Max 15 minutes

    def test_backoff_blocks_calls(self, rate_limiter):
        """Calls should be blocked during backoff."""
        rate_limiter.trigger_backoff()
        assert rate_limiter.can_call() is False

    def test_successful_call_resets_backoff(self, rate_limiter):
        """Successful call should reset backoff."""
        rate_limiter.trigger_backoff()
        rate_limiter.trigger_backoff()

        # Force clear backoff for test
        rate_limiter._backoff_until = None

        # Record successful call
        rate_limiter.record_call()

        # Next backoff should be base value
        backoff = rate_limiter.trigger_backoff()
        assert backoff == 60

    def test_get_next_available_when_available(self, rate_limiter):
        """Should return None when calls available."""
        result = rate_limiter.get_next_available()
        assert result is None

    def test_get_next_available_at_limit(self, rate_limiter):
        """Should return time when next call available."""
        for _ in range(5):
            rate_limiter.record_call()

        next_available = rate_limiter.get_next_available()
        assert next_available is not None
        assert next_available > datetime.now()

    def test_get_status(self, rate_limiter):
        """Should return complete status."""
        rate_limiter.record_call()
        rate_limiter.record_call()

        status = rate_limiter.get_status()

        assert status["max_calls"] == 5
        assert status["window_seconds"] == 60
        assert status["current_calls"] == 2
        assert status["remaining_calls"] == 3
        assert status["in_backoff"] is False


# =============================================================================
# Scheduler Capture Tests
# =============================================================================


class TestSchedulerCapture:
    """Test snapshot capture functionality."""

    def test_capture_snapshot(self, scheduler, mock_ha_cameras):
        """Should capture snapshot and store observation."""
        result = scheduler.capture_snapshot("camera.front_door_live_view")

        assert result["success"] is True
        assert result["camera_id"] == "camera.front_door_live_view"
        assert result["observation_id"] is not None

    def test_capture_snapshot_motion_triggered(self, scheduler, mock_ha_cameras):
        """Should mark motion-triggered snapshots."""
        result = scheduler.capture_snapshot(
            "camera.front_door_live_view",
            motion_triggered=True,
        )

        assert result["success"] is True
        assert result["capture_type"] == "motion"

    def test_capture_all_cameras(self, scheduler, mock_ha_cameras):
        """Should capture from all available cameras."""
        results = scheduler.capture_all_cameras()

        # Should capture 2 (excluding unavailable)
        successful = [r for r in results if r.get("success")]
        assert len(successful) == 2

    def test_capture_skips_unavailable(self, scheduler, mock_ha_cameras):
        """Should skip unavailable cameras."""
        results = scheduler.capture_all_cameras()

        camera_ids = [r.get("camera_id") for r in results]
        assert "camera.unavailable_cam" not in camera_ids

    def test_capture_with_filter(self, scheduler_db, camera_store, mock_ha_cameras, monkeypatch):
        """Should respect camera filter."""
        from src.camera_scheduler import CameraScheduler, SchedulerConfig

        config = SchedulerConfig(
            camera_filter=["camera.front_door_live_view"],
        )
        scheduler = CameraScheduler(config=config, store=camera_store)

        results = scheduler.capture_all_cameras()

        assert len(results) == 1
        assert results[0]["camera_id"] == "camera.front_door_live_view"


# =============================================================================
# Motion Event Tests
# =============================================================================


class TestMotionEvents:
    """Test motion event handling."""

    def test_handle_motion_event(self, scheduler, mock_ha_cameras):
        """Should capture snapshot on motion."""
        result = scheduler.handle_motion_event("camera.front_door_live_view")

        assert result["success"] is True
        assert result["camera_id"] == "camera.front_door_live_view"

    def test_motion_event_rate_limited(self, scheduler, mock_ha_cameras):
        """Should rate limit motion events."""
        # Exhaust rate limit
        for _ in range(10):
            scheduler.rate_limiter.record_call()

        result = scheduler.handle_motion_event("camera.front_door_live_view")

        assert result["success"] is False
        assert result["error"] == "Rate limited"
        assert "rate_limit_status" in result

    def test_motion_event_records_call(self, scheduler, mock_ha_cameras):
        """Should record successful motion call for rate limiting."""
        initial = scheduler.rate_limiter.get_remaining_calls()

        scheduler.handle_motion_event("camera.front_door_live_view")

        assert scheduler.rate_limiter.get_remaining_calls() == initial - 1


# =============================================================================
# Hourly Baseline Tests
# =============================================================================


class TestHourlyBaseline:
    """Test hourly baseline capture."""

    def test_run_hourly_baseline(self, scheduler, mock_ha_cameras):
        """Should capture from all cameras."""
        results = scheduler.run_hourly_baseline()

        successful = [r for r in results if r.get("success")]
        assert len(successful) == 2

    def test_run_hourly_baseline_disabled(
        self, scheduler_db, camera_store, mock_ha_cameras, monkeypatch
    ):
        """Should skip when disabled."""
        from src.camera_scheduler import CameraScheduler, SchedulerConfig

        config = SchedulerConfig(hourly_baseline_enabled=False)
        scheduler = CameraScheduler(config=config, store=camera_store)

        results = scheduler.run_hourly_baseline()
        assert len(results) == 0

    def test_should_run_hourly_baseline_initially(self, scheduler):
        """Should run hourly baseline if never run."""
        assert scheduler.should_run_hourly_baseline() is True

    def test_should_run_hourly_baseline_after_hour(self, scheduler):
        """Should run after an hour has passed."""
        # Simulate running an hour ago
        scheduler._save_state(
            "last_hourly_baseline",
            (datetime.now() - timedelta(hours=2)).isoformat(),
        )

        assert scheduler.should_run_hourly_baseline() is True

    def test_should_not_run_if_recent(self, scheduler):
        """Should not run if recently completed."""
        scheduler._save_state(
            "last_hourly_baseline",
            datetime.now().isoformat(),
        )

        assert scheduler.should_run_hourly_baseline() is False

    def test_get_last_hourly_baseline(self, scheduler):
        """Should retrieve last run time."""
        now = datetime.now()
        scheduler._save_state("last_hourly_baseline", now.isoformat())

        result = scheduler.get_last_hourly_baseline()
        assert result is not None
        # Compare within 1 second tolerance
        assert abs((result - now).total_seconds()) < 1


# =============================================================================
# State Management Tests
# =============================================================================


class TestStateManagement:
    """Test scheduler state persistence."""

    def test_save_and_get_state(self, scheduler):
        """Should persist and retrieve state."""
        scheduler._save_state("test_key", "test_value")
        result = scheduler._get_state("test_key")

        assert result == "test_value"

    def test_get_nonexistent_state(self, scheduler):
        """Should return None for nonexistent key."""
        result = scheduler._get_state("nonexistent")
        assert result is None

    def test_log_capture(self, scheduler):
        """Should log capture attempts."""
        scheduler._log_capture(
            camera_id="camera.test",
            capture_type="hourly",
            success=True,
            observation_id=123,
        )

        stats = scheduler.get_capture_stats(hours=1)
        assert stats["total_captures"] == 1
        assert stats["successful_captures"] == 1

    def test_log_capture_failure(self, scheduler):
        """Should log failed captures."""
        scheduler._log_capture(
            camera_id="camera.test",
            capture_type="motion",
            success=False,
            error="Test error",
        )

        stats = scheduler.get_capture_stats(hours=1)
        assert stats["failed_captures"] == 1
        assert len(stats["recent_errors"]) == 1


# =============================================================================
# Statistics Tests
# =============================================================================


class TestSchedulerStats:
    """Test scheduler statistics."""

    def test_capture_stats_empty(self, scheduler):
        """Should return zeros when no captures."""
        stats = scheduler.get_capture_stats(hours=1)

        assert stats["total_captures"] == 0
        assert stats["successful_captures"] == 0
        assert stats["success_rate"] == 0

    def test_capture_stats_by_type(self, scheduler):
        """Should track captures by type."""
        scheduler._log_capture("cam1", "hourly", True)
        scheduler._log_capture("cam2", "hourly", True)
        scheduler._log_capture("cam1", "motion", True)

        stats = scheduler.get_capture_stats(hours=1)

        assert stats["by_type"]["hourly"] == 2
        assert stats["by_type"]["motion"] == 1

    def test_capture_stats_success_rate(self, scheduler):
        """Should calculate success rate correctly."""
        scheduler._log_capture("cam1", "hourly", True)
        scheduler._log_capture("cam2", "hourly", True)
        scheduler._log_capture("cam3", "hourly", False, error="Test")

        stats = scheduler.get_capture_stats(hours=1)

        assert stats["total_captures"] == 3
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_capture_stats_recent_errors(self, scheduler):
        """Should track recent errors."""
        for i in range(7):
            scheduler._log_capture(
                f"cam{i}", "motion", False, error=f"Error {i}"
            )

        stats = scheduler.get_capture_stats(hours=1)

        # Should only return 5 most recent
        assert len(stats["recent_errors"]) == 5

    def test_get_status(self, scheduler):
        """Should return comprehensive status."""
        status = scheduler.get_status()

        assert "running" in status
        assert "hourly_baseline_enabled" in status
        assert "motion_trigger_enabled" in status
        assert "rate_limiter" in status
        assert "stats_24h" in status


# =============================================================================
# Module-Level Functions Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_camera_scheduler(self, scheduler_db, camera_store, monkeypatch):
        """Should return global scheduler."""
        from src import camera_scheduler as cs_module

        # Reset global
        cs_module._scheduler = None

        scheduler1 = cs_module.get_camera_scheduler()
        scheduler2 = cs_module.get_camera_scheduler()

        # Should return same instance
        assert scheduler1 is scheduler2

    def test_get_scheduler_status(self, scheduler_db, camera_store, monkeypatch):
        """Should return status through convenience function."""
        from src import camera_scheduler as cs_module

        cs_module._scheduler = None

        status = cs_module.get_scheduler_status()

        assert "running" in status
        assert "rate_limiter" in status


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_capture_handles_error(self, scheduler, monkeypatch):
        """Should handle capture errors gracefully."""
        def mock_snapshot(entity_id):
            return {"success": False, "error": "Camera offline"}

        monkeypatch.setattr("src.camera_scheduler.get_camera_snapshot", mock_snapshot)

        result = scheduler.capture_snapshot("camera.test")

        assert result["success"] is False
        assert "error" in result

    def test_error_callback_called(self, scheduler_db, camera_store, monkeypatch):
        """Should call error callback on failure."""
        from src.camera_scheduler import CameraScheduler, SchedulerConfig

        errors = []

        def error_callback(camera_id, error):
            errors.append((camera_id, error))

        config = SchedulerConfig(error_callback=error_callback)
        scheduler = CameraScheduler(config=config, store=camera_store)

        def mock_snapshot(entity_id):
            raise Exception("Test error")

        monkeypatch.setattr("src.camera_scheduler.get_camera_snapshot", mock_snapshot)

        scheduler.capture_snapshot("camera.test")

        assert len(errors) == 1
        assert errors[0][0] == "camera.test"

    def test_concurrent_rate_limiting(self, rate_limiter):
        """Should handle concurrent access to rate limiter."""
        import threading

        results = []
        errors = []

        def record_calls():
            try:
                for _ in range(3):
                    results.append(rate_limiter.record_call())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_calls) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Only 5 should succeed (limit)
        successful = sum(1 for r in results if r)
        assert successful == 5
