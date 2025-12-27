"""
Unit tests for ReminderManager - Todo List & Reminders (WP-4.1)

Tests cover all reminder CRUD operations and scheduling.
Written TDD-style before implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sqlite3
import tempfile
import os


class TestReminderManagerInitialization:
    """Tests for ReminderManager initialization and database setup."""

    def test_creates_reminders_table(self, reminder_manager):
        """ReminderManager should create the reminders table on initialization."""
        with reminder_manager._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'"
            )
            result = cursor.fetchone()
        assert result is not None
        assert result[0] == "reminders"


class TestSetReminder:
    """Tests for creating reminders."""

    def test_set_reminder_returns_id(self, reminder_manager):
        """Setting a reminder should return a positive integer ID."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("Test reminder", remind_at)
        assert isinstance(reminder_id, int)
        assert reminder_id > 0

    def test_set_reminder_with_message_and_time(self, reminder_manager):
        """Should create a reminder with message and time."""
        remind_at = datetime.now() + timedelta(hours=2)
        reminder_id = reminder_manager.set_reminder("Call mom", remind_at)
        reminder = reminder_manager.get_reminder(reminder_id)

        assert reminder["message"] == "Call mom"
        assert reminder["status"] == "pending"

    def test_set_reminder_with_todo_link(self, reminder_manager, todo_manager):
        """Should link reminder to a todo item."""
        todo_id = todo_manager.add_todo("Task with reminder")
        remind_at = datetime.now() + timedelta(hours=1)

        reminder_id = reminder_manager.set_reminder(
            "Don't forget this task",
            remind_at,
            todo_id=todo_id
        )
        reminder = reminder_manager.get_reminder(reminder_id)

        assert reminder["todo_id"] == todo_id

    def test_set_reminder_with_repeat_daily(self, reminder_manager):
        """Should set daily repeat interval."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder(
            "Take meds",
            remind_at,
            repeat_interval="daily"
        )
        reminder = reminder_manager.get_reminder(reminder_id)

        assert reminder["repeat_interval"] == "daily"

    def test_set_reminder_with_repeat_weekly(self, reminder_manager):
        """Should set weekly repeat interval."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder(
            "Weekly meeting",
            remind_at,
            repeat_interval="weekly"
        )
        reminder = reminder_manager.get_reminder(reminder_id)

        assert reminder["repeat_interval"] == "weekly"

    def test_set_reminder_empty_message_raises(self, reminder_manager):
        """Setting a reminder with empty message should raise ValueError."""
        remind_at = datetime.now() + timedelta(hours=1)
        with pytest.raises(ValueError, match="message cannot be empty"):
            reminder_manager.set_reminder("", remind_at)

    def test_set_reminder_past_time_raises(self, reminder_manager):
        """Setting a reminder in the past should raise ValueError."""
        remind_at = datetime.now() - timedelta(hours=1)
        with pytest.raises(ValueError, match="remind_at must be in the future"):
            reminder_manager.set_reminder("Past reminder", remind_at)


class TestGetReminder:
    """Tests for retrieving individual reminders."""

    def test_get_existing_reminder(self, reminder_manager):
        """Should retrieve a reminder by ID."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("Test", remind_at)
        reminder = reminder_manager.get_reminder(reminder_id)

        assert reminder is not None
        assert reminder["id"] == reminder_id

    def test_get_nonexistent_reminder_returns_none(self, reminder_manager):
        """Should return None for non-existent reminder ID."""
        reminder = reminder_manager.get_reminder(99999)
        assert reminder is None

    def test_get_reminder_includes_all_fields(self, reminder_manager):
        """Retrieved reminder should include all expected fields."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("Complete item", remind_at)
        reminder = reminder_manager.get_reminder(reminder_id)

        expected_fields = [
            "id", "todo_id", "message", "remind_at", "repeat_interval",
            "status", "created_at", "triggered_at"
        ]
        for field in expected_fields:
            assert field in reminder


