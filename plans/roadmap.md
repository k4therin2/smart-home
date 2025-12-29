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

**2025-12-29:** Intensive roadmap gardening by Agent-Henry. Moved 30 completed work packages to archive (`plans/archive/`). Added 27 new work packages from backlog, requirements gaps, and deferrals. Roadmap now shows only active/future work.

**Archive Location:** All completed work packages now in `plans/archive/phase*/`

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

## Active Work & Backlog

### USER TASKS (In Progress)

#### WP-2.5: Philips Hue Hardware Validation
- **Status:** 🟡 In Progress
- **Priority:** P1 (blocking for lighting features)
- **Effort:** S (hardware setup, not coding)
- **Owner:** USER (Katherine)
- **Note:** Integration code complete - this is physical hardware validation
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
  - Physical Hue bridge and lights installed ✓
  - Hue integration active in Home Assistant ✓
  - Room names in config match HA entity IDs
  - All vibe presets work with real hardware
  - CLI command works: `python agent.py "turn living room to fire"`
  - Web UI controls work at localhost:5050

---

## BUGS & ISSUES

#### BUG-001: Voice Puck Green Blink But No Response
- **Status:** 🔴 Blocked (needs user to check HA logs)
- **Priority:** P0 (core voice feature broken)
- **Reported:** 2025-12-20
- **Reporter:** Katherine (user)
- **Investigated:** 2025-12-20 by Agent-Anette, Agent-Nadia
- **Owner:** User (needs HA log inspection)
- **Symptom:** Voice puck blinks green after "hey jarvis what time is it" but doesn't produce any audio response
- **Investigation Findings (Agent-Nadia, 2025-12-20 14:16):**
  - ✅ Voice puck (192.168.1.30) is online and pingable
  - ✅ SmartHome server running correctly on ports 5049/5050
  - ✅ HA running in Docker with --network=host (localhost works correctly)
  - ✅ Direct API calls work: curl to /api/voice_command returns correct responses
  - ✅ Assist pipeline correctly configured:
    - STT: stt.faster_whisper
    - TTS: tts.piper (en_US-lessac-medium)
    - Conversation: smart_home_agent custom component
  - ❌ SmartHome logs show NO voice puck commands today - only test suite and curl tests
  - ❓ Issue is between wake word detection and SmartHome server
- **Diagnosis:**
  The SmartHome server and HA configuration are correct. The issue is in the HA voice pipeline:
  1. **Faster Whisper STT** may not be transcribing correctly
  2. **Assist pipeline** may not be routing to smart_home_agent
  3. **Voice puck** may not be sending audio to HA correctly
- **Required User Actions:**
  - [ ] When speaking to puck, check HA logs in real-time: Settings > System > Logs (set to DEBUG)
  - [ ] Test assist pipeline directly: Developer Tools > Services > assist_pipeline.run
  - [ ] Check voice puck ESPHome logs for audio/connection errors
  - [ ] Verify faster_whisper is transcribing: check HA logs for "stt" entries
- **Related:** WP-3.1a (Voice Software - Complete), WP-3.1b (Voice Hardware - Complete), WP-9.2 (Voice Diagnostics - Complete)

---

## Phase 10: Deferred Features & Enhancements

**Status:** Backlog - Items deferred from completed work or identified from requirements gaps

### Parallel Group 1: Alerting & Notifications

#### WP-10.1: Slack Alerting Configuration
- **Status:** 🟢 Complete (2025-12-29)
- **Completed By:** Agent-Nadia
- **Priority:** P2 (operational visibility)
- **Effort:** S
- **Source:** Deferred from WP-2.1, WP-2.7
- **Note:** Alerting was already implemented in WP-2.1/WP-2.7. This WP added test coverage and documentation.
- **Tasks:**
  - [x] Configure Slack alerts to #smarthome-health for auth failures (from WP-2.1) - Already implemented
  - [x] Configure Slack alerts to #smarthome-health for Spotify API errors (from WP-2.7) - Already implemented
  - [x] Test alert delivery and message formatting - Added 12 tests
  - [x] Document alerting configuration - Created docs/alerting.md
  - [x] Create devlog entry - Created devlog/2025-12-29-wp-10.1-alerting-tests-docs.md
