"""
Security Monitors

Monitors for various security events:
- SSH failed login attempts
- API cost thresholds
- Service health
"""

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from typing import Any

from src.security.config import (
    ALERT_HISTORY_FILE,
    API_COST_ALERT_THRESHOLD,
    AUTH_LOG_PATH,
    COST_VELOCITY_THRESHOLD,
    DISK_SPACE_THRESHOLD,
    MONITORED_SERVICES,
    SLACK_COST_WEBHOOK_URL,
    SLACK_HEALTH_WEBHOOK_URL,
    SLACK_SERVER_HEALTH_WEBHOOK,
    SLACK_WEBHOOK_URL,
    SSH_FAILED_THRESHOLD,
    SSH_STATE_FILE,
    SUDO_FAILED_THRESHOLD,
    UFW_BLOCK_THRESHOLD,
    UFW_LOG_PATH,
    WEEKLY_REPORT_DAY,
    WEEKLY_REPORT_HOUR,
)
from src.security.slack_client import SlackNotifier


logger = logging.getLogger("security.monitors")


class BaseMonitor:
    """Base class for security monitors."""

    def __init__(self, notifier: SlackNotifier | None = None):
        self.notifier = notifier or SlackNotifier()
        self.alert_history = self._load_alert_history()

    def _load_alert_history(self) -> dict[str, Any]:
        """Load alert history from file."""
        if ALERT_HISTORY_FILE.exists():
            try:
                with open(ALERT_HISTORY_FILE) as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                return {"alerts": []}
        return {"alerts": []}

    def _save_alert_history(self) -> None:
        """Save alert history to file."""
        # Keep only last 1000 alerts
        self.alert_history["alerts"] = self.alert_history["alerts"][-1000:]
        with open(ALERT_HISTORY_FILE, "w") as file:
            json.dump(self.alert_history, file, indent=2)

    def _record_alert(self, alert_type: str, details: dict[str, Any]) -> None:
        """Record an alert in history."""
        self.alert_history["alerts"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": alert_type,
                "details": details,
            }
        )
        self._save_alert_history()

    def _should_alert(self, alert_key: str, cooldown_minutes: int = 30) -> bool:
        """
        Check if we should send an alert (respects cooldown).

        Args:
            alert_key: Unique key for this type of alert
            cooldown_minutes: Minimum minutes between similar alerts

        Returns:
            True if we should send the alert
        """
        now = datetime.now()
        cooldown = timedelta(minutes=cooldown_minutes)

        for alert in reversed(self.alert_history.get("alerts", [])):
            if alert.get("details", {}).get("key") == alert_key:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if now - alert_time < cooldown:
                    logger.debug(f"Skipping alert {alert_key} - in cooldown period")
                    return False
                break

        return True


