# Roadmap Gardening Analysis
**Date:** 2025-12-29
**Gardener:** Agent-Henry (Project Manager)
**Session:** Intensive roadmap gardening per user request

---

## Executive Summary

This document captures all identified work items that should be added to the roadmap. The goal is to extract EVERY possible ticket from backlog, requirements, devlogs, and deferrals.

---

## 1. COMPLETED WORK PACKAGES TO ARCHIVE

The following 30 completed work packages will be moved to archive:

### Phase 2: Device Integrations + Security
- WP-2.1: Application Security Baseline ✅ Complete (2025-12-18)
- WP-2.2: HTTPS/TLS Configuration ✅ Complete (2025-12-18)
- WP-2.3: Vacuum Control ✅ Complete (2025-12-18)
- WP-2.4: Smart Blinds Control ✅ Complete (2025-12-18)
- WP-2.6: Remaining Test Suites ✅ Complete (2025-12-18)
- WP-2.7: Spotify Integration ✅ Complete (2025-12-19)

### Phase 3: Voice & Critical Foundation
- WP-3.1a: Voice Control Software Implementation ✅ Complete (2025-12-18)
- WP-3.1b: Voice Puck Hardware Validation ✅ Complete (2025-12-20)
- WP-3.2: Request Caching & Optimization ✅ Complete (2025-12-18)
- WP-3.3: Mobile-Optimized Web Interface ✅ Complete (2025-12-18)
- WP-3.4: Time & Date Queries ✅ Complete (2025-12-18)

### Phase 4A: Essential Intelligence
- WP-4.1: Todo List & Reminders ✅ Complete (2025-12-18)
- WP-4.2: Simple Automation Creation ✅ Complete (2025-12-18)
- WP-4.3: Timers & Alarms ✅ Complete (2025-12-18)
- WP-4.4: Shopping List Management ✅ Complete (2025-12-18)

### Phase 5: Advanced Intelligence
- WP-5.1: Self-Monitoring & Self-Healing ✅ Complete (2025-12-18)
- WP-5.2: Device Organization Assistant ✅ Complete (2025-12-18)
- WP-5.3: Location-Aware Commands ✅ Complete (2025-12-18)
- WP-5.4: Music Education & Context ✅ Complete (2025-12-18)
- WP-5.5: Continuous Improvement & Self-Optimization ✅ Complete (2025-12-18)

### Phase 6: Community Preparation
- WP-6.1: Log Viewer UI ✅ Complete (2025-12-18)
- WP-6.2: CI/CD Pipeline ✅ Complete (2025-12-18)
- WP-6.3: Public Repository Preparation ✅ Complete (2025-12-18)
- WP-6.4: Setup & Installation Documentation ✅ Complete (2025-12-19)

### Phase 7: Additional Device Integrations
- WP-7.1: Smart Plug Control ✅ Complete (2025-12-19)

### Phase 8: Presence Detection
- WP-8.1: Presence-Based Automation ✅ Complete (2025-12-19)
- WP-8.2: Device Onboarding (REMOVED 2025-12-20)

### Phase 8+ Post-Launch
- WP-9.1: Conversational Automation Setup ✅ Complete (2025-12-25)
- WP-9.2: Ring Camera Integration ✅ Complete (2025-12-27)

### Maintenance
- WP-M1: Fix Failing Tests ✅ Complete (2025-12-19)

---

## 2. DEFERRED ITEMS FROM COMPLETED WORK

These deferrals from completed work packages should become new tickets:

### From Phase 2 Security
**WP-10.1: Slack Alerting Configuration (Phase 2 Deferrals)**
- Priority: P2 (operational visibility)
- Effort: S
- Source: Deferred from WP-2.1, WP-2.7
- Tasks:
  - [ ] Configure Slack alerts to #smarthome-health for auth failures (from WP-2.1)
  - [ ] Configure Slack alerts to #smarthome-health for Spotify API errors (from WP-2.7)
  - [ ] Test alert delivery and message formatting
  - [ ] Document alerting configuration

### From Phase 4 Productivity
**WP-10.2: Background Notification Worker**
- Priority: P2 (user-facing feature completion)
- Effort: M
- Source: Deferred from WP-4.1 (Todo/Reminders)
- Blocked by: None (independent feature)
- Tasks:
  - [ ] Design background worker process for reminder notifications
  - [ ] Implement notification delivery (voice puck + web push)
  - [ ] Add retry logic for failed notifications
  - [ ] Write tests for notification worker
  - [ ] Create systemd service for worker daemon