- **Acceptance Criteria:**
  - [x] Auth failures trigger alerts to #smarthome-health
  - [x] Spotify API errors trigger alerts to #smarthome-health
  - [x] Alert messages are actionable
  - [x] Alerts tested and verified (12 new tests)

#### WP-10.2: Background Notification Worker
- **Status:** 🟢 Complete (2025-12-29)
- **Completed By:** Agent-Nadia
- **Priority:** P2 (user-facing feature completion)
- **Effort:** M
- **Source:** Deferred from WP-4.1 (Todo/Reminders)
- **Note:** Worker implementation existed from WP-67.2. This WP added systemd service and documentation.
- **Tasks:**
  - [x] Design background worker process for reminder notifications (WP-67.2)
  - [x] Implement notification delivery (Slack - WP-67.2, voice/web push deferred)
  - [x] Add retry logic for failed notifications (WP-67.2)
  - [x] Write tests for notification worker (WP-67.2, 20+ tests)
  - [x] Create systemd service for worker daemon (new)
  - [x] Document notification worker setup (new - docs/notification-worker.md)
  - [x] Create devlog entry (new)
- **Acceptance Criteria:**
  - [x] Reminders trigger notifications at deadline time
  - [x] Notifications delivered to Slack (voice puck + web push deferred)
  - [x] Failed notifications retry automatically
  - [x] Worker runs as systemd service

#### WP-10.3: Automation Scheduler Background Process
- **Status:** 🟢 Complete (2025-12-29)
- **Completed By:** Agent-Nadia
- **Priority:** P2 (automation feature completion)
- **Effort:** M
- **Source:** Deferred from WP-4.2 (Automation Creation)
- **Tasks:**
  - [x] Design scheduler daemon for automation execution
  - [x] Implement time-based trigger evaluation
  - [x] Implement state-based trigger evaluation
  - [x] Add action execution (agent commands + HA services)
  - [x] Write tests for scheduler (39 unit tests)
  - [x] Create systemd service for scheduler daemon
  - [x] Document automation scheduler
  - [x] Create devlog entry
- **Acceptance Criteria:**
  - [x] Time-based automations execute at specified times
  - [x] State-based automations execute on state changes
  - [x] Both agent commands and HA services work as actions
  - [x] Scheduler runs as systemd service
  - [x] Error handling and logging
- **Implementation Notes:**
  - Created `src/automation_scheduler.py` - Core scheduler with polling-based state detection
  - Created `deploy/systemd/smarthome-automation-scheduler.service` - Production systemd unit
  - Created `docs/automation-scheduler.md` - Complete documentation
  - 39 new unit tests in `tests/unit/test_automation_scheduler.py`
  - Devlog: `devlog/automation-scheduler/2025-12-29-wp-10-3-automation-scheduler.md`

---

### Parallel Group 2: Device Enhancements

#### WP-10.4: Vacuum Cleaning Progress Tracking
- **Status:** ⚪ Not Started
- **Priority:** P3 (nice-to-have enhancement)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Deferred from WP-8.1 (Presence Detection)
- **Blocked by:** Vacuum hardware integration validation needed
- **Tasks:**
  - [ ] Design cleaning progress tracking (rooms, time, battery)
  - [ ] Integrate with vacuum entity status
  - [ ] Add progress reporting to presence callbacks
  - [ ] Test with real vacuum hardware
  - [ ] Write tests for progress tracking
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Track which rooms vacuum has cleaned
  - [ ] Track cleaning time and battery level
  - [ ] Progress visible in presence callback logs
  - [ ] Tested with actual Dreame L10s vacuum

#### WP-10.5: Slack Alerts for Presence/Automation
- **Status:** 🟢 Complete (2025-12-29)
- **Completed By:** Agent-Nadia
- **Priority:** P3 (operational visibility)
- **Effort:** S
- **Source:** Deferred from WP-8.1
- **Tasks:**
  - [x] Configure presence state change alerts
  - [x] Configure automation execution alerts
  - [x] Test alert delivery to #smarthome-health (8 new tests)
  - [x] Document presence/automation alerting
- **Acceptance Criteria:**
  - [x] Presence changes (home/away) trigger alerts
  - [x] Critical automation executions logged to Slack
  - [x] Alerts tested and verified
