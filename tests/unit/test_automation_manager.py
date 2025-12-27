"""
Unit tests for AutomationManager.

Tests the core automation CRUD operations and validation.
Part of WP-4.2: Simple Automation Creation.
"""

import json
import pytest
import tempfile
from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import will be created after tests
# from src.automation_manager import AutomationManager, VALID_TRIGGER_TYPES, VALID_ACTION_TYPES


class TestAutomationManagerInitialization:
    """Tests for AutomationManager initialization."""

    def test_creates_database_file(self, tmp_path):
        """AutomationManager creates database file on initialization."""
        from src.automation_manager import AutomationManager

        database_path = tmp_path / "test_automations.db"
        manager = AutomationManager(database_path=database_path)

        assert database_path.exists()

    def test_creates_automations_table(self, tmp_path):
        """AutomationManager creates automations table on initialization."""
        from src.automation_manager import AutomationManager

        database_path = tmp_path / "test_automations.db"
        manager = AutomationManager(database_path=database_path)

        # Verify table exists by querying it
        automations = manager.get_automations()
        assert automations == []

    def test_uses_default_path_when_none_provided(self):
        """AutomationManager uses default path from config when none provided."""
        from src.automation_manager import AutomationManager, DEFAULT_DATABASE_PATH

        # When no path is provided, manager uses DEFAULT_DATABASE_PATH
        manager = AutomationManager()
        assert manager.database_path == DEFAULT_DATABASE_PATH


