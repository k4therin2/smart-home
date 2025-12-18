# Roadmap

## How to Read This Roadmap

### Terminology
- **Phase**: Major milestone grouping (e.g., "Phase 2: Device Integrations + Security")
- **Work Package**: Individual unit of work that can be assigned to one agent (atomic, single-PR scope)
- **Parallel Group**: Work packages with no dependencies that can run simultaneously

### Understanding Dependencies
- **Can start immediately**: Status is ⚪ Not Started with no "Blocked by" line
- **Must wait**: Has "Blocked by" line listing required work packages
- **Parallel-safe**: Work packages in the same Parallel Group can run at the same time

### Claiming Work
1. Check `#coordination` channel for active work to avoid conflicts
2. Choose a ⚪ Not Started work package with no blockers
3. Post to `#coordination`: "Claiming [Work Package ID]: [Title]"
4. Begin work immediately

### Status Icons
- ⚪ Not Started (available to claim if no blockers)
- 🟡 In Progress (actively being worked)
- 🟢 Complete (moved to archive)
- 🔴 Blocked (waiting on dependencies)

---

## Recent Completions

**2025-12-18 (PM):** Phase 2.1 Application Security Baseline & Phase 2.2 HTTPS/TLS Configuration complete. Session-based authentication, CSRF protection, Pydantic validation, rate limiting, self-signed SSL certificates, HSTS headers. See `devlog/2025-12-18-phase2-security.md`.

**2025-12-18 (AM):** Security quick wins, test suite foundation (4 test suites, 57 test cases), security monitoring Slack integration. See `plans/completed/2025-12-18-security-and-testing.md` for details.

---

## Alerting Standards

All work packages must include appropriate Slack alerts for operational visibility. Use these channels:

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

**Acceptance Criteria for All Work:**
- [ ] Appropriate alerts configured for the feature area
- [ ] Alert messages include actionable context
- [ ] Alert severity appropriate to the channel

---

## Phase 2: Device Integrations + Security Hardening

### Parallel Group 1: Security Hardening (COMPLETE)

Both work packages completed 2025-12-18.

#### WP-2.1: Application Security Baseline
- **Status:** 🟢 Complete (2025-12-18)
- **Priority:** CRITICAL (blocking for production use)
- **Effort:** M
- **Owner:** Agent-Security-Phase2
- **Tasks:**
  - [x] Implement basic authentication for web UI (session-based)
  - [x] Add CSRF protection for all POST endpoints
  - [x] Implement Pydantic schema validation on API inputs
  - [x] Add rate limiting on `/api/command` (10 req/min per IP)
  - [x] Review all SQL queries for parameterization (prevent SQL injection)
  - [ ] Configure Slack alerts to #smarthome-health for auth failures (deferred to Phase 5)
- **Implementation:** `devlog/2025-12-18-phase2-security.md`
- **Files:** `src/security/auth.py`, `templates/auth/*.html`

#### WP-2.2: HTTPS/TLS Configuration
- **Status:** 🟢 Complete (2025-12-18)
- **Priority:** HIGH
- **Effort:** S
- **Owner:** Agent-Security-Phase2
- **Tasks:**
  - [x] Generate self-signed certificate for local network use
  - [x] Configure Flask to use HTTPS
  - [x] Add HTTP→HTTPS redirect
  - [x] Configure HSTS header (max-age=31536000)
  - [x] Document certificate generation process
  - [ ] Update Slack webhook URLs to use HTTPS (N/A - Slack webhooks are already HTTPS)
- **Implementation:** `devlog/2025-12-18-phase2-security.md`
- **Files:** `src/security/ssl_config.py`, `scripts/generate_cert.py`

---

### Parallel Group 2: Device Integrations

All three work packages can run in parallel with each other AND with Parallel Group 1 (Security).

#### WP-2.3: Vacuum Control (Dreamehome L10s)
- **Status:** 🟡 Code Complete - Pending Hardware Validation
- **Priority:** MEDIUM
- **Effort:** M
- **Owner:** Agent (2025-12-18)
- **Can start:** N/A (code done)
- **Requirement:** REQ-010
- **Tasks:**
  - [x] Integrate Dreamehome L10s with Home Assistant (tools/vacuum.py)
  - [x] Implement start/stop/pause controls via HA API (control_vacuum)
  - [x] Add status monitoring (cleaning/docked/battery) (get_vacuum_status)
  - [x] Create tool definition for main agent (VACUUM_TOOLS in agent.py)
  - [ ] Test natural language commands (pending HACS integration)
  - [ ] Configure Slack alerts to #smarthome-health for vacuum errors
