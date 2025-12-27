"""
Unit tests for TimerManager class.

Part of WP-4.3: Timers & Alarms feature.
TDD approach - tests written before implementation.
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import will fail until we implement - that's expected in TDD
try:
    from src.timer_manager import TimerManager, get_timer_manager, TimerStatus
except ImportError:
    pytest.skip("TimerManager not implemented yet", allow_module_level=True)


class TestTimerManagerInitialization:
    """Tests for TimerManager initialization and database setup."""

    def test_creates_database_file(self, tmp_path):
        """TimerManager creates database file on initialization."""
        db_path = tmp_path / "timers.db"
        manager = TimerManager(database_path=db_path)
        assert db_path.exists()

    def test_creates_timers_table(self, tmp_path):
        """TimerManager creates timers table with correct schema."""
        db_path = tmp_path / "timers.db"
        manager = TimerManager(database_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timers'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_alarms_table(self, tmp_path):
        """TimerManager creates alarms table with correct schema."""
        db_path = tmp_path / "timers.db"
        manager = TimerManager(database_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alarms'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_initializes_with_empty_tables(self, tmp_path):
        """Fresh database has no timers or alarms."""
        db_path = tmp_path / "timers.db"
        manager = TimerManager(database_path=db_path)

        assert manager.get_active_timers() == []
        assert manager.get_active_alarms() == []


class TestTimerCreation:
    """Tests for creating timers."""

    def test_create_timer_with_duration_seconds(self, tmp_path):
        """Create timer with duration in seconds."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)  # 5 minutes

        assert timer_id is not None
        assert timer_id > 0

    def test_create_timer_with_name(self, tmp_path):
        """Create named timer."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=600, name="pizza timer")

        timer = manager.get_timer(timer_id)
        assert timer["name"] == "pizza timer"

    def test_create_timer_default_name(self, tmp_path):
        """Timer without name gets default."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=60)

        timer = manager.get_timer(timer_id)
        assert timer["name"] is None or timer["name"] == ""

    def test_create_timer_calculates_end_time(self, tmp_path):
        """Timer end_time is calculated from creation + duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        before = datetime.now()
        timer_id = manager.create_timer(duration_seconds=300)
        after = datetime.now()

        timer = manager.get_timer(timer_id)
        end_time = datetime.fromisoformat(timer["end_time"])

        # End time should be approximately 5 minutes from now
        expected_min = before + timedelta(seconds=299)
        expected_max = after + timedelta(seconds=301)
        assert expected_min <= end_time <= expected_max

    def test_create_timer_status_is_running(self, tmp_path):
        """New timer status is 'running'."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)

        timer = manager.get_timer(timer_id)
        assert timer["status"] == "running"

    def test_create_timer_stores_original_duration(self, tmp_path):
        """Timer stores original duration for display purposes."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=600)

        timer = manager.get_timer(timer_id)
        assert timer["duration_seconds"] == 600

    def test_create_multiple_simultaneous_timers(self, tmp_path):
        """Can create multiple timers at once."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        timer1 = manager.create_timer(duration_seconds=300, name="pasta")
        timer2 = manager.create_timer(duration_seconds=600, name="sauce")
        timer3 = manager.create_timer(duration_seconds=900, name="garlic bread")

        active = manager.get_active_timers()
        assert len(active) == 3

    def test_create_timer_rejects_zero_duration(self, tmp_path):
        """Cannot create timer with zero duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        with pytest.raises(ValueError, match="duration"):
            manager.create_timer(duration_seconds=0)

    def test_create_timer_rejects_negative_duration(self, tmp_path):
        """Cannot create timer with negative duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        with pytest.raises(ValueError, match="duration"):
            manager.create_timer(duration_seconds=-60)


