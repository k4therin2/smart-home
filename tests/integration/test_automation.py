"""
Integration tests for Automation feature.

Tests the end-to-end automation workflow including:
- Creating automations via agent tools
- Natural language time parsing
- Automation lifecycle (create, list, toggle, delete)
- Edge cases and error handling

Part of WP-4.2: Simple Automation Creation.
"""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.automation import (
    create_automation,
    list_automations,
    toggle_automation,
    delete_automation,
    update_automation,
    execute_automation_tool,
    _parse_time,
    _parse_days,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    database_path = tmp_path / "test_automations.db"

    # Patch the singleton to use temp database
    with patch('tools.automation.get_automation_manager') as mock_get:
        from src.automation_manager import AutomationManager
        manager = AutomationManager(database_path=database_path)
        mock_get.return_value = manager
        yield manager


class TestCreateAutomationTool:
    """Tests for create_automation tool."""

    def test_create_time_based_automation_simple(self, temp_db):
        """Can create a simple time-based automation."""
        result = create_automation(
            name="Evening lights",
            trigger_type="time",
            trigger_time="20:00",
            action_command="turn living room to warm yellow"
        )

        assert result["success"] is True
        assert result["automation_id"] > 0
        assert "Evening lights" in result["message"]

    def test_create_automation_with_am_pm_time(self, temp_db):
        """Can parse am/pm time format."""
        result = create_automation(
            name="Morning lights",
            trigger_type="time",
            trigger_time="8pm",
            action_command="turn bedroom on"
        )

        assert result["success"] is True
        assert "20:00" in result["message"]

    def test_create_automation_with_days(self, temp_db):
        """Can specify days of week."""
        result = create_automation(
            name="Weekday alarm",
            trigger_type="time",
            trigger_time="07:00",
            trigger_days=["mon", "tue", "wed", "thu", "fri"],
            action_command="turn on bedroom lights"
        )

        assert result["success"] is True
        assert "weekdays" in result["message"].lower()

    def test_create_state_based_automation(self, temp_db):
        """Can create state-based automation."""
        result = create_automation(
            name="Goodbye vacuum",
            trigger_type="state",
            trigger_entity="person.katherine",
            trigger_to_state="not_home",
            action_command="start vacuum"
        )

        assert result["success"] is True
        assert "becomes" in result["message"]

    def test_create_automation_missing_name_fails(self, temp_db):
        """Creating automation without name fails."""
        result = create_automation(
            name="",
            trigger_type="time",
            trigger_time="20:00",
            action_command="test"
        )

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_create_automation_invalid_time_fails(self, temp_db):
        """Creating automation with invalid time fails."""
        result = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="invalid",
            action_command="test"
        )

        assert result["success"] is False
        assert "time" in result["error"].lower()

    def test_create_state_automation_missing_entity_fails(self, temp_db):
        """State automation without entity fails."""
        result = create_automation(
            name="Test",
            trigger_type="state",
            trigger_to_state="on",
            action_command="test"
        )

        assert result["success"] is False
        assert "entity" in result["error"].lower()


class TestListAutomationsTool:
    """Tests for list_automations tool."""

    def test_list_empty_automations(self, temp_db):
        """Listing with no automations returns empty."""
        result = list_automations()

        assert result["success"] is True
        assert result["count"] == 0
        assert "No automations" in result["message"]

    def test_list_all_automations(self, temp_db):
        """Can list all automations."""
        create_automation(
            name="Auto 1",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test1"
        )
        create_automation(
            name="Auto 2",
            trigger_type="time",
            trigger_time="10:00",
            action_command="test2"
        )

        result = list_automations()

        assert result["success"] is True
        assert result["count"] == 2
        assert "Auto 1" in result["message"]
        assert "Auto 2" in result["message"]

    def test_list_enabled_only(self, temp_db):
        """Can filter to enabled automations only."""
        auto1 = create_automation(
            name="Enabled",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )
        auto2 = create_automation(
            name="Will Disable",
            trigger_type="time",
            trigger_time="10:00",
            action_command="test"
        )
        toggle_automation(automation_id=auto2["automation_id"])

        result = list_automations(enabled_only=True)

        assert result["count"] == 1
        assert "Enabled" in result["message"]
        assert "Will Disable" not in result["message"]


class TestToggleAutomationTool:
    """Tests for toggle_automation tool."""

    def test_toggle_by_id(self, temp_db):
        """Can toggle automation by ID."""
        created = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )

        result = toggle_automation(automation_id=created["automation_id"])

        assert result["success"] is True
        assert "Disabled" in result["message"]

    def test_toggle_by_name(self, temp_db):
        """Can toggle automation by name match."""
        create_automation(
            name="Evening lights",
            trigger_type="time",
            trigger_time="20:00",
            action_command="test"
        )

        result = toggle_automation(name_match="evening")

        assert result["success"] is True
        assert "Disabled" in result["message"]

    def test_toggle_enables_disabled(self, temp_db):
        """Toggling disabled automation enables it."""
        created = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )
        toggle_automation(automation_id=created["automation_id"])  # Disable

        result = toggle_automation(automation_id=created["automation_id"])  # Enable

        assert result["success"] is True
        assert "Enabled" in result["message"]

    def test_toggle_nonexistent_fails(self, temp_db):
        """Toggling nonexistent automation fails."""
        result = toggle_automation(automation_id=99999)

        assert result["success"] is False