class SSHMonitor(BaseMonitor):
    """Monitor for SSH failed login attempts."""

    # Regex patterns for auth.log
    FAILED_PASSWORD_PATTERN = re.compile(
        r"(\w+\s+\d+\s+\d+:\d+:\d+).*sshd.*Failed password for (?:invalid user )?(\S+) from (\S+)"
    )
    INVALID_USER_PATTERN = re.compile(
        r"(\w+\s+\d+\s+\d+:\d+:\d+).*sshd.*Invalid user (\S+) from (\S+)"
    )

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load monitor state from file."""
        if SSH_STATE_FILE.exists():
            try:
                with open(SSH_STATE_FILE) as file:
                    return json.load(file)
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "last_position": 0,
            "last_inode": 0,
            "failed_attempts": {},  # IP -> list of timestamps
        }

    def _save_state(self) -> None:
        """Save monitor state to file."""
        with open(SSH_STATE_FILE, "w") as file:
            json.dump(self.state, file, indent=2)

    def check(self) -> list[dict[str, Any]]:
        """
        Check auth.log for new failed SSH attempts.

        Returns:
            List of alert dictionaries
        """
        alerts = []

        if not AUTH_LOG_PATH.exists():
            logger.warning(f"Auth log not found at {AUTH_LOG_PATH}")
            return alerts

        try:
            # Check if log file was rotated (inode changed)
            current_inode = AUTH_LOG_PATH.stat().st_ino
            if current_inode != self.state["last_inode"]:
                logger.info("Auth log rotated, resetting position")
                self.state["last_position"] = 0
                self.state["last_inode"] = current_inode

            # Read new lines from log
            with open(AUTH_LOG_PATH) as file:
                file.seek(self.state["last_position"])
                new_lines = file.readlines()
                self.state["last_position"] = file.tell()

            # Parse failed attempts
            now = datetime.now()
            window_start = now - timedelta(minutes=10)

            for line in new_lines:
                # Check for failed password
                match = self.FAILED_PASSWORD_PATTERN.search(line)
                if not match:
                    match = self.INVALID_USER_PATTERN.search(line)

                if match:
                    timestamp_str, username, source_ip = match.groups()
                    logger.debug(f"Failed SSH attempt: {username}@{source_ip}")

                    # Track by IP
                    if source_ip not in self.state["failed_attempts"]:
                        self.state["failed_attempts"][source_ip] = []

                    self.state["failed_attempts"][source_ip].append(now.isoformat())

            # Clean old attempts and check thresholds
            for source_ip, timestamps in list(self.state["failed_attempts"].items()):
                # Keep only recent attempts (last 10 minutes)
                recent = [ts for ts in timestamps if datetime.fromisoformat(ts) > window_start]
                self.state["failed_attempts"][source_ip] = recent

                # Check if threshold exceeded
                if len(recent) >= SSH_FAILED_THRESHOLD:
                    alert_key = f"ssh_failed_{source_ip}"
                    if self._should_alert(alert_key, cooldown_minutes=60):
                        alert = {
                            "type": "ssh_failed",
                            "source_ip": source_ip,
                            "attempts": len(recent),
                            "threshold": SSH_FAILED_THRESHOLD,
                        }
                        alerts.append(alert)
                        self._send_ssh_alert(alert)

            self._save_state()

        except PermissionError:
            logger.error(f"Permission denied reading {AUTH_LOG_PATH}")
        except Exception as error:
            logger.error(f"Error checking SSH attempts: {error}")

        return alerts

    def _send_ssh_alert(self, alert: dict[str, Any]) -> None:
        """Send SSH failed login alert to Slack."""
        self.notifier.send_alert(
            title="SSH Brute Force Detected",
            message=f"*{alert['attempts']}* failed SSH login attempts from `{alert['source_ip']}` in the last 10 minutes.",
            severity="critical",
            fields=[
                {"title": "Source IP", "value": alert["source_ip"]},
                {"title": "Attempts", "value": str(alert["attempts"])},
                {"title": "Threshold", "value": str(alert["threshold"])},
            ],
        )
        self._record_alert("ssh_failed", {"key": f"ssh_failed_{alert['source_ip']}", **alert})

    def get_stats(self, days: int = 7) -> dict[str, Any]:
        """Get SSH attempt statistics for the past N days."""
        total_attempts = 0
        unique_ips = set()

        for source_ip, timestamps in self.state.get("failed_attempts", {}).items():
            total_attempts += len(timestamps)
            if timestamps:
                unique_ips.add(source_ip)

        # Also check alert history for more comprehensive stats
        cutoff = datetime.now() - timedelta(days=days)
        historical_attempts = 0
        for alert in self.alert_history.get("alerts", []):
            if alert.get("type") == "ssh_failed":
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if alert_time > cutoff:
                    historical_attempts += alert.get("details", {}).get("attempts", 0)

        return {
            "recent_failed_attempts": total_attempts,
            "unique_source_ips": len(unique_ips),
            "historical_alerts": historical_attempts,
        }


class APICostMonitor(BaseMonitor):
    """Monitor for API cost thresholds."""

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)

    def check(self) -> list[dict[str, Any]]:
        """
        Check current API costs against threshold.

        Returns:
            List of alert dictionaries
        """
        alerts = []

        try:
            # Import here to avoid circular imports
            from src.utils import get_daily_usage

            daily_cost = get_daily_usage()

            if daily_cost >= API_COST_ALERT_THRESHOLD:
                alert_key = f"api_cost_{datetime.now().date().isoformat()}"
                if self._should_alert(alert_key, cooldown_minutes=120):  # 2 hour cooldown
                    alert = {
                        "type": "api_cost",
                        "daily_cost": daily_cost,
                        "threshold": API_COST_ALERT_THRESHOLD,
                    }
                    alerts.append(alert)
                    self._send_cost_alert(alert)

        except ImportError:
            logger.warning("Could not import utils module for cost checking")
        except Exception as error:
            logger.error(f"Error checking API costs: {error}")

        return alerts

    def _send_cost_alert(self, alert: dict[str, Any]) -> None:
        """Send API cost alert to Slack."""
        self.notifier.send_alert(
            title="API Cost Alert",
            message=f"Daily API cost has reached *${alert['daily_cost']:.2f}*, exceeding the ${alert['threshold']:.2f} threshold.",
            severity="warning",
            fields=[
                {"title": "Current Cost", "value": f"${alert['daily_cost']:.2f}"},
                {"title": "Threshold", "value": f"${alert['threshold']:.2f}"},
            ],
        )
        self._record_alert(
            "api_cost", {"key": f"api_cost_{datetime.now().date().isoformat()}", **alert}
        )

    def get_stats(self, days: int = 7) -> dict[str, Any]:
        """Get API cost statistics for the past N days."""
        try:
            from src.utils import get_usage_stats

            return get_usage_stats(days)
        except ImportError:
            return {"total_cost": 0, "total_requests": 0, "daily_breakdown": []}


class ServiceMonitor(BaseMonitor):
    """Monitor for service health."""

    def __init__(self, notifier: SlackNotifier | None = None, services: list[str] | None = None):
        super().__init__(notifier)
        self.services = services or MONITORED_SERVICES
        self.last_status: dict[str, str] = {}

    def _check_systemd_service(self, service_name: str) -> tuple[bool, str]:
        """Check if a systemd service is running."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name], capture_output=True, text=True, timeout=10
            )
            status = result.stdout.strip()
            return status == "active", status
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except FileNotFoundError:
            return False, "systemctl not found"
        except Exception as error:
            return False, str(error)

    def _check_docker_container(self, container_name: str) -> tuple[bool, str]:
        """Check if a Docker container is running."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                status = result.stdout.strip()
                return status == "running", status
            return False, "not found"
        except subprocess.TimeoutExpired:
            return False, "timeout"
        except FileNotFoundError:
            return False, "docker not found"
        except Exception as error:
            return False, str(error)

    def check(self) -> list[dict[str, Any]]:
        """
        Check all monitored services.

        Returns:
            List of alert dictionaries
        """
        alerts = []

        for service in self.services:
            # Try systemd first, then Docker
            is_running, status = self._check_systemd_service(service)

            if status == "inactive" or status == "systemctl not found":
                # Try as Docker container
                is_running, status = self._check_docker_container(service)

            # Check for status change (went down)
            previous_status = self.last_status.get(service)
            self.last_status[service] = status

            if previous_status and previous_status in ("active", "running") and not is_running:
                alert_key = f"service_down_{service}"
                if self._should_alert(alert_key, cooldown_minutes=5):
                    alert = {
                        "type": "service_down",
                        "service": service,
                        "status": status,
                        "previous_status": previous_status,
                    }
                    alerts.append(alert)
                    self._send_service_alert(alert)

            # Log status
            if not is_running and status not in (
                "not found",
                "docker not found",
                "systemctl not found",
            ):
                logger.warning(f"Service {service} is not running: {status}")

        return alerts

    def _send_service_alert(self, alert: dict[str, Any]) -> None:
        """Send service down alert to Slack."""
        self.notifier.send_alert(
            title="Service Down",
            message=f"Service `{alert['service']}` has stopped running.",
            severity="critical",
            fields=[
                {"title": "Service", "value": alert["service"]},
                {"title": "Current Status", "value": alert["status"]},
                {"title": "Previous Status", "value": alert["previous_status"]},
            ],
        )
        self._record_alert("service_down", {"key": f"service_down_{alert['service']}", **alert})

    def get_status(self) -> dict[str, str]:
        """Get current status of all monitored services."""
        status = {}
        for service in self.services:
            is_running, service_status = self._check_systemd_service(service)
            if service_status in ("inactive", "systemctl not found"):
                is_running, service_status = self._check_docker_container(service)
            status[service] = service_status
        return status


class UFWMonitor(BaseMonitor):
    """Monitor for UFW firewall block events."""

    # Regex pattern for UFW blocks in syslog/ufw.log
    UFW_BLOCK_PATTERN = re.compile(
        r"(\w+\s+\d+\s+\d+:\d+:\d+).*\[UFW BLOCK\].*SRC=(\d+\.\d+\.\d+\.\d+).*DPT=(\d+)"
    )

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)
        self.blocked_ips: dict[str, list[str]] = {}  # IP -> list of timestamps

    def check(self) -> list[dict[str, Any]]:
        """Check UFW log for blocked connections."""
        alerts = []

        if not UFW_LOG_PATH.exists():
            logger.debug(f"UFW log not found at {UFW_LOG_PATH}")
            return alerts

        try:
            now = datetime.now()
            window_start = now - timedelta(minutes=5)

            # Read recent log entries (tail approach for efficiency)
            with open(UFW_LOG_PATH) as file:
                lines = file.readlines()[-500:]  # Last 500 lines

            for line in lines:
                match = self.UFW_BLOCK_PATTERN.search(line)
                if match:
                    timestamp_str, source_ip, dest_port = match.groups()

                    # Skip multicast/broadcast noise
                    if source_ip.startswith("224.") or source_ip.endswith(".255"):
                        continue

                    if source_ip not in self.blocked_ips:
                        self.blocked_ips[source_ip] = []
                    self.blocked_ips[source_ip].append(now.isoformat())

            # Check thresholds and clean old entries
            for source_ip, timestamps in list(self.blocked_ips.items()):
                recent = [ts for ts in timestamps if datetime.fromisoformat(ts) > window_start]
                self.blocked_ips[source_ip] = recent

                if len(recent) >= UFW_BLOCK_THRESHOLD:
                    alert_key = f"ufw_block_{source_ip}"
                    if self._should_alert(alert_key, cooldown_minutes=30):
                        alert = {
                            "type": "ufw_block",
                            "source_ip": source_ip,
                            "block_count": len(recent),
                            "threshold": UFW_BLOCK_THRESHOLD,
                        }
                        alerts.append(alert)
                        self._send_ufw_alert(alert)

        except PermissionError:
            logger.error(f"Permission denied reading {UFW_LOG_PATH}")
        except Exception as error:
            logger.error(f"Error checking UFW blocks: {error}")

        return alerts

    def _send_ufw_alert(self, alert: dict[str, Any]) -> None:
        """Send UFW block alert to Slack."""
        self.notifier.send_alert(
            title="Firewall Blocking IP",
            message=f"UFW blocked *{alert['block_count']}* connection attempts from `{alert['source_ip']}` in the last 5 minutes.",
            severity="warning",
            fields=[
                {"title": "Source IP", "value": alert["source_ip"]},
                {"title": "Blocked Attempts", "value": str(alert["block_count"])},
            ],
        )
        self._record_alert("ufw_block", {"key": f"ufw_block_{alert['source_ip']}", **alert})


class SudoMonitor(BaseMonitor):
    """Monitor for failed sudo attempts."""

    SUDO_FAILED_PATTERN = re.compile(
        r"(\w+\s+\d+\s+\d+:\d+:\d+).*sudo.*(\S+).*authentication failure"
    )

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)
        self.failed_attempts: list[dict[str, str]] = []

    def check(self) -> list[dict[str, Any]]:
        """Check auth.log for failed sudo attempts."""
        alerts = []

        if not AUTH_LOG_PATH.exists():
            logger.debug(f"Auth log not found at {AUTH_LOG_PATH}")
            return alerts

        try:
            now = datetime.now()
            window_start = now - timedelta(minutes=10)

            with open(AUTH_LOG_PATH) as file:
                lines = file.readlines()[-200:]

            for line in lines:
                if "sudo" in line and (
                    "authentication failure" in line or "incorrect password" in line
                ):
                    self.failed_attempts.append(
                        {"timestamp": now.isoformat(), "line": line.strip()[:100]}
                    )

            # Keep only recent attempts
            self.failed_attempts = [
                attempt
                for attempt in self.failed_attempts
                if datetime.fromisoformat(attempt["timestamp"]) > window_start
            ]

            if len(self.failed_attempts) >= SUDO_FAILED_THRESHOLD:
                alert_key = "sudo_failed"
                if self._should_alert(alert_key, cooldown_minutes=30):
                    alert = {
                        "type": "sudo_failed",
                        "attempts": len(self.failed_attempts),
                        "threshold": SUDO_FAILED_THRESHOLD,
                    }
                    alerts.append(alert)
                    self._send_sudo_alert(alert)

        except PermissionError:
            logger.error(f"Permission denied reading {AUTH_LOG_PATH}")
        except Exception as error:
            logger.error(f"Error checking sudo attempts: {error}")

        return alerts

    def _send_sudo_alert(self, alert: dict[str, Any]) -> None:
        """Send sudo failure alert to Slack."""
        self.notifier.send_alert(
            title="Failed Sudo Attempts",
            message=f"*{alert['attempts']}* failed sudo/privilege escalation attempts in the last 10 minutes.",
            severity="critical",
            fields=[
                {"title": "Failed Attempts", "value": str(alert["attempts"])},
                {"title": "Threshold", "value": str(alert["threshold"])},
            ],
        )
        self._record_alert("sudo_failed", {"key": "sudo_failed", **alert})


class DiskSpaceMonitor(BaseMonitor):
    """Monitor for disk space usage."""

    def __init__(self, notifier: SlackNotifier | None = None, paths: list[str] | None = None):
        super().__init__(notifier)
        self.paths = paths or ["/", "/home"]

    def check(self) -> list[dict[str, Any]]:
        """Check disk space on monitored paths."""
        alerts = []

        for path in self.paths:
            try:
                result = subprocess.run(
                    ["df", "-h", path], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        if len(parts) >= 5:
                            usage_pct = int(parts[4].rstrip("%"))
                            if usage_pct >= DISK_SPACE_THRESHOLD:
                                alert_key = f"disk_space_{path}"
                                if self._should_alert(alert_key, cooldown_minutes=60):
                                    alert = {
                                        "type": "disk_space",
                                        "path": path,
                                        "usage_percent": usage_pct,
                                        "threshold": DISK_SPACE_THRESHOLD,
                                        "available": parts[3],
                                    }
                                    alerts.append(alert)
                                    self._send_disk_alert(alert)

            except subprocess.TimeoutExpired:
                logger.error(f"Timeout checking disk space for {path}")
            except Exception as error:
                logger.error(f"Error checking disk space for {path}: {error}")

        return alerts

    def _send_disk_alert(self, alert: dict[str, Any]) -> None:
        """Send disk space alert to Slack."""
        self.notifier.send_alert(
            title="Disk Space Critical",
            message=f"Disk usage on `{alert['path']}` has reached *{alert['usage_percent']}%*.",
            severity="critical" if alert["usage_percent"] >= 95 else "warning",
            fields=[
                {"title": "Path", "value": alert["path"]},
                {"title": "Usage", "value": f"{alert['usage_percent']}%"},
                {"title": "Available", "value": alert["available"]},
            ],
        )
        self._record_alert("disk_space", {"key": f"disk_space_{alert['path']}", **alert})


class HAHealthMonitor(BaseMonitor):
    """Monitor for Home Assistant availability."""

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)
        self.consecutive_failures = 0
        self.last_status = "unknown"

    def check(self) -> list[dict[str, Any]]:
        """Check if Home Assistant API is responding."""
        alerts = []

        try:
            import os

            ha_url = os.getenv("HA_URL", "http://localhost:8123")
            ha_token = os.getenv("HA_TOKEN", "")

            import urllib.request

            request = urllib.request.Request(
                f"{ha_url}/api/", headers={"Authorization": f"Bearer {ha_token}"}
            )

            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    if response.status == 200:
                        if self.last_status == "down":
                            # HA recovered - send recovery notice
                            self.notifier.send_alert(
                                title="Home Assistant Recovered",
                                message="Home Assistant is responding again.",
                                severity="info",
                            )
                        self.consecutive_failures = 0
                        self.last_status = "up"
                        return alerts
            except urllib.error.URLError as error:
                self.consecutive_failures += 1
                logger.warning(f"HA health check failed: {error}")

            # Alert after 3 consecutive failures
            if self.consecutive_failures >= 3 and self.last_status != "down":
                alert_key = "ha_unavailable"
                if self._should_alert(alert_key, cooldown_minutes=15):
                    alert = {
                        "type": "ha_unavailable",
                        "consecutive_failures": self.consecutive_failures,
                        "ha_url": ha_url,
                    }
                    alerts.append(alert)
                    self._send_ha_alert(alert)
                    self.last_status = "down"

        except Exception as error:
            logger.error(f"Error checking HA health: {error}")

        return alerts

    def _send_ha_alert(self, alert: dict[str, Any]) -> None:
        """Send HA unavailable alert to Slack."""
        self.notifier.send_alert(
            title="Home Assistant Unavailable",
            message=f"Home Assistant API is not responding after *{alert['consecutive_failures']}* checks.",
            severity="critical",
            fields=[
                {"title": "URL", "value": alert["ha_url"]},
                {"title": "Failed Checks", "value": str(alert["consecutive_failures"])},
            ],
        )
        self._record_alert("ha_unavailable", {"key": "ha_unavailable", **alert})


class CostVelocityMonitor(BaseMonitor):
    """Monitor for API cost velocity (spending rate)."""

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)

    def check(self) -> list[dict[str, Any]]:
        """Check if API spending rate is too high."""
        alerts = []

        try:
            import sqlite3

            from src.utils import USAGE_DB_PATH

            if not USAGE_DB_PATH.exists():
                return alerts

            # Get cost in the last hour
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

            with sqlite3.connect(USAGE_DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0)
                    FROM api_usage
                    WHERE timestamp > ?
                """,
                    (one_hour_ago,),
                )
                result = cursor.fetchone()
                hourly_cost = result[0] if result else 0.0

            if hourly_cost >= COST_VELOCITY_THRESHOLD:
                alert_key = f"cost_velocity_{datetime.now().strftime('%Y-%m-%d-%H')}"
                if self._should_alert(alert_key, cooldown_minutes=60):
                    projected_daily = hourly_cost * 24
                    alert = {
                        "type": "cost_velocity",
                        "hourly_cost": hourly_cost,
                        "projected_daily": projected_daily,
                        "threshold": COST_VELOCITY_THRESHOLD,
                    }
                    alerts.append(alert)
                    self._send_velocity_alert(alert)

        except Exception as error:
            logger.error(f"Error checking cost velocity: {error}")

        return alerts

    def _send_velocity_alert(self, alert: dict[str, Any]) -> None:
        """Send cost velocity alert to Slack."""
        self.notifier.send_alert(
            title="High API Spending Rate",
            message=f"API spending rate is *${alert['hourly_cost']:.2f}/hour* (projected ${alert['projected_daily']:.2f}/day).",
            severity="warning",
            fields=[
                {"title": "Last Hour", "value": f"${alert['hourly_cost']:.2f}"},
                {"title": "Projected Daily", "value": f"${alert['projected_daily']:.2f}"},
                {"title": "Threshold", "value": f"${alert['threshold']:.2f}/hour"},
            ],
        )
        self._record_alert("cost_velocity", {"key": "cost_velocity", **alert})


