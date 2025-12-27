# Voice Control Architecture Design
## WP-3.1: Voice Control via HA Voice Puck

**Date:** 2025-12-18
**Agent:** Agent-Worker-4721
**Status:** Architecture Design Phase

---

## Requirements Analysis (REQ-016)

### User Requirements
- Wake word detection configured and working
- Voice input sent to system for processing
- Minimal personality responses (concise, not chatty)
- Multi-room support (multiple pucks if added later)
- Voice feedback for confirmations and errors
- Handles failed recognition gracefully

### Current State
- **Web UI** has browser-based speech recognition (Web Speech API) ✓
- **Home Assistant** has assist_pipeline configured (conversation.home_assistant)
- **No physical voice puck** hardware present yet
- Agent system routes through `agent.py` with Claude Sonnet 4 LLM

### Hardware Dependencies
**BLOCKER:** Physical HA Voice Puck hardware must be purchased and set up before software integration can be tested. This is a **USER task** that blocks full implementation.

Available HA Voice Puck options (2025):
- **Home Assistant Voice PE** (Official, $59)
- **ATOM Echo** (M5Stack, ~$30, DIY-friendly)
- **ESP32-based custom builds** (Various)

---

## Architecture Design

### Integration Approach

Home Assistant's Voice Assist system provides a complete pipeline:
1. **Wake Word Detection** → HA Voice Puck (hardware)
2. **Speech-to-Text (STT)** → HA Whisper integration or cloud STT
3. **Intent Recognition** → HA Conversation Agent (can be custom)
4. **Action Execution** → HA Services/Automations
5. **Text-to-Speech (TTS)** → HA TTS engine
6. **Audio Output** → HA Voice Puck speaker

### Integration Strategy

Instead of replacing HA's voice pipeline, we **integrate** with it:

```
┌─────────────────┐
│  Voice Puck     │
│  (Hardware)     │
└────────┬────────┘
         │ Wake word detected
         ▼
┌─────────────────────────┐
│ HA Voice Assist Pipeline│
│ - STT (Whisper)         │
│ - Intent Recognition    │
└────────┬────────────────┘
         │ Conversation API
         ▼
┌─────────────────────────┐
│ Custom Conversation     │
│ Agent (webhook)         │
│ → /api/voice_command    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ agent.py                │
│ - LLM Processing        │
│ - Tool Selection        │
│ - Device Control        │
└────────┬────────────────┘
         │ Response text
         ▼
┌─────────────────────────┐
│ HA TTS Engine           │
│ → Voice Puck Speaker    │
└─────────────────────────┘
```

### Implementation Components

#### 1. **Voice Command Webhook** (`src/voice_handler.py`)
New module to handle HA Conversation Agent webhook calls:
- Receives text from HA's STT
- Routes to agent.py for LLM processing
- Returns minimal, concise response text
- Handles errors gracefully

#### 2. **HA Conversation Integration**
Configure HA to use our custom agent:
```yaml
# configuration.yaml
conversation:
  intents:
    - intent: CustomSmartHome
      action:
        - service: conversation.process
          data:
            text: "{{ trigger.text }}"
```

Or use webhook approach:
```yaml
# automations.yaml
automation:
  - alias: "Route Voice to Custom Agent"
    trigger:
      - platform: event
        event_type: conversation_processed
    action:
      - service: rest_command.custom_agent
        data:
          text: "{{ trigger.event.data.text }}"
```

#### 3. **Response Formatting** (`src/voice_response.py`)
Minimal personality response formatter:
- Strip unnecessary verbosity from LLM output
- Format for TTS (no special characters, clean pronunciation)
- Handle multi-sentence responses (keep concise)
- Confirmation templates ("Done", "Lights turned on", "Error: [brief description]")

#### 4. **Multi-Room Support**
Track which voice puck/room initiated the request:
- HA provides `context.source` or device_id in webhook
- Store in request context
- Use for location-aware commands (REQ-018 future)

---

## TDD Implementation Plan

### Phase 1: Webhook Foundation (Works without hardware)
**Test First:**
1. Test voice command webhook endpoint exists
2. Test webhook accepts POST with `{"text": "command"}`
3. Test webhook routes to agent.py
4. Test webhook returns JSON response
5. Test error handling (timeout, invalid input)

