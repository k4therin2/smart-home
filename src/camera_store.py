"""
Smart Home Assistant - Camera Observation Storage Module

SQLite-based storage for camera observations and LLM descriptions,
with image file management and automatic retention policy.

WP-11.2: Storage System (SQLite + Image Retention)
- SQLite database for camera event metadata
- Image storage with timestamp-based cleanup
- Query API for voice commands
- Disk space monitoring and alerts
"""

import json
import os
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator

from src.config import DATA_DIR
from src.utils import setup_logging


logger = setup_logging("camera_store")

# Database and storage paths
CAMERA_DB_PATH = DATA_DIR / "camera_observations.db"
CAMERA_IMAGES_DIR = DATA_DIR / "camera_images"

# Configuration
DEFAULT_RETENTION_DAYS = 14
DISK_SPACE_WARNING_PERCENT = 80
DISK_SPACE_CRITICAL_PERCENT = 90


# =============================================================================
# Database Connection Management
# =============================================================================


def _apply_sqlite_optimizations(connection: sqlite3.Connection) -> None:
    """Apply SQLite performance optimizations to a connection."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-4000")
    cursor.execute("PRAGMA foreign_keys=ON")
    connection.commit()


def get_connection() -> sqlite3.Connection:
    """
    Create a database connection with row factory.

    Returns:
        SQLite connection with dict-like row access
    """
    # Ensure parent directory exists
    CAMERA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(CAMERA_DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    _apply_sqlite_optimizations(connection)
    return connection


@contextmanager
def get_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database operations.

    Yields:
        SQLite cursor

    Example:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM camera_events")
            rows = cursor.fetchall()
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    except Exception as error:
        connection.rollback()
        logger.error(f"Database error: {error}")
        raise
    finally:
        connection.close()


# =============================================================================
# Database Schema
# =============================================================================


def initialize_database() -> None:
    """
    Initialize the camera observations database with required tables.

    Creates tables:
    - camera_events: Core event metadata and LLM descriptions
    """
    with get_cursor() as cursor:
        # Camera Events Table
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

        # Indexes for common query patterns
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_camera_events_timestamp
            ON camera_events(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_camera_events_camera_id
            ON camera_events(camera_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_camera_events_camera_timestamp
            ON camera_events(camera_id, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_camera_events_objects
            ON camera_events(objects_detected)
        """)

    # Ensure images directory exists
    CAMERA_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Camera database initialized at {CAMERA_DB_PATH}")


# =============================================================================
# Camera Observation Store
# =============================================================================


