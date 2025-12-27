#!/usr/bin/env python3
"""
Security Monitoring Daemon

Continuously monitors for security events and sends alerts to Slack.
Run as a systemd service for production use.
"""

import argparse
import logging
import signal
import sys
import time

from src.security.config import (
    COST_CHECK_INTERVAL,
    SERVICE_CHECK_INTERVAL,
    SSH_CHECK_INTERVAL,
)
from src.security.monitors import SecurityMonitor


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("security.daemon")


class SecurityDaemon:
    """
    Security monitoring daemon.

    Runs continuous checks at configured intervals.
    """

    def __init__(self, webhook_url: str | None = None):
        self.monitor = SecurityMonitor(webhook_url)
        self.running = False
        self.last_ssh_check = 0
        self.last_cost_check = 0
        self.last_service_check = 0

    def _setup_signal_handlers(self):
        """Set up graceful shutdown handlers."""

        def handle_shutdown(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)

    def run(self):
        """
        Run the monitoring daemon.

        Checks each monitor at its configured interval.
        """
        self._setup_signal_handlers()
        self.running = True

        logger.info("Security monitoring daemon starting...")
        logger.info(f"SSH check interval: {SSH_CHECK_INTERVAL}s")
        logger.info(f"Cost check interval: {COST_CHECK_INTERVAL}s")
        logger.info(f"Service check interval: {SERVICE_CHECK_INTERVAL}s")

        # Test Slack connection on startup
        if self.monitor.notifier.webhook_url:
            logger.info("Testing Slack connection...")
            self.monitor.notifier.send_alert(
                title="Security Monitoring Started",
                message="Security monitoring daemon is now running on colby.",
                severity="info",
            )

        while self.running:
            try:
                now = time.time()

                # SSH check
                if now - self.last_ssh_check >= SSH_CHECK_INTERVAL:
                    try:
                        self.monitor.ssh_monitor.check()
                        self.last_ssh_check = now
                    except Exception as error:
                        logger.error(f"SSH check failed: {error}")

                # Cost check
                if now - self.last_cost_check >= COST_CHECK_INTERVAL:
                    try:
                        self.monitor.cost_monitor.check()
                        self.last_cost_check = now
                    except Exception as error:
                        logger.error(f"Cost check failed: {error}")

                # Service check
                if now - self.last_service_check >= SERVICE_CHECK_INTERVAL:
                    try:
                        self.monitor.service_monitor.check()
                        self.last_service_check = now
                    except Exception as error:
                        logger.error(f"Service check failed: {error}")

                # Sleep for a short interval before next check cycle
                time.sleep(10)

            except Exception as error:
                logger.error(f"Unexpected error in main loop: {error}")
                time.sleep(30)  # Wait longer on error

        logger.info("Security monitoring daemon stopped")

    def run_once(self):
        """Run all checks once and exit."""
        logger.info("Running single security check...")
        results = self.monitor.run_all_checks()

        total_alerts = sum(len(alerts) for alerts in results.values())
        logger.info(f"Check complete. Alerts generated: {total_alerts}")

        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Security monitoring daemon")
    parser.add_argument(
        "--once", action="store_true", help="Run checks once and exit (for testing)"
    )
    parser.add_argument("--webhook", type=str, help="Override Slack webhook URL")
    parser.add_argument("--test", action="store_true", help="Send a test alert and exit")
    args = parser.parse_args()

    daemon = SecurityDaemon(webhook_url=args.webhook)

    if args.test:
        logger.info("Sending test alert...")
        success = daemon.monitor.notifier.test_connection()
        if success:
            print("Test alert sent successfully!")
        else:
            print("Failed to send test alert. Check SLACK_SECURITY_WEBHOOK.")
            sys.exit(1)
    elif args.once:
        daemon.run_once()
    else:
        daemon.run()


if __name__ == "__main__":
    main()
