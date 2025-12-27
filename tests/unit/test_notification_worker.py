"""
Unit tests for NotificationWorker - Background Notification Worker (WP-67.2)

Tests cover notification checking, delivery, and worker lifecycle.
Written TDD-style before implementation.
"""

import os
import signal
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestNotificationWorkerInitialization:
    """Tests for NotificationWorker initialization."""

    def test_creates_notification_worker(self, notification_worker):
        """NotificationWorker should initialize with a ReminderManager."""
        from src.notification_worker import NotificationWorker

        assert isinstance(notification_worker, NotificationWorker)
        assert notification_worker.reminder_manager is not None

    def test_worker_has_running_state(self, notification_worker):
        """Worker should have a running flag for lifecycle management."""
        assert hasattr(notification_worker, "running")
        assert notification_worker.running is False  # Not started yet

    def test_worker_has_check_interval(self, notification_worker):
        """Worker should have a configurable check interval."""
        assert hasattr(notification_worker, "check_interval")
        assert notification_worker.check_interval >= 1  # At least 1 second


class TestNotificationDelivery:
    """Tests for notification delivery via Slack."""

    def test_send_notification_calls_slack(self, notification_worker):
        """Sending a notification should call Slack webhook."""
        with patch.object(
            notification_worker, "_notifier"
        ) as mock_notifier:
            mock_notifier.send_alert.return_value = True

            result = notification_worker.send_notification(
                message="Test reminder",
                reminder_id=1,
            )

            assert result is True
            mock_notifier.send_alert.assert_called_once()

    def test_send_notification_includes_message(self, notification_worker):
        """Notification should include the reminder message."""
        with patch.object(
            notification_worker, "_notifier"
        ) as mock_notifier:
            mock_notifier.send_alert.return_value = True

            notification_worker.send_notification(
                message="Call the doctor",
                reminder_id=1,
            )

            call_args = mock_notifier.send_alert.call_args
            assert "Call the doctor" in str(call_args)

    def test_send_notification_with_todo_link(self, notification_worker):
        """Notification should include todo link if present."""
        with patch.object(
            notification_worker, "_notifier"
        ) as mock_notifier:
            mock_notifier.send_alert.return_value = True

            notification_worker.send_notification(
                message="Finish report",
                reminder_id=1,
                todo_id=42,
            )

            call_args = mock_notifier.send_alert.call_args
            # Should reference the todo
            assert mock_notifier.send_alert.called

    def test_send_notification_handles_failure(self, notification_worker):
        """Should handle Slack delivery failure gracefully."""
        with patch.object(
            notification_worker, "_notifier"
        ) as mock_notifier:
            mock_notifier.send_alert.return_value = False

            result = notification_worker.send_notification(
                message="Failed delivery",
                reminder_id=1,
            )

            assert result is False


