"""
Integration tests for Timer and Alarm Tools (WP-4.3)

Tests the full flow from tool functions through TimerManager class.
"""

import pytest
from datetime import datetime, timedelta
import tempfile
import os


class TestSetTimerIntegration:
    """Integration tests for setting timers via tools."""

    def test_set_timer_basic(self, timer_setup):
        """Should set a timer via tool function."""
        from tools.timers import set_timer

        result = set_timer("10 minutes")

        assert result["success"] is True
        assert result["timer_id"] > 0
        assert result["duration_seconds"] == 600
        assert "10 minute" in result["message"]

    def test_set_timer_with_name(self, timer_setup):
        """Should set a named timer."""
        from tools.timers import set_timer

        result = set_timer("5 minutes", name="pizza")

        assert result["success"] is True
        assert result["name"] == "pizza"
        assert "pizza" in result["message"]

    def test_set_timer_hours_and_minutes(self, timer_setup):
        """Should parse complex duration."""
        from tools.timers import set_timer

        result = set_timer("1 hour 30 minutes")

        assert result["success"] is True
        assert result["duration_seconds"] == 5400  # 90 minutes

    def test_set_timer_short_forms(self, timer_setup):
        """Should parse short duration forms."""
        from tools.timers import set_timer

        result = set_timer("30 min")

        assert result["success"] is True
        assert result["duration_seconds"] == 1800

    def test_set_timer_seconds(self, timer_setup):
        """Should parse seconds duration."""
        from tools.timers import set_timer

        result = set_timer("45 seconds")

        assert result["success"] is True
        assert result["duration_seconds"] == 45

    def test_set_timer_invalid_duration_fails(self, timer_setup):
        """Should fail with invalid duration."""
        from tools.timers import set_timer

        result = set_timer("gibberish duration")

        assert result["success"] is False
        assert "understand" in result["error"].lower()

    def test_set_timer_empty_duration_fails(self, timer_setup):
        """Should fail with empty duration."""
        from tools.timers import set_timer

        result = set_timer("")

        assert result["success"] is False


class TestListTimersIntegration:
    """Integration tests for listing timers."""

    def test_list_timers_empty(self, timer_setup):
        """Should return empty list when no timers."""
        from tools.timers import list_timers

        result = list_timers()

        assert result["success"] is True
        assert result["count"] == 0
        assert "no active timers" in result["message"].lower()

    def test_list_timers_with_active(self, timer_setup):
        """Should list active timers with remaining time."""
        from tools.timers import set_timer, list_timers

        set_timer("10 minutes", name="test1")
        set_timer("20 minutes", name="test2")

        result = list_timers()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["timers"]) == 2
        assert all("remaining_seconds" in t for t in result["timers"])

    def test_list_timers_shows_names(self, timer_setup):
        """Should show timer names in message."""
        from tools.timers import set_timer, list_timers

        set_timer("5 minutes", name="pasta")

        result = list_timers()

        assert "pasta" in result["message"]


class TestCancelTimerIntegration:
    """Integration tests for cancelling timers."""

    def test_cancel_timer_by_id(self, timer_setup):
        """Should cancel by ID."""
        from tools.timers import set_timer, cancel_timer

        timer_result = set_timer("10 minutes")
        timer_id = timer_result["timer_id"]

        result = cancel_timer(timer_id=timer_id)

        assert result["success"] is True

    def test_cancel_timer_by_name(self, timer_setup):
        """Should cancel by name."""
        from tools.timers import set_timer, cancel_timer

        set_timer("10 minutes", name="pizza")

        result = cancel_timer(name="pizza")

        assert result["success"] is True
        assert "pizza" in result["message"].lower()

    def test_cancel_timer_fuzzy_match(self, timer_setup):
        """Should match partial name."""
        from tools.timers import set_timer, cancel_timer

        set_timer("10 minutes", name="pizza timer")

        result = cancel_timer(name="pizza")

        assert result["success"] is True

    def test_cancel_all_timers(self, timer_setup):
        """Should cancel all active timers."""
        from tools.timers import set_timer, cancel_timer, list_timers

        set_timer("10 minutes", name="timer1")
        set_timer("20 minutes", name="timer2")
        set_timer("30 minutes", name="timer3")

        result = cancel_timer(cancel_all=True)

        assert result["success"] is True
        assert result["cancelled_count"] == 3

        list_result = list_timers()
        assert list_result["count"] == 0

    def test_cancel_only_active_returns_error_if_none(self, timer_setup):
        """Should error when no timers to cancel."""
        from tools.timers import cancel_timer

        result = cancel_timer()

        assert result["success"] is False
        assert "no active timers" in result["error"].lower()

    def test_cancel_single_timer_auto_selects(self, timer_setup):
        """Should auto-cancel if only one timer active."""
        from tools.timers import set_timer, cancel_timer

        set_timer("10 minutes")

        result = cancel_timer()  # No specific ID or name

        assert result["success"] is True

    def test_cancel_multiple_requires_specification(self, timer_setup):
        """Should require name when multiple timers active."""
        from tools.timers import set_timer, cancel_timer

        set_timer("10 minutes", name="timer1")
        set_timer("20 minutes", name="timer2")

        result = cancel_timer()  # No specific ID or name

        assert result["success"] is False
        assert "multiple" in result["error"].lower()