class TestTimerRetrieval:
    """Tests for retrieving timers."""

    def test_get_timer_by_id(self, tmp_path):
        """Retrieve timer by ID."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300, name="test")

        timer = manager.get_timer(timer_id)
        assert timer is not None
        assert timer["id"] == timer_id
        assert timer["name"] == "test"

    def test_get_timer_nonexistent_returns_none(self, tmp_path):
        """Get nonexistent timer returns None."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        timer = manager.get_timer(9999)
        assert timer is None

    def test_get_active_timers_excludes_completed(self, tmp_path):
        """Get active timers excludes completed ones."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        timer1 = manager.create_timer(duration_seconds=300)
        timer2 = manager.create_timer(duration_seconds=600)
        manager.complete_timer(timer1)

        active = manager.get_active_timers()
        assert len(active) == 1
        assert active[0]["id"] == timer2

    def test_get_active_timers_excludes_cancelled(self, tmp_path):
        """Get active timers excludes cancelled ones."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        timer1 = manager.create_timer(duration_seconds=300)
        timer2 = manager.create_timer(duration_seconds=600)
        manager.cancel_timer(timer1)

        active = manager.get_active_timers()
        assert len(active) == 1
        assert active[0]["id"] == timer2

    def test_get_timer_by_name(self, tmp_path):
        """Find timer by name (fuzzy match)."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        manager.create_timer(duration_seconds=300, name="pizza timer")
        manager.create_timer(duration_seconds=600, name="pasta timer")

        timer = manager.get_timer_by_name("pizza")
        assert timer is not None
        assert "pizza" in timer["name"]

    def test_get_timer_by_name_case_insensitive(self, tmp_path):
        """Timer name search is case insensitive."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        manager.create_timer(duration_seconds=300, name="PIZZA timer")

        timer = manager.get_timer_by_name("pizza")
        assert timer is not None


class TestTimerOperations:
    """Tests for timer operations (cancel, complete, pause)."""

    def test_cancel_timer(self, tmp_path):
        """Cancel a running timer."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)

        result = manager.cancel_timer(timer_id)

        assert result is True
        timer = manager.get_timer(timer_id)
        assert timer["status"] == "cancelled"

    def test_cancel_nonexistent_timer_returns_false(self, tmp_path):
        """Cancel nonexistent timer returns False."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        result = manager.cancel_timer(9999)
        assert result is False

    def test_complete_timer(self, tmp_path):
        """Complete (ring) a timer."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)

        result = manager.complete_timer(timer_id)

        assert result["success"] is True
        timer = manager.get_timer(timer_id)
        assert timer["status"] == "completed"

    def test_complete_timer_records_triggered_at(self, tmp_path):
        """Completing timer records triggered_at timestamp."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)

        before = datetime.now()
        manager.complete_timer(timer_id)
        after = datetime.now()

        timer = manager.get_timer(timer_id)
        triggered_at = datetime.fromisoformat(timer["triggered_at"])
        assert before <= triggered_at <= after

    def test_get_expired_timers(self, tmp_path):
        """Get timers that have expired but not completed."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        # Create a timer that's already expired (by manipulating end_time)
        timer_id = manager.create_timer(duration_seconds=1)

        # Manually set end_time to past
        conn = sqlite3.connect(tmp_path / "timers.db")
        cursor = conn.cursor()
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        cursor.execute("UPDATE timers SET end_time = ? WHERE id = ?", (past_time, timer_id))
        conn.commit()
        conn.close()

        expired = manager.get_expired_timers()
        assert len(expired) == 1
        assert expired[0]["id"] == timer_id


class TestTimerRemainingTime:
    """Tests for calculating remaining time."""

    def test_get_remaining_seconds(self, tmp_path):
        """Get remaining seconds for a timer."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=300)

        remaining = manager.get_remaining_seconds(timer_id)

        # Should be close to 300 (allowing for test execution time)
        assert 295 <= remaining <= 300

    def test_get_remaining_seconds_expired_returns_zero(self, tmp_path):
        """Expired timer returns 0 remaining seconds."""
        manager = TimerManager(database_path=tmp_path / "timers.db")
        timer_id = manager.create_timer(duration_seconds=1)

        # Manipulate to be expired
        conn = sqlite3.connect(tmp_path / "timers.db")
        cursor = conn.cursor()
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        cursor.execute("UPDATE timers SET end_time = ? WHERE id = ?", (past_time, timer_id))
        conn.commit()
        conn.close()

        remaining = manager.get_remaining_seconds(timer_id)
        assert remaining == 0

    def test_format_remaining_time(self, tmp_path):
        """Format remaining time as human-readable string."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        # Test various durations
        assert manager.format_duration(60) == "1 minute"
        assert manager.format_duration(120) == "2 minutes"
        assert manager.format_duration(90) == "1 minute 30 seconds"
        assert manager.format_duration(3600) == "1 hour"
        assert manager.format_duration(3660) == "1 hour 1 minute"
        assert manager.format_duration(30) == "30 seconds"


class TestAlarmCreation:
    """Tests for creating alarms."""

    def test_create_alarm_with_time(self, tmp_path):
        """Create alarm for specific time."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=8)
        alarm_id = manager.create_alarm(alarm_time=alarm_time)

        assert alarm_id is not None
        assert alarm_id > 0

    def test_create_alarm_with_name(self, tmp_path):
        """Create named alarm."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=8)
        alarm_id = manager.create_alarm(alarm_time=alarm_time, name="wake up")

        alarm = manager.get_alarm(alarm_id)
        assert alarm["name"] == "wake up"

    def test_create_alarm_status_is_pending(self, tmp_path):
        """New alarm status is 'pending'."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=8)
        alarm_id = manager.create_alarm(alarm_time=alarm_time)

        alarm = manager.get_alarm(alarm_id)
        assert alarm["status"] == "pending"

    def test_create_alarm_rejects_past_time(self, tmp_path):
        """Cannot create alarm for past time."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        past_time = datetime.now() - timedelta(hours=1)
        with pytest.raises(ValueError, match="past"):
            manager.create_alarm(alarm_time=past_time)

    def test_create_repeating_alarm(self, tmp_path):
        """Create alarm that repeats daily."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=8)
        alarm_id = manager.create_alarm(
            alarm_time=alarm_time,
            name="morning alarm",
            repeat_days=["monday", "tuesday", "wednesday", "thursday", "friday"]
        )

        alarm = manager.get_alarm(alarm_id)
        assert alarm["repeat_days"] is not None
        assert "monday" in alarm["repeat_days"]