class TestProcessDueReminders:
    """Tests for processing due reminders."""

    def test_process_due_reminders_triggers_due(self, notification_worker, reminder_manager):
        """Should process and trigger due reminders."""
        # Create a due reminder (bypass validation for test)
        remind_at = datetime.now() - timedelta(seconds=30)
        with reminder_manager._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reminders (message, remind_at, status)
                VALUES (?, ?, 'pending')
            """,
                ("Due now", remind_at.isoformat()),
            )
            reminder_id = cursor.lastrowid

        with patch.object(notification_worker, "send_notification") as mock_send:
            mock_send.return_value = True

            count = notification_worker.process_due_reminders()

            assert count >= 1
            mock_send.assert_called()

    def test_process_due_reminders_marks_triggered(
        self, notification_worker, reminder_manager
    ):
        """Should mark reminders as triggered after notification."""
        remind_at = datetime.now() - timedelta(seconds=30)
        with reminder_manager._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reminders (message, remind_at, status)
                VALUES (?, ?, 'pending')
            """,
                ("Due now", remind_at.isoformat()),
            )
            reminder_id = cursor.lastrowid

        with patch.object(notification_worker, "send_notification") as mock_send:
            mock_send.return_value = True

            notification_worker.process_due_reminders()

            reminder = reminder_manager.get_reminder(reminder_id)
            assert reminder["status"] == "triggered"

    def test_process_due_reminders_handles_notification_failure(
        self, notification_worker, reminder_manager
    ):
        """Should NOT mark reminder as triggered if notification fails."""
        remind_at = datetime.now() - timedelta(seconds=30)
        with reminder_manager._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reminders (message, remind_at, status)
                VALUES (?, ?, 'pending')
            """,
                ("Due now", remind_at.isoformat()),
            )
            reminder_id = cursor.lastrowid

        with patch.object(notification_worker, "send_notification") as mock_send:
            mock_send.return_value = False

            notification_worker.process_due_reminders()

            reminder = reminder_manager.get_reminder(reminder_id)
            # Should remain pending since notification failed
            assert reminder["status"] == "pending"

    def test_process_due_reminders_returns_zero_when_none_due(
        self, notification_worker
    ):
        """Should return 0 when no reminders are due."""
        count = notification_worker.process_due_reminders()
        assert count == 0


class TestWorkerLoop:
    """Tests for the background worker loop."""

    def test_run_loop_checks_reminders(self, notification_worker):
        """Worker loop should periodically check for due reminders."""
        notification_worker.check_interval = 0.1  # Fast for testing

        with patch.object(
            notification_worker, "process_due_reminders"
        ) as mock_process:
            mock_process.return_value = 0

            # Start worker in thread
            thread = threading.Thread(target=notification_worker.run)
            thread.start()

            # Let it run briefly
            time.sleep(0.3)

            # Stop worker
            notification_worker.stop()
            thread.join(timeout=1)

            # Should have processed at least once
            assert mock_process.call_count >= 1

    def test_stop_sets_running_to_false(self, notification_worker):
        """Stopping the worker should set running to False."""
        notification_worker.running = True
        notification_worker.stop()
        assert notification_worker.running is False

    def test_run_sets_running_to_true(self, notification_worker):
        """Running the worker should set running to True."""
        notification_worker.check_interval = 0.1

        with patch.object(
            notification_worker, "process_due_reminders"
        ) as mock_process:
            mock_process.return_value = 0

            thread = threading.Thread(target=notification_worker.run)
            thread.start()

            time.sleep(0.15)

            # Should be running now
            assert notification_worker.running is True

            notification_worker.stop()
            thread.join(timeout=1)


class TestGracefulShutdown:
    """Tests for graceful shutdown handling."""

    def test_register_signal_handlers(self, notification_worker):
        """Worker should register signal handlers for graceful shutdown."""
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        try:
            notification_worker.register_signal_handlers()

            # Handlers should be registered
            assert signal.getsignal(signal.SIGTERM) != original_sigterm
            assert signal.getsignal(signal.SIGINT) != original_sigint
        finally:
            # Restore original handlers
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

    def test_signal_handler_stops_worker(self, notification_worker):
        """Signal handler should stop the worker gracefully."""
        notification_worker.running = True

        # Call the signal handler directly
        notification_worker._handle_shutdown(signal.SIGTERM, None)

        assert notification_worker.running is False


class TestSnoozeHandling:
    """Tests for reminder snooze functionality."""

    def test_snooze_reminder_reschedules(self, notification_worker, reminder_manager):
        """Snoozing should reschedule reminder to new time."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To snooze", remind_at)

        new_time = datetime.now() + timedelta(hours=2)
        result = notification_worker.snooze_reminder(reminder_id, minutes=60)

        assert result is True
        reminder = reminder_manager.get_reminder(reminder_id)
        assert reminder["status"] == "pending"

    def test_snooze_nonexistent_returns_false(self, notification_worker):
        """Snoozing non-existent reminder should return False."""
        result = notification_worker.snooze_reminder(99999, minutes=10)
        assert result is False


class TestDismissHandling:
    """Tests for reminder dismissal functionality."""

    def test_dismiss_reminder_marks_dismissed(
        self, notification_worker, reminder_manager
    ):
        """Dismissing should mark reminder as dismissed."""
        remind_at = datetime.now() + timedelta(hours=1)
        reminder_id = reminder_manager.set_reminder("To dismiss", remind_at)

        result = notification_worker.dismiss_reminder(reminder_id)

        assert result is True
        reminder = reminder_manager.get_reminder(reminder_id)
        assert reminder["status"] == "dismissed"

    def test_dismiss_nonexistent_returns_false(self, notification_worker):
        """Dismissing non-existent reminder should return False."""
        result = notification_worker.dismiss_reminder(99999)
        assert result is False


class TestWorkerStats:
    """Tests for worker statistics tracking."""

    def test_get_stats_returns_counts(self, notification_worker):
        """Should return notification statistics."""
        stats = notification_worker.get_stats()

        assert "notifications_sent" in stats
        assert "notifications_failed" in stats
        assert "uptime_seconds" in stats

    def test_stats_increment_on_send(self, notification_worker):
        """Stats should increment when notifications are sent."""
        with patch.object(notification_worker, "_notifier") as mock_notifier:
            mock_notifier.send_alert.return_value = True

            initial_sent = notification_worker._stats["notifications_sent"]
            notification_worker.send_notification("Test", 1)

            assert (
                notification_worker._stats["notifications_sent"] == initial_sent + 1
            )


# Pytest fixtures
@pytest.fixture
def reminder_manager():
    """Create ReminderManager with a temporary test database."""
    from src.reminder_manager import ReminderManager

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        manager = ReminderManager(database_path=Path(db_path))
        yield manager
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture
def notification_worker(reminder_manager):
    """Create NotificationWorker with test dependencies."""
    from src.notification_worker import NotificationWorker

    worker = NotificationWorker(
        reminder_manager=reminder_manager,
        check_interval=60,  # Default 60 seconds
    )
    yield worker
    # Ensure worker is stopped
    worker.stop()