- **Done When:**
  - Voice commands control vacuum (start/stop/pause)
  - Status visible in web UI
  - At least 3 test NL commands working
  - Error handling for offline/low battery states
- **Notes:** Requires Tasshack/dreame-vacuum HACS integration. See `devlog/vacuum-integration/2025-12-18-dreame-l10s-tools.md`

#### WP-2.4: Smart Blinds Control (Hapadif)
- **Status:** ⚪ Not Started
- **Priority:** MEDIUM
- **Effort:** M
- **Owner:** Available
- **Can start:** Yes (no blockers)
- **Requirement:** REQ-013
- **Tasks:**
  - [ ] Integrate Hapadif blinds with Home Assistant
  - [ ] Implement open/close/partial control (percentage-based)
  - [ ] Create light scene integration (coordinate with Hue)
  - [ ] Add scheduling automation (sunrise/sunset)
  - [ ] Test natural language commands ("close bedroom blinds 50%")
  - [ ] Configure Slack alerts to #smarthome-health for blind motor failures
- **Done When:**
  - Voice commands control blinds (open/close/position)
  - Blinds coordinate with light scenes
  - Sunrise/sunset automation working
  - At least 3 test NL commands working

#### WP-2.5: Philips Hue Hardware Validation (USER TASK)
- **Status:** 🟡 In Progress
- **Priority:** MEDIUM
- **Effort:** S (hardware setup, not coding)
- **Owner:** USER (Katherine)
- **Can start:** Already started
- **Note:** Integration code already complete - this is physical hardware validation
- **Tasks:**
  - [x] Purchase Philips Hue bridge
  - [x] Purchase Philips Hue bulbs/light strips
  - [x] Physically install lights in rooms
  - [x] Set up Hue bridge on local network
  - [x] Add Philips Hue integration to Home Assistant
  - [ ] Configure room mappings in HA to match `src/config.py`
  - [ ] Test existing demo code with actual hardware
  - [ ] Verify vibe presets (cozy/energize/focus/sleep) work
  - [ ] Test dynamic scenes (fire/ocean/aurora) and tune speed/brightness
  - [ ] Update room mappings in `src/config.py` if layout differs
- **Done When:**
  - Physical Hue bridge and lights installed
  - Hue integration active in Home Assistant
  - Room names in config match HA entity IDs
  - All vibe presets work with real hardware
  - CLI command works: `python agent.py "turn living room to fire"`
  - Web UI controls work at localhost:5050

#### WP-2.7: Spotify Integration
- **Status:** ⚪ Not Started
- **Priority:** HIGH (user high-value daily use case)
- **Effort:** M
- **Owner:** Available
- **Can start:** Yes (no blockers)
- **Requirement:** REQ-025
- **Use Case:** Daily Spotify playback to Amazon Echo devices (especially living room)
- **Tasks:**
  - [ ] Implement Spotify API OAuth 2.0 integration (Web API + Spotify Connect)
  - [ ] Add Spotify credential storage (encrypted in database or secrets.yaml)
  - [ ] Implement playback controls (play/pause/skip/volume)
  - [ ] Add search functionality (tracks, albums, playlists, artists)
  - [ ] Implement Spotify Connect device targeting (Amazon Echo devices)
  - [ ] Create tool definitions for main agent (play_spotify, control_playback, search_spotify)
  - [ ] Add natural language command support ("play X on living room speaker")
  - [ ] Test NL commands: play track, play playlist, play to specific device, control playback
  - [ ] Configure Slack alerts to #smarthome-health for Spotify API errors
  - [ ] Document OAuth setup process for users
- **Done When:**
  - OAuth flow working (user can authenticate)
  - Voice commands play Spotify to specific Echo devices
  - Playback controls work (play/pause/skip)
  - Search finds tracks/playlists/artists
  - At least 5 test NL commands working
  - Error handling for API failures and device offline states
- **Notes:** Requires Spotify Premium account. See Spotify Web API docs for Connect endpoints.

---

### Parallel Group 3: Test Coverage Completion

Can run in parallel with all work in Parallel Groups 1 and 2.

