"""
Smart Home Assistant - Automation Manager

Manages home automation rules with SQLite persistence.
Part of WP-4.2: Simple Automation Creation.
"""

import json
import logging
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DATABASE_PATH = DATA_DIR / "automations.db"

# Valid trigger types
VALID_TRIGGER_TYPES = ["time", "state", "presence"]

# Valid action types
VALID_ACTION_TYPES = ["agent_command", "ha_service"]

# Valid days of week
VALID_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class AutomationManager:
    """
    Manages home automation rules with SQLite persistence.

    Provides CRUD operations for automations with support for:
    - Time-based triggers (specific times, days of week)
    - State-based triggers (entity state changes)
    - Agent command actions (natural language commands)
    - Home Assistant service call actions
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize AutomationManager with database connection.

        Args:
            database_path: Path to SQLite database file (defaults to DATA_DIR/automations.db)
        """
        self.database_path = database_path or DEFAULT_DATABASE_PATH
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        connection = sqlite3.connect(self.database_path)
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    trigger_type TEXT NOT NULL,
                    trigger_config TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_config TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    ha_automation_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_triggered TIMESTAMP
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_automations_enabled
                ON automations(enabled)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_automations_trigger_type
                ON automations(trigger_type)
            """)

        logger.info(f"AutomationManager initialized with database at {self.database_path}")

    def create_automation(
        self,
        name: str,
        trigger_type: str,
        trigger_config: dict,
        action_type: str,
        action_config: dict,
        description: str | None = None,
    ) -> int:
        """
        Create a new automation.

        Args:
            name: Name for the automation (required, non-empty)
            trigger_type: Type of trigger ('time', 'state', 'presence')
            trigger_config: Trigger configuration dict
            action_type: Type of action ('agent_command', 'ha_service')
            action_config: Action configuration dict
            description: Optional description

        Returns:
            ID of the created automation

        Raises:
            ValueError: If validation fails
        """
        if not name or not name.strip():
            raise ValueError("name cannot be empty")

        if trigger_type not in VALID_TRIGGER_TYPES:
            raise ValueError(
                f"Invalid trigger_type: {trigger_type}. Must be one of {VALID_TRIGGER_TYPES}"
            )

        if action_type not in VALID_ACTION_TYPES:
            raise ValueError(
                f"Invalid action_type: {action_type}. Must be one of {VALID_ACTION_TYPES}"
            )

        name = name.strip()
        trigger_config_json = json.dumps(trigger_config)
        action_config_json = json.dumps(action_config)

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO automations (name, description, trigger_type, trigger_config, action_type, action_config)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    name,
                    description,
                    trigger_type,
                    trigger_config_json,
                    action_type,
                    action_config_json,
                ),
            )

            automation_id = cursor.lastrowid
            logger.info(
                f"Created automation {automation_id}: '{name}' ({trigger_type} -> {action_type})"
            )
            return automation_id

    def get_automation(self, automation_id: int) -> dict[str, Any] | None:
        """
        Get an automation by ID.

        Args:
            automation_id: Automation ID

        Returns:
            Automation dict or None if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_dict(row)

    def get_automations(
        self,
        enabled_only: bool = False,
        trigger_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get automations with optional filtering.

        Args:
            enabled_only: Only return enabled automations
            trigger_type: Filter by trigger type

        Returns:
            List of automation dicts ordered by name
        """
        query = "SELECT * FROM automations WHERE 1=1"
        params = []

        if enabled_only:
            query += " AND enabled = 1"

        if trigger_type:
            query += " AND trigger_type = ?"
            params.append(trigger_type)

        query += " ORDER BY name ASC"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_automation(self, automation_id: int, **kwargs) -> bool:
        """
        Update an automation.

        Args:
            automation_id: Automation ID
            **kwargs: Fields to update (name, description, trigger_config, action_config, enabled)

        Returns:
            True if automation was updated, False if not found
        """
        allowed_fields = {"name", "description", "trigger_config", "action_config", "enabled"}
        updates = {key: value for key, value in kwargs.items() if key in allowed_fields}

        if not updates:
            return False

        # Special handling for JSON fields
        if "trigger_config" in updates:
            updates["trigger_config"] = json.dumps(updates["trigger_config"])
        if "action_config" in updates:
            updates["action_config"] = json.dumps(updates["action_config"])

        # Always update updated_at
        updates["updated_at"] = datetime.now().isoformat()

        # Build dynamic SET clause - safe because keys are validated against allowed_fields
        # Column names are from allowlist, values use parameterized queries
        set_clause = ", ".join(f"{key} = ?" for key in updates)  # nosec B608
        values = list(updates.values()) + [automation_id]

        with self._get_cursor() as cursor:
            cursor.execute(f"UPDATE automations SET {set_clause} WHERE id = ?", values)  # nosec B608
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Updated automation {automation_id}: {list(updates.keys())}")
            return success

    def delete_automation(self, automation_id: int) -> bool:
        """
        Delete an automation.

        Args:
            automation_id: Automation ID

        Returns:
            True if automation was deleted, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Deleted automation {automation_id}")
            return success

    def toggle_automation(self, automation_id: int) -> bool:
        """
        Toggle automation enabled/disabled state.

        Args:
            automation_id: Automation ID

        Returns:
            True if toggled, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE automations
                SET enabled = NOT enabled, updated_at = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), automation_id),
            )
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Toggled automation {automation_id}")
            return success

    def validate_trigger_config(self, trigger_type: str, config: dict) -> bool:
        """
        Validate a trigger configuration.

        Args:
            trigger_type: Type of trigger
            config: Trigger configuration dict

        Returns:
            True if valid, False otherwise
        """
        if trigger_type == "time":
            if "time" not in config:
                return False
            # Validate time format (HH:MM)
            time_str = config.get("time", "")
            if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_str):
                return False
            return True

        elif trigger_type == "state" or trigger_type == "presence":
            if "entity_id" not in config:
                return False
            return True

        return False

    def validate_action_config(self, action_type: str, config: dict) -> bool:
        """
        Validate an action configuration.

        Args:
            action_type: Type of action
            config: Action configuration dict

        Returns:
            True if valid, False otherwise
        """
        if action_type == "agent_command":
            if "command" not in config:
                return False
            return True

        elif action_type == "ha_service":
            if "domain" not in config or "service" not in config:
                return False
            return True

        return False

    def get_due_automations(self) -> list[dict[str, Any]]:
        """
        Get time-based automations that are due now.

        Checks enabled automations with time triggers that match:
        - Current time (within minute precision)
        - Current day of week

        Returns:
            List of automation dicts that are due
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%a").lower()

        automations = self.get_automations(enabled_only=True, trigger_type="time")
        due = []

        for automation in automations:
            trigger_config = automation["trigger_config"]
            trigger_time = trigger_config.get("time", "")
            trigger_days = trigger_config.get("days", VALID_DAYS)

            # Check if time matches
            if trigger_time != current_time:
                continue

            # Check if day matches
            if current_day not in trigger_days:
                continue

            due.append(automation)

        return due

    def mark_triggered(self, automation_id: int) -> bool:
        """
        Mark an automation as triggered.

        Args:
            automation_id: Automation ID

        Returns:
            True if marked, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE automations
                SET last_triggered = ?
                WHERE id = ?
            """,
                (datetime.now().isoformat(), automation_id),
            )
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Marked automation {automation_id} as triggered")
            return success

    def get_stats(self) -> dict[str, int]:
        """
        Get automation statistics.

        Returns:
            Dict with total, enabled, and disabled counts
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled,
                    SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) as disabled
                FROM automations
            """)
            row = cursor.fetchone()
            return {
                "total": row["total"] or 0,
                "enabled": row["enabled"] or 0,
                "disabled": row["disabled"] or 0,
            }

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a database row to a dict with parsed JSON fields."""
        result = dict(row)
        # Parse JSON fields
        if result.get("trigger_config"):
            result["trigger_config"] = json.loads(result["trigger_config"])
        if result.get("action_config"):
            result["action_config"] = json.loads(result["action_config"])
        # Convert enabled to boolean
        result["enabled"] = bool(result.get("enabled", 1))
        return result


# Singleton instance
_automation_manager: AutomationManager | None = None


def get_automation_manager() -> AutomationManager:
    """Get the singleton AutomationManager instance."""
    global _automation_manager
    if _automation_manager is None:
        _automation_manager = AutomationManager()
    return _automation_manager
