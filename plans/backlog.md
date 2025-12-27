# SmartHome Backlog

Deferred items and future enhancements not yet scheduled.

---

## Deferred Integrations

### Ring Camera Integration (WP-9.2) ✅ COMPLETE (2025-12-27)
**Priority:** P2 (user-requested feature)
**Effort:** L (large - new integration domain)
**Source:** Slack #colby-agent-work (2025-12-26)
**Status:** Complete - See plans/index.yaml and devlog/camera-integration/

User wants to integrate Ring cameras (doorbell + indoor) for:
1. Layout understanding - Agent references camera feeds to understand home layout
2. Remote monitoring - Check house status while traveling
3. Scene testing - Agents verify lighting changes via camera feeds

**Key Points:**
- User has Ring doorbell with camera on front door
- Multiple indoor Ring cameras (repositioned based on need)
- May require Ring account credentials or HA Cloud subscription
- LLM vision capability needed for scene understanding

**Implemented:** tools/camera.py with list_cameras, get_camera_snapshot, check_house_status

### LLM-Generated Dynamic Scenes (WP-2.8)
**Priority:** MEDIUM
**Effort:** M
**Blocked by:** WP-2.5 (Hue Hardware Validation)

Extend hue_specialist.py to generate custom color/brightness from abstract descriptions like "romantic dinner" or "calm meditation" instead of preset Hue scenes.

### Smart Thermostat Control (WP-7.2)
**Priority:** LOW
**Effort:** M
**Blocked by:** User hardware replacement

Requires user to replace Google Nest with open-source compatible thermostat before development can proceed.

---

## Deferred From Completed Work

These items were deferred during work package completion:

### Phase 2 Deferrals
- Configure Slack alerts to #smarthome-health for auth failures (from WP-2.1) ✅ PROMOTED TO WP-67.1 (2025-12-27)
- Configure Slack alerts to #smarthome-health for Spotify API errors (from WP-2.7) ✅ PROMOTED TO WP-67.1 (2025-12-27)

### Phase 4 Deferrals
- Background notification worker for reminders (from WP-4.1) ✅ PROMOTED TO WP-67.2 (2025-12-27)
- Automation scheduler (from WP-4.2)

### Phase 5 Deferrals
- All Phase 5+ Slack alerting configurations

### Phase 8 Deferrals
- Cleaning progress tracking (from WP-8.1, needs vacuum integration)
- Configure Slack alerts to smarthome-health (from WP-8.1)

---

## Future Ideas

### Local LLM Migration
**Priority:** P3 (cost optimization)
**Status:** Under consideration

Replace OpenAI API with local LLM (Ollama, LM Studio) for:
- Cost reduction
- Privacy improvement
- No rate limits

Currently using gpt-4o-mini via unified abstraction layer in `src/llm_client.py`.

### CI/CD Test Automation ✅ PROMOTED TO WP-67.3 (2025-12-27)
**Priority:** P2 (engineering quality)
**Status:** Promoted to agent-automation Batch 67

From WP-2.6 - GitHub Actions for test automation not yet complete:
- Tests run manually (81% coverage)
- Need automated CI/CD pipeline
- Need coverage report generation

---

## Archive

Removed/cancelled items for historical reference.

### WP-8.2: Device Onboarding & Organization System
**Removed:** 2025-12-20
**Reason:** User decided to skip zone onboarding. Home Assistant is source of truth for device organization.

---

*Last updated: 2025-12-27 by Agent-Anette (WP-62.2)*
