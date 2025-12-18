"""
Security Monitoring Module

Provides security alerting and weekly reports via Slack.
Monitors:
- Failed SSH login attempts
- API cost thresholds
- Service health
- Authentication failures
"""

from src.security.slack_client import SlackNotifier
from src.security.monitors import (
    SSHMonitor,
    APICostMonitor,
    ServiceMonitor,
    SecurityMonitor,
)
from src.security.weekly_report import WeeklySecurityReport

__all__ = [
    "SlackNotifier",
    "SSHMonitor",
    "APICostMonitor",
    "ServiceMonitor",
    "SecurityMonitor",
    "WeeklySecurityReport",
]