class TestDeleteAutomationTool:
    """Tests for delete_automation tool."""

    def test_delete_by_id(self, temp_db):
        """Can delete automation by ID."""
        created = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )

        result = delete_automation(automation_id=created["automation_id"])

        assert result["success"] is True
        assert list_automations()["count"] == 0

    def test_delete_by_name(self, temp_db):
        """Can delete automation by name match."""
        create_automation(
            name="Evening lights",
            trigger_type="time",
            trigger_time="20:00",
            action_command="test"
        )

        result = delete_automation(name_match="evening")

        assert result["success"] is True

    def test_delete_nonexistent_fails(self, temp_db):
        """Deleting nonexistent automation fails."""
        result = delete_automation(automation_id=99999)

        assert result["success"] is False


class TestUpdateAutomationTool:
    """Tests for update_automation tool."""

    def test_update_name(self, temp_db):
        """Can update automation name."""
        created = create_automation(
            name="Original",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )

        result = update_automation(
            automation_id=created["automation_id"],
            new_name="Updated"
        )

        assert result["success"] is True
        assert "Updated" in result["message"]

    def test_update_time(self, temp_db):
        """Can update automation time."""
        created = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="09:00",
            action_command="test"
        )

        result = update_automation(
            automation_id=created["automation_id"],
            new_time="21:00"
        )

        assert result["success"] is True
        assert "21:00" in result["message"]

    def test_update_action(self, temp_db):
        """Can update automation action."""
        created = create_automation(
            name="Test",
            trigger_type="time",
            trigger_time="09:00",
            action_command="original command"
        )

        result = update_automation(
            automation_id=created["automation_id"],
            new_action="new command"
        )

        assert result["success"] is True
        assert "new command" in result["message"]


class TestTimeParsingHelper:
    """Tests for _parse_time helper function."""

    def test_parse_24h_format(self):
        """Parses 24-hour format."""
        assert _parse_time("20:00") == "20:00"
        assert _parse_time("9:30") == "09:30"
        assert _parse_time("00:00") == "00:00"

    def test_parse_12h_format_pm(self):
        """Parses 12-hour PM format."""
        assert _parse_time("8pm") == "20:00"
        assert _parse_time("8:30pm") == "20:30"
        assert _parse_time("12pm") == "12:00"

    def test_parse_12h_format_am(self):
        """Parses 12-hour AM format."""
        assert _parse_time("8am") == "08:00"
        assert _parse_time("12am") == "00:00"
        assert _parse_time("6:15am") == "06:15"

    def test_parse_invalid_time(self):
        """Returns None for invalid time."""
        assert _parse_time("invalid") is None
        assert _parse_time("25:00") is None
        assert _parse_time("") is None


class TestDaysParsingHelper:
    """Tests for _parse_days helper function."""

    def test_parse_weekdays_shortcut(self):
        """Parses 'weekdays' shortcut."""
        result = _parse_days(["weekdays"])
        assert set(result) == {"mon", "tue", "wed", "thu", "fri"}

    def test_parse_weekends_shortcut(self):
        """Parses 'weekends' shortcut."""
        result = _parse_days(["weekends"])
        assert set(result) == {"sat", "sun"}

    def test_parse_full_day_names(self):
        """Parses full day names."""
        result = _parse_days(["monday", "wednesday", "friday"])
        assert result == ["mon", "wed", "fri"]

    def test_parse_mixed_formats(self):
        """Parses mixed formats."""
        result = _parse_days(["mon", "wednesday", "fri"])
        assert result == ["mon", "wed", "fri"]

    def test_parse_empty_returns_all_days(self):
        """Empty input returns all days."""
        result = _parse_days(None)
        assert len(result) == 7


class TestExecuteAutomationTool:
    """Tests for execute_automation_tool dispatcher."""

    def test_dispatch_create(self, temp_db):
        """Dispatches to create_automation."""
        result = execute_automation_tool("create_automation", {
            "name": "Test",
            "trigger_type": "time",
            "trigger_time": "20:00",
            "action_command": "test"
        })

        assert result["success"] is True

    def test_dispatch_list(self, temp_db):
        """Dispatches to list_automations."""
        result = execute_automation_tool("list_automations", {})

        assert result["success"] is True

    def test_dispatch_unknown_tool(self, temp_db):
        """Unknown tool returns error."""
        result = execute_automation_tool("unknown_tool", {})

        assert result["success"] is False
        assert "Unknown" in result["error"]