class TestAlarmOperations:
    """Tests for alarm operations."""

    def test_cancel_alarm(self, tmp_path):
        """Cancel a pending alarm."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=8)
        alarm_id = manager.create_alarm(alarm_time=alarm_time)

        result = manager.cancel_alarm(alarm_id)

        assert result is True
        alarm = manager.get_alarm(alarm_id)
        assert alarm["status"] == "cancelled"

    def test_snooze_alarm(self, tmp_path):
        """Snooze a triggered alarm."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        # Create alarm in the near future (simulating one that just triggered)
        alarm_time = datetime.now() + timedelta(minutes=1)
        alarm_id = manager.create_alarm(alarm_time=alarm_time)

        # Snooze for 10 minutes - this resets alarm to now + snooze_minutes
        before_snooze = datetime.now()
        result = manager.snooze_alarm(alarm_id, minutes=10)
        after_snooze = datetime.now()

        assert result is True
        alarm = manager.get_alarm(alarm_id)
        new_time = datetime.fromisoformat(alarm["alarm_time"])

        # Snooze sets alarm to now + snooze_minutes (not original_time + minutes)
        expected_min = before_snooze + timedelta(minutes=10)
        expected_max = after_snooze + timedelta(minutes=10)

        # New time should be between expected_min and expected_max
        assert expected_min <= new_time <= expected_max

    def test_get_active_alarms(self, tmp_path):
        """Get all active alarms."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm1_time = datetime.now() + timedelta(hours=8)
        alarm2_time = datetime.now() + timedelta(hours=12)

        manager.create_alarm(alarm_time=alarm1_time, name="alarm 1")
        manager.create_alarm(alarm_time=alarm2_time, name="alarm 2")

        active = manager.get_active_alarms()
        assert len(active) == 2

    def test_get_due_alarms(self, tmp_path):
        """Get alarms that are due (past alarm_time but not triggered)."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        alarm_time = datetime.now() + timedelta(hours=1)
        alarm_id = manager.create_alarm(alarm_time=alarm_time)

        # Manually set alarm_time to past
        conn = sqlite3.connect(tmp_path / "timers.db")
        cursor = conn.cursor()
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        cursor.execute("UPDATE alarms SET alarm_time = ? WHERE id = ?", (past_time, alarm_id))
        conn.commit()
        conn.close()

        due = manager.get_due_alarms()
        assert len(due) == 1
        assert due[0]["id"] == alarm_id


