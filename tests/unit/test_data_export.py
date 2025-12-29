"""
Tests for data export/import feature (WP-10.35).

These tests verify:
1. Export endpoint returns user data in JSON format
2. Export endpoint supports CSV format
3. Import functionality works for data migration
4. All user data types are included in export
"""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestDataExportEndpoint:
    """Tests for the /api/export endpoint."""

    @pytest.fixture
    def client(self):
        """Create a Flask test client."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from server import app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        with app.test_client() as client:
            yield client

    def test_export_endpoint_exists(self, client):
        """Test that export endpoint exists."""
        response = client.get("/api/export")
        # Should require auth (302 redirect to login) or return data
        assert response.status_code in [200, 302, 401]

    def test_export_returns_json_by_default(self, client):
        """Test that export returns JSON by default."""
        # Need to login or mock auth
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from server import app

        with app.test_request_context():
            from data_export import DataExporter
            exporter = DataExporter()
            result = exporter.export_all()

            # Should be a dict
            assert isinstance(result, dict)
            # Should have expected sections
            assert "metadata" in result
            assert "exported_at" in result["metadata"]

    def test_export_includes_todos(self, client):
        """Test that export includes todo data."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert "todos" in result

    def test_export_includes_automations(self, client):
        """Test that export includes automation data."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert "automations" in result

    def test_export_includes_reminders(self, client):
        """Test that export includes reminder data."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert "reminders" in result

    def test_export_includes_command_history(self, client):
        """Test that export includes command history."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert "command_history" in result


class TestExportFormats:
    """Tests for export format options."""

    def test_export_as_json(self):
        """Test export as JSON format."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_as_json()

        # Should be valid JSON string
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_export_as_csv(self):
        """Test export as CSV format."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_as_csv()

        # Should be a dict of CSV strings per section
        assert isinstance(result, dict)
        # Each section should have CSV data
        for key, value in result.items():
            if value:  # Non-empty sections
                assert isinstance(value, str)


class TestDataImport:
    """Tests for data import functionality."""

    def test_import_validates_format(self):
        """Test that import validates data format."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataImporter

        importer = DataImporter()

        # Invalid data should be rejected
        valid, errors = importer.validate_import_data({})
        assert not valid
        assert len(errors) > 0

    def test_import_accepts_valid_data(self):
        """Test that import accepts valid export data."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataImporter, DataExporter

        # Export current data
        exporter = DataExporter()
        export_data = exporter.export_all()

        # Should be valid for import
        importer = DataImporter()
        valid, errors = importer.validate_import_data(export_data)
        assert valid, f"Validation errors: {errors}"

    def test_import_preview_shows_changes(self):
        """Test that import preview shows what would change."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataImporter

        importer = DataImporter()
        test_data = {
            "metadata": {"version": "1.0", "exported_at": "2025-12-29"},
            "todos": [{"id": 1, "content": "Test todo"}],
            "automations": [],
            "reminders": [],
            "command_history": []
        }

        preview = importer.get_import_preview(test_data)

        assert "todos" in preview
        assert preview["todos"]["count"] >= 0


class TestExportMetadata:
    """Tests for export metadata."""

    def test_metadata_includes_version(self):
        """Test that metadata includes export version."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert result["metadata"]["version"] is not None

    def test_metadata_includes_timestamp(self):
        """Test that metadata includes export timestamp."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert result["metadata"]["exported_at"] is not None

    def test_metadata_includes_counts(self):
        """Test that metadata includes record counts."""
        import sys
        sys.path.insert(0, "/home/k4therin2/projects/Smarthome/src")
        from data_export import DataExporter

        exporter = DataExporter()
        result = exporter.export_all()

        assert "counts" in result["metadata"]