- **Implementation Notes:**
  - Added alerting to `PresenceManager.set_presence_state()` via new `_send_presence_alert()` method
  - Added alerting to `AutomationScheduler._execute_automation()` via new `_send_automation_alert()` method
  - Both use existing `send_health_alert()` infrastructure to #smarthome-health
  - 5 new presence alert tests + 3 new automation alert tests = 8 total

#### WP-10.6: LLM-Generated Dynamic Scenes
- **Status:** ⚪ Not Started
- **Priority:** P2 (creative enhancement)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** Backlog WP-2.8 placeholder
- **Blocked by:** WP-2.5 (Hue Hardware Validation - USER)
- **Requirement:** Extension of REQ-009
- **Description:** Extend hue_specialist.py to generate custom color/brightness from descriptions like "romantic dinner" or "calm meditation"
- **Tasks:**
  - [ ] Research color theory for mood-to-color mappings
  - [ ] Design LLM prompt for scene generation
  - [ ] Implement RGB/color-temp generation from descriptions
  - [ ] Support multi-light scenes (different settings per light)
  - [ ] Write unit tests for scene generation
  - [ ] Write integration tests for voice commands
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] User can request arbitrary scene descriptions
  - [ ] LLM generates appropriate colors/brightness
  - [ ] Works with multi-room setups
  - [ ] Graceful fallback to presets if generation fails

#### WP-10.7: Smart Thermostat Control
- **Status:** ⚪ Not Started
- **Priority:** P3 (deferred hardware)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** Backlog, REQ-011
- **Blocked by:** User hardware replacement (Google Nest → open-source)
- **Requirement:** REQ-011
- **Tasks:**
  - [ ] User: Select and install open-source compatible thermostat
  - [ ] User: Add thermostat to Home Assistant
  - [ ] Write unit tests for ThermostatController (TDD)
  - [ ] Implement tools/thermostat.py
  - [ ] Create tool definitions (set_temperature, get_temperature, set_hvac_mode, get_thermostat_status)
  - [ ] Add schedule management support
  - [ ] Implement presence detection integration
  - [ ] Write integration tests for voice commands
  - [ ] Add THERMOSTAT_TOOLS to agent.py
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-011):**
  - [ ] Open-source compatible thermostat selected and installed
  - [ ] Temperature setting via voice and UI
  - [ ] Schedule creation and management
  - [ ] Current temperature monitoring
  - [ ] Integration with presence detection (energy saving when away)

---

### Parallel Group 3: Cost Optimization & Privacy

#### WP-10.8: Local LLM Migration (SmartHome Only)
- **Status:** ⚪ Not Started
- **Priority:** P2 (cost optimization - $730/yr → $36/yr)
- **Effort:** L
- **Owner:** Unassigned
- **Source:** Backlog, REQ-004
- **Requirement:** REQ-004
- **Description:** Replace SmartHome OpenAI API requests with local LLM (Ollama/LM Studio)
- **Scope:** SmartHome project only - replaces ONLY the OpenAI API calls in SmartHome's `src/llm_client.py`. Does NOT touch agent-automation, orchestrator, or any other project.
- **Benefits:**
  - 95% cost reduction ($730/yr → $36/yr electricity)
  - Privacy improvement (no data to third parties)
  - No rate limits
  - No internet dependency for LLM calls
- **Tasks:**
  - [ ] Research local LLM options (Qwen, Llama, Mistral)
  - [ ] Benchmark quality vs gpt-4o-mini
  - [ ] Set up Ollama or LM Studio on colby
  - [ ] Test LLM abstraction layer with local provider
  - [ ] Performance optimization (GPU acceleration if available)
  - [ ] Implement fallback to OpenAI if local fails
  - [ ] Write tests for local LLM integration
  - [ ] Document setup process
  - [ ] Migration guide for existing deployments
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Local LLM selected and benchmarked
  - [ ] Quality comparable to gpt-4o-mini for smart home tasks
  - [ ] System works with local LLM via existing abstraction layer
  - [ ] Fallback to OpenAI works if local unavailable
  - [ ] Cost reduced to ~$36/yr
  - [ ] Documentation complete

---

### Parallel Group 4: Advanced Features (Post-Launch)