class TestGetPendingReminders:
    """Tests for retrieving pending reminders."""

    def test_get_pending_reminders(self, reminder_manager):
        """Should get all pending reminders."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_manager.set_reminder("Reminder 1", remind_at)
        reminder_manager.set_reminder("Reminder 2", remind_at)

        pending = reminder_manager.get_pending_reminders()
        assert len(pending) >= 2
        assert all(r["status"] == "pending" for r in pending)

    def test_get_pending_excludes_dismissed(self, reminder_manager):
        """Should exclude dismissed reminders."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To dismiss", remind_at)
        reminder_manager.dismiss_reminder(reminder_id)

        pending = reminder_manager.get_pending_reminders()
        ids = [r["id"] for r in pending]
        assert reminder_id not in ids

    def test_get_pending_ordered_by_time(self, reminder_manager):
        """Should order reminders by remind_at ascending."""
        now = datetime.now()
        reminder_manager.set_reminder("Later", now + timedelta(hours=3))
        reminder_manager.set_reminder("Sooner", now + timedelta(hours=1))
        reminder_manager.set_reminder("Middle", now + timedelta(hours=2))

        pending = reminder_manager.get_pending_reminders()
        times = [r["remind_at"] for r in pending]
        assert times == sorted(times)


class TestGetDueReminders:
    """Tests for retrieving due reminders."""

    def test_get_due_reminders_none_due(self, reminder_manager):
        """Should return empty list when no reminders are due."""
        remind_at = datetime.now() + timedelta(hours=24)
        reminder_manager.set_reminder("Future reminder", remind_at)

        due = reminder_manager.get_due_reminders()
        assert due == []

    def test_get_due_reminders_returns_due_ones(self, reminder_manager):
        """Should return reminders that are due now."""
        # Create a reminder that's due now (within the window)
        remind_at = datetime.now() - timedelta(seconds=30)

        # Bypass the past time check for testing
        with reminder_manager._get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO reminders (message, remind_at, status)
                VALUES (?, ?, 'pending')
            """, ("Due now", remind_at.isoformat()))

        due = reminder_manager.get_due_reminders()
        assert len(due) >= 1
        assert any(r["message"] == "Due now" for r in due)


class TestTriggerReminder:
    """Tests for triggering reminders."""

    def test_trigger_reminder_updates_status(self, reminder_manager):
        """Triggering a reminder should update its status."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To trigger", remind_at)

        result = reminder_manager.trigger_reminder(reminder_id)

        assert result["success"] is True
        reminder = reminder_manager.get_reminder(reminder_id)
        assert reminder["status"] == "triggered"
        assert reminder["triggered_at"] is not None

    def test_trigger_nonexistent_reminder_returns_false(self, reminder_manager):
        """Should return failure for non-existent reminder."""
        result = reminder_manager.trigger_reminder(99999)
        assert result["success"] is False

    def test_trigger_reminder_returns_message(self, reminder_manager):
        """Triggering should return the reminder message."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("Important reminder", remind_at)

        result = reminder_manager.trigger_reminder(reminder_id)
        assert result["message"] == "Important reminder"

    def test_trigger_repeating_reminder_reschedules(self, reminder_manager):
        """Triggering a daily reminder should create a new reminder."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder(
            "Daily task",
            remind_at,
            repeat_interval="daily"
        )

        result = reminder_manager.trigger_reminder(reminder_id)

        # Original should be triggered
        original = reminder_manager.get_reminder(reminder_id)
        assert original["status"] == "triggered"

        # Should have created a new pending reminder
        pending = reminder_manager.get_pending_reminders()
        daily_pending = [r for r in pending if r["message"] == "Daily task"]
        assert len(daily_pending) >= 1