class TestTimeParser:
    """Tests for natural language time parsing."""

    def test_parse_duration_minutes(self, tmp_path):
        """Parse '10 minutes' duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        seconds = manager.parse_duration("10 minutes")
        assert seconds == 600

    def test_parse_duration_hours(self, tmp_path):
        """Parse '2 hours' duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        seconds = manager.parse_duration("2 hours")
        assert seconds == 7200

    def test_parse_duration_hours_and_minutes(self, tmp_path):
        """Parse '1 hour 30 minutes' duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        seconds = manager.parse_duration("1 hour 30 minutes")
        assert seconds == 5400

    def test_parse_duration_seconds(self, tmp_path):
        """Parse '30 seconds' duration."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        seconds = manager.parse_duration("30 seconds")
        assert seconds == 30

    def test_parse_duration_short_forms(self, tmp_path):
        """Parse short forms like '10 min', '2 hr'."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        assert manager.parse_duration("10 min") == 600
        assert manager.parse_duration("2 hr") == 7200
        assert manager.parse_duration("30 sec") == 30

    def test_parse_alarm_time_am_pm(self, tmp_path):
        """Parse '7am', '3:30pm' alarm times."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        result = manager.parse_alarm_time("7am")
        assert result is not None
        assert result.hour == 7

        result = manager.parse_alarm_time("3:30pm")
        assert result is not None
        assert result.hour == 15
        assert result.minute == 30

    def test_parse_alarm_time_24hour(self, tmp_path):
        """Parse '07:00', '15:30' alarm times."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        result = manager.parse_alarm_time("07:00")
        assert result is not None
        assert result.hour == 7

        result = manager.parse_alarm_time("15:30")
        assert result is not None
        assert result.hour == 15
        assert result.minute == 30

    def test_parse_alarm_time_tomorrow(self, tmp_path):
        """Parse 'tomorrow at 7am' alarm time."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        result = manager.parse_alarm_time("tomorrow at 7am")
        assert result is not None
        assert result.date() == (datetime.now() + timedelta(days=1)).date()
        assert result.hour == 7


class TestTimerStatistics:
    """Tests for timer statistics."""

    def test_get_stats_empty(self, tmp_path):
        """Stats for empty database."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        stats = manager.get_stats()
        assert stats["total_timers"] == 0
        assert stats["active_timers"] == 0
        assert stats["total_alarms"] == 0
        assert stats["active_alarms"] == 0

    def test_get_stats_with_data(self, tmp_path):
        """Stats with timers and alarms."""
        manager = TimerManager(database_path=tmp_path / "timers.db")

        # Create some timers
        timer1 = manager.create_timer(duration_seconds=300)
        timer2 = manager.create_timer(duration_seconds=600)
        manager.cancel_timer(timer1)

        # Create some alarms
        alarm_time = datetime.now() + timedelta(hours=8)
        manager.create_alarm(alarm_time=alarm_time)

        stats = manager.get_stats()
        assert stats["total_timers"] == 2
        assert stats["active_timers"] == 1
        assert stats["total_alarms"] == 1
        assert stats["active_alarms"] == 1


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_timer_manager_returns_same_instance(self):
        """get_timer_manager returns singleton instance."""
        # Note: This test may need adjustment based on implementation
        manager1 = get_timer_manager()
        manager2 = get_timer_manager()

        assert manager1 is manager2