#### WP-10.10: Secure Remote Access
- **Status:** ⚪ Not Started
- **Priority:** P2 (security + convenience)
- **Effort:** L
- **Owner:** Unassigned
- **Requirement:** REQ-007
- **Phase:** 7 (post-launch)
- **Tasks:**
  - [ ] Research VPN vs Tailscale vs Cloudflare Tunnel options
  - [ ] Implement chosen secure tunnel solution
  - [ ] Configure authentication for remote access
  - [ ] Set up failed login monitoring
  - [ ] Implement session timeout
  - [ ] Security audit of remote access surface
  - [ ] Write tests for remote access flows
  - [ ] Document setup for users
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-007):**
  - [ ] HTTPS enabled for web UI
  - [ ] Authentication required for access
  - [ ] VPN or secure tunnel for remote access (not direct port forwarding)
  - [ ] Failed login attempt monitoring
  - [ ] Session timeout after inactivity
  - [ ] Security audit completed and documented

#### WP-10.11: Multi-User Support
- **Status:** ⚪ Not Started
- **Priority:** P3 (nice-to-have)
- **Effort:** L
- **Owner:** Unassigned
- **Requirement:** REQ-008
- **Phase:** 7 (post-launch)
- **Blocked by:** WP-10.10 (Secure Remote Access)
- **Tasks:**
  - [ ] Design user profile system
  - [ ] Implement guest mode with basic controls
  - [ ] User permission levels (owner, resident, guest)
  - [ ] Per-user preferences and history
  - [ ] Simple guest access via password-protected URL
  - [ ] Guest session expiration
  - [ ] Write tests for multi-user scenarios
  - [ ] Document user management
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-008):**
  - [ ] Guest mode with basic controls (lights, temperature)
  - [ ] User profiles (owner, resident, guest)
  - [ ] Per-user preferences and history
  - [ ] Simple guest access via password-protected URL
  - [ ] Guest sessions expire after configurable time

#### WP-10.12: Pattern Learning & Routine Discovery
- **Status:** ⚪ Not Started
- **Priority:** P3 (advanced intelligence)
- **Effort:** XL (needs breakdown into sub-work-packages)
- **Owner:** Unassigned
- **Requirement:** REQ-020
- **Phase:** 7 (post-launch - needs validation)
- **Note:** Break into smaller work packages before starting
- **Tasks (high-level):**
  - [ ] Design pattern learning architecture
  - [ ] Implement device usage monitoring
  - [ ] Build pattern detection algorithms
  - [ ] Create suggestion generation system
  - [ ] Implement approval/rejection learning
  - [ ] Add implicit rejection detection
  - [ ] Write comprehensive tests
  - [ ] User acceptance validation
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-020):**
  - [ ] Monitors device usage patterns over time
  - [ ] Identifies repeated manual actions (lights on at same time daily)
  - [ ] Suggests automation only when confidence is high
  - [ ] User can approve/reject suggestions easily
  - [ ] Learns from rejections (don't suggest similar things)
  - [ ] Detects implicit rejection signals (immediate manual override)

#### WP-10.13: Music Discovery Agent
- **Status:** ⚪ Not Started
- **Priority:** P3 (enhancement)
- **Effort:** L
- **Owner:** Unassigned
- **Requirement:** REQ-026
- **Phase:** 7 (post-launch)
- **Tasks:**
  - [ ] Design LLM-powered music research agent
  - [ ] Implement taste profile questioning system
  - [ ] Build playlist/recommendation generation
  - [ ] Add results push to mobile UI
  - [ ] Implement feedback learning
  - [ ] Write tests for discovery agent
  - [ ] Document music discovery features
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-026):**
  - [ ] LLM-powered research agent for music discovery
  - [ ] Prompts user with questions to refine taste
  - [ ] Generates playlists or recommendations
  - [ ] Results pushed to mobile UI (web notifications or dedicated section)
  - [ ] Learns from user feedback on recommendations

#### WP-10.14: Proactive Todo Assistance
- **Status:** ⚪ Not Started
- **Priority:** P3 (enhancement)
- **Effort:** L
- **Owner:** Unassigned
- **Requirement:** REQ-031
- **Phase:** 7 (post-launch)
- **Blocked by:** WP-10.12 (Pattern Learning)
- **Tasks:**
  - [ ] Design stale todo detection system
  - [ ] Implement solution suggestion generation
  - [ ] Build research and options presentation
  - [ ] Add user approval workflow
  - [ ] Implement intervention timing learning
  - [ ] Write tests for proactive assistance
  - [ ] Document proactive features
  - [ ] Create devlog entry
