# Voice Control Software Implementation

## WP-3.1a: Voice Control Software Implementation
**Date:** 2025-12-18
**Agent:** Agent-TDD-4821
**Status:** Complete

---

## Summary

Implemented the software infrastructure for Home Assistant voice puck integration following TDD methodology. This enables natural language voice commands to be processed through the smart home agent.

## Implementation Details

### New Files Created

1. **`src/voice_handler.py`** - VoiceHandler class
   - Parses Home Assistant conversation webhook payloads
   - Routes voice text to agent with timeout protection
   - Extracts device/room context for multi-room support
   - Handles errors gracefully with user-friendly messages

2. **`src/voice_response.py`** - ResponseFormatter class
   - Removes chatty phrases for minimal personality ("Sure!", "Absolutely!", etc.)
   - Strips emojis and special characters for TTS compatibility
   - Truncates long responses (max 100 words default)
   - Provides confirmation and error message templates
   - Normalizes whitespace and joins multiline responses

3. **`src/server.py`** additions:
   - `/api/voice_command` endpoint for HA webhook
   - `VoiceCommandRequest` Pydantic model for validation
   - Dual authentication: session auth OR Bearer token (for HA webhook)
   - Rate limiting: 20 requests/minute per IP

### Test Suites Created

1. **`tests/unit/test_voice_handler.py`** - 20+ test cases
   - VoiceHandler instantiation and configuration
   - Command processing and agent routing
   - Context extraction from HA payloads
   - Error handling (empty input, agent errors, timeouts)
   - Request parsing validation

2. **`tests/unit/test_voice_response.py`** - 25+ test cases
   - Chatty phrase removal
   - Emoji and special character stripping
   - Response truncation
   - Whitespace normalization
   - Confirmation and error message templates
   - Edge cases (empty, None, multiline)

3. **`tests/integration/test_voice_flow.py`** - 15+ test cases
   - End-to-end webhook → agent → response flow
   - Authentication (session and token)
   - Input validation
   - Real-world command scenarios

---

## Home Assistant Configuration

To connect HA voice puck to this system, add the following configuration:

### Option 1: REST Command Webhook

```yaml
# configuration.yaml
rest_command:
  smart_home_voice:
    url: "https://colby:5050/api/voice_command"
    method: POST
    headers:
      Authorization: "Bearer {{ states('input_text.voice_webhook_token') }}"
      Content-Type: "application/json"
    payload: '{"text": "{{ text }}", "language": "{{ language }}", "device_id": "{{ device_id }}"}'

input_text:
  voice_webhook_token:
    name: Voice Webhook Token
    initial: ""  # Set via UI or secrets.yaml
```

### Option 2: Custom Conversation Agent

```yaml
# configuration.yaml
conversation:
  - platform: rest
    name: "Smart Home Agent"
    url: "https://colby:5050/api/voice_command"
    headers:
      Authorization: "Bearer {{ states('input_text.voice_webhook_token') }}"
```

### Option 3: Automation-Based Routing

```yaml
# automations.yaml
automation:
  - alias: "Route Voice Commands to Smart Home Agent"
    trigger:
      - platform: conversation
        command: "*"  # Match all commands
    action:
      - service: rest_command.smart_home_voice
        data:
          text: "{{ trigger.sentence }}"
          language: "{{ trigger.language }}"
          device_id: "{{ trigger.device_id }}"
```

### Environment Variables

Add to `.env` on the server:

```bash
# Optional: Webhook authentication token
# If set, HA must include this in Authorization header
VOICE_WEBHOOK_TOKEN=your-secure-random-token-here
```

Generate a secure token:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Architecture

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
         │ Webhook POST
         ▼
┌─────────────────────────┐
│ /api/voice_command      │  ← New endpoint
│ - Authentication        │
│ - Validation            │
│ - Rate limiting         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ VoiceHandler            │  ← New class
│ - Parse HA payload      │
│ - Route to agent        │
│ - Timeout protection    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ agent.py                │
│ - LLM Processing        │
│ - Tool Selection        │
│ - Device Control        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ ResponseFormatter       │  ← New class
│ - Minimal personality   │
│ - TTS-friendly output   │
│ - Truncation            │
└────────┬────────────────┘
         │ JSON response
         ▼
┌─────────────────────────┐
│ HA TTS Engine           │
│ → Voice Puck Speaker    │
└─────────────────────────┘
```

---

## Response Examples

### Before Formatting (Raw Agent Output)
```
Sure! I'd be happy to help! The living room lights have been turned on and set to 80% brightness. 💡
```

### After Formatting (TTS Output)
```
The living room lights have been turned on and set to 80% brightness.
```

### Error Response
```
Sorry, I couldn't connect to the home system. Please try again.
```

---

## Security Considerations

1. **Authentication**: Supports both session-based auth (web UI) and Bearer token auth (HA webhook)
2. **Rate Limiting**: 20 requests/minute prevents abuse
3. **Input Validation**: Pydantic validates all input, max 1000 chars
4. **Timeout Protection**: Agent calls timeout after 30 seconds
5. **Error Sanitization**: Technical errors not exposed to users

---

## Testing Notes

Run all voice control tests:
```bash
pytest tests/unit/test_voice_handler.py tests/unit/test_voice_response.py tests/integration/test_voice_flow.py -v
```

---

## Blocked Items

Hardware validation (WP-3.1b) is blocked until user purchases voice puck:
- Home Assistant Voice PE ($59)
- ATOM Echo ($30)
- ESP32-based custom build

---

## Files Changed

- `src/voice_handler.py` (new)
- `src/voice_response.py` (new)
- `src/server.py` (modified - new endpoint)
- `tests/unit/test_voice_handler.py` (new)
- `tests/unit/test_voice_response.py` (new)
- `tests/integration/test_voice_flow.py` (new)
