# Roadmap

## Current Phase: Phase 2 Device Integrations

### Phase 2: Device Integration Workstreams
**Status:** All 3 streams can run in parallel
**Parallelization:** 2 agent streams + 1 user stream working simultaneously

#### Stream A: Vacuum Control - Dreamehome L10s (REQ-010)
- **Status:** ⚪ Not Started
- **Owner:** Agent A
- **Effort:** M
- **Tasks:**
  - [ ] Integrate Dreamehome L10s with Home Assistant
  - [ ] Implement start/stop/pause controls
  - [ ] Add status monitoring
  - [ ] Test natural language commands
- **Done When:** Voice-controlled vacuum with status visibility

#### Stream B: Smart Blinds Control - Hapadif (REQ-013)
- **Status:** ⚪ Not Started
- **Owner:** Agent B
- **Effort:** M
- **Tasks:**
  - [ ] Integrate Hapadif blinds with Home Assistant
  - [ ] Implement open/close/partial control
  - [ ] Create light scene integration
  - [ ] Add scheduling automation
- **Done When:** Voice-controlled blinds with light coordination

#### Stream C: Philips Hue Hardware Validation (USER)
- **Status:** 🟡 In Progress
- **Owner:** USER (Katherine)
- **Effort:** S (USER effort - hardware setup, not agent coding)
- **Note:** Integration code already complete - this is physical hardware validation
- **Tasks:**
  - [x] Purchase Philips Hue bridge (if not already owned)
  - [x] Purchase Philips Hue bulbs/light strips for desired rooms
  - [x] Physically install Hue lights in rooms (living room, bedroom, kitchen, etc.)
  - [x] Set up Philips Hue bridge on local network
  - [x] Add Philips Hue integration to Home Assistant
  - [ ] Configure room mappings in Home Assistant to match `src/config.py` room names
  - [ ] Test existing demo code with actual hardware (verify scenes work)
  - [ ] Verify vibe presets apply correctly with real lights
  - [ ] Update room mappings in `src/config.py` if physical layout differs
  - [ ] Test dynamic scenes (fire, ocean, aurora) and tune speed/brightness if needed
- **Done When:**
  - Physical Philips Hue bridge and lights are installed
  - Hue integration is active in Home Assistant
  - All room names in config match Home Assistant entity IDs
  - Existing vibe presets and scene keywords work with real hardware
  - User can control lights via CLI: `python agent.py "turn living room to fire"`
  - User can control lights via Web UI at localhost:5050

---

## Backlog

### Phase 3: Voice & Critical Foundation (After Phase 2)
- [ ] Voice Control via HA Voice Puck (REQ-016) - CRITICAL PATH
- [ ] Request Caching & Optimization (REQ-005)
- [ ] Mobile-Optimized Web Interface (REQ-017)
- [ ] Time & Date Queries (REQ-024)

### Phase 4A: Essential Intelligence (After Phase 3)
- [ ] Todo List & Reminders (REQ-028)
- [ ] Spotify Playback Control (REQ-025)
- [ ] Simple Automation Creation (REQ-022)
- [ ] Timers & Alarms (REQ-023)
- [ ] Shopping List Management (REQ-029)

### Phase 5: Advanced Intelligence
- [ ] Self-Monitoring & Self-Healing (REQ-021)
- [ ] Device Organization Assistant (REQ-019)
- [ ] Location-Aware Commands (REQ-018)
- [ ] Music Education & Context (REQ-027)
- [ ] Continuous Improvement (REQ-034)

### Phase 6: Community Preparation
- [ ] Comprehensive Logging Enhancement (REQ-036)
- [ ] CI/CD Pipeline (REQ-037)
- [ ] Public Repository (REQ-032)
- [ ] Setup & Installation Documentation (REQ-033)

### Phase 7: Additional Device Integrations (Deferred)
- [ ] Smart Plug Control (REQ-012) - Moved from Phase 2
- [ ] Smart Thermostat Control (REQ-011) - Moved from Phase 2

### Phase 8+: Advanced Features (Post-launch)
- [ ] Future Local LLM Support (REQ-004)
- [ ] Secure Remote Access (REQ-007)
- [ ] Multi-User Support (REQ-008)
- [ ] Ring Camera Integration (REQ-014)
- [ ] Pattern Learning & Routine Discovery (REQ-020)
- [ ] Music Discovery Agent (REQ-026)
- [ ] Proactive Todo Assistance (REQ-031)

---

**Last Updated:** 2025-12-09
**Next Review:** After Phase 2 completion
