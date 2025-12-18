# Dreame L10s Vacuum Integration - Tools Implementation

**Date:** 2025-12-18
**Status:** Code Complete - Pending Hardware Validation
**REQ:** REQ-010

## Summary

Implemented vacuum control tools for the Dreame L10s robot vacuum. The integration uses the [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) HACS custom component which provides comprehensive control over Dreame robot vacuums.

## Changes Made

### New Files
- `tools/vacuum.py` - Vacuum control tools module with 4 tools:
  - `control_vacuum` - Start, stop, pause, resume, return home, locate
  - `get_vacuum_status` - Get current state, battery, cleaning stats
  - `set_vacuum_fan_speed` - Set suction power (quiet/standard/strong/turbo)
  - `clean_rooms` - Clean specific rooms by name

### Modified Files
- `src/config.py` - Added `VACUUM_ENTITY_ID` configuration and `get_vacuum_entity()` function
- `tools/__init__.py` - Added exports for `VACUUM_TOOLS` and `execute_vacuum_tool`
- `agent.py` - Integrated vacuum tools into the agent's tool list and executor

## Architecture

The vacuum tools follow the same pattern as the light tools:
1. Tool definitions with JSON schemas for Claude
2. Implementation functions that call Home Assistant services
3. A dispatcher function `execute_vacuum_tool()` for the agent

The integration uses:
- Standard HA vacuum services: `vacuum.start`, `vacuum.stop`, `vacuum.pause`, `vacuum.return_to_base`, `vacuum.locate`, `vacuum.set_fan_speed`
- Dreame-specific service: `dreame_vacuum.vacuum_clean_segment` for room-based cleaning

## Configuration

The vacuum entity ID is configurable via environment variable:
```bash
VACUUM_ENTITY_ID=vacuum.dreame_l10s  # Default
```

The entity ID will depend on how the Dreame integration names the vacuum after setup.

## Prerequisites

1. Install the Dreame Vacuum HACS integration:
   - Via HACS: Search for "Dreame Vacuum"
   - Manual: `wget -O - https://raw.githubusercontent.com/Tasshack/dreame-vacuum/master/install | bash -`

2. Configure the integration in Home Assistant with the vacuum's credentials

3. Update `VACUUM_ENTITY_ID` in `.env` if the entity ID differs from the default

## Example Commands

Natural language commands the agent can now handle:
- "Start the vacuum"
- "Stop vacuuming"
- "Send the robot home"
- "What's the vacuum status?"
- "Vacuum the living room"
- "Set vacuum to turbo mode"
- "Clean the kitchen and bedroom"
- "Pause the vacuum"
- "Where's the vacuum?" (locate/beep)

## Testing Notes

- Module imports tested successfully
- Agent correctly includes all 10 tools (6 existing + 4 vacuum)
- Actual hardware testing pending Dreame integration setup in Home Assistant

## Next Steps

1. User to install Dreame Vacuum HACS integration
2. Configure integration with vacuum credentials
3. Verify entity ID and update config if needed
4. Test commands with actual hardware
5. Map room segment IDs if using room-specific cleaning

## References

- [Tasshack/dreame-vacuum GitHub](https://github.com/Tasshack/dreame-vacuum)
- [Home Assistant Vacuum Integration](https://www.home-assistant.io/integrations/vacuum/)
- [REQ-010 Requirements](../plans/REQUIREMENTS.md)