**WP-10.3: Automation Scheduler Background Process**
- Priority: P2 (automation feature completion)
- Effort: M
- Source: Deferred from WP-4.2 (Automation Creation)
- Blocked by: None (infrastructure ready in AutomationManager)
- Tasks:
  - [ ] Design scheduler daemon for automation execution
  - [ ] Implement time-based trigger evaluation
  - [ ] Implement state-based trigger evaluation
  - [ ] Add action execution (agent commands + HA services)
  - [ ] Write tests for scheduler
  - [ ] Create systemd service for scheduler daemon

### From Phase 8 Presence
**WP-10.4: Vacuum Cleaning Progress Tracking**
- Priority: P3 (nice-to-have enhancement)
- Effort: S
- Source: Deferred from WP-8.1 (Presence Detection)
- Blocked by: Needs vacuum hardware integration validation
- Tasks:
  - [ ] Design cleaning progress tracking (rooms, time, battery)
  - [ ] Integrate with vacuum entity status
  - [ ] Add progress reporting to presence callbacks
  - [ ] Test with real vacuum hardware

**WP-10.5: Slack Alerts for Presence/Automation**
- Priority: P3 (operational visibility)
- Effort: S
- Source: Deferred from WP-8.1
- Tasks:
  - [ ] Configure presence state change alerts
  - [ ] Configure automation execution alerts
  - [ ] Test alert delivery

---

## 3. BACKLOG ITEMS TO PROMOTE

### From backlog.md

**WP-10.6: LLM-Generated Dynamic Scenes**
- Priority: P2 (creative enhancement)
- Effort: M
- Source: backlog.md (WP-2.8 placeholder)
- Blocked by: WP-2.5 (Hue Hardware Validation - USER)
- Requirement: Extension of REQ-009
- Description: Extend hue_specialist.py to generate custom color/brightness from descriptions
- Tasks:
  - [ ] Research color theory for mood-to-color mappings
  - [ ] Design LLM prompt for scene generation
  - [ ] Implement RGB/color-temp generation from descriptions
  - [ ] Support multi-light scenes (different settings per light)
  - [ ] Write unit tests for scene generation
  - [ ] Write integration tests for voice commands
  - [ ] Create devlog entry

**WP-10.7: Smart Thermostat Control**
- Priority: P3 (deferred hardware)
- Effort: M
- Source: backlog.md, REQ-011
- Blocked by: User hardware replacement (Google Nest → open-source)
- Tasks:
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

**WP-10.8: Local LLM Migration**
- Priority: P2 (cost optimization - $730/yr → $36/yr)
- Effort: L
- Source: backlog.md, REQ-004
- Requirement: REQ-004
- Description: Replace OpenAI API with local LLM (Ollama/LM Studio)
- Benefits:
  - 95% cost reduction ($730/yr → $36/yr electricity)
  - Privacy improvement
  - No rate limits
  - No internet dependency for LLM calls
- Tasks:
  - [ ] Research local LLM options (Qwen, Llama, Mistral)
  - [ ] Benchmark quality vs gpt-4o-mini
  - [ ] Set up Ollama or LM Studio on colby
  - [ ] Test LLM abstraction layer with local provider
  - [ ] Performance optimization (GPU acceleration if available)
  - [ ] Implement fallback to OpenAI if local fails
  - [ ] Write tests for local LLM integration
  - [ ] Document setup process
  - [ ] Migration guide for existing deployments

**WP-10.9: Meshtastic Integration**
- Priority: P3 (research phase)
- Effort: XL (break down into phases)
- Source: backlog.md (added 2025-12-29)
- Description: LoRa mesh network for smart home automation
- Research Phase Tasks:
  - [ ] Research Meshtastic hardware options
  - [ ] Research HA integration via MQTT
  - [ ] Create detailed implementation plan
  - [ ] Estimate hardware costs
  - [ ] Prioritize use cases (dog tracking, presence, coop, garden)
- Use Cases:
  1. Dog tracking (Sophie) - GPS collar tracker
  2. User presence detection - keychain tracker
  3. Chicken coop automation - door, temp, lights, predator detection
  4. Garden sensors - soil moisture, temp, irrigation
- Technical Notes:
  - LoRa long-range, low-power mesh
  - No subscription fees (vs cellular)
  - Native HA integration via MQTT
  - Solar-powered outdoor nodes
  - Range testing needed across property

---

## 4. REQUIREMENTS GAPS TO FILL

These requirements from REQUIREMENTS.md don't have work packages yet:

**WP-10.10: Secure Remote Access**
- Priority: P2 (security + convenience)
- Effort: L
- Requirement: REQ-007
- Phase: 7 (post-launch)
- Tasks:
  - [ ] Research VPN vs Tailscale vs Cloudflare Tunnel options
  - [ ] Implement chosen secure tunnel solution
  - [ ] Configure authentication for remote access
  - [ ] Set up failed login monitoring
  - [ ] Implement session timeout
  - [ ] Security audit of remote access surface
  - [ ] Write tests for remote access flows
  - [ ] Document setup for users

**WP-10.11: Multi-User Support**
- Priority: P3 (nice-to-have)
- Effort: L
- Requirement: REQ-008
- Phase: 7 (post-launch)
- Blocked by: WP-10.10 (Secure Remote Access)
- Tasks:
  - [ ] Design user profile system
  - [ ] Implement guest mode with basic controls
  - [ ] User permission levels (owner, resident, guest)
  - [ ] Per-user preferences and history
  - [ ] Simple guest access via password-protected URL
  - [ ] Guest session expiration
  - [ ] Write tests for multi-user scenarios
  - [ ] Document user management

**WP-10.12: Pattern Learning & Routine Discovery**
- Priority: P3 (advanced intelligence)
- Effort: XL (needs breakdown)
- Requirement: REQ-020
- Phase: 7 (post-launch - needs validation)
- Complexity: Break into sub-work-packages
- Tasks (high-level):
  - [ ] Design pattern learning architecture
  - [ ] Implement device usage monitoring
  - [ ] Build pattern detection algorithms
  - [ ] Create suggestion generation system
  - [ ] Implement approval/rejection learning
  - [ ] Add implicit rejection detection
  - [ ] Write comprehensive tests
  - [ ] User acceptance validation

**WP-10.13: Music Discovery Agent**
- Priority: P3 (enhancement)
- Effort: L
- Requirement: REQ-026
- Phase: 7 (post-launch)
- Tasks:
  - [ ] Design LLM-powered music research agent
  - [ ] Implement taste profile questioning system
  - [ ] Build playlist/recommendation generation
  - [ ] Add results push to mobile UI
  - [ ] Implement feedback learning
  - [ ] Write tests for discovery agent
  - [ ] Document music discovery features

**WP-10.14: Proactive Todo Assistance**
- Priority: P3 (enhancement)
- Effort: L
- Requirement: REQ-031
- Phase: 7 (post-launch)
- Blocked by: WP-10.12 (Pattern Learning)
- Tasks:
  - [ ] Design stale todo detection system
  - [ ] Implement solution suggestion generation
  - [ ] Build research and options presentation
  - [ ] Add user approval workflow
  - [ ] Implement intervention timing learning
  - [ ] Write tests for proactive assistance
  - [ ] Document proactive features

**WP-10.15: Automated Order Management**
- Priority: P4 (defer indefinitely - high risk)
- Effort: XL
- Requirement: REQ-030
- Status: Deferred indefinitely (legal/financial risk)
- Notes: Only reconsider if community demand emerges Month 12+

**WP-10.16: Secure E-Commerce Integration**
- Priority: P4 (defer indefinitely)
- Effort: L
- Requirement: REQ-035
- Status: Deferred indefinitely (dependency for REQ-030)
- Notes: Only reconsider with REQ-030

---

## 5. BUG FIXES & INVESTIGATIONS

**BUG-001: Voice Puck Green Blink But No Response**
- Status: 🔴 Blocked (needs user HA log inspection)
- Priority: P0 (core voice feature broken)
- Current Work Package: Already documented in roadmap
- Action: Keep as-is, waiting for user diagnosis

**WP-10.17: Voice Pipeline Diagnostic Suite Enhancement**
- Priority: P2 (already complete, but potential enhancements)
- Source: WP-9.2 (Voice Pipeline Diagnostics) completed 2025-12-25
- Potential Enhancements:
  - [ ] Add HA assist pipeline auto-configuration wizard
  - [ ] Add STT/TTS quality testing tools
  - [ ] Add voice puck firmware update checker
  - [ ] Add comprehensive troubleshooting guide integration

---

## 6. USER HARDWARE VALIDATION TASKS

**WP-2.5: Philips Hue Hardware Validation (USER TASK)**
- Status: 🟡 In Progress
- Priority: P1 (blocking for lighting features)
- Current Status: Hardware installed, room config pending
- Remaining Tasks:
  - [ ] Configure room mappings in HA to match src/config.py
  - [ ] Test existing demo code with actual hardware
  - [ ] Verify vibe presets (cozy/energize/focus/sleep)
  - [ ] Test dynamic scenes (fire/ocean/aurora) and tune
  - [ ] Update room mappings in src/config.py if needed

