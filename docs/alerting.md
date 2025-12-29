# SmartHome Alerting Configuration

This document describes the Slack alerting system for SmartHome, including all alert channels, alert types, and configuration options.

## Overview

SmartHome uses Slack webhooks to send operational alerts. Alerts are categorized by channel based on their type and audience.

## Slack Channels

| Channel | Purpose | Alert Types |
|---------|---------|-------------|
| `#smarthome-health` | Service health and errors | Auth failures, API errors, device failures |
| `#smarthome-costs` | Cost management | Daily API cost threshold exceeded |
| `#colby-server-security` | Server-level security | SSH failures, UFW blocks, sudo failures |
| `#colby-server-health` | Server health reports | Weekly security reports |

## Alert Types

### Authentication Failure Alerts

**Channel:** `#smarthome-health`
**Component:** `auth`

Alerts are triggered when failed login attempts from the same IP address reach thresholds:

| Threshold | Severity | Alert Title |
|-----------|----------|-------------|
| 3 failed attempts | warning | Authentication Failures Detected |
| 5 failed attempts | critical | IP Address Locked Out |

**Behavior:**
- Alerts are sent once at each threshold (no spam)
- Failed attempts are tracked per IP address in a 15-minute window
- Details include: IP address, username attempted, failed count

**Code Location:** `src/security/auth.py`

### Spotify API Error Alerts

**Channel:** `#smarthome-health`
**Component:** `spotify`

Alerts are triggered when consecutive Spotify API errors reach the threshold:

| Threshold | Severity | Alert Title |
|-----------|----------|-------------|
| 3 consecutive errors | warning | Spotify API Errors Detected |
| Recovery after error state | info | Spotify API Recovered |

**Behavior:**
- Alert sent once at threshold (no spam on subsequent errors)
- Error counter resets on successful API call
- Recovery alert sent when API starts working again after being in error state
- Details include: operation, error message (truncated to 200 chars), consecutive error count

**Code Location:** `tools/spotify.py`

### Device Error Alerts

**Channel:** `#smarthome-health`
**Components:** `vacuum`, `blinds`, etc.

Similar threshold-based alerting for device-specific errors:
- Vacuum communication failures
- Blinds control errors

## Configuration

### Environment Variables

```bash
# Slack Webhooks (required)
SLACK_HEALTH_WEBHOOK=https://hooks.slack.com/services/...
SLACK_COST_WEBHOOK=https://hooks.slack.com/services/...
SLACK_SECURITY_WEBHOOK=https://hooks.slack.com/services/...
SLACK_SERVER_HEALTH_WEBHOOK=https://hooks.slack.com/services/...
SLACK_REMINDER_WEBHOOK=https://hooks.slack.com/services/...
```

### Alert Thresholds

Thresholds are configured in the code:

| Alert Type | Threshold Constant | Value | Location |
|------------|-------------------|-------|----------|
| Auth failures | `AUTH_FAILURE_ALERT_THRESHOLD` | 3 | `src/security/auth.py` |
| Auth lockout | (hardcoded) | 5 | `src/security/auth.py` |
| Spotify errors | `_SPOTIFY_ERROR_ALERT_THRESHOLD` | 3 | `tools/spotify.py` |
| API cost | `DAILY_COST_ALERT` | $5.00 | `src/config.py` |

## Alert Format

All alerts use Slack Block Kit format with:
- Color-coded sidebar (red=critical, yellow=warning, blue=info)
- Title with emoji indicator
- Message body with markdown formatting
- Optional fields for additional context
- Timestamp footer

### Severity Colors

| Severity | Color | Emoji |
|----------|-------|-------|
| critical | #dc3545 (red) | :rotating_light: |
| warning | #ffc107 (yellow) | :warning: |
| info | #17a2b8 (blue) | :information_source: |

## Testing Alerts

### Manual Test

```python
from src.utils import send_health_alert

send_health_alert(
    title="Test Alert",
    message="This is a test alert",
    severity="info",
    component="test"
)
```

### Automated Tests

Tests for alerting are located in:
- `tests/test_security.py::TestAuthFailureAlerting` - Auth failure alert tests
- `tests/integration/test_spotify.py::TestSpotifyErrorAlerting` - Spotify error alert tests
- `tests/unit/test_utils.py::test_send_health_alert_*` - Core alert function tests

Run tests:
```bash
pytest tests/test_security.py::TestAuthFailureAlerting -v
pytest tests/integration/test_spotify.py::TestSpotifyErrorAlerting -v
```

## Adding New Alerts

To add a new alert type:

1. Import the alert function:
   ```python
   from src.utils import send_health_alert
   ```

2. Call with appropriate parameters:
   ```python
   send_health_alert(
       title="Short descriptive title",
       message="Detailed message with *markdown* support",
       severity="warning",  # critical, warning, or info
       component="your_component",
       details={
           "key1": "value1",
           "key2": "value2"
       }
   )
   ```

3. Consider threshold-based alerting to avoid spam:
   ```python
   if error_count == THRESHOLD:
       send_health_alert(...)  # Only alert at threshold
   ```

4. Add recovery alerts when appropriate:
   ```python
   if was_in_error_state and now_working:
       send_health_alert(title="Recovered", severity="info")
   ```

## Troubleshooting

### Alerts Not Sending

1. Check webhook URL is configured:
   ```bash
   echo $SLACK_HEALTH_WEBHOOK
   ```

2. Test webhook manually:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test"}' \
     $SLACK_HEALTH_WEBHOOK
   ```

3. Check application logs for errors:
   ```bash
   cat data/logs/smarthome_*.log | grep -i "slack\|alert"
   ```

### Too Many Alerts

If receiving too many alerts:
1. Increase threshold constants (requires code change)
2. Review if the underlying issue needs fixing (alerts are working correctly!)

### Missing Context

If alerts lack context, add details:
```python
send_health_alert(
    ...,
    details={
        "entity_id": entity_id,
        "error_code": error.code,
        "suggestion": "Try restarting the device"
    }
)
```
