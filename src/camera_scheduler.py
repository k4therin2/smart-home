"""
Smart Home Assistant - Camera Snapshot Scheduler Module

Implements snapshot scheduling with hourly baselines and motion-triggered
captures. Includes rate limiting to prevent LLM API overload.

WP-11.3: Snapshot Scheduler with Motion-Trigger Optimization
- Hourly baseline captures for all cameras
- Motion-triggered snapshot processing
- Rate limiting (max 10 LLM calls/hour)
- Backoff when rate limit hit
"""

import atexit
import json
import sqlite3
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Generator

from src.camera_store import CameraObservationStore, get_camera_store
from src.config import DATA_DIR
from src.ha_client import get_ha_client
from src.utils import setup_logging
from tools.camera import get_camera_snapshot, list_cameras


logger = setup_logging("camera_scheduler")

# Rate limiting configuration
DEFAULT_MAX_LLM_CALLS_PER_HOUR = 10
RATE_LIMIT_WINDOW_SECONDS = 3600
BACKOFF_BASE_SECONDS = 60
MAX_BACKOFF_SECONDS = 900  # 15 minutes

# Scheduler database path
SCHEDULER_DB_PATH = DATA_DIR / "camera_scheduler.db"


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """
    Token bucket rate limiter for LLM API calls.

    Tracks calls within a sliding window and implements backoff
    when limit is exceeded.
    """

    def __init__(
        self,
        max_calls: int = DEFAULT_MAX_LLM_CALLS_PER_HOUR,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ):
        """
        Initialize the rate limiter.

        Args:
            max_calls: Maximum calls allowed per window
            window_seconds: Window size in seconds
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: deque[datetime] = deque()
        self._lock = threading.Lock()
        self._current_backoff = 0
        self._backoff_until: datetime | None = None

    def _cleanup_old_calls(self) -> None:
        """Remove calls outside the current window."""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        while self._calls and self._calls[0] < cutoff:
            self._calls.popleft()

    def can_call(self) -> bool:
        """
        Check if a call can be made within rate limits.

        Returns:
            True if call is allowed
        """
        with self._lock:
            # Check if in backoff period
            if self._backoff_until and datetime.now() < self._backoff_until:
                return False

            self._cleanup_old_calls()
            return len(self._calls) < self.max_calls

    def record_call(self) -> bool:
        """
        Record a successful call.

        Returns:
            True if recorded, False if rate limited
        """
        with self._lock:
            self._cleanup_old_calls()

            if len(self._calls) >= self.max_calls:
                return False

            self._calls.append(datetime.now())
            # Reset backoff on successful call
            self._current_backoff = 0
            self._backoff_until = None
            return True

    def trigger_backoff(self) -> int:
        """
        Trigger backoff after rate limit hit.

        Returns:
            Backoff duration in seconds
        """
        with self._lock:
            if self._current_backoff == 0:
                self._current_backoff = BACKOFF_BASE_SECONDS
            else:
                self._current_backoff = min(
                    self._current_backoff * 2, MAX_BACKOFF_SECONDS
                )

            self._backoff_until = datetime.now() + timedelta(
                seconds=self._current_backoff
            )
            logger.warning(
                f"Rate limit backoff triggered: {self._current_backoff}s until {self._backoff_until}"
            )
            return self._current_backoff

    def get_remaining_calls(self) -> int:
        """Get remaining calls in current window."""
        with self._lock:
            self._cleanup_old_calls()
            return max(0, self.max_calls - len(self._calls))

    def get_next_available(self) -> datetime | None:
        """
        Get when the next call will be available.

        Returns:
            Datetime when next call allowed, or None if available now
        """
        with self._lock:
            if self._backoff_until and datetime.now() < self._backoff_until:
                return self._backoff_until

            if len(self._calls) < self.max_calls:
                return None

            # Next call available when oldest call expires
            if self._calls:
                oldest = self._calls[0]
                return oldest + timedelta(seconds=self.window_seconds)

            return None

    def get_status(self) -> dict[str, Any]:
        """Get rate limiter status."""
        with self._lock:
            self._cleanup_old_calls()

            # Calculate next_available without calling get_next_available (avoid deadlock)
            next_available = None
            if self._backoff_until and datetime.now() < self._backoff_until:
                next_available = self._backoff_until
            elif len(self._calls) >= self.max_calls and self._calls:
                oldest = self._calls[0]
                next_available = oldest + timedelta(seconds=self.window_seconds)

            return {
                "max_calls": self.max_calls,
                "window_seconds": self.window_seconds,
                "current_calls": len(self._calls),
                "remaining_calls": max(0, self.max_calls - len(self._calls)),
                "in_backoff": self._backoff_until is not None and datetime.now() < self._backoff_until,
                "backoff_until": self._backoff_until.isoformat() if self._backoff_until else None,
                "next_available": next_available.isoformat() if next_available else None,
            }


# =============================================================================
# Scheduler Database
# =============================================================================


def _get_scheduler_db() -> sqlite3.Connection:
    """Get scheduler database connection."""
    SCHEDULER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SCHEDULER_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _get_scheduler_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for scheduler database operations."""
    conn = _get_scheduler_db()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as error:
        conn.rollback()
        logger.error(f"Scheduler DB error: {error}")
        raise
    finally:
        conn.close()


