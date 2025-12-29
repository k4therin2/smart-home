# Automation Scheduler

Background daemon that evaluates automation triggers and executes actions.

## Overview

The Automation Scheduler runs as a background process, continuously checking for:

- **Time-based triggers** - Automations scheduled for specific times and days
- **State-based triggers** - Automations triggered by entity state changes
- **Presence-based triggers** - Automations triggered by presence state changes

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              AutomationScheduler                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐    ┌──────────────────┐      │
│  │ Time Triggers    │    │ State Triggers   │      │
│  │ (every 60s)      │    │ (every 60s)      │      │
│  └────────┬─────────┘    └────────┬─────────┘      │
│           │                       │                 │
│           ▼                       ▼                 │
│  ┌────────────────────────────────────────┐        │
│  │         Action Executor                 │        │
│  │  ┌──────────────┐ ┌──────────────────┐ │        │
│  │  │ Agent        │ │ HA Service       │ │        │
│  │  │ Commands     │ │ Calls            │ │        │
│  │  └──────────────┘ └──────────────────┘ │        │
│  └────────────────────────────────────────┘        │
│                                                      │
└─────────────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
    ┌─────────┐             ┌─────────────┐
    │  Agent  │             │     Home    │
    │ (Claude)│             │  Assistant  │
    └─────────┘             └─────────────┘
```

## Action Types

### Agent Commands (`agent_command`)

Executes natural language commands through the SmartHome agent (Claude).

```json
{
  "action_type": "agent_command",
  "action_config": {
    "command": "turn living room lights to warm"
  }
}
```

### HA Service Calls (`ha_service`)

Calls Home Assistant services directly via the REST API.

```json
{
  "action_type": "ha_service",
  "action_config": {
    "domain": "light",
    "service": "turn_on",
    "service_data": {
      "entity_id": "light.living_room",
      "brightness_pct": 80
    }
  }
}
```

## Running the Scheduler

### Manual (Development)

```bash
cd /home/k4therin2/projects/Smarthome
./venv/bin/python -m src.automation_scheduler
```

### Systemd Service (Production)

```bash
# Install the service
sudo cp deploy/systemd/smarthome-automation-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable smarthome-automation-scheduler
sudo systemctl start smarthome-automation-scheduler

# Check status
sudo systemctl status smarthome-automation-scheduler

# View logs
journalctl -u smarthome-automation-scheduler -f
```

## Configuration

The scheduler uses these defaults:

- **Check Interval:** 60 seconds (evaluates all trigger types)
- **Database:** `data/automations.db` (SQLite)

## Statistics

The scheduler tracks execution statistics accessible via `get_stats()`:

```python
from src.automation_scheduler import get_automation_scheduler

scheduler = get_automation_scheduler()
stats = scheduler.get_stats()

# Returns:
# {
#     "executions_success": 42,
#     "executions_failed": 3,
#     "check_cycles": 1440,
#     "state_checks": 1440,
#     "uptime_seconds": 86400,
#     "running": True
# }
```

## Error Handling

- **Failed automations** are logged but don't stop the scheduler
- **HA API errors** are caught and logged; automation retries next cycle
- **Agent command errors** are caught and logged; automation marked as failed
- **Database errors** are caught and logged; cycle continues

## Trigger Types

### Time Triggers

Evaluated against current time and day of week.

```json
{
  "trigger_type": "time",
  "trigger_config": {
    "time": "08:00",
    "days": ["mon", "tue", "wed", "thu", "fri"]
  }
}
```

### State Triggers

Evaluated by polling entity states and detecting changes.

```json
{
  "trigger_type": "state",
  "trigger_config": {
    "entity_id": "binary_sensor.front_door",
    "from_state": "off",
    "to_state": "on"
  }
}
```

### Presence Triggers

Similar to state triggers but for person entities.

```json
{
  "trigger_type": "presence",
  "trigger_config": {
    "entity_id": "person.katherine",
    "to_state": "not_home"
  }
}
```

## Troubleshooting

### Scheduler not running

```bash
# Check service status
sudo systemctl status smarthome-automation-scheduler

# Check logs
journalctl -u smarthome-automation-scheduler -n 50

# Verify HA connectivity
curl -s http://localhost:8123/api/states | head
```

### Automations not triggering

1. Check automation is enabled: `automation_manager.get_automation(id)`
2. Verify trigger config matches: time format "HH:MM", valid days
3. Check HA entity exists: `ha_client.get_state("entity_id")`
4. Check scheduler logs for errors

### State triggers not firing

State triggers require a state change from the cached value:
- First check initializes the cache (no trigger)
- Subsequent checks detect changes

To debug:
```python
scheduler = get_automation_scheduler()
print(scheduler._entity_states)  # View cached states
```

## Related

- [Automation Manager](automation-manager.md) - CRUD operations for automations
- [Automation Tools](automation-tools.md) - Voice/web automation creation
- [Notification Worker](notification-worker.md) - Similar background worker pattern
