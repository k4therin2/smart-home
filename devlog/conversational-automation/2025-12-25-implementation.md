# WP-9.1: Conversational Automation Setup via Voice

**Date:** 2025-12-25
**Author:** Agent-Dorian
**Status:** Complete
**Tests:** 42 new tests (28 unit + 14 integration), all passing

## Summary

Implemented multi-turn conversational voice interface for creating automations. Users can now say "create an automation that turns off lights at 10pm" and the system will guide them through any missing information with back-and-forth dialog.

## Release Notes

**What:** Voice-driven automation creation with natural language clarification dialogs.

**Why:** Previously, creating automations required knowing the exact format upfront. Now users can describe their intent naturally and the system asks clarifying questions when needed.

**How:** Added ConversationManager to track multi-turn state, integrated with existing VoiceHandler and AutomationManager.

## Example Flow

```
User: "Create an automation that turns off lights"
System: "At what time should this automation run?"
User: "10pm on weekdays"
System: "I'll turn off lights at 10:00pm on weekdays. Should I create this automation?"
User: "Yes"
System: "Created automation 'turn off lights'."
```

## Architecture

### Components

1. **ConversationManager** (`src/conversation_manager.py`)
   - Tracks conversation state per `conversation_id`
   - States: IDLE → COLLECTING → CONFIRMING → IDLE
   - Stores `AutomationDraft` with partial automation parameters
   - Auto-expires inactive conversations after 10 minutes

2. **VoiceHandler** (extended)
   - Checks for automation creation intent before passing to agent
   - Routes multi-turn conversations through ConversationManager
   - Falls through to normal agent for non-automation commands

3. **AutomationDraft** (dataclass)
   - Holds partial automation during collection
   - Tracks: name, trigger_type, trigger_config, action_command
   - `is_complete()` validates all required fields are present
   - `missing_fields()` returns list of what's still needed

### State Machine

```
┌──────┐  "create automation..."  ┌────────────┐
│ IDLE │ ────────────────────────▶│ COLLECTING │
└──────┘                          └────────────┘
    ▲                                   │
    │  cancel/confirm                   │ draft complete
    │                                   ▼
    └───────────────────────────  ┌────────────┐
                                  │ CONFIRMING │
                                  └────────────┘
```

### Intent Detection

Automation creation is detected by these phrases:
- "create automation"
- "make automation"
- "new automation"
- "set up automation"
- "automation that"
- "automation to"

### Parsing Capabilities

**Time parsing:**
- "at 10pm" → 22:00
- "8:30am" → 08:30
- "every night at 10" → 22:00
- "on weekdays" → ["mon", "tue", "wed", "thu", "fri"]
- "on weekends" → ["sat", "sun"]

**Device/room parsing:**
- "the living room lights" → action_command includes "living room"
- "all of them" → accepts as-is
- "turn on the kitchen" → action_command: "turn on kitchen lights"

## Files Changed

### New Files
- `src/conversation_manager.py` (~500 lines)
  - ConversationManager class
  - ConversationState enum
  - AutomationDraft dataclass
- `tests/unit/test_conversation_manager.py` (28 tests)
- `tests/integration/test_voice_automation.py` (14 tests)

### Modified Files
- `src/voice_handler.py`
  - Added import for conversation_manager
  - Added `_get_conversation_id()` method
  - Added `_handle_conversation()` method
  - Modified `process_command()` to check conversation first

## Testing

### Unit Tests (28)
- ConversationState transitions
- AutomationDraft completeness checking
- ConversationManager state management
- Response parsing (time, devices, confirmation/cancel)
- Conversation timeout/expiry
- Multi-turn state persistence

### Integration Tests (14)
- Simple one-shot automation creation
- Multi-turn flow with clarification
- Cancel mid-flow
- Non-automation passthrough
- Conversation isolation between IDs
- State-trigger automation
- Weekday time automation
- TTS-friendly response formatting

### Full Suite
- 1328 tests passing (up from 1286)
- No regressions in existing functionality

## Design Decisions

1. **Singleton ConversationManager**: Uses module-level singleton for persistence across webhook calls. Thread-safe for concurrent conversations.

2. **Conversation ID from HA**: Uses `conversation_id` from Home Assistant webhook payload for state tracking. Generates UUID if not provided.

3. **10-minute timeout**: Conversations auto-expire after 10 minutes of inactivity to prevent stale state buildup.

4. **Passthrough for non-automation**: If the command doesn't match automation intent, falls through to normal agent processing. No interruption to existing functionality.

5. **Name auto-generation**: If user doesn't provide an automation name, generates one from the action command (first 30 chars).

## Known Limitations

1. **State triggers not fully parsed**: "when I leave" is detected but requires more parsing to extract entity_id and to_state. Full implementation would need presence integration.

2. **Single device per automation**: Currently supports one action command. Multi-action automations would need additional work.

3. **No undo/modify mid-flow**: User can cancel but not go back and modify specific fields. They'd need to start over.

## Future Enhancements

- Integration with presence detection for "when I leave" parsing
- Support for "every hour" / "every 30 minutes" time patterns
- Device name autocomplete/suggestions
- "Add another action" for multi-action automations
- Voice feedback on what was understood (echo back)

## Verification

```bash
# Run all conversation manager tests
pytest tests/unit/test_conversation_manager.py -v

# Run all voice automation integration tests
pytest tests/integration/test_voice_automation.py -v

# Run full test suite
pytest tests/ -v
```

All tests pass. Ready for user testing via voice puck.