class TestSetAlarmIntegration:
    """Integration tests for setting alarms."""

    def test_set_alarm_basic(self, timer_setup):
        """Should set an alarm via tool function."""
        from tools.timers import set_alarm

        result = set_alarm("7am")

        assert result["success"] is True
        assert result["alarm_id"] > 0

    def test_set_alarm_with_name(self, timer_setup):
        """Should set a named alarm."""
        from tools.timers import set_alarm

        result = set_alarm("7:30am", name="wake up")

        assert result["success"] is True
        assert result["name"] == "wake up"
        assert "wake up" in result["message"]

    def test_set_alarm_24h_format(self, timer_setup):
        """Should parse 24-hour format."""
        from tools.timers import set_alarm

        result = set_alarm("15:30")

        assert result["success"] is True
        alarm_time = datetime.fromisoformat(result["alarm_time"])
        assert alarm_time.hour == 15
        assert alarm_time.minute == 30

    def test_set_alarm_tomorrow(self, timer_setup):
        """Should parse 'tomorrow at' format."""
        from tools.timers import set_alarm

        result = set_alarm("tomorrow at 8am")

        assert result["success"] is True
        alarm_time = datetime.fromisoformat(result["alarm_time"])
        tomorrow = datetime.now() + timedelta(days=1)
        assert alarm_time.date() == tomorrow.date()

    def test_set_alarm_repeating_weekdays(self, timer_setup):
        """Should set repeating weekday alarm."""
        from tools.timers import set_alarm

        result = set_alarm(
            "7am",
            name="work alarm",
            repeat_days=["monday", "tuesday", "wednesday", "thursday", "friday"]
        )

        assert result["success"] is True
        assert result["repeat_days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"]
        assert "weekdays" in result["message"].lower()

    def test_set_alarm_invalid_time_fails(self, timer_setup):
        """Should fail with invalid time."""
        from tools.timers import set_alarm

        result = set_alarm("gibberish time")

        assert result["success"] is False
        assert "understand" in result["error"].lower()

    def test_set_alarm_invalid_repeat_day_fails(self, timer_setup):
        """Should fail with invalid repeat day."""
        from tools.timers import set_alarm

        result = set_alarm("7am", repeat_days=["notaday"])

        assert result["success"] is False
        assert "invalid" in result["error"].lower()


class TestListAlarmsIntegration:
    """Integration tests for listing alarms."""

    def test_list_alarms_empty(self, timer_setup):
        """Should return empty list when no alarms."""
        from tools.timers import list_alarms

        result = list_alarms()

        assert result["success"] is True
        assert result["count"] == 0
        assert "no alarm" in result["message"].lower()

    def test_list_alarms_with_active(self, timer_setup):
        """Should list active alarms."""
        from tools.timers import set_alarm, list_alarms

        set_alarm("7am", name="morning")
        set_alarm("9pm", name="evening")

        result = list_alarms()

        assert result["success"] is True
        assert result["count"] == 2