- **Acceptance Criteria (from REQ-031):**
  - [ ] Tracks todo age and priority
  - [ ] Suggests solutions for stale todos ("I notice you haven't sent Dale a birthday card...")
  - [ ] Can research and present options (card vendors, prices)
  - [ ] Requires user approval before taking action
  - [ ] Learns when to intervene vs when to stay quiet

---

### Parallel Group 5: Documentation & Developer Experience

#### WP-10.17: Voice Pipeline Diagnostic Enhancements
- **Status:** ⚪ Not Started
- **Priority:** P2 (developer/user experience)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Enhancement to completed WP-9.2
- **Note:** WP-9.2 (Voice Pipeline Diagnostics) completed 2025-12-25
- **Potential Enhancements:**
  - [ ] Add HA assist pipeline auto-configuration wizard
  - [ ] Add STT/TTS quality testing tools
  - [ ] Add voice puck firmware update checker
  - [ ] Add comprehensive troubleshooting guide integration
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] One-click HA assist pipeline configuration
  - [ ] STT/TTS quality tests run automatically
  - [ ] Voice puck firmware version checked
  - [ ] Troubleshooting guide integrated into diagnostics UI

#### WP-10.18: API Documentation
- **Status:** ⚪ Not Started
- **Priority:** P2 (developer experience)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** No API docs currently exist
- **Tasks:**
  - [ ] Document all REST API endpoints
  - [ ] Add OpenAPI/Swagger spec
  - [ ] Create API usage examples
  - [ ] Document authentication flows
  - [ ] Add rate limiting documentation
  - [ ] Generate interactive API docs (Swagger UI)
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] All API endpoints documented
  - [ ] OpenAPI/Swagger spec complete
  - [ ] API examples provided
  - [ ] Interactive docs accessible at /api/docs

#### WP-10.19: Developer Guide
- **Status:** ⚪ Not Started
- **Priority:** P2 (contributor onboarding)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** CONTRIBUTING.md exists but could be enhanced
- **Tasks:**
  - [ ] Create development setup guide
  - [ ] Document codebase architecture (extend ARCHITECTURE.md)
  - [ ] Add code style guide
  - [ ] Document testing strategy and how to add tests
  - [ ] Create guide for adding new integrations
  - [ ] Document LLM abstraction layer usage
  - [ ] Add troubleshooting guide for common dev issues
- **Acceptance Criteria:**
  - [ ] Developer can set up environment in <30 min
  - [ ] Architecture documented with diagrams
  - [ ] Code style guide clear and complete
  - [ ] Testing guide includes examples
  - [ ] Integration guide with step-by-step instructions

---

### Parallel Group 6: Operational Maturity

#### WP-10.20: Prometheus Metrics Exporter
- **Status:** ⚪ Not Started
- **Priority:** P3 (operational maturity)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** No metrics exporter currently
- **Description:** Add Prometheus metrics for monitoring
- **Tasks:**
  - [ ] Add prometheus_client library
  - [ ] Implement /metrics endpoint
  - [ ] Export key metrics (API calls, costs, response times, errors)
  - [ ] Add Grafana dashboard template
  - [ ] Document metrics setup
  - [ ] Write tests for metrics exporter
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] /metrics endpoint exposes Prometheus-compatible metrics
  - [ ] Key metrics tracked: API calls, costs, latency, errors
  - [ ] Grafana dashboard template provided
  - [ ] Documentation for setup and configuration

#### WP-10.21: Health Check Improvements
- **Status:** ✅ Complete (2025-12-29)
- **Priority:** P2 (reliability)
- **Effort:** S
- **Owner:** Nadia
- **Source:** Existing /api/health could be enhanced
- **Tasks:**
  - [x] Add dependency health checks (database, HA, LLM provider)
  - [x] Implement readiness vs liveness endpoints
  - [x] Add health check history retention policies
  - [x] Improve healing action logging
  - [x] Add manual healing triggers via API
  - [x] Write tests for enhanced health checks
  - [x] Create devlog entry
- **Acceptance Criteria:**
  - [x] /healthz (liveness) and /readyz (readiness) endpoints
  - [x] All critical dependencies checked
  - [x] Health history retained for troubleshooting
  - [x] Manual healing triggers via API
  - [x] Improved logging and alerting

