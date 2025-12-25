# Voice Pipeline Diagnostic Suite - Development Log

**Work Package:** WP-9.2
**Created:** 2025-12-25
**Author:** Agent-Anette
**Status:** Complete

---

## Overview

This devlog documents the Voice Pipeline Diagnostic Suite - a comprehensive diagnostic tool to test the entire voice pipeline from voice puck to TTS response. This was developed as a Christmas gift for the user, addressing their #1 pain point (BUG-001: Voice Puck not responding).

## Release Notes

**What:** A new diagnostic dashboard at `/diagnostics` that tests all 5 components of the voice pipeline in one click, shows pass/fail status for each step, and provides actionable fix suggestions when things go wrong.

**Why:** The voice puck was unreliable - sometimes it would listen (green blink) but never respond. Debugging required manually checking each piece of the pipeline (ESPHome, HA Assist, webhook, SmartHome server, TTS). This tool automates that investigation and pinpoints exactly where things break.

**How:** Created a visual pipeline diagram with 5 test stages. Each test runs automatically, checks specific functionality (network connectivity, API availability, configuration completeness), and provides specific fix suggestions based on the failure mode.

---

## Architecture

### Pipeline Components Tested

1. **Voice Puck Connectivity**
   - DNS resolution of ESPHome device
   - ESPHome API port reachability (6053)

2. **HA Assist Pipeline**
   - Home Assistant API connectivity
   - Assist pipeline configuration
   - STT (Speech-to-Text) presence
   - TTS (Text-to-Speech) presence
   - Conversation agent status

3. **SmartHome Webhook**
   - `/api/health` endpoint reachability
   - Server is running and responding

4. **SmartHome Voice Endpoint**
   - `/api/voice` accepts test commands
   - Agent processes and responds
   - No LLM API errors

5. **TTS Output**
   - TTS entities configured in HA
   - Available media players for output

### Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `src/voice_diagnostics.py` | Core diagnostic logic with 5 test methods | ~550 |
| `templates/diagnostics.html` | Dashboard UI with pipeline visualization | ~230 |
| `static/diagnostics.js` | Frontend logic for running tests and displaying results | ~150 |
| `tests/test_voice_diagnostics.py` | 27 unit tests for diagnostic suite | ~400 |

### Server Routes Added

- `GET /diagnostics` - Renders the diagnostic dashboard page
- `POST /api/diagnostics/voice` - Runs all 5 diagnostic tests and returns results

---

## Usage

### Accessing the Dashboard

1. Navigate to `https://your-smarthome-server/diagnostics`
2. Log in if not already authenticated
3. Click "Run Full Diagnostic"

### Understanding Results

Each test shows:
- **Green checkmark** - Test passed
- **Red X** - Test failed
- **Yellow !** - Warning (partially working)

Failed tests automatically expand to show:
- Error message
- Technical details (JSON)
- Actionable fix suggestions

### Common Issues and Fixes

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| Voice Puck - DNS failed | mDNS not working | Use IP address directly |
| Voice Puck - Port closed | ESPHome not running | Power cycle the device |
| HA Assist - Not connected | HA down or token expired | Check HA, regenerate token |
| HA Assist - No STT/TTS | Incomplete pipeline setup | Configure in HA Settings > Voice assistants |
| Webhook - Connection refused | SmartHome server not running | Start with `python -m src.server` |
| Voice Endpoint - Timeout | LLM API issues | Check OPENAI_API_KEY, network |
| TTS - No media players | Speaker offline | Check voice puck in HA |

---

## Testing Commands

### Manual Testing (from SmartHome directory)

```bash
# Run the diagnostic suite tests
./venv/bin/python -m pytest tests/test_voice_diagnostics.py -v

# Test the diagnostic module directly
./venv/bin/python -c "
from src.voice_diagnostics import VoicePipelineDiagnostics
diag = VoicePipelineDiagnostics()
summary = diag.run_all_diagnostics()
print(diag.to_dict(summary))
"

# Check individual endpoints
curl -X POST http://localhost:5000/api/diagnostics/voice -H "Content-Type: application/json"
```

### Testing Voice Pipeline Manually

```bash
# 1. Check voice puck connectivity
ping esphome-voice.local

# 2. Check HA connection
curl -H "Authorization: Bearer $HA_TOKEN" http://localhost:8123/api/

# 3. Check SmartHome webhook
curl http://localhost:5000/api/health

# 4. Test voice endpoint
curl -X POST http://localhost:5000/api/voice_command \
  -H "Content-Type: application/json" \
  -d '{"text": "what time is it"}'
```

---

## Design Decisions

1. **Dataclass-based Results**
   - Used `@dataclass` for `DiagnosticResult` and `DiagnosticSummary`
   - Clean, typed, immutable result objects
   - Easy JSON serialization via `to_dict()` method

2. **Status Enum**
   - `TestStatus.PASSED`, `FAILED`, `WARNING`, `SKIPPED`
   - Clear semantics for pipeline visualization

3. **Fix Suggestions per Failure Mode**
   - Each failure type has specific, actionable suggestions
   - Not generic "check logs" but "verify ESPHome API is enabled on port 6053"

4. **Visual Pipeline Diagram**
   - Shows data flow from puck to speaker
   - Real-time status indicators during test run
   - Expandable details for failed tests

5. **Rate Limiting**
   - Diagnostics endpoint limited to 5/minute
   - Prevents abuse while allowing repeated testing

---

## Known Limitations

1. **Voice Puck Hostname**
   - Defaults to `esphome-voice.local`
   - May need configuration if using different hostname or IP

2. **HA Pipeline Discovery**
   - Uses REST API to discover pipelines
   - Some pipeline details may require WebSocket API for full inspection

3. **TTS Verification**
   - Checks TTS entities exist
   - Does not actually play audio (would be intrusive)

---

## Future Enhancements

If needed, the diagnostic suite could be extended with:

- **Audio test** - Play a test TTS message (with user permission)
- **Wake word test** - Verify wake word detection
- **Latency tracking** - Measure end-to-end response time
- **Historical tracking** - Store and graph diagnostic results over time
- **Automated scheduling** - Run diagnostics on a schedule with alerts

---

## Commit History

- Initial implementation: 2025-12-25
- Tests: 27 tests, all passing
- Coverage: Core diagnostic logic and API routes tested