class TestCancelAlarmIntegration:
    """Integration tests for cancelling alarms."""

    def test_cancel_alarm_by_id(self, timer_setup):
        """Should cancel by ID."""
        from tools.timers import set_alarm, cancel_alarm

        alarm_result = set_alarm("7am")
        alarm_id = alarm_result["alarm_id"]

        result = cancel_alarm(alarm_id=alarm_id)

        assert result["success"] is True

    def test_cancel_alarm_by_name(self, timer_setup):
        """Should cancel by name."""
        from tools.timers import set_alarm, cancel_alarm

        set_alarm("7am", name="morning alarm")

        result = cancel_alarm(name="morning")

        assert result["success"] is True
        assert "morning" in result["message"].lower()

    def test_cancel_alarm_by_time(self, timer_setup):
        """Should cancel by time match."""
        from tools.timers import set_alarm, cancel_alarm

        set_alarm("7:30am")

        result = cancel_alarm(time_match="7:30am")

        assert result["success"] is True

    def test_cancel_all_alarms(self, timer_setup):
        """Should cancel all active alarms."""
        from tools.timers import set_alarm, cancel_alarm, list_alarms

        set_alarm("7am")
        set_alarm("8am")
        set_alarm("9am")

        result = cancel_alarm(cancel_all=True)

        assert result["success"] is True
        assert result["cancelled_count"] == 3

        list_result = list_alarms()
        assert list_result["count"] == 0


class TestSnoozeAlarmIntegration:
    """Integration tests for snoozing alarms."""

    def test_snooze_alarm_by_id(self, timer_setup):
        """Should snooze by ID."""
        from tools.timers import set_alarm, snooze_alarm

        alarm_result = set_alarm("7am")
        alarm_id = alarm_result["alarm_id"]

        result = snooze_alarm(alarm_id=alarm_id, minutes=10)

        assert result["success"] is True
        assert "10 minute" in result["message"]

    def test_snooze_alarm_by_name(self, timer_setup):
        """Should snooze by name."""
        from tools.timers import set_alarm, snooze_alarm

        set_alarm("7am", name="wake up")

        result = snooze_alarm(name="wake up", minutes=5)

        assert result["success"] is True
        assert "5 minute" in result["message"]

    def test_snooze_no_alarms_fails(self, timer_setup):
        """Should fail when no alarms to snooze."""
        from tools.timers import snooze_alarm

        result = snooze_alarm()

        assert result["success"] is False
        assert "no alarm" in result["error"].lower()


class TestExecuteTimerTool:
    """Integration tests for the tool dispatcher."""

    def test_execute_set_timer(self, timer_setup):
        """Should dispatch set_timer correctly."""
        from tools.timers import execute_timer_tool

        result = execute_timer_tool("set_timer", {
            "duration": "10 minutes",
            "name": "test"
        })

        assert result["success"] is True

    def test_execute_list_timers(self, timer_setup):
        """Should dispatch list_timers correctly."""
        from tools.timers import execute_timer_tool

        execute_timer_tool("set_timer", {"duration": "10 minutes"})

        result = execute_timer_tool("list_timers", {})

        assert result["success"] is True
        assert result["count"] >= 1

    def test_execute_cancel_timer(self, timer_setup):
        """Should dispatch cancel_timer correctly."""
        from tools.timers import execute_timer_tool

        timer_result = execute_timer_tool("set_timer", {"duration": "10 minutes"})

        result = execute_timer_tool("cancel_timer", {
            "timer_id": timer_result["timer_id"]
        })

        assert result["success"] is True

    def test_execute_set_alarm(self, timer_setup):
        """Should dispatch set_alarm correctly."""
        from tools.timers import execute_timer_tool

        result = execute_timer_tool("set_alarm", {
            "time": "7am",
            "name": "morning"
        })

        assert result["success"] is True

    def test_execute_list_alarms(self, timer_setup):
        """Should dispatch list_alarms correctly."""
        from tools.timers import execute_timer_tool

        execute_timer_tool("set_alarm", {"time": "7am"})

        result = execute_timer_tool("list_alarms", {})

        assert result["success"] is True
        assert result["count"] >= 1

    def test_execute_cancel_alarm(self, timer_setup):
        """Should dispatch cancel_alarm correctly."""
        from tools.timers import execute_timer_tool

        alarm_result = execute_timer_tool("set_alarm", {"time": "7am"})

        result = execute_timer_tool("cancel_alarm", {
            "alarm_id": alarm_result["alarm_id"]
        })

        assert result["success"] is True

    def test_execute_snooze_alarm(self, timer_setup):
        """Should dispatch snooze_alarm correctly."""
        from tools.timers import execute_timer_tool

        alarm_result = execute_timer_tool("set_alarm", {"time": "7am"})

        result = execute_timer_tool("snooze_alarm", {
            "alarm_id": alarm_result["alarm_id"],
            "minutes": 10
        })

        assert result["success"] is True

    def test_execute_unknown_tool(self, timer_setup):
        """Should return error for unknown tool."""
        from tools.timers import execute_timer_tool

        result = execute_timer_tool("unknown_tool", {})

        assert result["success"] is False
        assert "unknown" in result["error"].lower()