---

### Parallel Group 7: Security & Performance

#### WP-10.22: Security Audit & Hardening
- **Status:** ⚪ Not Started
- **Priority:** P2 (security posture)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** Ongoing security improvement
- **Tasks:**
  - [ ] Run bandit security scan and fix issues
  - [ ] Run pip-audit for dependency vulnerabilities
  - [ ] Implement input sanitization review
  - [ ] Add CSP headers to web UI
  - [ ] Review and rotate any hardcoded secrets
  - [ ] Implement API key rotation support
  - [ ] Add security.txt for vulnerability disclosure
  - [ ] Create security response plan
  - [ ] Write tests for security features
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Bandit scan passes with no critical issues
  - [ ] All dependencies up to date and audited
  - [ ] Input sanitization complete
  - [ ] CSP headers configured
  - [ ] API key rotation mechanism implemented
  - [ ] security.txt present at /.well-known/security.txt

#### WP-10.23: Rate Limiting Enhancements
- **Status:** ⚪ Not Started
- **Priority:** P2 (abuse prevention)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Basic rate limiting exists, could be improved
- **Tasks:**
  - [ ] Implement per-user rate limiting (vs per-IP)
  - [ ] Add configurable rate limit thresholds
  - [ ] Implement rate limit headers (X-RateLimit-*)
  - [ ] Add rate limit bypass for authenticated admin
  - [ ] Document rate limiting behavior
  - [ ] Write tests for rate limiting
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Per-user rate limiting working
  - [ ] Rate limits configurable via environment variables
  - [ ] Standard rate limit headers returned
  - [ ] Admin bypass mechanism implemented
  - [ ] Documentation complete

#### WP-10.24: Database Query Optimization
- **Status:** ⚪ Not Started
- **Priority:** P3 (performance)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** No query optimization done yet
- **Tasks:**
  - [ ] Add database indexes for common queries
  - [ ] Implement connection pooling
  - [ ] Add query performance monitoring
  - [ ] Optimize N+1 query patterns
  - [ ] Add database backup automation
  - [ ] Write tests for optimized queries
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Common queries have indexes
  - [ ] Connection pooling implemented
  - [ ] Slow query logging enabled
  - [ ] N+1 queries eliminated
  - [ ] Automated backups configured

#### WP-10.25: Frontend Performance Optimization
- **Status:** 🟢 Complete
- **Priority:** P3 (user experience)
- **Effort:** S
- **Owner:** Agent-Ginny
- **Completed:** 2025-12-29
- **Source:** Web UI could be faster
- **Tasks:**
  - [x] Implement code splitting for JS (defer loading)
  - [x] Add CSS minification (34% reduction achieved)
  - [x] Optimize image assets (SVG icons optimized)
  - [x] Add lazy loading for non-critical resources (defer attribute)
  - [x] Measure and optimize Time to Interactive (TTI)
  - [x] Write tests for performance metrics (23 tests)
  - [x] Create devlog entry
- **Acceptance Criteria:**
  - [x] JS bundle size reduced by 30%+ (33.9% achieved)
  - [x] CSS minified in production (30.2% reduction)
  - [x] Images optimized and compressed (SVG icons)
  - [x] TTI improved via defer loading
  - [x] Performance metrics tracked (build script stats)
- **Devlog:** `devlog/frontend-performance/2025-12-29-performance-optimization.md`

---

### Parallel Group 8: Testing & Quality

#### WP-10.26: Increase Test Coverage
- **Status:** ⚪ Not Started
- **Priority:** P2 (quality)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** Currently at 81% coverage (target 85%+)
- **Tasks:**
  - [ ] Identify uncovered code paths
  - [ ] Add tests for edge cases
  - [ ] Add tests for error handling paths
  - [ ] Reach 85%+ overall coverage
  - [ ] Ensure 90%+ coverage for critical modules
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Overall coverage ≥85%
  - [ ] Critical modules (agent, ha_client, database) ≥90%
  - [ ] All edge cases covered
  - [ ] All error paths tested