#### WP-2.6: Remaining Test Suites
- **Status:** ⚪ Not Started
- **Priority:** MEDIUM
- **Effort:** M
- **Owner:** Available
- **Can start:** Yes (test infrastructure complete)
- **Tasks:**
  - [ ] Implement Agent Loop integration tests (11 test cases)
  - [ ] Implement Device Sync tests (12 test cases)
  - [ ] Implement Hue Specialist tests (11 test cases)
  - [ ] Implement Server API tests (13 test cases)
  - [ ] Implement Effects tests (7 test cases)
  - [ ] Implement Utils tests (12 test cases)
  - [ ] Achieve 85%+ code coverage
  - [ ] Add CI/CD test automation (GitHub Actions)
- **Done When:**
  - All 6 test suites implemented and passing
  - Code coverage ≥85%
  - CI/CD runs tests on every push
  - Coverage report generated automatically
- **Reference:** `plans/test-plan.md`

---

## Phase 3: Voice & Critical Foundation

**Unblocked:** Security hardening (WP-2.1, WP-2.2) complete as of 2025-12-18.

### Work Packages (Ready to Start)

#### WP-3.1: Voice Control via HA Voice Puck
- **Status:** ⚪ Not Started
- **Can start:** Yes (security baseline complete)
- **Priority:** CRITICAL (critical path item)
- **Effort:** TBD
- **Requirement:** REQ-016

#### WP-3.2: Request Caching & Optimization
- **Status:** ⚪ Not Started
- **Can start:** Yes
- **Priority:** HIGH
- **Effort:** TBD
- **Requirement:** REQ-005

#### WP-3.3: Mobile-Optimized Web Interface
- **Status:** ⚪ Not Started
- **Can start:** Yes (HTTPS/TLS complete)
- **Priority:** MEDIUM
- **Effort:** TBD
- **Requirement:** REQ-017

#### WP-3.4: Time & Date Queries
- **Status:** ⚪ Not Started
- **Can start:** Yes
- **Priority:** LOW
- **Effort:** TBD
- **Requirement:** REQ-024

---

## Phase 4A: Essential Intelligence

**Blocked by:** Phase 3 completion

### Work Packages (Not Yet Detailed)
- [ ] WP-4.1: Todo List & Reminders (REQ-028)
- [ ] WP-4.2: Simple Automation Creation (REQ-022)
- [ ] WP-4.3: Timers & Alarms (REQ-023)
- [ ] WP-4.4: Shopping List Management (REQ-029)

---

## Phase 5: Advanced Intelligence

**Blocked by:** Phase 4A completion

### Work Packages (Not Yet Detailed)
- [ ] WP-5.1: Self-Monitoring & Self-Healing (REQ-021)
- [ ] WP-5.2: Device Organization Assistant (REQ-019)
- [ ] WP-5.3: Location-Aware Commands (REQ-018)
- [ ] WP-5.4: Music Education & Context (REQ-027)
- [ ] WP-5.5: Continuous Improvement (REQ-034)

---

## Phase 6: Community Preparation

**Blocked by:** Phase 5 completion

### Work Packages (Not Yet Detailed)
- [ ] WP-6.1: Comprehensive Logging Enhancement (REQ-036)
- [ ] WP-6.2: CI/CD Pipeline (REQ-037)
- [ ] WP-6.3: Public Repository (REQ-032)
- [ ] WP-6.4: Setup & Installation Documentation (REQ-033)

---

## Phase 7: Additional Device Integrations (Deferred)

**Blocked by:** Phase 3 completion

### Work Packages (Not Yet Detailed)
- [ ] WP-7.1: Smart Plug Control (REQ-012)
- [ ] WP-7.2: Smart Thermostat Control (REQ-011)

---

## Phase 8+: Advanced Features (Post-Launch)

**Status:** Backlog (no immediate plan)

### Work Packages (Not Yet Detailed)
- [ ] Future Local LLM Support (REQ-004)
- [ ] Secure Remote Access (REQ-007)
- [ ] Multi-User Support (REQ-008)
- [ ] Ring Camera Integration (REQ-014)
- [ ] Pattern Learning & Routine Discovery (REQ-020)
- [ ] Music Discovery Agent (REQ-026)
- [ ] Proactive Todo Assistance (REQ-031)

---

**Last Updated:** 2025-12-18
**Next Review:** After Parallel Group 1 (Security Hardening) completion
