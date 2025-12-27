# WP-5.3: Location-Aware Commands Implementation

**Date:** 2025-12-18
**Author:** Agent-Worker-2663
**Status:** Complete

## Overview

Implemented location-aware command capabilities that enable the smart home system to infer user location from voice puck activity, track user movements between rooms, and provide context-aware command execution.

## Requirements Addressed (REQ-018)

- [x] Location inferred from which voice puck was used when possible
- [x] If location unknown, system asks for clarification ("Which room?")
- [x] Commands without room specification use current location IF known
- [x] Manual room override available ("turn on bedroom lights" when in living room)
- [x] Graceful degradation when location cannot be determined

## Architecture

### LocationManager Class (`src/location_manager.py`)

Core component for location tracking with SQLite persistence.

**Database Schema:**
- `voice_pucks`: Maps device IDs to room assignments
- `user_locations`: Current user location (single row)
- `location_history`: Chronological movement log
- `location_settings`: Configuration (default location, etc.)

**Key Features:**
- Thread-safe database operations
- Room name normalization (snake_case)
- Alias resolution (e.g., "lounge" → "living_room")
- Staleness detection (configurable timeout)
- Location history tracking

### Location Priority Chain

When determining effective location:

1. **Explicit room parameter** (highest priority) - User specifies room in command
2. **Current tracked location** - From recent voice puck activity or manual set
3. **Default location** (fallback) - Configured "home base" room

### Agent Tools (`tools/location.py`)

8 tools integrated into the main agent:

| Tool | Purpose |
|------|---------|
| `get_user_location` | Get current effective location |
| `set_user_location` | Manually set location |
| `get_room_from_voice_context` | Infer room from voice puck |
| `register_voice_puck` | Register puck with room |
| `list_voice_pucks` | List all registered pucks |
| `set_default_location` | Configure fallback room |
| `get_location_history` | View movement history |
| `clear_user_location` | Clear tracked location |

## Implementation Details

### Voice Puck Registration

Voice pucks are registered with their device IDs (from Home Assistant) and room assignments:

```python
manager.register_voice_puck(
    device_id="puck_living_room_001",
    room_name="living_room",
    display_name="Living Room Puck"
)
```

### Location Inference from Voice Context

When a voice command comes through Home Assistant webhook:

```python
context = {
    "device_id": "puck_living_room_001",
    "language": "en",
    "conversation_id": "conv_123"
}
room = manager.get_room_from_context(context)  # Returns "living_room"
```

### Room Name Normalization

All room names are normalized to snake_case for consistency:

- "Living Room" → "living_room"
- "Master Bedroom" → "master_bedroom"
- "lounge" (alias) → "living_room"

### Staleness Detection

Location is considered stale after configurable timeout (default 30 minutes):

```python
manager = LocationManager(stale_timeout_minutes=30)
# After timeout, get_effective_location falls back to default
```

## Test Coverage

**Unit Tests:** 43 tests in `tests/unit/test_location_manager.py`
- Initialization and database setup
- Voice puck registration and management
- Location inference
- User location tracking
- Location history
- Default location fallback
- Room normalization and alias resolution
- Staleness detection
- Room validation
- Concurrency (thread safety)

**Integration Tests:** 22 tests in `tests/integration/test_location_aware.py`
- Voice puck workflow
- Tool execution
- Effective location logic
- Room alias resolution
- Agent integration

**Total:** 65 tests, 100% passing

## Files Created/Modified

**New Files:**
- `src/location_manager.py` - LocationManager class
- `tools/location.py` - Agent tools
- `tests/unit/test_location_manager.py` - Unit tests
- `tests/integration/test_location_aware.py` - Integration tests
- `devlog/location-aware/2025-12-18-implementation.md` - This devlog

**Modified Files:**
- `tools/__init__.py` - Added location tools export
- `agent.py` - Added location tools to TOOLS and execute_tool

## Usage Examples

### Setting Up Voice Pucks

```bash
# Register voice pucks during setup
python agent.py "register the living room voice puck as device puck_001"
python agent.py "register the bedroom voice puck as device puck_002"
```

### Location-Aware Commands

```bash
# Explicit location (always works)
python agent.py "turn on the bedroom lights"

# Context-aware (uses inferred location)
python agent.py "turn on the lights"  # Uses current room

# Manual location update
python agent.py "I'm in the kitchen"
python agent.py "turn on the lights"  # Kitchen lights
```

### Querying Location

```bash
python agent.py "where am I"
python agent.py "show my location history"
python agent.py "what pucks are registered"
```

## Future Enhancements

1. **Multi-user support** - Track locations per user
2. **Phone location integration** - Use phone's room detection
3. **Presence sensors** - Integrate motion/presence sensors
4. **Zone-based targeting** - "Turn off all upstairs lights"
5. **Automatic device discovery** - Detect new voice pucks automatically

## Notes

- This implementation provides the foundation for location-aware commands
- Voice puck hardware validation requires user setup (HA Voice PE, ATOM Echo, etc.)
- The location tools gracefully handle unknown locations by asking for clarification