class ServerHealthMonitor(BaseMonitor):
    """
    Comprehensive server health monitor with weekly reports.

    Checks:
    - Disk space usage
    - Memory usage
    - Load average
    - Stale tmux sessions
    - Zombie processes
    - System uptime
    """

    def __init__(self, notifier: SlackNotifier | None = None):
        super().__init__(notifier)
        self.last_report_date: str | None = None

    def check(self) -> list[dict[str, Any]]:
        """Run health checks and send alerts for issues."""
        alerts = []
        health_data = self._collect_health_data()

        # Check for critical issues
        if health_data.get("memory_percent", 0) > 90:
            alert_key = "memory_critical"
            if self._should_alert(alert_key, cooldown_minutes=30):
                alert = {"type": "memory_critical", **health_data}
                alerts.append(alert)
                self._send_memory_alert(health_data)

        if health_data.get("load_1min", 0) > 8:  # High for 4-core i7
            alert_key = "load_critical"
            if self._should_alert(alert_key, cooldown_minutes=30):
                alert = {"type": "load_critical", **health_data}
                alerts.append(alert)
                self._send_load_alert(health_data)

        if health_data.get("zombie_count", 0) > 5:
            alert_key = "zombies"
            if self._should_alert(alert_key, cooldown_minutes=60):
                alert = {"type": "zombie_processes", **health_data}
                alerts.append(alert)
                self._send_zombie_alert(health_data)

        stale_tmux = health_data.get("stale_tmux_sessions", 0)
        if stale_tmux > 10:
            alert_key = "stale_tmux"
            if self._should_alert(alert_key, cooldown_minutes=120):
                alert = {"type": "stale_tmux", **health_data}
                alerts.append(alert)
                self._send_tmux_alert(health_data)

        # Check if it's time for weekly report
        self._maybe_send_weekly_report(health_data)

        return alerts

    def _collect_health_data(self) -> dict[str, Any]:
        """Collect comprehensive health metrics."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "hostname": self._run_cmd("hostname"),
        }

        # Disk space
        try:
            df_output = self._run_cmd("df -h / /home 2>/dev/null | tail -n +2")
            disks = []
            for line in df_output.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 5:
                    disks.append(
                        {
                            "mount": parts[5] if len(parts) > 5 else parts[0],
                            "size": parts[1],
                            "used": parts[2],
                            "available": parts[3],
                            "percent": int(parts[4].rstrip("%")),
                        }
                    )
            data["disks"] = disks
        except Exception:
            data["disks"] = []

        # Memory
        try:
            mem_output = self._run_cmd("free -m | grep Mem")
            parts = mem_output.split()
            if len(parts) >= 3:
                total = int(parts[1])
                used = int(parts[2])
                data["memory_total_mb"] = total
                data["memory_used_mb"] = used
                data["memory_percent"] = round((used / total) * 100, 1) if total > 0 else 0
        except Exception:
            data["memory_percent"] = 0

        # Load average
        try:
            load_output = self._run_cmd("cat /proc/loadavg")
            parts = load_output.split()
            if len(parts) >= 3:
                data["load_1min"] = float(parts[0])
                data["load_5min"] = float(parts[1])
                data["load_15min"] = float(parts[2])
        except Exception:
            data["load_1min"] = 0

        # Uptime
        try:
            uptime_output = self._run_cmd("uptime -p")
            data["uptime"] = uptime_output.strip()
        except Exception:
            data["uptime"] = "unknown"

        # Zombie processes
        try:
            zombie_count = self._run_cmd("ps aux | grep -c ' Z '")
            data["zombie_count"] = max(0, int(zombie_count.strip()) - 1)  # Subtract grep itself
        except Exception:
            data["zombie_count"] = 0

        # Tmux sessions
        try:
            tmux_output = self._run_cmd("tmux list-sessions 2>/dev/null | wc -l")
            data["tmux_sessions"] = int(tmux_output.strip())

            # Check for stale sessions (older than 7 days based on activity)
            stale_output = self._run_cmd("tmux list-sessions -F '#{session_activity}' 2>/dev/null")
            stale_count = 0
            week_ago = (datetime.now() - timedelta(days=7)).timestamp()
            for line in stale_output.strip().split("\n"):
                if line:
                    try:
                        activity_time = int(line)
                        if activity_time < week_ago:
                            stale_count += 1
                    except ValueError:
                        pass
            data["stale_tmux_sessions"] = stale_count
        except Exception:
            data["tmux_sessions"] = 0
            data["stale_tmux_sessions"] = 0

        # Running containers
        try:
            container_count = self._run_cmd("docker ps -q 2>/dev/null | wc -l")
            data["docker_containers"] = int(container_count.strip())
        except Exception:
            data["docker_containers"] = 0

        return data

    def _run_cmd(self, cmd: str) -> str:
        """Run a shell command and return output.

        Security note: All commands passed to this method are hardcoded strings
        in the calling methods (hostname, df, free, etc.) - no user input is passed.
        Shell features (pipes, redirects) are required for these monitoring commands.
        """
        try:
            result = subprocess.run(
                cmd,
                shell=True,  # nosec B602 - hardcoded commands only, no user input
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _send_memory_alert(self, data: dict[str, Any]) -> None:
        """Send high memory usage alert."""
        self.notifier.send_alert(
            title="High Memory Usage",
            message=f"Memory usage at *{data.get('memory_percent', 0)}%* ({data.get('memory_used_mb', 0)}MB / {data.get('memory_total_mb', 0)}MB)",
            severity="critical" if data.get("memory_percent", 0) > 95 else "warning",
            fields=[
                {"title": "Used", "value": f"{data.get('memory_used_mb', 0)}MB"},
                {"title": "Total", "value": f"{data.get('memory_total_mb', 0)}MB"},
            ],
        )
        self._record_alert("memory_critical", {"key": "memory_critical", **data})

    def _send_load_alert(self, data: dict[str, Any]) -> None:
        """Send high load average alert."""
        self.notifier.send_alert(
            title="High System Load",
            message=f"Load average is *{data.get('load_1min', 0):.2f}* (1min), {data.get('load_5min', 0):.2f} (5min), {data.get('load_15min', 0):.2f} (15min)",
            severity="warning",
            fields=[
                {"title": "1 min", "value": f"{data.get('load_1min', 0):.2f}"},
                {"title": "5 min", "value": f"{data.get('load_5min', 0):.2f}"},
                {"title": "15 min", "value": f"{data.get('load_15min', 0):.2f}"},
            ],
        )
        self._record_alert("load_critical", {"key": "load_critical", **data})

    def _send_zombie_alert(self, data: dict[str, Any]) -> None:
        """Send zombie process alert."""
        self.notifier.send_alert(
            title="Zombie Processes Detected",
            message=f"Found *{data.get('zombie_count', 0)}* zombie processes that need cleanup.",
            severity="warning",
            fields=[
                {"title": "Zombie Count", "value": str(data.get("zombie_count", 0))},
            ],
        )
        self._record_alert("zombie_processes", {"key": "zombies", **data})

    def _send_tmux_alert(self, data: dict[str, Any]) -> None:
        """Send stale tmux session alert."""
        self.notifier.send_alert(
            title="Stale Tmux Sessions",
            message=f"Found *{data.get('stale_tmux_sessions', 0)}* tmux sessions inactive for 7+ days. Consider cleaning up with `tmux kill-session -t <name>`",
            severity="info",
            fields=[
                {"title": "Total Sessions", "value": str(data.get("tmux_sessions", 0))},
                {"title": "Stale (7+ days)", "value": str(data.get("stale_tmux_sessions", 0))},
            ],
        )
        self._record_alert("stale_tmux", {"key": "stale_tmux", **data})

    def _maybe_send_weekly_report(self, health_data: dict[str, Any]) -> None:
        """Send weekly report if it's the scheduled time."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # Check if it's the right day and hour
        if now.weekday() != WEEKLY_REPORT_DAY or now.hour != WEEKLY_REPORT_HOUR:
            return

        # Check if we already sent today's report
        if self.last_report_date == today_str:
            return

        # Send the report
        self._send_weekly_report(health_data)
        self.last_report_date = today_str

    def _send_weekly_report(self, health_data: dict[str, Any]) -> None:
        """Send comprehensive weekly health report."""
        # Build disk summary
        disk_summary = []
        for disk in health_data.get("disks", []):
            status = (
                "OK" if disk["percent"] < 80 else "WARN" if disk["percent"] < 90 else "CRITICAL"
            )
            disk_summary.append(
                f"{disk['mount']}: {disk['percent']}% ({disk['available']} free) [{status}]"
            )

        # Determine overall status
        issues = []
        if health_data.get("memory_percent", 0) > 80:
            issues.append("High memory usage")
        if health_data.get("load_1min", 0) > 4:
            issues.append("Elevated load average")
        if health_data.get("zombie_count", 0) > 0:
            issues.append(f"{health_data.get('zombie_count')} zombie processes")
        if health_data.get("stale_tmux_sessions", 0) > 5:
            issues.append(f"{health_data.get('stale_tmux_sessions')} stale tmux sessions")

        for disk in health_data.get("disks", []):
            if disk["percent"] > 80:
                issues.append(f"Disk {disk['mount']} at {disk['percent']}%")

        overall_status = "All systems healthy" if not issues else f"{len(issues)} issue(s) found"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Weekly Server Health Report",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Server:* {health_data.get('hostname', 'colby')}\n*Uptime:* {health_data.get('uptime', 'unknown')}\n*Status:* {overall_status}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Disk Usage*\n```\n" + "\n".join(disk_summary) + "\n```",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Memory:*\n{health_data.get('memory_percent', 0)}% ({health_data.get('memory_used_mb', 0)}MB / {health_data.get('memory_total_mb', 0)}MB)",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Load Avg:*\n{health_data.get('load_1min', 0):.2f} / {health_data.get('load_5min', 0):.2f} / {health_data.get('load_15min', 0):.2f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Docker Containers:*\n{health_data.get('docker_containers', 0)} running",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Tmux Sessions:*\n{health_data.get('tmux_sessions', 0)} total ({health_data.get('stale_tmux_sessions', 0)} stale)",
                    },
                ],
            },
        ]

        if issues:
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Issues to Address:*\n"
                        + "\n".join([f"• {issue}" for issue in issues]),
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Report generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            }
        )

        payload = {"blocks": blocks}
        self.notifier._send(payload)
        logger.info("Sent weekly server health report")

    def send_report_now(self) -> bool:
        """Manually trigger a health report."""
        health_data = self._collect_health_data()
        self._send_weekly_report(health_data)
        return True


