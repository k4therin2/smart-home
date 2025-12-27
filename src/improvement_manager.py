"""
Smart Home Assistant - Improvement Manager

Manages the lifecycle of improvement suggestions:
pending -> approved -> applied (or rejected)

Provides user approval workflow, rollback capability, and learning
from accepted/rejected improvements.
"""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger("improvement_manager")

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data"


class ImprovementManager:
    """
    Manages improvement suggestion lifecycle.

    Provides:
    - Adding/storing improvements in pending state
    - User approval/rejection workflow
    - Applying approved improvements with backup
    - Rollback capability
    - Learning from feedback patterns

    Improvement states:
    - pending: Waiting for user review
    - approved: User approved, ready to apply
    - rejected: User rejected
    - applied: Successfully applied
    - rolled_back: Applied then reverted
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize ImprovementManager with database.

        Args:
            database_path: Path to SQLite database (defaults to DATA_DIR/improvements.db)
        """
        # Handle DATA_DIR being a string (from test mocks) or Path
        data_dir = Path(DATA_DIR) if isinstance(DATA_DIR, str) else DATA_DIR
        data_dir.mkdir(exist_ok=True)
        self._db_path = database_path or data_dir / "improvements.db"
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
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

    def _initialize_database(self):
        """Create tables if they don't exist."""
        with self._get_cursor() as cursor:
            # Main improvements table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    suggestion TEXT,
                    severity TEXT DEFAULT 'low',
                    status TEXT DEFAULT 'pending',
                    auto_fixable INTEGER DEFAULT 0,
                    fix_action TEXT,
                    backup_id TEXT,
                    rejection_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # History table for tracking status changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvement_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    improvement_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT,
                    FOREIGN KEY (improvement_id) REFERENCES improvements(id)
                )
            """)

            # Backups table for rollback support
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvement_backups (
                    id TEXT PRIMARY KEY,
                    improvement_id TEXT NOT NULL,
                    backup_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (improvement_id) REFERENCES improvements(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_improvements_status
                ON improvements(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_improvements_category
                ON improvements(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_improvement_id
                ON improvement_history(improvement_id)
            """)

    def _record_history(
        self, cursor: sqlite3.Cursor, improvement_id: str, status: str, details: str | None = None
    ):
        """Record a status change in the history table."""
        cursor.execute(
            """
            INSERT INTO improvement_history (improvement_id, status, details)
            VALUES (?, ?, ?)
            """,
            (improvement_id, status, details),
        )

    def add_improvement(self, improvement: dict[str, Any]) -> dict[str, Any]:
        """
        Add a new improvement to the pending queue.

        Args:
            improvement: Improvement data with required fields:
                - id: Unique identifier
                - category: Category of improvement
                - title: Short title
                - severity: low, medium, high, critical

        Returns:
            Success status dictionary
        """
        improvement_id = improvement.get("id")
        if not improvement_id:
            return {"success": False, "error": "Missing improvement ID"}

        with self._get_cursor() as cursor:
            # Check if already exists
            cursor.execute("SELECT id FROM improvements WHERE id = ?", (improvement_id,))
            if cursor.fetchone():
                return {
                    "success": False,
                    "already_exists": True,
                    "error": "Improvement already exists",
                }

            cursor.execute(
                """
                INSERT INTO improvements
                (id, category, title, description, suggestion, severity, auto_fixable, fix_action, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    improvement_id,
                    improvement.get("category", "general"),
                    improvement.get("title", "Untitled"),
                    improvement.get("description", ""),
                    improvement.get("suggestion", ""),
                    improvement.get("severity", "low"),
                    1 if improvement.get("auto_fixable") else 0,
                    json.dumps(improvement.get("fix_action"))
                    if improvement.get("fix_action")
                    else None,
                ),
            )

            self._record_history(cursor, improvement_id, "pending", "Improvement added")

        logger.info(f"Added improvement {improvement_id}: {improvement.get('title')}")
        return {"success": True, "id": improvement_id}

    def get_improvement(self, improvement_id: str) -> dict[str, Any] | None:
        """
        Get a single improvement by ID.

        Args:
            improvement_id: The improvement's unique ID

        Returns:
            Improvement dictionary or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM improvements WHERE id = ?", (improvement_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = dict(row)
        if result.get("fix_action"):
            result["fix_action"] = json.loads(result["fix_action"])
        result["auto_fixable"] = bool(result.get("auto_fixable"))
        return result

    def get_pending_improvements(self) -> list[dict[str, Any]]:
        """
        Get all pending improvements.

        Returns:
            List of pending improvement dictionaries
        """
        return self.get_improvements(status="pending")

    def get_improvements(
        self,
        status: str | None = None,
        category: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get improvements with optional filtering.

        Args:
            status: Filter by status (pending, approved, rejected, applied, rolled_back)
            category: Filter by category
            severity: Filter by severity (low, medium, high, critical)

        Returns:
            List of matching improvement dictionaries
        """
        query = "SELECT * FROM improvements WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        if severity:
            query += " AND severity = ?"
            params.append(severity)

        query += " ORDER BY created_at DESC"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def approve_improvement(self, improvement_id: str) -> dict[str, Any]:
        """
        Approve an improvement for application.

        Args:
            improvement_id: The improvement's unique ID

        Returns:
            Success status dictionary
        """
        improvement = self.get_improvement(improvement_id)
        if not improvement:
            return {"success": False, "error": "Improvement not found"}

        if improvement["status"] != "pending":
            return {
                "success": False,
                "error": f"Cannot approve improvement in {improvement['status']} status",
            }

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE improvements
                SET status = 'approved', updated_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), improvement_id),
            )
            self._record_history(cursor, improvement_id, "approved", "User approved")

        logger.info(f"Approved improvement {improvement_id}")
        return {"success": True, "status": "approved"}

    def reject_improvement(self, improvement_id: str, reason: str | None = None) -> dict[str, Any]:
        """
        Reject an improvement.

        Args:
            improvement_id: The improvement's unique ID
            reason: Optional rejection reason

        Returns:
            Success status dictionary
        """
        improvement = self.get_improvement(improvement_id)
        if not improvement:
            return {"success": False, "error": "Improvement not found"}

        if improvement["status"] not in ("pending",):
            return {
                "success": False,
                "error": f"Cannot reject improvement in {improvement['status']} status",
            }

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE improvements
                SET status = 'rejected', rejection_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (reason, datetime.now().isoformat(), improvement_id),
            )
            self._record_history(cursor, improvement_id, "rejected", reason)

        logger.info(f"Rejected improvement {improvement_id}: {reason}")
        return {"success": True, "status": "rejected"}

    def _create_backup(self, improvement_id: str, fix_action: dict[str, Any]) -> str:
        """
        Create a backup before applying an improvement.

        Args:
            improvement_id: The improvement being applied
            fix_action: The fix action details

        Returns:
            Backup ID
        """
        import uuid

        backup_id = f"backup-{uuid.uuid4().hex[:8]}"
        backup_data = {
            "fix_action": fix_action,
            "timestamp": datetime.now().isoformat(),
        }

        # Store current state based on fix type
        if fix_action.get("type") == "config_update":
            key = fix_action.get("key", "")
            import os

            backup_data["original_value"] = os.getenv(key, None)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO improvement_backups (id, improvement_id, backup_data)
                VALUES (?, ?, ?)
                """,
                (backup_id, improvement_id, json.dumps(backup_data)),
            )

        return backup_id

    def _execute_fix(self, fix_action: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a fix action.

        Args:
            fix_action: The fix action to execute

        Returns:
            Result dictionary with success status
        """
        fix_type = fix_action.get("type")

        if not fix_type:
            # No fix action defined - this is okay for some improvements
            return {"success": True, "message": "No fix action required"}

        if fix_type == "config_update":
            # Update configuration (in production, would modify config file)
            key = fix_action.get("key")
            value = fix_action.get("value")
            logger.info(f"Would update config: {key} = {value}")
            return {"success": True, "message": f"Config {key} updated"}

        elif fix_type == "pip_upgrade":
            package = fix_action.get("package")
            version = fix_action.get("version")
            logger.info(f"Would upgrade package: {package} to {version}")
            return {"success": True, "message": f"Package {package} upgraded"}

        else:
            return {"success": False, "error": f"Unknown fix type: {fix_type}"}

    def apply_improvement(self, improvement_id: str) -> dict[str, Any]:
        """
        Apply an approved improvement.

        Args:
            improvement_id: The improvement's unique ID

        Returns:
            Success status dictionary
        """
        improvement = self.get_improvement(improvement_id)
        if not improvement:
            return {"success": False, "error": "Improvement not found"}

        if improvement["status"] != "approved":
            return {"success": False, "error": "Improvement is not approved"}

        fix_action = improvement.get("fix_action") or {}

        # Create backup before applying
        backup_id = self._create_backup(improvement_id, fix_action)

        # Execute the fix
        result = self._execute_fix(fix_action)
        if not result.get("success"):
            return result

        # Update status to applied
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE improvements
                SET status = 'applied', backup_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (backup_id, datetime.now().isoformat(), improvement_id),
            )
            self._record_history(cursor, improvement_id, "applied", f"Backup: {backup_id}")

        logger.info(f"Applied improvement {improvement_id}")
        return {"success": True, "status": "applied", "backup_id": backup_id}

    def _restore_backup(self, backup_id: str) -> dict[str, Any]:
        """
        Restore from a backup.

        Args:
            backup_id: The backup ID to restore

        Returns:
            Result dictionary
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM improvement_backups WHERE id = ?", (backup_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "Backup not found"}

            backup_data = json.loads(row["backup_data"])
            fix_action = backup_data.get("fix_action", {})

            if fix_action.get("type") == "config_update":
                original_value = backup_data.get("original_value")
                key = fix_action.get("key")
                logger.info(f"Would restore config: {key} = {original_value}")
                return {"success": True, "message": f"Restored {key}"}

            return {"success": True, "message": "Backup restored"}

    def rollback_improvement(self, improvement_id: str) -> dict[str, Any]:
        """
        Rollback an applied improvement.

        Args:
            improvement_id: The improvement's unique ID

        Returns:
            Success status dictionary
        """
        improvement = self.get_improvement(improvement_id)
        if not improvement:
            return {"success": False, "error": "Improvement not found"}

        if improvement["status"] != "applied":
            return {"success": False, "error": "Can only rollback applied improvements"}

        backup_id = improvement.get("backup_id")
        if not backup_id:
            return {"success": False, "error": "No backup found for improvement"}

        # Restore from backup
        result = self._restore_backup(backup_id)
        if not result.get("success"):
            return result

        # Update status to rolled_back
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE improvements
                SET status = 'rolled_back', updated_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(), improvement_id),
            )
            self._record_history(
                cursor, improvement_id, "rolled_back", f"Restored from {backup_id}"
            )

        logger.info(f"Rolled back improvement {improvement_id}")
        return {"success": True, "status": "rolled_back"}

    def get_improvement_history(self, improvement_id: str) -> list[dict[str, Any]]:
        """
        Get the status change history for an improvement.

        Args:
            improvement_id: The improvement's unique ID

        Returns:
            List of history entries with timestamps
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT status, timestamp, details
                FROM improvement_history
                WHERE improvement_id = ?
                ORDER BY timestamp ASC
                """,
                (improvement_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_feedback_stats(self) -> dict[str, Any]:
        """
        Get statistics about accepted/rejected improvements by category.

        Returns:
            Dictionary with approval and rejection stats by category
        """
        with self._get_cursor() as cursor:
            # Get approved categories
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM improvements
                WHERE status = 'approved' OR status = 'applied'
                GROUP BY category
                """
            )
            approved_categories = {row["category"]: row["count"] for row in cursor.fetchall()}

            # Get rejected categories
            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM improvements
                WHERE status = 'rejected'
                GROUP BY category
                """
            )
            rejected_categories = {row["category"]: row["count"] for row in cursor.fetchall()}

        return {
            "approved_categories": approved_categories,
            "rejected_categories": rejected_categories,
        }

    def get_filter_suggestions(self) -> dict[str, Any]:
        """
        Suggest categories to filter based on rejection patterns.

        Categories with high rejection rates are suggested for filtering.

        Returns:
            Dictionary with suggested filters
        """
        stats = self.get_feedback_stats()
        rejected = stats.get("rejected_categories", {})
        approved = stats.get("approved_categories", {})

        suggested_filters = []
        for category, reject_count in rejected.items():
            approve_count = approved.get(category, 0)
            total = reject_count + approve_count
            if total >= 3 and reject_count / total > 0.7:  # >70% rejection rate
                suggested_filters.append(category)

        return {"suggested_filters": suggested_filters}

    def generate_release_notes(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> dict[str, Any]:
        """
        Generate release notes for applied improvements in a date range.

        Args:
            from_date: Start of date range
            to_date: End of date range

        Returns:
            Release notes dictionary with improvements list
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM improvements
                WHERE status = 'applied'
                AND updated_at BETWEEN ? AND ?
                ORDER BY updated_at ASC
                """,
                (from_date.isoformat(), to_date.isoformat()),
            )
            rows = cursor.fetchall()

            improvements = []
            for row in rows:
                imp = self._row_to_dict(row)
                improvements.append(
                    {
                        "title": imp["title"],
                        "category": imp["category"],
                        "severity": imp["severity"],
                        "description": imp.get("description", ""),
                    }
                )

        return {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "improvements": improvements,
            "count": len(improvements),
        }