class TestCreateAutomation:
    """Tests for creating automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_create_time_based_automation(self, manager):
        """Can create a simple time-based automation."""
        trigger_config = {
            "type": "time",
            "time": "20:00",
            "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        }
        action_config = {
            "type": "agent_command",
            "command": "turn living room to warm yellow"
        }

        automation_id = manager.create_automation(
            name="Evening lights",
            trigger_type="time",
            trigger_config=trigger_config,
            action_type="agent_command",
            action_config=action_config
        )

        assert automation_id is not None
        assert automation_id > 0

    def test_create_automation_returns_id(self, manager):
        """Creating automation returns the new automation ID."""
        automation_id = manager.create_automation(
            name="Test automation",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00", "days": ["mon"]},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        automation = manager.get_automation(automation_id)
        assert automation is not None
        assert automation["id"] == automation_id

    def test_create_state_based_automation(self, manager):
        """Can create a state-change based automation."""
        trigger_config = {
            "type": "state",
            "entity_id": "person.katherine",
            "from_state": "home",
            "to_state": "not_home"
        }
        action_config = {
            "type": "agent_command",
            "command": "start vacuum"
        }

        automation_id = manager.create_automation(
            name="Vacuum when leaving",
            trigger_type="state",
            trigger_config=trigger_config,
            action_type="agent_command",
            action_config=action_config
        )

        assert automation_id is not None

    def test_create_automation_with_description(self, manager):
        """Can create automation with optional description."""
        automation_id = manager.create_automation(
            name="Morning routine",
            description="Turns on lights when I wake up",
            trigger_type="time",
            trigger_config={"type": "time", "time": "07:00", "days": ["mon", "tue", "wed", "thu", "fri"]},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "turn bedroom to energize"}
        )

        automation = manager.get_automation(automation_id)
        assert automation["description"] == "Turns on lights when I wake up"

    def test_create_automation_validates_empty_name(self, manager):
        """Creating automation with empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            manager.create_automation(
                name="",
                trigger_type="time",
                trigger_config={"type": "time", "time": "09:00"},
                action_type="agent_command",
                action_config={"type": "agent_command", "command": "test"}
            )

    def test_create_automation_validates_trigger_type(self, manager):
        """Creating automation with invalid trigger type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            manager.create_automation(
                name="Test",
                trigger_type="invalid_type",
                trigger_config={},
                action_type="agent_command",
                action_config={"type": "agent_command", "command": "test"}
            )

    def test_create_automation_validates_action_type(self, manager):
        """Creating automation with invalid action type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid action_type"):
            manager.create_automation(
                name="Test",
                trigger_type="time",
                trigger_config={"type": "time", "time": "09:00"},
                action_type="invalid_action",
                action_config={}
            )

    def test_automation_enabled_by_default(self, manager):
        """New automations are enabled by default."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        automation = manager.get_automation(automation_id)
        assert automation["enabled"] is True


class TestGetAutomation:
    """Tests for retrieving automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_get_automation_by_id(self, manager):
        """Can retrieve automation by ID."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        automation = manager.get_automation(automation_id)

        assert automation is not None
        assert automation["name"] == "Test"

    def test_get_nonexistent_automation_returns_none(self, manager):
        """Getting nonexistent automation returns None."""
        automation = manager.get_automation(99999)
        assert automation is None

    def test_get_automation_includes_trigger_config(self, manager):
        """Retrieved automation includes parsed trigger_config."""
        trigger_config = {"type": "time", "time": "20:00", "days": ["mon", "fri"]}
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config=trigger_config,
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        automation = manager.get_automation(automation_id)

        assert automation["trigger_config"] == trigger_config

    def test_get_automation_includes_action_config(self, manager):
        """Retrieved automation includes parsed action_config."""
        action_config = {"type": "agent_command", "command": "turn lights on"}
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config=action_config
        )

        automation = manager.get_automation(automation_id)

        assert automation["action_config"] == action_config


class TestListAutomations:
    """Tests for listing automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_list_all_automations(self, manager):
        """Can list all automations."""
        manager.create_automation(
            name="Automation 1",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test1"}
        )
        manager.create_automation(
            name="Automation 2",
            trigger_type="time",
            trigger_config={"type": "time", "time": "10:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test2"}
        )

        automations = manager.get_automations()

        assert len(automations) == 2

    def test_list_enabled_only(self, manager):
        """Can filter to enabled automations only."""
        auto1 = manager.create_automation(
            name="Enabled",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        auto2 = manager.create_automation(
            name="Disabled",
            trigger_type="time",
            trigger_config={"type": "time", "time": "10:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        manager.toggle_automation(auto2)  # Disable the second one

        automations = manager.get_automations(enabled_only=True)

        assert len(automations) == 1
        assert automations[0]["name"] == "Enabled"

    def test_list_by_trigger_type(self, manager):
        """Can filter automations by trigger type."""
        manager.create_automation(
            name="Time based",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        manager.create_automation(
            name="State based",
            trigger_type="state",
            trigger_config={"type": "state", "entity_id": "light.test", "to_state": "on"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        time_automations = manager.get_automations(trigger_type="time")
        state_automations = manager.get_automations(trigger_type="state")

        assert len(time_automations) == 1
        assert time_automations[0]["name"] == "Time based"
        assert len(state_automations) == 1
        assert state_automations[0]["name"] == "State based"

    def test_list_empty_database(self, manager):
        """Listing empty database returns empty list."""
        automations = manager.get_automations()
        assert automations == []


class TestUpdateAutomation:
    """Tests for updating automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_update_automation_name(self, manager):
        """Can update automation name."""
        automation_id = manager.create_automation(
            name="Original name",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        success = manager.update_automation(automation_id, name="New name")

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["name"] == "New name"

    def test_update_automation_description(self, manager):
        """Can update automation description."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        success = manager.update_automation(automation_id, description="New description")

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["description"] == "New description"

    def test_update_automation_trigger_config(self, manager):
        """Can update automation trigger config."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        new_trigger = {"type": "time", "time": "21:00", "days": ["sat", "sun"]}
        success = manager.update_automation(automation_id, trigger_config=new_trigger)

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["trigger_config"] == new_trigger

    def test_update_automation_action_config(self, manager):
        """Can update automation action config."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "old command"}
        )

        new_action = {"type": "agent_command", "command": "new command"}
        success = manager.update_automation(automation_id, action_config=new_action)

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["action_config"] == new_action

    def test_update_nonexistent_automation_returns_false(self, manager):
        """Updating nonexistent automation returns False."""
        success = manager.update_automation(99999, name="New name")
        assert success is False

    def test_update_sets_updated_at_timestamp(self, manager):
        """Updating automation sets updated_at timestamp."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        original = manager.get_automation(automation_id)
        original_updated = original["updated_at"]

        import time as time_module
        time_module.sleep(0.01)  # Small delay to ensure different timestamp

        manager.update_automation(automation_id, name="Updated")
        updated = manager.get_automation(automation_id)

        assert updated["updated_at"] >= original_updated


class TestDeleteAutomation:
    """Tests for deleting automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_delete_automation(self, manager):
        """Can delete an automation."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        success = manager.delete_automation(automation_id)

        assert success is True
        assert manager.get_automation(automation_id) is None

    def test_delete_nonexistent_automation_returns_false(self, manager):
        """Deleting nonexistent automation returns False."""
        success = manager.delete_automation(99999)
        assert success is False


class TestToggleAutomation:
    """Tests for enabling/disabling automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_toggle_disables_enabled_automation(self, manager):
        """Toggling enabled automation disables it."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        success = manager.toggle_automation(automation_id)

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["enabled"] is False

    def test_toggle_enables_disabled_automation(self, manager):
        """Toggling disabled automation enables it."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        manager.toggle_automation(automation_id)  # Disable

        success = manager.toggle_automation(automation_id)  # Enable

        assert success is True
        automation = manager.get_automation(automation_id)
        assert automation["enabled"] is True

    def test_toggle_nonexistent_returns_false(self, manager):
        """Toggling nonexistent automation returns False."""
        success = manager.toggle_automation(99999)
        assert success is False


class TestValidation:
    """Tests for config validation."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_validate_time_trigger_valid(self, manager):
        """Valid time trigger config passes validation."""
        config = {"type": "time", "time": "20:00", "days": ["mon", "tue"]}
        assert manager.validate_trigger_config("time", config) is True

    def test_validate_time_trigger_missing_time(self, manager):
        """Time trigger without time field fails validation."""
        config = {"type": "time", "days": ["mon"]}
        assert manager.validate_trigger_config("time", config) is False

    def test_validate_time_trigger_invalid_time_format(self, manager):
        """Time trigger with invalid time format fails validation."""
        config = {"type": "time", "time": "invalid"}
        assert manager.validate_trigger_config("time", config) is False

    def test_validate_state_trigger_valid(self, manager):
        """Valid state trigger config passes validation."""
        config = {"type": "state", "entity_id": "light.living_room", "to_state": "on"}
        assert manager.validate_trigger_config("state", config) is True

    def test_validate_state_trigger_missing_entity(self, manager):
        """State trigger without entity_id fails validation."""
        config = {"type": "state", "to_state": "on"}
        assert manager.validate_trigger_config("state", config) is False

    def test_validate_agent_command_action_valid(self, manager):
        """Valid agent_command action config passes validation."""
        config = {"type": "agent_command", "command": "turn lights on"}
        assert manager.validate_action_config("agent_command", config) is True

    def test_validate_agent_command_action_missing_command(self, manager):
        """Agent command action without command fails validation."""
        config = {"type": "agent_command"}
        assert manager.validate_action_config("agent_command", config) is False

    def test_validate_ha_service_action_valid(self, manager):
        """Valid ha_service action config passes validation."""
        config = {
            "type": "ha_service",
            "domain": "light",
            "service": "turn_on",
            "service_data": {"entity_id": "light.test"}
        }
        assert manager.validate_action_config("ha_service", config) is True

    def test_validate_ha_service_action_missing_domain(self, manager):
        """HA service action without domain fails validation."""
        config = {"type": "ha_service", "service": "turn_on"}
        assert manager.validate_action_config("ha_service", config) is False


class TestDueAutomations:
    """Tests for getting due automations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_get_due_time_automations(self, manager):
        """Can get automations due at current time."""
        # Create automation for current time
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%a").lower()

        manager.create_automation(
            name="Due now",
            trigger_type="time",
            trigger_config={"type": "time", "time": current_time, "days": [current_day]},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        due = manager.get_due_automations()

        assert len(due) >= 1
        assert any(a["name"] == "Due now" for a in due)

    def test_get_due_excludes_disabled(self, manager):
        """Due automations excludes disabled ones."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%a").lower()

        automation_id = manager.create_automation(
            name="Disabled",
            trigger_type="time",
            trigger_config={"type": "time", "time": current_time, "days": [current_day]},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        manager.toggle_automation(automation_id)  # Disable

        due = manager.get_due_automations()

        assert not any(a["name"] == "Disabled" for a in due)

    def test_get_due_respects_days(self, manager):
        """Due automations respects day-of-week config."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        # Use a day that's not today
        other_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        current_day = now.strftime("%a").lower()
        other_days.remove(current_day)

        manager.create_automation(
            name="Wrong day",
            trigger_type="time",
            trigger_config={"type": "time", "time": current_time, "days": other_days},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        due = manager.get_due_automations()

        assert not any(a["name"] == "Wrong day" for a in due)


class TestMarkTriggered:
    """Tests for marking automations as triggered."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_mark_triggered_updates_last_triggered(self, manager):
        """Marking automation triggered updates last_triggered timestamp."""
        automation_id = manager.create_automation(
            name="Test",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )

        before = manager.get_automation(automation_id)
        assert before["last_triggered"] is None

        manager.mark_triggered(automation_id)

        after = manager.get_automation(automation_id)
        assert after["last_triggered"] is not None


class TestStats:
    """Tests for automation statistics."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a fresh manager for each test."""
        from src.automation_manager import AutomationManager
        return AutomationManager(database_path=tmp_path / "test.db")

    def test_get_stats_returns_counts(self, manager):
        """Stats returns total, enabled, and disabled counts."""
        auto1 = manager.create_automation(
            name="Enabled 1",
            trigger_type="time",
            trigger_config={"type": "time", "time": "09:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        auto2 = manager.create_automation(
            name="Enabled 2",
            trigger_type="time",
            trigger_config={"type": "time", "time": "10:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        auto3 = manager.create_automation(
            name="Disabled",
            trigger_type="time",
            trigger_config={"type": "time", "time": "11:00"},
            action_type="agent_command",
            action_config={"type": "agent_command", "command": "test"}
        )
        manager.toggle_automation(auto3)  # Disable

        stats = manager.get_stats()

        assert stats["total"] == 3
        assert stats["enabled"] == 2
        assert stats["disabled"] == 1