---

## 7. DOCUMENTATION GAPS

**WP-10.18: API Documentation**
- Priority: P2 (developer experience)
- Effort: M
- Source: No API docs currently exist
- Tasks:
  - [ ] Document all REST API endpoints
  - [ ] Add OpenAPI/Swagger spec
  - [ ] Create API usage examples
  - [ ] Document authentication flows
  - [ ] Add rate limiting documentation

**WP-10.19: Developer Guide**
- Priority: P2 (contributor onboarding)
- Effort: M
- Source: CONTRIBUTING.md exists but could be enhanced
- Tasks:
  - [ ] Create development setup guide
  - [ ] Document codebase architecture (extend ARCHITECTURE.md)
  - [ ] Add code style guide
  - [ ] Document testing strategy and how to add tests
  - [ ] Create guide for adding new integrations
  - [ ] Document LLM abstraction layer usage

---

## 8. OPERATIONAL & MONITORING

**WP-10.20: Prometheus Metrics Exporter**
- Priority: P3 (operational maturity)
- Effort: M
- Source: No metrics exporter currently
- Description: Add Prometheus metrics for monitoring
- Tasks:
  - [ ] Add prometheus_client library
  - [ ] Implement /metrics endpoint
  - [ ] Export key metrics (API calls, costs, response times, errors)
  - [ ] Add Grafana dashboard template
  - [ ] Document metrics setup

**WP-10.21: Health Check Improvements**
- Priority: P2 (reliability)
- Effort: S
- Source: Existing /api/health could be enhanced
- Tasks:
  - [ ] Add dependency health checks (database, HA, LLM provider)
  - [ ] Implement readiness vs liveness endpoints
  - [ ] Add health check history retention policies
  - [ ] Improve healing action logging
  - [ ] Add manual healing triggers via API

---

## 9. SECURITY ENHANCEMENTS

**WP-10.22: Security Audit & Hardening**
- Priority: P2 (security posture)
- Effort: M
- Source: Ongoing security improvement
- Tasks:
  - [ ] Run bandit security scan and fix issues
  - [ ] Run pip-audit for dependency vulnerabilities
  - [ ] Implement input sanitization review
  - [ ] Add CSP headers to web UI
  - [ ] Review and rotate any hardcoded secrets
  - [ ] Implement API key rotation support
  - [ ] Add security.txt for vulnerability disclosure
  - [ ] Create security response plan

**WP-10.23: Rate Limiting Enhancements**
- Priority: P2 (abuse prevention)
- Effort: S
- Source: Basic rate limiting exists, could be improved
- Tasks:
  - [ ] Implement per-user rate limiting (vs per-IP)
  - [ ] Add configurable rate limit thresholds
  - [ ] Implement rate limit headers (X-RateLimit-*)
  - [ ] Add rate limit bypass for authenticated admin
  - [ ] Document rate limiting behavior

---

## 10. PERFORMANCE OPTIMIZATIONS

**WP-10.24: Database Query Optimization**
- Priority: P3 (performance)
- Effort: M
- Source: No query optimization done yet
- Tasks:
  - [ ] Add database indexes for common queries
  - [ ] Implement connection pooling
  - [ ] Add query performance monitoring
  - [ ] Optimize N+1 query patterns
  - [ ] Add database backup automation

**WP-10.25: Frontend Performance Optimization**
- Priority: P3 (user experience)
- Effort: S
- Source: Web UI could be faster
- Tasks:
  - [ ] Implement code splitting for JS
  - [ ] Add CSS minification
  - [ ] Optimize image assets
  - [ ] Add lazy loading for non-critical resources
  - [ ] Measure and optimize Time to Interactive (TTI)

---

## 11. TESTING IMPROVEMENTS

**WP-10.26: Increase Test Coverage**
- Priority: P2 (quality)
- Effort: M
- Source: Currently at 81% coverage (target 85%+)
- Blocked by: None
- Tasks:
  - [ ] Identify uncovered code paths
  - [ ] Add tests for edge cases
  - [ ] Add tests for error handling paths
  - [ ] Reach 85%+ overall coverage
  - [ ] Ensure 90%+ coverage for critical modules

**WP-10.27: E2E Testing Suite**
- Priority: P3 (quality)
- Effort: L
- Source: No E2E tests currently
- Tasks:
  - [ ] Design E2E test scenarios
  - [ ] Set up E2E test environment
  - [ ] Implement voice command E2E tests
  - [ ] Implement web UI E2E tests
  - [ ] Implement automation execution E2E tests
  - [ ] Add E2E tests to CI/CD pipeline

---

