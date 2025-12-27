# Presence-Based Automation Implementation

**Date:** 2025-12-19
**Work Package:** WP-8.1
**Author:** Agent-Dorian

## Summary

Implemented a complete presence detection system for the smart home assistant. The system supports multi-source presence detection (WiFi/router, GPS, Bluetooth), presence state tracking (home/away/arriving/leaving), pattern learning for departure/arrival predictions, and vacuum automation hooks.

## Implementation Details

### Core Components

#### PresenceManager (`src/presence_manager.py`)
- SQLite-backed storage with 5 tables:
  - `presence_state`: Single-row table for current presence state
  - `device_trackers`: Registered device trackers (phone GPS, router, etc.)
  - `presence_history`: Audit log of all state changes
  - `presence_patterns`: Learned departure/arrival times by day of week
  - `presence_settings`: Configuration storage

- Multi-source detection:
  - Router/WiFi trackers (95% confidence, priority 10)
  - Bluetooth trackers (85% confidence, priority 8)
  - GPS trackers (80% confidence, priority 5)
  - Manual override (100% confidence, priority 15)
  - Pattern-based predictions (60% confidence, priority 2)

- Presence states:
  - `home`: User is at home
  - `away`: User has left home
  - `arriving`: User is approaching home (within arriving distance)
  - `leaving`: User is departing (transitional state)
  - `unknown`: Initial state or cannot determine

- Pattern learning:
  - Records departure/arrival times automatically
  - Predicts typical times by day of week
  - Requires minimum 3 data points for predictions
  - Confidence based on time variance

- Vacuum automation hooks:
  - `on_departure(callback)`: Register callback for when user leaves
  - `on_arrival(callback)`: Register callback for when user arrives/is arriving
  - Configurable delay before vacuum starts (default 5 minutes)

### Agent Tools (`tools/presence.py`)

11 tools implemented:

1. **get_presence_status**: Get current presence state, confidence, and source
2. **set_presence_mode**: Manually set presence (override automatic detection)
3. **get_presence_history**: View recent presence changes
4. **register_presence_tracker**: Add a device tracker for monitoring
5. **list_presence_trackers**: List all registered trackers
6. **predict_departure**: Predict typical departure time for a day
7. **predict_arrival**: Predict typical arrival time for a day
8. **get_presence_settings**: View configuration settings
9. **set_vacuum_delay**: Configure delay before vacuum starts
10. **discover_ha_trackers**: Find device_tracker entities in Home Assistant
11. **sync_presence_from_ha**: Update presence from HA tracker states

### Example Voice Commands

- "Am I home?" -> get_presence_status
- "I'm leaving" -> set_presence_mode(state='leaving')
- "I'll be gone for 2 hours" -> set_presence_mode(state='away', duration_minutes=120)
- "When do I usually leave?" -> predict_departure()
- "Add my phone as a tracker" -> register_presence_tracker(entity_id='device_tracker.phone', source_type='gps')
- "Wait 10 minutes before vacuuming" -> set_vacuum_delay(minutes=10)

## Technical Design

### Multi-Source Confidence Calculation

When multiple trackers report conflicting states, the system uses priority-weighted voting:

```python
# Priority weights
router (WiFi)  = 10 * 0.95 = 9.5
bluetooth      = 8  * 0.85 = 6.8
gps            = 5  * 0.80 = 4.0
pattern        = 2  * 0.60 = 1.2

# Final state = highest weighted vote
# Conflicting sources reduce confidence by 20%
```

### Arriving Detection

The system detects "arriving" state using:
1. GPS distance from home (configurable, default 500m)
2. Pattern predictions for expected arrival time
3. Router reconnection after "away" state

### Pattern Learning Algorithm

Patterns are stored as individual records with hour, minute, and day_of_week. Prediction uses:

1. Fetch last 20 matching records for pattern_type + day_of_week
2. Calculate average time (in minutes from midnight)
3. Calculate variance to determine confidence
4. Require minimum 3 data points for prediction

## Test Coverage

### Unit Tests (`tests/unit/test_presence_manager.py`)
50 tests covering:
- Initialization and database setup
- Device tracker CRUD operations
- Presence state management
- Multi-source detection
- History tracking
- Pattern learning
- Manual overrides
- Vacuum automation callbacks
- Settings management
- HA integration

### Integration Tests (`tests/integration/test_presence.py`)
27 tests covering:
- Tool definitions
- Tool dispatcher
- All 11 agent tools
- Error handling
- Edge cases

**Total: 77 presence-specific tests, 1224 tests passing in full suite**

## Files Changed

### New Files
- `src/presence_manager.py` (570 lines)
- `tools/presence.py` (380 lines)
- `tests/unit/test_presence_manager.py` (560 lines)
- `tests/integration/test_presence.py` (380 lines)

### Modified Files
- `tools/__init__.py` - Added presence exports
- `agent.py` - Added PRESENCE_TOOLS to agent

## Future Enhancements

1. **Vacuum scheduler**: Background process to execute vacuum automation on departure
2. **Zone-based presence**: Multiple zones (home, work, gym) for richer automations
3. **Bluetooth beacon support**: Room-level presence using ESP32 BLE proxies
4. **Presence modes**: "Night mode", "Guest mode" that affect automation behavior
5. **HA automation sync**: Create HA automations for presence events

## Dependencies

- No new dependencies required
- Uses existing SQLite, threading, and HA client patterns

## Configuration

New environment variables (optional):
- None required - uses sensible defaults

Settings stored in SQLite:
- `home_zone_radius`: 100 meters (default)
- `arriving_distance`: 500 meters (default)
- `vacuum_start_delay`: 5 minutes (default)

## Testing Notes

All tests run with temporary databases to avoid affecting production data. Mock HA client for integration tests.