class SecurityMonitor:
    """
    Combined security monitor that runs all checks.

    Uses separate Slack channels:
    - #colby-server-security: SSH failures, UFW blocks, sudo failures
    - #smarthome-costs: API cost threshold and velocity alerts
    - #smarthome-health: Service up/down, HA availability, disk space
    - #colby-server-health: Weekly reports, system metrics
    """

    def __init__(
        self,
        security_webhook: str | None = None,
        cost_webhook: str | None = None,
        health_webhook: str | None = None,
        server_health_webhook: str | None = None,
    ):
        # Each monitor gets its own notifier with the appropriate webhook
        security_notifier = SlackNotifier(security_webhook or SLACK_WEBHOOK_URL)
        cost_notifier = SlackNotifier(cost_webhook or SLACK_COST_WEBHOOK_URL)
        health_notifier = SlackNotifier(health_webhook or SLACK_HEALTH_WEBHOOK_URL)
        server_health_notifier = SlackNotifier(server_health_webhook or SLACK_SERVER_HEALTH_WEBHOOK)

        # Security channel monitors (#colby-server-security)
        self.ssh_monitor = SSHMonitor(security_notifier)
        self.ufw_monitor = UFWMonitor(security_notifier)
        self.sudo_monitor = SudoMonitor(security_notifier)

        # Cost channel monitors (#smarthome-costs)
        self.cost_monitor = APICostMonitor(cost_notifier)
        self.velocity_monitor = CostVelocityMonitor(cost_notifier)

        # Health channel monitors (#smarthome-health)
        self.service_monitor = ServiceMonitor(health_notifier)
        self.ha_monitor = HAHealthMonitor(health_notifier)
        self.disk_monitor = DiskSpaceMonitor(health_notifier)

        # Server health channel monitors (#colby-server-health)
        self.server_health_monitor = ServerHealthMonitor(server_health_notifier)

    def run_all_checks(self) -> dict[str, list[dict[str, Any]]]:
        """
        Run all security checks.

        Returns:
            Dictionary of check type -> alerts
        """
        results = {
            # Security channel (#colby-server-security)
            "ssh": self.ssh_monitor.check(),
            "ufw": self.ufw_monitor.check(),
            "sudo": self.sudo_monitor.check(),
            # Cost channel (#smarthome-costs)
            "api_cost": self.cost_monitor.check(),
            "cost_velocity": self.velocity_monitor.check(),
            # Health channel (#smarthome-health)
            "services": self.service_monitor.check(),
            "ha_health": self.ha_monitor.check(),
            "disk_space": self.disk_monitor.check(),
            # Server health channel (#colby-server-health)
            "server_health": self.server_health_monitor.check(),
        }

        total_alerts = sum(len(alerts) for alerts in results.values())
        if total_alerts > 0:
            logger.info(f"Security check completed with {total_alerts} alert(s)")
        else:
            logger.debug("Security check completed - no alerts")

        return results

    def get_all_stats(self, days: int = 7) -> dict[str, Any]:
        """Get statistics from all monitors."""
        return {
            "ssh": self.ssh_monitor.get_stats(days),
            "api_cost": self.cost_monitor.get_stats(days),
            "services": self.service_monitor.get_status(),
        }