#### WP-10.27: E2E Testing Suite
- **Status:** ⚪ Not Started
- **Priority:** P3 (quality)
- **Effort:** L
- **Owner:** Unassigned
- **Source:** No E2E tests currently
- **Tasks:**
  - [ ] Design E2E test scenarios
  - [ ] Set up E2E test environment
  - [ ] Implement voice command E2E tests
  - [ ] Implement web UI E2E tests
  - [ ] Implement automation execution E2E tests
  - [ ] Add E2E tests to CI/CD pipeline
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] E2E tests cover critical user journeys
  - [ ] Tests run in CI/CD
  - [ ] Test environment automated
  - [ ] E2E tests pass reliably

---

### Parallel Group 9: Integration & Deployment

#### WP-10.28: MQTT Support
- **Status:** ⚪ Not Started
- **Priority:** P3 (flexibility)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** No MQTT integration currently
- **Description:** Add MQTT broker integration for custom devices
- **Tasks:**
  - [ ] Add MQTT client library
  - [ ] Design MQTT topic structure
  - [ ] Implement device discovery via MQTT
  - [ ] Add MQTT publish/subscribe for device control
  - [ ] Write tests for MQTT integration
  - [ ] Document MQTT setup
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] MQTT broker connection working
  - [ ] Device discovery via MQTT
  - [ ] Device control via MQTT topics
  - [ ] Documentation complete

#### WP-10.33: Home Assistant Add-on
- **Status:** ⚪ Not Started
- **Priority:** P2 (distribution)
- **Effort:** M
- **Owner:** Unassigned
- **Source:** Currently standalone install
- **Description:** Package as HA add-on for easy installation
- **Tasks:**
  - [ ] Create Dockerfile for HA add-on
  - [ ] Design add-on configuration UI
  - [ ] Implement HA add-on manifest
  - [ ] Test add-on installation flow
  - [ ] Submit to HA add-on store
  - [ ] Document add-on setup
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Add-on installable from HA add-on store
  - [ ] Configuration UI works in HA
  - [ ] Installation process <5 min
  - [ ] Documentation complete

#### WP-10.34: Docker Compose Improvements
- **Status:** ⚪ Not Started
- **Priority:** P2 (deployment)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Basic docker-compose exists
- **Tasks:**
  - [ ] Add environment variable validation
  - [ ] Add volume management for persistence
  - [ ] Improve logging configuration
  - [ ] Add health checks to compose
  - [ ] Document compose deployment
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] Environment variables validated on startup
  - [ ] Persistent volumes configured
  - [ ] Logging to stdout/stderr
  - [ ] Health checks working in compose
  - [ ] Documentation complete

---

### Parallel Group 10: Data & Privacy

#### WP-10.35: Data Export Feature
- **Status:** ⚪ Not Started
- **Priority:** P2 (user control)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Partial from REQ-006
- **Tasks:**
  - [ ] Implement full data export API
  - [ ] Add export format options (JSON, CSV)
  - [ ] Include all user data (devices, commands, settings, history)
  - [ ] Add data import for migration
  - [ ] Document data export/import
  - [ ] Write tests for export/import
  - [ ] Create devlog entry
- **Acceptance Criteria:**
  - [ ] /api/export endpoint returns all user data
  - [ ] JSON and CSV formats supported
  - [ ] Import functionality works for migration
  - [ ] Documentation complete

#### WP-10.36: Privacy Policy & Terms
- **Status:** ⚪ Not Started
- **Priority:** P2 (legal/community)
- **Effort:** S
- **Owner:** Unassigned
- **Source:** Required for community release
- **Tasks:**
  - [ ] Draft privacy policy
  - [ ] Draft terms of service
  - [ ] Add data retention policies
  - [ ] Document third-party data sharing (OpenAI, Spotify, etc.)
  - [ ] Add consent management
  - [ ] Legal review (if needed)
- **Acceptance Criteria:**
  - [ ] Privacy policy complete
  - [ ] Terms of service complete
  - [ ] Data retention policy documented
  - [ ] Third-party data sharing disclosed
  - [ ] Consent management implemented

---

### Parallel Group 11: Future Research

#### WP-10.9: Meshtastic Integration (Research Phase)
- **Status:** ⚪ Not Started
- **Priority:** P3 (research phase)
- **Effort:** XL (needs breakdown after research)
- **Owner:** Unassigned
- **Source:** Backlog (added 2025-12-29)
- **Description:** LoRa mesh network for smart home automation
- **Research Phase Tasks:**
  - [ ] Research Meshtastic hardware options
  - [ ] Research HA integration via MQTT
  - [ ] Create detailed implementation plan
  - [ ] Estimate hardware costs
  - [ ] Prioritize use cases (dog tracking, presence, coop, garden)
  - [ ] Create devlog entry for research findings
