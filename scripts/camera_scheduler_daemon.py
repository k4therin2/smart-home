#!/usr/bin/env python3
"""
Camera Scheduler Daemon

Long-running daemon that captures hourly baseline snapshots from cameras
and responds to motion events. Designed to run as a systemd service.

WP-11.3: Snapshot Scheduler with Motion-Trigger Optimization

Usage:
    python -m scripts.camera_scheduler_daemon
    # Or directly:
    ./scripts/camera_scheduler_daemon.py

Systemd:
    sudo systemctl enable smarthome-camera-scheduler
    sudo systemctl start smarthome-camera-scheduler
"""

import argparse
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.camera_scheduler import CameraScheduler, SchedulerConfig, get_camera_scheduler
from src.utils import setup_logging


logger = setup_logging("camera_scheduler_daemon")

# Daemon state
_running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _running
    logger.info(f"Received signal {signum}, shutting down...")
    _running = False


def send_slack_alert(message: str, channel: str = "smarthome-health") -> bool:
    """
    Send alert to Slack channel.

    Args:
        message: Alert message
        channel: Slack channel name

    Returns:
        True if sent successfully
    """
    try:
        # Import here to avoid circular imports
        from src.security.slack_client import send_slack_message
        return send_slack_message(message, channel)
    except ImportError:
        logger.warning("Slack client not available")
        return False
    except Exception as error:
        logger.error(f"Failed to send Slack alert: {error}")
        return False


def error_callback(camera_id: str, error: str) -> None:
    """Handle capture errors by alerting to Slack."""
    message = f":warning: Camera scheduler error on `{camera_id}`: {error}"
    send_slack_alert(message)


def run_daemon(check_interval: int = 60) -> None:
    """
    Run the camera scheduler daemon.

    Args:
        check_interval: Seconds between checks
    """
    global _running

    logger.info("Starting camera scheduler daemon")

    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create scheduler with error callback
    config = SchedulerConfig(
        hourly_baseline_enabled=True,
        motion_trigger_enabled=True,
        max_llm_calls_per_hour=10,
        error_callback=error_callback,
    )
    scheduler = CameraScheduler(config=config)

    # Log startup status
    status = scheduler.get_status()
    logger.info(f"Scheduler initialized: {status}")

    # Send startup notification
    send_slack_alert(
        ":camera: Camera scheduler daemon started",
        channel="smarthome-health",
    )

    last_hourly_run: datetime | None = None

    while _running:
        try:
            now = datetime.now()

            # Check if hourly baseline should run
            if scheduler.should_run_hourly_baseline():
                logger.info("Running hourly baseline capture")
                results = scheduler.run_hourly_baseline()

                success_count = sum(1 for r in results if r.get("success"))
                total_count = len(results)

                if success_count < total_count:
                    # Some captures failed
                    failed = [r for r in results if not r.get("success")]
                    for failure in failed[:3]:  # Limit to 3 alerts
                        error_callback(
                            failure.get("camera_id", "unknown"),
                            failure.get("error", "Unknown error"),
                        )

                last_hourly_run = now
                logger.info(f"Hourly baseline complete: {success_count}/{total_count}")

            # Sleep until next check
            time.sleep(check_interval)

        except Exception as error:
            logger.exception(f"Daemon error: {error}")
            send_slack_alert(
                f":x: Camera scheduler daemon error: {error}",
                channel="smarthome-health",
            )
            # Continue running after error
            time.sleep(check_interval)

    logger.info("Camera scheduler daemon stopped")
    send_slack_alert(
        ":stop_sign: Camera scheduler daemon stopped",
        channel="smarthome-health",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Camera Scheduler Daemon"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=60,
        help="Seconds between checks (default: 60)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)",
    )

    args = parser.parse_args()

    if args.once:
        # Single run mode for testing
        scheduler = get_camera_scheduler()
        if scheduler.should_run_hourly_baseline():
            results = scheduler.run_hourly_baseline()
            print(f"Captured {len(results)} snapshots")
            for result in results:
                status = "OK" if result.get("success") else "FAIL"
                camera = result.get("camera_id", "unknown")
                print(f"  [{status}] {camera}")
        else:
            print("Hourly baseline not due yet")
    else:
        run_daemon(check_interval=args.check_interval)


if __name__ == "__main__":
    main()
