# SmartHome Notification Worker

The notification worker is a background process that checks for due reminders and delivers notifications via Slack webhooks.

## Overview

The notification worker runs continuously in the background, periodically checking for reminders that are due and sending notifications to the configured Slack channel.

**Key Features:**
- Periodic checking for due reminders (default: every 60 seconds)
- Slack webhook notifications
- Automatic retry on notification failure (reminder stays pending)
- Graceful shutdown handling (SIGTERM, SIGINT)
- Statistics tracking (sent, failed, uptime)
- Snooze and dismiss functionality

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   NotificationWorker                        │
├─────────────────────────────────────────────────────────────┤
│  - check_interval: 60s                                      │
│  - running: bool                                            │
│  - _stats: {sent, failed, cycles}                          │
├─────────────────────────────────────────────────────────────┤
│  run() → Main loop                                          │
│  process_due_reminders() → Check and trigger due reminders │
│  send_notification() → Send via Slack                       │
│  snooze_reminder() → Reschedule                             │
│  dismiss_reminder() → Cancel                                │
│  get_stats() → Statistics                                   │
└─────────────────────────────────────────────────────────────┘
          │                         │
          ▼                         ▼
   ┌──────────────┐         ┌──────────────┐
   │ ReminderMgr  │         │ SlackNotifier│
   │ (database)   │         │ (webhook)    │
   └──────────────┘         └──────────────┘
```

## Configuration

### Environment Variables

```bash
# Slack webhook for reminder notifications
# Falls back to SLACK_HEALTH_WEBHOOK if not set
SLACK_REMINDER_WEBHOOK=https://hooks.slack.com/services/...
```

### Runtime Configuration

The worker can be configured at initialization:

```python
from src.notification_worker import NotificationWorker

worker = NotificationWorker(
    check_interval=30,  # Check every 30 seconds
    webhook_url="https://..."  # Custom webhook
)
```

## Running the Worker

### Manual Execution

```bash
cd /home/k4therin2/projects/Smarthome
./venv/bin/python -m src.notification_worker
```

### Systemd Service

Install the systemd service:

```bash
# Copy service file
sudo cp deploy/systemd/smarthome-notification-worker.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable smarthome-notification-worker
sudo systemctl start smarthome-notification-worker
```

Check status:

```bash
sudo systemctl status smarthome-notification-worker
```

View logs:

```bash
journalctl -u smarthome-notification-worker -f
```

## API

### NotificationWorker Class

#### `run()`
Start the worker loop. Runs until `stop()` is called or a signal is received.

#### `stop()`
Stop the worker gracefully.

#### `process_due_reminders() -> int`
Check for and process all due reminders. Returns the number processed.

#### `send_notification(message, reminder_id, todo_id=None) -> bool`
Send a notification via Slack. Returns True on success.

#### `snooze_reminder(reminder_id, minutes=None, new_time=None) -> bool`
Reschedule a reminder. Provide either `minutes` (from now) or `new_time` (explicit datetime).

#### `dismiss_reminder(reminder_id) -> bool`
Cancel a reminder (mark as dismissed).

#### `get_stats() -> dict`
Get worker statistics:
```python
{
    "notifications_sent": int,
    "notifications_failed": int,
    "check_cycles": int,
    "uptime_seconds": float,
    "running": bool
}
```

### Singleton Pattern

Use the singleton for shared access:

```python
from src.notification_worker import get_notification_worker

worker = get_notification_worker()
stats = worker.get_stats()
```

## Retry Behavior

When a notification fails to send:
1. The reminder remains in "pending" status
2. It will be retried on the next check cycle
3. Failed notifications increment the `notifications_failed` stat

This ensures no reminders are lost due to temporary Slack outages.

## Notification Format

Notifications are sent as Slack alerts with:
- **Title:** "Reminder"
- **Message:** The reminder text
- **Fields:**
  - Reminder ID
  - Time (formatted as "HH:MM AM/PM")
- **Todo Link:** If the reminder is linked to a todo, it's mentioned in the message

Example notification:
```
📣 Reminder

Call the dentist to schedule appointment

Linked to todo #42

Reminder ID: 15
Time: 3:00 PM
```

## Graceful Shutdown

The worker handles shutdown gracefully:
- Registers handlers for SIGTERM and SIGINT
- Finishes current processing cycle
- Logs shutdown status

This allows systemd to stop the service cleanly:
```bash
sudo systemctl stop smarthome-notification-worker
```

## Testing

Tests are located in `tests/unit/test_notification_worker.py`:

```bash
pytest tests/unit/test_notification_worker.py -v
```

Test coverage includes:
- Worker initialization
- Notification delivery (success/failure)
- Due reminder processing
- Worker loop behavior
- Graceful shutdown
- Snooze/dismiss functionality
- Statistics tracking

## Troubleshooting

### Worker not starting

1. Check environment file exists:
   ```bash
   ls -la /home/k4therin2/projects/Smarthome/.env
   ```

2. Verify Slack webhook is configured:
   ```bash
   grep SLACK_REMINDER_WEBHOOK .env
   ```

3. Check systemd logs:
   ```bash
   journalctl -u smarthome-notification-worker -n 50
   ```

### Notifications not sending

1. Test webhook manually:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test"}' \
     $SLACK_REMINDER_WEBHOOK
   ```

2. Check worker stats:
   ```python
   from src.notification_worker import get_notification_worker
   print(get_notification_worker().get_stats())
   ```

3. Review failed count in stats

### Reminders not triggering

1. Verify reminder is pending:
   ```python
   from src.reminder_manager import get_reminder_manager
   print(get_reminder_manager().list_reminders(status='pending'))
   ```

2. Check reminder time is in the past:
   ```python
   reminder = get_reminder_manager().get_reminder(reminder_id)
   print(f"Remind at: {reminder['remind_at']}")
   ```

3. Ensure worker is running:
   ```bash
   systemctl status smarthome-notification-worker
   ```