- **Use Cases:**
  1. **Dog tracking (Sophie)** - GPS collar tracker, no subscription fees
  2. **User presence detection** - Keychain tracker for automations
  3. **Chicken coop automation** - Door, temp, lights, predator detection
  4. **Garden sensors** - Soil moisture, temp, irrigation
- **Technical Notes:**
  - LoRa long-range, low-power mesh
  - No subscription fees (vs cellular trackers)
  - Native HA integration via MQTT
  - Solar-powered outdoor nodes possible
  - Range testing needed across property
  - Weatherproofing for outdoor nodes
  - Privacy/security of mesh network
- **Decision Point:** After research, break into smaller work packages or defer

---

## DEFERRED INDEFINITELY (High Risk / Low ROI)

These items are explicitly deferred and will not be added to active roadmap unless strong community demand emerges:

### REQ-030: Automated Order Management
- **Status:** ❌ Deferred Indefinitely
- **Reason:** High legal/financial risk, unclear user value
- **Reconsider:** Only if community demand emerges Month 12+

### REQ-035: Secure E-Commerce Integration
- **Status:** ❌ Deferred Indefinitely
- **Reason:** Dependency for REQ-030 (also deferred)
- **Reconsider:** Only with REQ-030

### Native Mobile App (React Native)
- **Status:** ❌ Deferred Indefinitely
- **Reason:** PWA works well, native app is low ROI
- **Reconsider:** Only if community strongly demands it

### Zigbee/Z-Wave Direct Support
- **Status:** ❌ Deferred Indefinitely
- **Reason:** Home Assistant handles this well already
- **Reconsider:** Unlikely - HA integration is the better path

---

## Architecture Decisions

### LLM Provider: OpenAI (Not Anthropic)

**Decision Date:** 2025-12-20

The Smart Home system uses **OpenAI API** (gpt-4o-mini) for all LLM calls, NOT Anthropic.

**Key Points:**
- All LLM calls go through the unified abstraction layer in `src/llm_client.py`
- Current default: OpenAI API with `gpt-4o-mini` model
- The abstraction layer supports OpenAI, Anthropic, and local LLMs (Ollama, LM Studio)
- Future plan: Replace with local LLM for cost reduction and privacy (WP-10.8)
- Another agent is working on improving the LLM abstraction layer

**Configuration:**
- Environment variables: `OPENAI_API_KEY` and `OPENAI_MODEL` (not `ANTHROPIC_API_KEY`)
- To switch providers: Set `LLM_PROVIDER` env var to "openai", "anthropic", or "local"
- Provider-specific config in `src/config.py` imports OpenAI settings by default

**Migration Notes:**
- Any legacy Anthropic API calls in the codebase should be migrated to use `src/llm_client.py`
- The main agent loop in `agent.py` may still reference Anthropic patterns in comments - these are historical
- All new features must use the LLMClient abstraction, not direct API calls

**Why This Matters:**
- Prevents agents from accidentally using the wrong API
- Centralizes all LLM calls for easier provider switching
- Prepares for future local LLM migration (cost reduction from $730/year to $36/year)

---

**Last Updated:** 2025-12-29 (Henry - Roadmap gardening)

**Summary:**
- Moved 30 completed work packages to archive (`plans/archive/`)
- Added 27 new work packages from backlog, requirements, and deferrals
- Roadmap now shows only active work and future backlog
- All completed work is archived for historical reference
- Clarified WP-10.8 scope per user request: SmartHome OpenAI API only

**Active Work Packages:** 1 (WP-2.5 - USER)
**Bugs:** 1 (BUG-001 - awaiting user diagnosis)
**Backlog Work Packages:** 27 (WP-10.1 through WP-10.36, excluding 4 deferred indefinitely)
**Archived Completed Work:** 30 work packages (see `plans/archive/`)

**Next Actions:**
1. User completes WP-2.5 (Hue hardware validation)
2. User investigates BUG-001 (voice puck issue)
3. Agents can claim any P2 backlog work packages

For completed work history, see archive files in `plans/archive/phase*/`.
