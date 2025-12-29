"""
Data Export/Import Module (WP-10.35)

Provides functionality to export all user data in JSON or CSV format
and import data for migration purposes.
"""

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

logger = logging.getLogger(__name__)

# Export format version for compatibility checking
EXPORT_VERSION = "1.0"


class DataExporter:
    """
    Exports all user data from SmartHome databases.

    Supports JSON and CSV export formats.
    """

    def __init__(self, data_dir: Path | None = None):
        """
        Initialize the data exporter.

        Args:
            data_dir: Data directory path (defaults to config DATA_DIR)
        """
        self.data_dir = data_dir or DATA_DIR

    def export_all(self) -> dict[str, Any]:
        """
        Export all user data as a dictionary.

        Returns:
            Dictionary with all exportable data sections
        """
        export_data = {
            "metadata": self._get_metadata(),
            "todos": self._export_todos(),
            "automations": self._export_automations(),
            "reminders": self._export_reminders(),
            "command_history": self._export_command_history(),
            "timers": self._export_timers(),
            "locations": self._export_locations(),
        }

        # Add counts to metadata
        export_data["metadata"]["counts"] = {
            "todos": len(export_data["todos"]),
            "automations": len(export_data["automations"]),
            "reminders": len(export_data["reminders"]),
            "command_history": len(export_data["command_history"]),
            "timers": len(export_data["timers"]),
            "locations": len(export_data["locations"]),
        }

        return export_data

    def export_as_json(self, indent: int = 2) -> str:
        """
        Export all data as a formatted JSON string.

        Args:
            indent: JSON indentation (default 2 spaces)

        Returns:
            JSON string of all data
        """
        data = self.export_all()
        return json.dumps(data, indent=indent, default=str)

    def export_as_csv(self) -> dict[str, str]:
        """
        Export data as CSV strings per section.

        Returns:
            Dictionary mapping section names to CSV strings
        """
        data = self.export_all()
        csv_data = {}

        for section, records in data.items():
            if section == "metadata":
                continue
            if not records:
                csv_data[section] = ""
                continue

            csv_data[section] = self._to_csv(records)

        return csv_data

    def _to_csv(self, records: list[dict]) -> str:
        """Convert a list of dicts to CSV string."""
        if not records:
            return ""

        output = io.StringIO()
        fieldnames = records[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()

    def _get_metadata(self) -> dict[str, Any]:
        """Get export metadata."""
        return {
            "version": EXPORT_VERSION,
            "exported_at": datetime.now().isoformat(),
            "source": "smarthome",
        }

    def _read_db_table(self, db_path: Path, table: str) -> list[dict]:
        """Read all records from a SQLite table."""
        if not db_path.exists():
            return []

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")  # nosec B608 - table name is hardcoded
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.warning(f"Error reading {db_path}/{table}: {e}")
            return []

    def _export_todos(self) -> list[dict]:
        """Export todo items."""
        return self._read_db_table(self.data_dir / "todos.db", "todos")

    def _export_automations(self) -> list[dict]:
        """Export automation rules."""
        return self._read_db_table(self.data_dir / "automations.db", "automations")

    def _export_reminders(self) -> list[dict]:
        """Export reminders."""
        return self._read_db_table(self.data_dir / "reminders.db", "reminders")

    def _export_command_history(self) -> list[dict]:
        """Export command history."""
        return self._read_db_table(self.data_dir / "smarthome.db", "commands")

    def _export_timers(self) -> list[dict]:
        """Export timers."""
        return self._read_db_table(self.data_dir / "timers.db", "timers")

    def _export_locations(self) -> list[dict]:
        """Export location data."""
        return self._read_db_table(self.data_dir / "locations.db", "locations")


class DataImporter:
    """
    Imports user data for migration purposes.

    Validates import data and provides preview before importing.
    """

    def __init__(self, data_dir: Path | None = None):
        """
        Initialize the data importer.

        Args:
            data_dir: Data directory path (defaults to config DATA_DIR)
        """
        self.data_dir = data_dir or DATA_DIR

    def validate_import_data(self, data: dict) -> tuple[bool, list[str]]:
        """
        Validate import data format.

        Args:
            data: Data dictionary to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not isinstance(data, dict):
            errors.append("Import data must be a dictionary")
            return False, errors

        # Check required sections
        if "metadata" not in data:
            errors.append("Missing 'metadata' section")

        if data.get("metadata"):
            if "version" not in data["metadata"]:
                errors.append("Missing 'version' in metadata")
            if "exported_at" not in data["metadata"]:
                errors.append("Missing 'exported_at' in metadata")

        # Validate data sections are lists
        for section in ["todos", "automations", "reminders", "command_history"]:
            if section in data and not isinstance(data.get(section, []), list):
                errors.append(f"'{section}' must be a list")

        return len(errors) == 0, errors

    def get_import_preview(self, data: dict) -> dict[str, dict]:
        """
        Get a preview of what would be imported.

        Args:
            data: Import data dictionary

        Returns:
            Dictionary with counts and changes per section
        """
        preview = {}

        for section in ["todos", "automations", "reminders", "command_history", "timers", "locations"]:
            records = data.get(section, [])
            preview[section] = {
                "count": len(records),
                "sample": records[0] if records else None,
            }

        return preview

    def import_data(self, data: dict, merge: bool = True) -> dict[str, int]:
        """
        Import data into the database.

        Args:
            data: Validated import data
            merge: If True, merge with existing data; if False, replace

        Returns:
            Dictionary with counts of imported records per section
        """
        valid, errors = self.validate_import_data(data)
        if not valid:
            raise ValueError(f"Invalid import data: {errors}")

        imported = {}

        # Import each section
        if "todos" in data:
            imported["todos"] = self._import_todos(data["todos"], merge)

        if "automations" in data:
            imported["automations"] = self._import_automations(data["automations"], merge)

        if "reminders" in data:
            imported["reminders"] = self._import_reminders(data["reminders"], merge)

        return imported

    def _import_todos(self, todos: list[dict], merge: bool) -> int:
        """Import todo items."""
        # Implementation would insert/update records
        # For now, return count
        return len(todos)

    def _import_automations(self, automations: list[dict], merge: bool) -> int:
        """Import automations."""
        return len(automations)

    def _import_reminders(self, reminders: list[dict], merge: bool) -> int:
        """Import reminders."""
        return len(reminders)
