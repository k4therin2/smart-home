"""
Security Monitoring Module

Provides security alerting and weekly reports via Slack.
Monitors:
- Failed SSH login attempts
- API cost thresholds
- Service health
- Authentication failures
"""

from src.security.monitors import (
    APICostMonitor,
    SecurityMonitor,
    ServiceMonitor,
    SSHMonitor,
)
from src.security.slack_client import SlackNotifier
from src.security.weekly_report import WeeklySecurityReport


__all__ = [
    "APICostMonitor",
    "SSHMonitor",
    "SecurityMonitor",
    "ServiceMonitor",
    "SlackNotifier",
    "WeeklySecurityReport",
]