class TestVoiceCommandScenarios:
    """Test realistic voice command scenarios."""

    def test_voice_set_timer_minutes(self, timer_setup):
        """Simulate: 'set a timer for 10 minutes'"""
        from tools.timers import set_timer

        result = set_timer("10 minutes")

        assert result["success"] is True
        assert result["duration_seconds"] == 600

    def test_voice_set_named_timer(self, timer_setup):
        """Simulate: 'set a pizza timer for 15 minutes'"""
        from tools.timers import set_timer

        result = set_timer("15 minutes", name="pizza")

        assert result["success"] is True
        assert result["name"] == "pizza"

    def test_voice_check_timers(self, timer_setup):
        """Simulate: 'how much time is left?'"""
        from tools.timers import set_timer, list_timers

        set_timer("10 minutes", name="cooking")

        result = list_timers()

        assert result["success"] is True
        assert "cooking" in result["message"]
        assert "remaining" in result["message"].lower()

    def test_voice_cancel_timer(self, timer_setup):
        """Simulate: 'cancel the pizza timer'"""
        from tools.timers import set_timer, cancel_timer

        set_timer("15 minutes", name="pizza")

        result = cancel_timer(name="pizza")

        assert result["success"] is True

    def test_voice_set_alarm(self, timer_setup):
        """Simulate: 'set an alarm for 7am'"""
        from tools.timers import set_alarm

        result = set_alarm("7am")

        assert result["success"] is True

    def test_voice_set_named_alarm(self, timer_setup):
        """Simulate: 'wake me up at 6:30am'"""
        from tools.timers import set_alarm

        result = set_alarm("6:30am", name="wake up")

        assert result["success"] is True
        assert result["name"] == "wake up"

    def test_voice_weekday_alarm(self, timer_setup):
        """Simulate: 'set a weekday alarm for 7am'"""
        from tools.timers import set_alarm

        result = set_alarm(
            "7am",
            repeat_days=["monday", "tuesday", "wednesday", "thursday", "friday"]
        )

        assert result["success"] is True
        assert "weekdays" in result["message"].lower()

    def test_voice_snooze(self, timer_setup):
        """Simulate: 'snooze'"""
        from tools.timers import set_alarm, snooze_alarm

        set_alarm("7am")

        result = snooze_alarm()  # No specific alarm, snooze first active

        assert result["success"] is True

    def test_voice_snooze_5_minutes(self, timer_setup):
        """Simulate: 'snooze for 5 minutes'"""
        from tools.timers import set_alarm, snooze_alarm

        set_alarm("7am")

        result = snooze_alarm(minutes=5)

        assert result["success"] is True
        assert "5 minute" in result["message"]


# Pytest fixtures
@pytest.fixture
def timer_setup(monkeypatch):
    """Set up isolated test environment for timer tools."""
    # Create temporary database
    fd, timer_db_path = tempfile.mkstemp(suffix='_timers.db')
    os.close(fd)

    # Patch the manager to use temp database
    from src import timer_manager
    import tools.timers as tools_timers

    # Reset singleton
    timer_manager._timer_manager = None

    # Create manager with temp path
    temp_timer_mgr = timer_manager.TimerManager(database_path=timer_db_path)

    # Patch get function in both places (source module AND tools module)
    monkeypatch.setattr(timer_manager, "get_timer_manager", lambda: temp_timer_mgr)
    monkeypatch.setattr(tools_timers, "get_timer_manager", lambda: temp_timer_mgr)

    yield {
        "timer_manager": temp_timer_mgr,
    }

    # Cleanup
    timer_manager._timer_manager = None

    if os.path.exists(timer_db_path):
        os.remove(timer_db_path)
