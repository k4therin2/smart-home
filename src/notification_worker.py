"""
Smart Home Assistant - Background Notification Worker

Runs as a background process to check for due reminders
and deliver notifications via Slack webhook.

Part of WP-67.2: SmartHome Background Notification Worker
"""

import logging
import os
import signal
import time
from datetime import datetime
from typing import Any

from src.reminder_manager import ReminderManager, get_reminder_manager
from src.security.config import SLACK_HEALTH_WEBHOOK_URL
from src.security.slack_client import SlackNotifier


logger = logging.getLogger(__name__)

# Default check interval (seconds)
DEFAULT_CHECK_INTERVAL = 60

# Slack webhook for personal reminders channel
# Uses the personal webhook if set, falls back to health webhook
SLACK_REMINDER_WEBHOOK_URL = os.getenv(
    "SLACK_REMINDER_WEBHOOK", SLACK_HEALTH_WEBHOOK_URL
)


class NotificationWorker:
    """
    Background worker for checking and delivering reminder notifications.

    Periodically checks for due reminders and sends notifications
    via Slack webhook. Supports graceful shutdown via signals.
    """

    def __init__(
        self,
        reminder_manager: ReminderManager | None = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL,
        webhook_url: str | None = None,
    ):
        """
        Initialize NotificationWorker.

        Args:
            reminder_manager: ReminderManager instance (uses singleton if None)
            check_interval: Seconds between reminder checks
            webhook_url: Slack webhook URL for notifications
        """
        self.reminder_manager = reminder_manager or get_reminder_manager()
        self.check_interval = check_interval
        self.running = False
        self._start_time: datetime | None = None

        # Initialize Slack notifier
        self._notifier = SlackNotifier(webhook_url=webhook_url or SLACK_REMINDER_WEBHOOK_URL)

        # Statistics tracking
        self._stats = {
            "notifications_sent": 0,
            "notifications_failed": 0,
            "check_cycles": 0,
        }

        logger.info(
            f"NotificationWorker initialized (check_interval={check_interval}s)"
        )

    def send_notification(
        self,
        message: str,
        reminder_id: int,
        todo_id: int | None = None,
    ) -> bool:
        """
        Send a reminder notification via Slack.

        Args:
            message: Reminder message to send
            reminder_id: ID of the reminder
            todo_id: Optional linked todo item ID

        Returns:
            True if notification was sent successfully
        """
        # Build notification title
        title = "Reminder"

        # Build message with optional todo link
        notification_message = message
        if todo_id:
            notification_message = f"{message}\n\n_Linked to todo #{todo_id}_"

        # Build fields
        fields = [
            {"title": "Reminder ID", "value": str(reminder_id)},
            {"title": "Time", "value": datetime.now().strftime("%I:%M %p")},
        ]

        # Send via Slack
        success = self._notifier.send_alert(
            title=title,
            message=notification_message,
            severity="info",
            fields=fields,
        )

        # Update stats
        if success:
            self._stats["notifications_sent"] += 1
            logger.info(f"Notification sent for reminder {reminder_id}")
        else:
            self._stats["notifications_failed"] += 1
            logger.error(f"Failed to send notification for reminder {reminder_id}")

        return success

    def process_due_reminders(self) -> int:
        """
        Check for and process all due reminders.

        Returns:
            Number of reminders processed
        """
        due_reminders = self.reminder_manager.get_due_reminders()
        processed_count = 0

        for reminder in due_reminders:
            reminder_id = reminder["id"]
            message = reminder["message"]
            todo_id = reminder.get("todo_id")

            logger.debug(f"Processing due reminder {reminder_id}: {message}")

            # Send notification
            if self.send_notification(message, reminder_id, todo_id):
                # Only trigger (mark as done) if notification succeeded
                self.reminder_manager.trigger_reminder(reminder_id)
                processed_count += 1
            else:
                # Leave as pending to retry on next cycle
                logger.warning(
                    f"Reminder {reminder_id} notification failed, will retry"
                )

        self._stats["check_cycles"] += 1
        return processed_count

    def run(self) -> None:
        """
        Start the worker loop.

        Runs until stopped via stop() or signal.
        """
        self.running = True
        self._start_time = datetime.now()
        logger.info("NotificationWorker started")

        while self.running:
            try:
                processed = self.process_due_reminders()
                if processed > 0:
                    logger.info(f"Processed {processed} due reminder(s)")
            except Exception as error:
                logger.error(f"Error processing reminders: {error}")

            # Sleep in short intervals to allow for quick shutdown
            sleep_remaining = self.check_interval
            while sleep_remaining > 0 and self.running:
                sleep_time = min(sleep_remaining, 1.0)
                time.sleep(sleep_time)
                sleep_remaining -= sleep_time

        logger.info("NotificationWorker stopped")

    def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info("Stopping NotificationWorker...")
        self.running = False

    def register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        logger.debug("Signal handlers registered (SIGTERM, SIGINT)")

    def _handle_shutdown(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown")
        self.stop()

    def snooze_reminder(
        self,
        reminder_id: int,
        minutes: int | None = None,
        new_time: datetime | None = None,
    ) -> bool:
        """
        Snooze a reminder to a later time.

        Args:
            reminder_id: ID of the reminder to snooze
            minutes: Minutes from now to snooze
            new_time: Explicit new time

        Returns:
            True if snooze was successful
        """
        return self.reminder_manager.snooze_reminder(
            reminder_id,
            new_time=new_time,
            minutes=minutes,
        )

    def dismiss_reminder(self, reminder_id: int) -> bool:
        """
        Dismiss a reminder.

        Args:
            reminder_id: ID of the reminder to dismiss

        Returns:
            True if dismissal was successful
        """
        return self.reminder_manager.dismiss_reminder(reminder_id)

    def get_stats(self) -> dict[str, Any]:
        """
        Get worker statistics.

        Returns:
            Dictionary with notification and uptime stats
        """
        uptime_seconds = 0
        if self._start_time:
            uptime_seconds = (datetime.now() - self._start_time).total_seconds()

        return {
            "notifications_sent": self._stats["notifications_sent"],
            "notifications_failed": self._stats["notifications_failed"],
            "check_cycles": self._stats["check_cycles"],
            "uptime_seconds": uptime_seconds,
            "running": self.running,
        }


# Singleton instance
_notification_worker: NotificationWorker | None = None


def get_notification_worker() -> NotificationWorker:
    """Get the singleton NotificationWorker instance."""
    global _notification_worker
    if _notification_worker is None:
        _notification_worker = NotificationWorker()
    return _notification_worker


def main() -> None:
    """Entry point for running the notification worker as a script."""
    from src.utils import setup_logging

    # Setup logging
    setup_logging("notification_worker")

    # Create and run worker
    worker = get_notification_worker()
    worker.register_signal_handlers()

    logger.info("Starting notification worker...")
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        worker.stop()
        logger.info("Notification worker shutdown complete")


if __name__ == "__main__":
    main()