## 12. INTEGRATION ENHANCEMENTS

**WP-10.28: MQTT Support**
- Priority: P3 (flexibility)
- Effort: M
- Source: No MQTT integration currently
- Description: Add MQTT broker integration for custom devices
- Tasks:
  - [ ] Add MQTT client library
  - [ ] Design MQTT topic structure
  - [ ] Implement device discovery via MQTT
  - [ ] Add MQTT publish/subscribe for device control
  - [ ] Write tests for MQTT integration
  - [ ] Document MQTT setup

**WP-10.29: Zigbee/Z-Wave Direct Support**
- Priority: P4 (advanced, low value vs HA)
- Effort: L
- Source: Currently relies on HA for Zigbee/Z-Wave
- Notes: Probably not worth it - HA handles this well
- Status: Defer indefinitely

---

## 13. USER EXPERIENCE ENHANCEMENTS

**WP-10.30: Voice Feedback Customization**
- Priority: P3 (personalization)
- Effort: S
- Source: Currently minimal personality only
- Tasks:
  - [ ] Add configurable verbosity levels
  - [ ] Implement response template customization
  - [ ] Add user-defined wake words (if HA supports)
  - [ ] Allow custom TTS voice selection
  - [ ] Write tests for voice customization

**WP-10.31: Dashboard Widgets**
- Priority: P3 (user experience)
- Effort: M
- Source: Current web UI is basic
- Tasks:
  - [ ] Design widget system architecture
  - [ ] Implement device status widgets
  - [ ] Add automation status widget
  - [ ] Add cost tracking widget
  - [ ] Add system health widget
  - [ ] Make widgets draggable/customizable

**WP-10.32: Mobile App (React Native or PWA Enhancement)**
- Priority: P4 (nice-to-have)
- Effort: XL
- Source: Currently PWA only
- Notes: PWA works well, native app is low ROI
- Status: Defer indefinitely unless community demands it

---

## 14. COMMUNITY & ECOSYSTEM

**WP-10.33: Home Assistant Add-on**
- Priority: P2 (distribution)
- Effort: M
- Source: Currently standalone install
- Description: Package as HA add-on for easy installation
- Tasks:
  - [ ] Create Dockerfile for HA add-on
  - [ ] Design add-on configuration UI
  - [ ] Implement HA add-on manifest
  - [ ] Test add-on installation flow
  - [ ] Submit to HA add-on store
  - [ ] Document add-on setup

**WP-10.34: Docker Compose Improvements**
- Priority: P2 (deployment)
- Effort: S
- Source: Basic docker-compose exists
- Tasks:
  - [ ] Add environment variable validation
  - [ ] Add volume management for persistence
  - [ ] Improve logging configuration
  - [ ] Add health checks to compose
  - [ ] Document compose deployment

---

## 15. DATA & PRIVACY

**WP-10.35: Data Export Feature**
- Priority: P2 (user control)
- Effort: S
- Source: Partial from REQ-006
- Tasks:
  - [ ] Implement full data export API
  - [ ] Add export format options (JSON, CSV)
  - [ ] Include all user data (devices, commands, settings, history)
  - [ ] Add data import for migration
  - [ ] Document data export/import

**WP-10.36: Privacy Policy & Terms**
- Priority: P2 (legal/community)
- Effort: S
- Source: Required for community release
- Tasks:
  - [ ] Draft privacy policy
  - [ ] Draft terms of service
  - [ ] Add data retention policies
  - [ ] Document third-party data sharing (OpenAI, Spotify, etc.)
  - [ ] Add consent management

---

## SUMMARY

**Total New Work Packages Identified:** 27 (WP-10.1 through WP-10.36, excluding WP-10.15, WP-10.16, WP-10.29, WP-10.32 which are deferred indefinitely)

**By Priority:**
- **P0:** 0 (BUG-001 already tracked)
- **P1:** 1 (WP-2.5 already tracked)
- **P2:** 16 work packages (high value)
- **P3:** 10 work packages (medium value)
- **P4:** 0 added (4 deferred indefinitely)

**By Effort:**
- **S:** 10 work packages
- **M:** 12 work packages
- **L:** 5 work packages
- **XL:** 0 active (2 need breakdown: WP-10.9, WP-10.12)

**Completed Work Packages to Archive:** 30

---

## NEXT STEPS

1. ✅ Create this analysis document
2. ⏳ Create archive directory structure
3. ⏳ Move all 30 completed work packages to archive
4. ⏳ Add all 27 new work packages to roadmap
5. ⏳ Update roadmap to show only active work
6. ⏳ Post summary to NATS #coordination