**Implementation:**
- Create `src/voice_handler.py`
- Add `/api/voice_command` endpoint to server.py
- Wire up agent.py integration

### Phase 2: Response Formatting
**Test First:**
1. Test response truncation (max 100 words)
2. Test minimal personality (no "Sure!", "Absolutely!", etc.)
3. Test TTS-friendly formatting (remove emojis, special chars)
4. Test confirmation templates
5. Test error message formatting

**Implementation:**
- Create `src/voice_response.py`
- ResponseFormatter class with personality rules
- TTS sanitization

### Phase 3: Multi-Room Context (Future-proof)
**Test First:**
1. Test room/device extraction from HA context
2. Test room stored in request metadata
3. Test room passed to agent for context

**Implementation:**
- Extend voice_handler to extract source device
- Store in agent context

### Phase 4: HA Integration (Requires Hardware)
**Manual Testing Only:**
1. Configure HA conversation agent to webhook
2. Test wake word → command → response flow
3. Test multi-room (if multiple pucks)
4. Validate TTS quality
5. Test error scenarios (network down, agent timeout)

---

## Testing Strategy

### Unit Tests (No Hardware Required)
- `tests/unit/test_voice_handler.py` - Webhook logic
- `tests/unit/test_voice_response.py` - Response formatting
- `tests/unit/test_voice_integration.py` - Agent routing

### Integration Tests (Mock HA)
- `tests/integration/test_voice_flow.py` - End-to-end webhook → agent → response
- Mock Home Assistant webhook calls
- Verify response format

### Hardware Tests (Requires Voice Puck)
- **USER TASK**: Manual testing with actual voice puck
- Wake word accuracy
- Response latency
- TTS quality
- Multi-room handoff

---

## Acceptance Criteria Mapping

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Wake word detection | HA Voice Puck hardware | ⚪ BLOCKED (hardware) |
| Voice input to system | Webhook `/api/voice_command` | ⚪ Ready to implement |
| Minimal personality | ResponseFormatter class | ⚪ Ready to implement |
| Multi-room support | Context extraction from HA | ⚪ Ready to implement |
| Voice feedback | TTS via HA pipeline | ⚪ BLOCKED (hardware) |
| Handle failures | Error handling in webhook | ⚪ Ready to implement |

---

## Dependencies

### Software (Can Implement Now)
- ✅ agent.py exists and works
- ✅ server.py has API endpoint infrastructure
- ✅ Home Assistant running and accessible

### Hardware (USER Must Provide)
- ⚠️ **HA Voice Puck** - Not yet purchased
- ⚠️ **STT Configuration** - Whisper or cloud STT in HA
- ⚠️ **TTS Configuration** - HA TTS engine setup

---

## Implementation Order

1. ✅ **Architecture Design** (this document)
2. **Write Tests** - Unit tests for voice handler and response formatter
3. **Implement Webhook** - `/api/voice_command` endpoint
4. **Implement Response Formatter** - Minimal personality, TTS-friendly
5. **Integration Tests** - Mock HA webhook calls
6. **HA Configuration** - Webhook routing setup (documented, not applied)
7. **USER: Hardware Setup** - Purchase and configure voice puck
8. **USER: Manual Testing** - Validate with real hardware

---

## Cost Considerations

- Webhook processing uses same agent.py loop (already tracked)
- No additional API costs beyond existing usage
- Voice puck hardware: $30-60 one-time cost (user expense)

---

## Security Considerations

- Webhook endpoint must be authenticated (HA token required)
- Rate limiting on `/api/voice_command` (prevent abuse)
- Input validation on text payload
- No storage of voice audio (privacy)

---

## Next Steps

1. Mark architecture design complete ✓
2. Write unit tests for voice_handler
3. Implement VoiceHandler class
4. Write unit tests for voice_response
5. Implement ResponseFormatter class
6. Integration tests
7. Update roadmap with partial completion status

---

## Notes

This work package can be **partially completed** without hardware:
- Software infrastructure: 80% complete
- HA configuration: Documented, ready to apply
- Hardware validation: Blocked on user hardware purchase

Recommend splitting WP-3.1:
- **WP-3.1a**: Voice webhook software implementation (Agent task, ready now)
- **WP-3.1b**: Voice puck hardware validation (User task, blocked)