def _initialize_scheduler_db() -> None:
    """Initialize scheduler database tables."""
    with _get_scheduler_cursor() as cursor:
        # Track last capture times for each camera
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_capture_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                capture_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                success BOOLEAN NOT NULL,
                observation_id INTEGER,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Track scheduler state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_capture_log_camera
            ON camera_capture_log(camera_id, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_capture_log_type
            ON camera_capture_log(capture_type, timestamp)
        """)


# =============================================================================
# Snapshot Scheduler
# =============================================================================


@dataclass
class SchedulerConfig:
    """Configuration for the camera scheduler."""

    # Capture intervals
    hourly_baseline_enabled: bool = True
    motion_trigger_enabled: bool = True

    # Rate limiting
    max_llm_calls_per_hour: int = DEFAULT_MAX_LLM_CALLS_PER_HOUR

    # Processing
    process_callback: Callable[[str, bytes, bool], int | None] | None = None
    error_callback: Callable[[str, str], None] | None = None

    # Camera filtering
    camera_filter: list[str] | None = None  # If set, only process these cameras


class CameraScheduler:
    """
    Manages camera snapshot scheduling and processing.

    Captures hourly baselines and responds to motion events
    while respecting rate limits.
    """

    def __init__(
        self,
        config: SchedulerConfig | None = None,
        store: CameraObservationStore | None = None,
    ):
        """
        Initialize the scheduler.

        Args:
            config: Scheduler configuration
            store: Camera observation store (defaults to global)
        """
        self.config = config or SchedulerConfig()
        self.store = store or get_camera_store()
        self.rate_limiter = RateLimiter(
            max_calls=self.config.max_llm_calls_per_hour
        )
        self._running = False
        self._lock = threading.Lock()

        # Initialize database
        _initialize_scheduler_db()

    # =========================================================================
    # Capture Methods
    # =========================================================================

    def capture_snapshot(
        self,
        camera_id: str,
        motion_triggered: bool = False,
    ) -> dict[str, Any]:
        """
        Capture a snapshot from a camera.

        Args:
            camera_id: Camera entity ID
            motion_triggered: Whether triggered by motion

        Returns:
            Result dict with success status and observation ID
        """
        capture_type = "motion" if motion_triggered else "hourly"
        logger.info(f"Capturing {capture_type} snapshot from {camera_id}")

        try:
            # Get snapshot from Home Assistant
            snapshot_result = get_camera_snapshot(camera_id)

            if not snapshot_result.get("success"):
                error = snapshot_result.get("error", "Unknown error")
                self._log_capture(camera_id, capture_type, False, error=error)
                return {"success": False, "error": error}

            # Decode image from base64
            import base64
            image_base64 = snapshot_result.get("image_base64", "")
            image_data = base64.b64decode(image_base64)

            # Store observation (without LLM processing for now)
            observation_id = self.store.add_observation(
                camera_id=camera_id,
                image_data=image_data,
                motion_triggered=motion_triggered,
            )

            self._log_capture(
                camera_id, capture_type, True, observation_id=observation_id
            )

            logger.info(f"Captured snapshot {observation_id} from {camera_id}")
            return {
                "success": True,
                "observation_id": observation_id,
                "camera_id": camera_id,
                "capture_type": capture_type,
            }

        except Exception as error:
            error_str = str(error)
            logger.error(f"Error capturing snapshot from {camera_id}: {error_str}")
            self._log_capture(camera_id, capture_type, False, error=error_str)

            if self.config.error_callback:
                self.config.error_callback(camera_id, error_str)

            return {"success": False, "error": error_str}

    def capture_all_cameras(self, motion_triggered: bool = False) -> list[dict]:
        """
        Capture snapshots from all available cameras.

        Args:
            motion_triggered: Whether triggered by motion

        Returns:
            List of capture results
        """
        results = []

        # Get list of cameras
        camera_list = list_cameras(live_view_only=True)
        if not camera_list.get("success"):
            logger.error(f"Failed to list cameras: {camera_list.get('error')}")
            return results

        cameras = camera_list.get("cameras", [])
        if not cameras:
            logger.warning("No cameras found")
            return results

        for camera in cameras:
            camera_id = camera.get("entity_id")
            if not camera_id:
                continue

            # Apply filter if configured
            if self.config.camera_filter and camera_id not in self.config.camera_filter:
                continue

            # Skip unavailable cameras
            if camera.get("state") == "unavailable":
                logger.debug(f"Skipping unavailable camera: {camera_id}")
                continue

            result = self.capture_snapshot(camera_id, motion_triggered)
            results.append(result)

        return results

    # =========================================================================
    # Motion Event Handling
    # =========================================================================

    def handle_motion_event(
        self,
        camera_id: str,
        event_data: dict | None = None,
    ) -> dict[str, Any]:
        """
        Handle a motion event from a camera.

        Args:
            camera_id: Camera entity ID that detected motion
            event_data: Optional event data from Home Assistant

        Returns:
            Result dict with capture status
        """
        logger.info(f"Motion detected on {camera_id}")

        # Check rate limit
        if not self.rate_limiter.can_call():
            status = self.rate_limiter.get_status()
            logger.warning(
                f"Rate limited, skipping motion capture. "
                f"Next available: {status['next_available']}"
            )
            return {
                "success": False,
                "error": "Rate limited",
                "rate_limit_status": status,
            }

        # Capture snapshot
        result = self.capture_snapshot(camera_id, motion_triggered=True)

        if result.get("success"):
            # Record the call for rate limiting
            self.rate_limiter.record_call()
        else:
            # Trigger backoff on error
            self.rate_limiter.trigger_backoff()

        return result

    # =========================================================================
    # Hourly Baseline Capture
    # =========================================================================

    def run_hourly_baseline(self) -> list[dict]:
        """
        Run hourly baseline capture for all cameras.

        Returns:
            List of capture results
        """
        if not self.config.hourly_baseline_enabled:
            logger.debug("Hourly baseline disabled")
            return []

        logger.info("Running hourly baseline capture")
        results = self.capture_all_cameras(motion_triggered=False)

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"Hourly baseline complete: {success_count}/{len(results)} successful")

        self._save_state("last_hourly_baseline", datetime.now().isoformat())
        return results

    # =========================================================================
    # State Management
    # =========================================================================

    def _log_capture(
        self,
        camera_id: str,
        capture_type: str,
        success: bool,
        observation_id: int | None = None,
        error: str | None = None,
    ) -> None:
        """Log a capture attempt to the database."""
        with _get_scheduler_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO camera_capture_log
                (camera_id, capture_type, timestamp, success, observation_id, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    camera_id,
                    capture_type,
                    datetime.now().isoformat(),
                    success,
                    observation_id,
                    error,
                ),
            )

    def _save_state(self, key: str, value: str) -> None:
        """Save scheduler state to database."""
        with _get_scheduler_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO scheduler_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def _get_state(self, key: str) -> str | None:
        """Get scheduler state from database."""
        with _get_scheduler_cursor() as cursor:
            cursor.execute(
                "SELECT value FROM scheduler_state WHERE key = ?",
                (key,),
            )
            row = cursor.fetchone()
            return row["value"] if row else None

    def get_last_hourly_baseline(self) -> datetime | None:
        """Get timestamp of last hourly baseline."""
        value = self._get_state("last_hourly_baseline")
        if value:
            return datetime.fromisoformat(value)
        return None

    def should_run_hourly_baseline(self) -> bool:
        """Check if hourly baseline should run."""
        last = self.get_last_hourly_baseline()
        if not last:
            return True
        return datetime.now() - last >= timedelta(hours=1)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_capture_stats(
        self,
        hours: int = 24,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get capture statistics.

        Args:
            hours: Hours to look back
            camera_id: Filter by camera

        Returns:
            Statistics dict
        """
        start_time = datetime.now() - timedelta(hours=hours)

        conditions = ["timestamp >= ?"]
        params: list[Any] = [start_time.isoformat()]

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)

        where_clause = "WHERE " + " AND ".join(conditions)

        with _get_scheduler_cursor() as cursor:
            # Total counts
            cursor.execute(
                f"SELECT COUNT(*) FROM camera_capture_log {where_clause}",
                params,
            )
            total = cursor.fetchone()[0]

            # Success counts
            cursor.execute(
                f"SELECT COUNT(*) FROM camera_capture_log {where_clause} AND success = 1",
                params,
            )
            successes = cursor.fetchone()[0]

            # By type
            cursor.execute(
                f"""
                SELECT capture_type, COUNT(*) as count
                FROM camera_capture_log
                {where_clause}
                GROUP BY capture_type
                """,
                params,
            )
            by_type = {row["capture_type"]: row["count"] for row in cursor.fetchall()}

            # Recent errors
            cursor.execute(
                f"""
                SELECT camera_id, error_message, timestamp
                FROM camera_capture_log
                {where_clause} AND success = 0
                ORDER BY timestamp DESC
                LIMIT 5
                """,
                params,
            )
            recent_errors = [
                {
                    "camera_id": row["camera_id"],
                    "error": row["error_message"],
                    "timestamp": row["timestamp"],
                }
                for row in cursor.fetchall()
            ]

        return {
            "period_hours": hours,
            "total_captures": total,
            "successful_captures": successes,
            "failed_captures": total - successes,
            "success_rate": successes / total if total > 0 else 0,
            "by_type": by_type,
            "recent_errors": recent_errors,
            "rate_limiter": self.rate_limiter.get_status(),
        }

    def get_status(self) -> dict[str, Any]:
        """Get overall scheduler status."""
        return {
            "running": self._running,
            "hourly_baseline_enabled": self.config.hourly_baseline_enabled,
            "motion_trigger_enabled": self.config.motion_trigger_enabled,
            "last_hourly_baseline": (
                self.get_last_hourly_baseline().isoformat()
                if self.get_last_hourly_baseline()
                else None
            ),
            "should_run_baseline": self.should_run_hourly_baseline(),
            "rate_limiter": self.rate_limiter.get_status(),
            "stats_24h": self.get_capture_stats(hours=24),
        }


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

_scheduler: CameraScheduler | None = None


def get_camera_scheduler() -> CameraScheduler:
    """Get or create the global camera scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = CameraScheduler()
    return _scheduler


def capture_camera_snapshot(
    camera_id: str,
    motion_triggered: bool = False,
) -> dict[str, Any]:
    """Capture a camera snapshot (convenience function)."""
    return get_camera_scheduler().capture_snapshot(camera_id, motion_triggered)


def handle_camera_motion(camera_id: str) -> dict[str, Any]:
    """Handle motion event (convenience function)."""
    return get_camera_scheduler().handle_motion_event(camera_id)


def run_hourly_camera_baseline() -> list[dict]:
    """Run hourly baseline (convenience function)."""
    return get_camera_scheduler().run_hourly_baseline()


def get_scheduler_status() -> dict[str, Any]:
    """Get scheduler status (convenience function)."""
    return get_camera_scheduler().get_status()


# Initialize database on import
_initialize_scheduler_db()