class CameraObservationStore:
    """
    Storage manager for camera observations and images.

    Provides CRUD operations for camera events, image file management,
    and query methods for voice commands.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        images_dir: Path | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        """
        Initialize the observation store.

        Args:
            db_path: Optional custom database path
            images_dir: Optional custom images directory
            retention_days: Days to retain images (default 14)
        """
        self.db_path = db_path or CAMERA_DB_PATH
        self.images_dir = images_dir or CAMERA_IMAGES_DIR
        self.retention_days = retention_days
        self._lock = threading.Lock()

        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection for this store."""
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        _apply_sqlite_optimizations(connection)
        return connection

    @contextmanager
    def _get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database operations."""
        connection = self._get_connection()
        try:
            cursor = connection.cursor()
            yield cursor
            connection.commit()
        except Exception as error:
            connection.rollback()
            logger.error(f"Database error: {error}")
            raise
        finally:
            connection.close()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def add_observation(
        self,
        camera_id: str,
        timestamp: datetime | None = None,
        image_data: bytes | None = None,
        objects_detected: list[str] | None = None,
        llm_description: str | None = None,
        confidence: float | None = None,
        motion_triggered: bool = False,
        processing_time_ms: int | None = None,
        metadata: dict | None = None,
    ) -> int:
        """
        Add a new camera observation.

        Args:
            camera_id: Camera entity ID
            timestamp: Event timestamp (defaults to now)
            image_data: Raw image bytes (saved to file)
            objects_detected: List of detected objects
            llm_description: LLM-generated scene description
            confidence: Detection confidence (0.0-1.0)
            motion_triggered: Whether triggered by motion
            processing_time_ms: Time to process the image
            metadata: Additional metadata dict

        Returns:
            ID of the created observation
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Save image to file if provided
        image_path = None
        if image_data:
            image_path = self._save_image(camera_id, timestamp, image_data)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO camera_events (
                    timestamp, camera_id, image_path, objects_detected,
                    llm_description, confidence, motion_triggered,
                    processing_time_ms, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    camera_id,
                    str(image_path) if image_path else None,
                    json.dumps(objects_detected) if objects_detected else None,
                    llm_description,
                    confidence,
                    motion_triggered,
                    processing_time_ms,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            observation_id = cursor.lastrowid

        logger.info(f"Added camera observation {observation_id} for {camera_id}")
        return observation_id

    def get_observation(self, observation_id: int) -> dict | None:
        """
        Get a camera observation by ID.

        Args:
            observation_id: Observation ID

        Returns:
            Observation dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM camera_events WHERE id = ?",
                (observation_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_dict(row)

    def get_observations(
        self,
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        motion_only: bool = False,
    ) -> list[dict]:
        """
        Query camera observations with filters.

        Args:
            camera_id: Filter by camera ID
            start_time: Filter events after this time
            end_time: Filter events before this time
            limit: Maximum results
            offset: Number of results to skip
            motion_only: Only return motion-triggered events

        Returns:
            List of observation dicts
        """
        conditions = []
        params = []

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        if motion_only:
            conditions.append("motion_triggered = 1")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT * FROM camera_events
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def delete_observation(self, observation_id: int) -> bool:
        """
        Delete an observation and its associated image.

        Args:
            observation_id: Observation ID

        Returns:
            True if deleted
        """
        # Get image path before deleting
        observation = self.get_observation(observation_id)
        if not observation:
            return False

        # Delete image file if exists
        if observation.get("image_path"):
            image_path = Path(observation["image_path"])
            if image_path.exists():
                image_path.unlink()
                logger.debug(f"Deleted image: {image_path}")

        # Delete database record
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM camera_events WHERE id = ?",
                (observation_id,),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted observation {observation_id}")

        return deleted

    def update_observation(
        self,
        observation_id: int,
        llm_description: str | None = None,
        objects_detected: list[str] | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """
        Update an existing observation.

        Args:
            observation_id: Observation ID
            llm_description: New LLM description
            objects_detected: New objects list
            confidence: New confidence
            metadata: New metadata

        Returns:
            True if updated
        """
        updates = []
        params = []

        if llm_description is not None:
            updates.append("llm_description = ?")
            params.append(llm_description)

        if objects_detected is not None:
            updates.append("objects_detected = ?")
            params.append(json.dumps(objects_detected))

        if confidence is not None:
            updates.append("confidence = ?")
            params.append(confidence)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(observation_id)

        with self._get_cursor() as cursor:
            cursor.execute(
                f"UPDATE camera_events SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            updated = cursor.rowcount > 0

        return updated

    # =========================================================================
    # Voice Command Query Methods
    # =========================================================================

    def query_by_object(
        self,
        object_type: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        camera_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Query observations that detected a specific object type.

        Supports queries like "what did the cat do today".

        Args:
            object_type: Object to search for (e.g., "cat", "person", "dog")
            start_time: Filter events after this time
            end_time: Filter events before this time
            camera_id: Filter by camera
            limit: Maximum results

        Returns:
            List of matching observations
        """
        conditions = ["objects_detected LIKE ?"]
        params = [f'%"{object_type}"%']

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)

        where_clause = "WHERE " + " AND ".join(conditions)

        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM camera_events
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                params + [limit],
            )
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_activity_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get activity summary for a time period.

        Args:
            start_time: Start of period (defaults to last 24h)
            end_time: End of period (defaults to now)
            camera_id: Filter by camera

        Returns:
            Summary dict with event counts by type
        """
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(hours=24)

        conditions = ["timestamp >= ?", "timestamp <= ?"]
        params = [start_time.isoformat(), end_time.isoformat()]

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)

        where_clause = "WHERE " + " AND ".join(conditions)

        with self._get_cursor() as cursor:
            # Total events
            cursor.execute(
                f"SELECT COUNT(*) FROM camera_events {where_clause}",
                params,
            )
            total_events = cursor.fetchone()[0]

            # Motion events
            cursor.execute(
                f"SELECT COUNT(*) FROM camera_events {where_clause} AND motion_triggered = 1",
                params,
            )
            motion_events = cursor.fetchone()[0]

            # Get all objects detected
            cursor.execute(
                f"SELECT objects_detected FROM camera_events {where_clause} AND objects_detected IS NOT NULL",
                params,
            )
            object_counts: dict[str, int] = {}
            for row in cursor.fetchall():
                if row[0]:
                    objects = json.loads(row[0])
                    for obj in objects:
                        object_counts[obj] = object_counts.get(obj, 0) + 1

        return {
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "total_events": total_events,
            "motion_events": motion_events,
            "objects_detected": object_counts,
            "top_objects": sorted(
                object_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def get_recent_descriptions(
        self,
        camera_id: str | None = None,
        hours: int = 24,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get recent LLM descriptions for summary generation.

        Args:
            camera_id: Filter by camera
            hours: Hours to look back
            limit: Maximum descriptions

        Returns:
            List of observations with descriptions
        """
        start_time = datetime.now() - timedelta(hours=hours)

        conditions = ["timestamp >= ?", "llm_description IS NOT NULL"]
        params: list[Any] = [start_time.isoformat()]

        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)

        where_clause = "WHERE " + " AND ".join(conditions)

        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM camera_events
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                params + [limit],
            )
            rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    # =========================================================================
    # Image File Management
    # =========================================================================

    def _save_image(
        self,
        camera_id: str,
        timestamp: datetime,
        image_data: bytes,
    ) -> Path:
        """
        Save image data to file with organized directory structure.

        Directory structure: images/{camera_id}/{date}/{timestamp}.jpg

        Args:
            camera_id: Camera entity ID
            timestamp: Event timestamp
            image_data: Raw image bytes

        Returns:
            Path to saved image
        """
        # Sanitize camera ID for filesystem
        safe_camera_id = camera_id.replace(".", "_").replace("/", "_")

        # Create directory structure
        date_str = timestamp.strftime("%Y-%m-%d")
        time_str = timestamp.strftime("%H-%M-%S-%f")

        image_dir = self.images_dir / safe_camera_id / date_str
        image_dir.mkdir(parents=True, exist_ok=True)

        image_path = image_dir / f"{time_str}.jpg"

        # Save image
        image_path.write_bytes(image_data)
        logger.debug(f"Saved image to {image_path}")

        return image_path

    def get_image(self, observation_id: int) -> bytes | None:
        """
        Get image data for an observation.

        Args:
            observation_id: Observation ID

        Returns:
            Image bytes or None if not found
        """
        observation = self.get_observation(observation_id)
        if not observation or not observation.get("image_path"):
            return None

        image_path = Path(observation["image_path"])
        if not image_path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None

        return image_path.read_bytes()

    # =========================================================================
    # Retention and Cleanup
    # =========================================================================

    def cleanup_old_images(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Delete images older than retention period.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        deleted_files = 0
        deleted_bytes = 0
        errors = []

        # Find old date directories
        for camera_dir in self.images_dir.iterdir():
            if not camera_dir.is_dir():
                continue

            for date_dir in camera_dir.iterdir():
                if not date_dir.is_dir():
                    continue

                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # Count files and bytes
                        for image_file in date_dir.iterdir():
                            if image_file.is_file():
                                deleted_bytes += image_file.stat().st_size
                                deleted_files += 1

                        if not dry_run:
                            shutil.rmtree(date_dir)
                            logger.info(f"Deleted old directory: {date_dir}")

                except ValueError:
                    # Skip directories that don't match date format
                    pass
                except Exception as error:
                    errors.append(str(error))
                    logger.error(f"Error cleaning {date_dir}: {error}")

        # Also delete orphaned database records
        deleted_records = 0
        if not dry_run:
            with self._get_cursor() as cursor:
                cursor.execute(
                    "DELETE FROM camera_events WHERE timestamp < ?",
                    (cutoff_date.isoformat(),),
                )
                deleted_records = cursor.rowcount

        result = {
            "cutoff_date": cutoff_date.isoformat(),
            "deleted_files": deleted_files,
            "deleted_bytes": deleted_bytes,
            "deleted_bytes_mb": round(deleted_bytes / (1024 * 1024), 2),
            "deleted_records": deleted_records,
            "dry_run": dry_run,
        }

        if errors:
            result["errors"] = errors

        logger.info(
            f"Cleanup {'would delete' if dry_run else 'deleted'} "
            f"{deleted_files} files ({result['deleted_bytes_mb']} MB)"
        )

        return result

    # =========================================================================
    # Disk Space Monitoring
    # =========================================================================

    def get_storage_stats(self) -> dict[str, Any]:
        """
        Get storage statistics for monitoring.

        Returns:
            Storage stats including disk usage and alerts
        """
        # Image storage stats
        image_files = 0
        image_bytes = 0

        for image_file in self.images_dir.rglob("*.jpg"):
            image_files += 1
            image_bytes += image_file.stat().st_size

        # Database stats
        db_bytes = 0
        if self.db_path.exists():
            db_bytes = self.db_path.stat().st_size

        # Disk space
        total, used, free = shutil.disk_usage(self.images_dir)
        used_percent = (used / total) * 100

        # Determine alert status
        alert_status = "ok"
        if used_percent >= DISK_SPACE_CRITICAL_PERCENT:
            alert_status = "critical"
        elif used_percent >= DISK_SPACE_WARNING_PERCENT:
            alert_status = "warning"

        return {
            "image_files": image_files,
            "image_bytes": image_bytes,
            "image_bytes_mb": round(image_bytes / (1024 * 1024), 2),
            "database_bytes": db_bytes,
            "database_bytes_mb": round(db_bytes / (1024 * 1024), 2),
            "disk_total_bytes": total,
            "disk_used_bytes": used,
            "disk_free_bytes": free,
            "disk_used_percent": round(used_percent, 1),
            "alert_status": alert_status,
            "retention_days": self.retention_days,
        }

    def check_disk_space_alert(self) -> dict[str, Any] | None:
        """
        Check if disk space alert should be triggered.

        Returns:
            Alert dict if threshold exceeded, None otherwise
        """
        stats = self.get_storage_stats()

        if stats["alert_status"] == "critical":
            return {
                "severity": "critical",
                "message": f"Disk space critical: {stats['disk_used_percent']}% used",
                "action": "Cleanup required immediately",
                "stats": stats,
            }
        elif stats["alert_status"] == "warning":
            return {
                "severity": "warning",
                "message": f"Disk space warning: {stats['disk_used_percent']}% used",
                "action": "Consider cleanup soon",
                "stats": stats,
            }

        return None

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert a database row to a dictionary."""
        result = dict(row)

        # Parse JSON fields
        if result.get("objects_detected"):
            result["objects_detected"] = json.loads(result["objects_detected"])
        if result.get("metadata"):
            result["metadata"] = json.loads(result["metadata"])

        return result


# =============================================================================
# Module-Level Convenience Functions
# =============================================================================

_store: CameraObservationStore | None = None


def get_camera_store() -> CameraObservationStore:
    """Get or create the global camera observation store."""
    global _store
    if _store is None:
        initialize_database()
        _store = CameraObservationStore()
    return _store


def add_camera_observation(**kwargs) -> int:
    """Add a camera observation (convenience function)."""
    return get_camera_store().add_observation(**kwargs)


def query_camera_by_object(object_type: str, **kwargs) -> list[dict]:
    """Query observations by object type (convenience function)."""
    return get_camera_store().query_by_object(object_type, **kwargs)


def get_camera_activity_summary(**kwargs) -> dict[str, Any]:
    """Get activity summary (convenience function)."""
    return get_camera_store().get_activity_summary(**kwargs)


def cleanup_old_camera_images(**kwargs) -> dict[str, Any]:
    """Run cleanup on old images (convenience function)."""
    return get_camera_store().cleanup_old_images(**kwargs)


def get_camera_storage_stats() -> dict[str, Any]:
    """Get storage statistics (convenience function)."""
    return get_camera_store().get_storage_stats()


# Initialize database on import (only creates tables if they don't exist)
initialize_database()