class TestDismissReminder:
    """Tests for dismissing reminders."""

    def test_dismiss_reminder(self, reminder_manager):
        """Should mark reminder as dismissed."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To dismiss", remind_at)

        success = reminder_manager.dismiss_reminder(reminder_id)

        assert success is True
        reminder = reminder_manager.get_reminder(reminder_id)
        assert reminder["status"] == "dismissed"

    def test_dismiss_nonexistent_reminder_returns_false(self, reminder_manager):
        """Should return False for non-existent reminder."""
        success = reminder_manager.dismiss_reminder(99999)
        assert success is False


class TestDeleteReminder:
    """Tests for deleting reminders."""

    def test_delete_reminder(self, reminder_manager):
        """Should delete a reminder."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To delete", remind_at)

        success = reminder_manager.delete_reminder(reminder_id)

        assert success is True
        assert reminder_manager.get_reminder(reminder_id) is None

    def test_delete_nonexistent_reminder_returns_false(self, reminder_manager):
        """Should return False for non-existent reminder."""
        success = reminder_manager.delete_reminder(99999)
        assert success is False


class TestSnoozeReminder:
    """Tests for snoozing reminders."""

    def test_snooze_reminder(self, reminder_manager):
        """Should reschedule a reminder to a later time."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To snooze", remind_at)

        new_time = datetime.now() + timedelta(hours=2)
        success = reminder_manager.snooze_reminder(reminder_id, new_time)

        assert success is True
        reminder = reminder_manager.get_reminder(reminder_id)
        stored_time = datetime.fromisoformat(reminder["remind_at"])
        assert abs((stored_time - new_time).total_seconds()) < 60

    def test_snooze_by_duration(self, reminder_manager):
        """Should snooze by a duration (e.g., 10 minutes)."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To snooze", remind_at)

        success = reminder_manager.snooze_reminder(reminder_id, minutes=10)

        assert success is True
        reminder = reminder_manager.get_reminder(reminder_id)
        # Should be approximately 10 minutes from now
        stored_time = datetime.fromisoformat(reminder["remind_at"])
        expected_time = datetime.now() + timedelta(minutes=10)
        assert abs((stored_time - expected_time).total_seconds()) < 60


class TestReminderStats:
    """Tests for reminder statistics."""

    def test_get_reminder_stats(self, reminder_manager):
        """Should return reminder statistics."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_manager.set_reminder("Pending 1", remind_at)
        reminder_manager.set_reminder("Pending 2", remind_at)

        stats = reminder_manager.get_stats()

        assert "total" in stats
        assert "pending" in stats
        assert "triggered" in stats
        assert "dismissed" in stats
        assert stats["total"] >= 2


class TestParseRelativeTime:
    """Tests for parsing relative time strings."""

    def test_parse_time_absolute(self, reminder_manager):
        """Should parse absolute time like '3pm' or '15:00'."""
        # Test various formats
        result = reminder_manager.parse_reminder_time("3pm")
        assert result is not None
        assert result.hour == 15

        result = reminder_manager.parse_reminder_time("15:00")
        assert result is not None
        assert result.hour == 15

    def test_parse_time_relative_hours(self, reminder_manager):
        """Should parse relative time like 'in 2 hours'."""
        result = reminder_manager.parse_reminder_time("in 2 hours")
        expected = datetime.now() + timedelta(hours=2)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 60

    def test_parse_time_relative_minutes(self, reminder_manager):
        """Should parse relative time like 'in 30 minutes'."""
        result = reminder_manager.parse_reminder_time("in 30 minutes")
        expected = datetime.now() + timedelta(minutes=30)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 60

    def test_parse_time_tomorrow(self, reminder_manager):
        """Should parse 'tomorrow at 9am'."""
        result = reminder_manager.parse_reminder_time("tomorrow at 9am")
        assert result is not None
        tomorrow = datetime.now() + timedelta(days=1)
        assert result.date() == tomorrow.date()
        assert result.hour == 9


# Pytest fixtures
@pytest.fixture
def reminder_manager():
    """Create ReminderManager with a temporary test database."""
    from src.reminder_manager import ReminderManager

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    try:
        manager = ReminderManager(database_path=db_path)
        yield manager
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture
def todo_manager():
    """Create TodoManager with a temporary test database."""
    from src.todo_manager import TodoManager

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    try:
        manager = TodoManager(database_path=db_path)
        yield manager
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
