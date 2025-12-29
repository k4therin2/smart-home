# WP-10.3: Automation Scheduler Background Process

**Date:** 2025-12-29
**Agent:** Nadia
**Status:** Complete

## Summary

Implemented background daemon for evaluating automation triggers and executing actions. Follows the same pattern as `NotificationWorker` for consistency.

## What Was Built

### 1. AutomationScheduler Class (`src/automation_scheduler.py`)

Core background worker that:
- Runs continuously checking for due automations
- Evaluates time-based triggers (using existing `get_due_automations()`)
- Evaluates state-based triggers via polling (compares current vs cached entity states)
- Executes actions: agent commands (via `run_agent()`) or HA service calls
- Tracks execution statistics
- Supports graceful shutdown via SIGTERM/SIGINT

**Key Methods:**
- `process_automations()` - Main work function called each cycle
- `_process_time_triggers()` - Check time-based automations
- `_process_state_triggers()` - Check state/presence-based automations
- `_execute_automation()` - Route to appropriate action executor
- `_execute_agent_command()` - Run natural language command via agent
- `_execute_ha_service()` - Call Home Assistant REST API

### 2. Systemd Service (`deploy/systemd/smarthome-automation-scheduler.service`)

Production-ready systemd unit file with:
- Automatic restart on failure
- Security hardening (NoNewPrivileges, ProtectSystem, etc.)
- Journal logging
- Dependency on network and Home Assistant

### 3. Comprehensive Test Suite (`tests/unit/test_automation_scheduler.py`)

39 unit tests covering:
- Initialization and configuration
- Run loop and graceful shutdown
- Signal handling
- Time trigger processing
- State trigger processing
- Action execution (both types)
- Statistics tracking
- Error handling
- Singleton pattern

### 4. Documentation (`docs/automation-scheduler.md`)

Complete documentation including:
- Architecture diagram
- Action type reference
- Installation instructions
- Configuration options
- Troubleshooting guide

## Technical Decisions

### State Trigger Implementation

Chose **polling approach** over WebSocket for initial implementation:
- Simpler to implement and maintain
- Works with any HA setup
- 60-second polling interval is acceptable for most home automations
- Can be upgraded to WebSocket later if needed

### Error Handling Strategy

- Failed automations logged but don't crash scheduler
- Automations marked triggered only on success
- Failed automations retry on next cycle
- Database/HA connection errors caught gracefully

### Statistics Tracking

Added comprehensive stats for observability:
- `executions_success` / `executions_failed`
- `check_cycles` / `state_checks`
- `uptime_seconds` / `running`

## Files Created

| File | Purpose |
|------|---------|
| `src/automation_scheduler.py` | Core scheduler implementation |
| `tests/unit/test_automation_scheduler.py` | 39 unit tests |
| `deploy/systemd/smarthome-automation-scheduler.service` | Systemd unit |
| `docs/automation-scheduler.md` | Documentation |

## Test Results

- 39 new tests for scheduler
- All 735 unit tests passing
- No regressions

## Usage

### Development

```bash
./venv/bin/python -m src.automation_scheduler
```

### Production

```bash
sudo cp deploy/systemd/smarthome-automation-scheduler.service /etc/systemd/system/
sudo systemctl enable smarthome-automation-scheduler
sudo systemctl start smarthome-automation-scheduler
```

## Acceptance Criteria

- [x] Time-based automations execute at specified times
- [x] State-based automations execute on state changes
- [x] Both agent commands and HA services work as actions
- [x] Scheduler runs as systemd service
- [x] Error handling and logging
- [x] Tests (39 unit tests)
- [x] Documentation complete

## Integration Points

- **AutomationManager**: Queries automations, marks triggered
- **HAClient**: Gets entity states, calls services
- **Agent (run_agent)**: Executes natural language commands
