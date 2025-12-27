# Hapadif Smart Blinds Integration - Tools Implementation

**Date:** 2025-12-18
**Status:** Code Complete - Pending Hardware Validation
**REQ:** REQ-013

## Summary

Implemented smart blinds control tools for Hapadif smart blinds. The integration uses the Tuya platform via the Hapadif Smart Bridge Hub (MH100), which connects to Home Assistant through the native Tuya integration.

## Integration Path

```
Hapadif Blinds → Hapadif Smart Bridge Hub (MH100) → Tuya/Smart Life App → Home Assistant Tuya Integration
```

The blinds appear as `cover` entities in Home Assistant.

## Changes Made

### New Files
- `tools/blinds.py` - Blinds control tools module with 4 tools:
  - `control_blinds` - Open, close, stop, set position (0-100%)
  - `get_blinds_status` - Get current position and state
  - `set_blinds_for_scene` - Set blinds based on scene presets (morning, day, evening, night, movie, work)
  - `list_rooms_with_blinds` - List configured rooms with blinds

### Modified Files
- `src/config.py` - Added blinds entity mappings to ROOM_ENTITY_MAP and `get_blinds_entities()` function
- `tools/__init__.py` - Added exports for `BLINDS_TOOLS` and `execute_blinds_tool`
- `agent.py` - Integrated blinds tools into the agent's tool list and executor

## Architecture

The blinds tools follow the same pattern as vacuum and light tools:
1. Tool definitions with JSON schemas for Claude
2. Implementation functions that call Home Assistant cover services
3. A dispatcher function `execute_blinds_tool()` for the agent

The integration uses standard HA cover services:
- `cover.open_cover` - Fully open
- `cover.close_cover` - Fully close
- `cover.stop_cover` - Stop movement
- `cover.set_cover_position` - Set to specific position (0-100%)

## Scene Presets

The `set_blinds_for_scene` tool supports coordinating blinds with lighting scenes:

| Scene   | Position | Description |
|---------|----------|-------------|
| morning | 100%     | Fully open for natural light |
| day     | 75%      | Mostly open, balanced light |
| evening | 25%      | Mostly closed for privacy |
| night   | 0%       | Fully closed |
| movie   | 0%       | Fully closed for dark room |
| work    | 50%      | Half open to reduce screen glare |

## Configuration

Rooms with blinds are configured in `src/config.py` ROOM_ENTITY_MAP:

```python
"living_room": {
    "lights": [...],
    "blinds": "cover.living_room_blinds",  # Hapadif via Tuya
},
```

Currently configured rooms with blinds:
- Living room
- Bedroom
- Office

## Prerequisites

1. Install Hapadif Smart Bridge Hub (MH100) and connect to WiFi (2.4GHz)
2. Connect blinds to the hub via the Smart Life/Tuya app
3. Add Tuya integration to Home Assistant
4. Verify entity IDs match configuration in `src/config.py`

## Example Commands

Natural language commands the agent can now handle:
- "Open the bedroom blinds"
- "Close living room blinds"
- "Set office blinds to 50%"
- "Lower the blinds halfway"
- "What's the blinds position in the bedroom?"
- "Set blinds for movie night"
- "Morning blinds" (opens all blinds)
- "Stop the blinds"

## Testing Notes

- Module imports tested successfully
- Agent correctly includes all 14 tools (10 existing + 4 blinds)
- Actual hardware testing pending Tuya integration setup in Home Assistant

## Next Steps

1. User to set up Hapadif Smart Bridge Hub
2. Connect blinds via Smart Life/Tuya app
3. Add Tuya integration to Home Assistant
4. Verify entity IDs and update config if needed
5. Test commands with actual hardware

## References

- [Home Assistant Tuya Integration](https://www.home-assistant.io/integrations/tuya/)
- [Home Assistant Cover Integration](https://www.home-assistant.io/integrations/cover/)
- [Hapadif Smart Bridge Amazon](https://www.amazon.com/Hapadif-Bridge-Compatible-Motorized-Realize/dp/B0CK4T67PG)
- [REQ-013 Requirements](../plans/REQUIREMENTS.md)

## Sources

- [Home Assistant Tuya Integration](https://www.home-assistant.io/integrations/tuya/)
- [Motionblinds Home Assistant Integration](https://www.home-assistant.io/integrations/motion_blinds/)
- [Hapadif Smart Blinds Review](https://smartshades.net/hapadif-smart-blinds-review/)
