"""
Security Monitoring Configuration
"""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

# Slack Configuration - Four separate channels
SLACK_WEBHOOK_URL = os.getenv("SLACK_SECURITY_WEBHOOK")  # #colby-server-security: SSH, UFW, sudo
SLACK_COST_WEBHOOK_URL = os.getenv("SLACK_COST_WEBHOOK")  # #smarthome-costs: API cost alerts
SLACK_HEALTH_WEBHOOK_URL = os.getenv("SLACK_HEALTH_WEBHOOK")  # #smarthome-health: Service up/down
SLACK_SERVER_HEALTH_WEBHOOK = os.getenv(
    "SLACK_SERVER_HEALTH_WEBHOOK"
)  # #colby-server-health: Weekly reports

# Alert Thresholds
SSH_FAILED_THRESHOLD = int(os.getenv("SSH_FAILED_THRESHOLD", "5"))  # Alert after N failed attempts
API_COST_ALERT_THRESHOLD = float(os.getenv("API_COST_ALERT_THRESHOLD", "5.00"))  # Daily cost alert

# Monitoring Intervals (seconds)
SSH_CHECK_INTERVAL = int(os.getenv("SSH_CHECK_INTERVAL", "60"))  # Check auth.log every N seconds
COST_CHECK_INTERVAL = int(os.getenv("COST_CHECK_INTERVAL", "300"))  # Check API cost every 5 min
SERVICE_CHECK_INTERVAL = int(os.getenv("SERVICE_CHECK_INTERVAL", "60"))  # Check services every min

# Log paths
AUTH_LOG_PATH = Path(os.getenv("AUTH_LOG_PATH", "/var/log/auth.log"))
UFW_LOG_PATH = Path(os.getenv("UFW_LOG_PATH", "/var/log/ufw.log"))

# Additional thresholds
UFW_BLOCK_THRESHOLD = int(
    os.getenv("UFW_BLOCK_THRESHOLD", "10")
)  # Alert after N blocks from same IP in 5 min
SUDO_FAILED_THRESHOLD = int(
    os.getenv("SUDO_FAILED_THRESHOLD", "3")
)  # Alert after N failed sudo in 10 min
DISK_SPACE_THRESHOLD = int(os.getenv("DISK_SPACE_THRESHOLD", "85"))  # Alert when disk > N% full
COST_VELOCITY_THRESHOLD = float(
    os.getenv("COST_VELOCITY_THRESHOLD", "1.00")
)  # Alert if >$N spent in 1 hour

# Services to monitor
MONITORED_SERVICES = [
    "home-assistant",  # Home Assistant container
    "nats-server",  # NATS JetStream
    "docker",  # Docker daemon
]

# State file for tracking last processed log position
STATE_DIR = Path(__file__).parent.parent.parent / "data" / "security"
STATE_DIR.mkdir(parents=True, exist_ok=True)

SSH_STATE_FILE = STATE_DIR / "ssh_monitor_state.json"
ALERT_HISTORY_FILE = STATE_DIR / "alert_history.json"

# Weekly report schedule (day of week, hour)
# 0=Monday, 4=Friday
WEEKLY_REPORT_DAY = int(os.getenv("WEEKLY_REPORT_DAY", "4"))  # Friday
WEEKLY_REPORT_HOUR = int(os.getenv("WEEKLY_REPORT_HOUR", "17"))  # 5 PM
