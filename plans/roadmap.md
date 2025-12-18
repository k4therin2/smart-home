# Roadmap

**Recent Completions (2025-12-18):** Security quick wins, test suite foundation (4 test suites, 57 test cases), security monitoring Slack integration. See `plans/completed/2025-12-18-security-and-testing.md` for details.

---

## Alerting Standards

All future phases must include appropriate Slack alerts for operational visibility. Use these channels:

**#colby-server-security** - Server-level security events:
- SSH authentication failures
- UFW firewall blocks
- Intrusion detection alerts
- File integrity violations
- Suspicious process activity

**#smarthome-costs** - Cost management alerts:
- Daily API cost threshold exceeded ($5/day)
- Monthly budget warnings
- Unusual API usage spikes

**#smarthome-health** - Service health monitoring:
- Service up/down status changes
- Home Assistant connectivity issues
- Device connectivity failures
- Self-healing actions (success/failure)
- Critical service restarts

**Acceptance Criteria for Future Work:**
All new features must include:
- [ ] Appropriate alerts configured for the feature area
- [ ] Alert messages include actionable context
- [ ] Alert severity appropriate to the channel

---

## Current Phase: Phase 2 Device Integrations + Security Hardening

### Batch 1: Security Hardening (HIGH PRIORITY)

#### Phase 2.1: Application Security Baseline
- **Status:** ⚪ Not Started
- **Priority:** CRITICAL (blocking for production use)
- **Effort:** M
- **Tasks:**
  - [ ] Implement basic authentication for web UI (session-based)
  - [ ] Add CSRF protection for all POST endpoints
  - [ ] Implement Pydantic schema validation on API inputs
  - [ ] Add rate limiting on `/api/command` (10 req/min per IP)
  - [ ] Review all SQL queries for parameterization (prevent SQL injection)
- **Done When:** Web UI requires authentication, input validation in place
- **Plan:** See `devlog/security-audit/2025-12-18-security-backlog-analysis.md`

#### Phase 2.2: HTTPS/TLS Configuration
- **Status:** ⚪ Not Started
- **Priority:** HIGH
- **Effort:** S
- **Dependencies:** Can run parallel with Phase 2.1
- **Tasks:**
  - [ ] Generate self-signed certificate for local network use
  - [ ] Configure Flask to use HTTPS
  - [ ] Add HTTP→HTTPS redirect
  - [ ] Configure HSTS header (max-age=31536000)
  - [ ] Document certificate generation process
- **Done When:** Web UI only accessible via HTTPS, valid cert installed

---

### Batch 2: Device Integrations (After/Parallel with Security)

#### Stream A: Vacuum Control - Dreamehome L10s (REQ-010)
- **Status:** ⚪ Not Started
- **Owner:** Available for any agent
- **Effort:** M
- **Tasks:**
  - [ ] Integrate Dreamehome L10s with Home Assistant
  - [ ] Implement start/stop/pause controls
  - [ ] Add status monitoring
  - [ ] Test natural language commands
- **Done When:** Voice-controlled vacuum with status visibility

#### Stream B: Smart Blinds Control - Hapadif (REQ-013)
- **Status:** ⚪ Not Started
- **Owner:** Available for any agent
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

### Batch 3: Test Coverage Completion (Can run parallel with Batch 2)

#### Phase 2.3: Remaining Test Suites
- **Status:** ⚪ Not Started
- **Priority:** MEDIUM
- **Effort:** M
- **Dependencies:** Test infrastructure complete (done)
- **Tasks:**
  - [ ] Implement Agent Loop integration tests (11 test cases)
  - [ ] Implement Device Sync tests (12 test cases)
  - [ ] Implement Hue Specialist tests (11 test cases)
  - [ ] Implement Server API tests (13 test cases)
  - [ ] Implement Effects tests (7 test cases)
  - [ ] Implement Utils tests (12 test cases)
  - [ ] Achieve 85%+ code coverage
  - [ ] Add CI/CD test automation
- **Done When:** All test suites passing, 85%+ coverage achieved
- **Plan:** See `plans/test-plan.md`

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

**Last Updated:** 2025-12-18
**Next Review:** After Batch 1 (Security Hardening) completion
