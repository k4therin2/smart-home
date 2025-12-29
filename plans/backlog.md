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

### Meshtastic Integration for Smart Home
**Priority:** P3 (research/planning phase)
**Effort:** L (large - new hardware + integration)
**Status:** Backlog (needs scoping)
**Added:** 2025-12-29

Investigate and implement Meshtastic LoRa mesh network for smart home automation, covering:

**1. Dog Tracking (Sophie)**
- Collar-mounted GPS tracker (SenseCAP T1000-E or similar)
- Detect dog arrivals/departures and track location
- No subscription fees (unlike cellular trackers)

**2. Presence Detection**
- Keychain tracker for user
- Trigger home automations (arriving/leaving geofences)

**3. Chicken Coop Automation**
- Remote coop monitoring and control:
  - Door open/closed status (magnetometer)
  - Temperature/humidity monitoring
  - Light sensor for sunrise/sunset automation
  - Predator detection with local AI camera processing + Meshtastic alert
  - Feed/water level monitoring
  - Solar-powered node (no wiring needed)

**4. Garden Sensor Network**
- Soil moisture monitoring
- Temperature monitoring
- Irrigation triggers

**5. General Infrastructure**
- Base station node at house
- Connected to Home Assistant via MQTT
- Single mesh network covers entire property

**Technical Notes:**
- Meshtastic uses LoRa for long-range, low-power mesh networking
- No subscription fees (unlike cellular trackers)
- Native Home Assistant integration via MQTT
- For predator detection: camera does local AI processing, Meshtastic only sends text alerts (can't handle video)

**Implementation Considerations:**
- Hardware sourcing (Meshtastic devices, sensors, solar panels)
- Range testing across property
- Battery life optimization
- Weatherproofing for outdoor nodes
- Home Assistant integration complexity
- Privacy/security of mesh network

---

## Archive

Removed/cancelled items for historical reference.

### WP-8.2: Device Onboarding & Organization System
**Removed:** 2025-12-20
**Reason:** User decided to skip zone onboarding. Home Assistant is source of truth for device organization.

---

*Last updated: 2025-12-27 by Agent-Anette (WP-62.2)*
