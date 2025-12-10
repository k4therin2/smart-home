# Smart Home Assistant - Parallel Execution Roadmap

**Last Updated:** 2025-12-09
**Purpose:** Multi-agent execution plan optimized for parallelization
**Based on:** REQUIREMENTS.md, priorities.md, BUSINESS_VALUE_ANALYSIS.md

---

## Executive Summary

This roadmap organizes the 37 requirements into **parallel work streams** that can be executed simultaneously by multiple agents. The critical path is **Voice Control (REQ-016)** - all other work must support or not block this feature.

**Key Principle:** Maximize parallelization while respecting hard dependencies. No timeframes - focus on what can run in parallel and what blocks what.

**CRITICAL INSIGHT FOR PHASE 2:**
- **3 parallel workstreams**: 2 agent streams (vacuum, blinds) + 1 user stream (Hue hardware validation)
- **THESE RUN IN PARALLEL** - User validates Hue hardware while agents code other device integrations
- **NO BLOCKING** - Agents don't wait for user, user doesn't wait for agents
- **Hue integration code is complete** - user stream is hardware validation only
- **Smart plugs and thermostat deferred** - moved to Phase 7 to simplify current work

---

## Current State

### Completed Phases

See `plans/completed/` for archived completed work:
- **PHASE1_COMPLETE.md** - Foundation & Core Infrastructure (completed 2025-12-09)
  - REQ-001, REQ-002, REQ-003, REQ-006, REQ-009, REQ-015

### What's Working Now
- Claude Sonnet 4 agent with 5-iteration agentic loop
- Cost tracking and daily usage monitoring
- Home Assistant REST API client (Docker container running)
- Light control via natural language (code complete - see Phase 2 Stream E for hardware validation)
- CLI mode (`python agent.py "command"`)
- Web UI at localhost:5050 with text and voice input
- Device status dashboard with 30-second auto-refresh
- 10 vibe presets for Philips Hue (code complete, physical hardware setup pending)

### 🎯 Next Steps: Parallel Work Available

**READY TO START NOW: Phase 2 Device Integrations**

All 3 streams can run simultaneously - 2 agent streams + 1 user stream:

#### Phase 2 Workstreams (ALL PARALLEL)
   - **Stream A (Agent):** REQ-010: Vacuum Control (Dreamehome L10s) - M complexity
   - **Stream B (Agent):** REQ-013: Smart Blinds Control (Hapadif) - M complexity
   - **Stream C (User):** Philips Hue Hardware Validation - S complexity (USER effort)
   - Status: All ready to start - completely parallel work
   - **Deferred:** REQ-012 (Smart Plugs) and REQ-011 (Thermostat) moved to Phase 7

**FUTURE: Phase 3 Voice Control (After Phase 2)**
   - REQ-016: Voice Control via HA Voice Puck - CRITICAL PATH
   - MAKE OR BREAK feature
   - Required for: Daily usage adoption, replacement of commercial assistants
   - Action: Purchase 2-3 HA voice pucks, implement wake word integration
   - Effort: M complexity, 2 agents recommended
   - Status: Wait until Phase 2 complete (or start early if hardware arrives)

---

## Phase 2: Device Integrations

**Critical Path:** None - expand device coverage
**Parallelization Level:** MEDIUM (2 agents + 1 user can work simultaneously)
**Dependencies:** Phase 1 complete (agent + HA integration working)
**Note:** Philips Hue integration code is done (Phase 1), Stream C is physical hardware validation
**Simplified:** Smart Plugs (REQ-012) and Thermostat (REQ-011) moved to Phase 7

#### 🟢 Stream A: Vacuum (Agent A)
**REQ-010: Vacuum Control (Dreamehome L10s)**
- **Complexity:** M
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **Tasks:**
  - Integrate Dreamehome L10s with Home Assistant
  - Implement start/stop/pause controls
  - Add status monitoring
  - Test natural language commands
- **Deliverable:** Voice-controlled vacuum with status visibility

#### 🟣 Stream B: Smart Blinds (Agent B)
**REQ-013: Smart Blinds Control (Hapadif)**
- **Complexity:** M
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **Tasks:**
  - Integrate Hapadif blinds with Home Assistant
  - Implement open/close/partial control
  - Create light scene integration
  - Add scheduling automation
- **Deliverable:** Voice-controlled blinds with light coordination

#### 🟠 Stream C: Philips Hue Hardware Validation (USER)
**Status:** IN_PROGRESS - Integration code complete, hardware validation pending
**Priority:** MEDIUM
**Complexity:** S (USER effort - shopping, installation, configuration)
**Owner:** USER (Katherine)
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **Note:** Integration code already complete - this is physical hardware validation only
- **Tasks:**
  - [x] Purchase Philips Hue bridge and bulbs/light strips
  - [x] Physically install Hue lights in rooms
  - [x] Set up Philips Hue bridge on local network
  - [x] Add Philips Hue integration to Home Assistant
  - [ ] Configure room mappings in Home Assistant to match `src/config.py` room names
  - [ ] Test existing demo code with actual hardware (verify scenes work)
  - [ ] Verify vibe presets apply correctly with real lights
  - [ ] Update room mappings in `src/config.py` if physical layout differs
  - [ ] Test dynamic scenes (fire, ocean, aurora) and tune speed/brightness if needed
- **Deliverable:** Physical Philips Hue lights working with existing integration code

**Current Status:**
- Integration code COMPLETE (tools/lights.py, tools/hue_specialist.py)
- Demo scenes and vibe presets configured (22 scene keywords, 10 vibe presets)
- Home Assistant client ready
- Physical hardware installed, Hue integration added to Home Assistant
- **Remaining:** Room mapping configuration and real hardware testing

**⚡ PARALLELIZATION:** All 3 streams (A, B, C) are independent - can run fully parallel

---

### Phase 3: Voice & Critical Foundation

**Critical Path:** REQ-016 (Voice Control) - MAKE OR BREAK
**Parallelization Level:** MEDIUM (2-3 agents, with coordination)
**Dependencies:** Phase 1 complete (agent + HA + web UI working)

#### 🔴 Stream 1: Voice Control - CRITICAL PATH (Agent A + B)
**REQ-016: Voice Control via HA Voice Puck**
- **Complexity:** M
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **PRIORITY:** HIGHEST - This is make-or-break
- **Hardware Action:** Purchase 2-3 HA voice pucks ASAP, test when they arrive

**Tasks - Part 1 (Agent A - Hardware Specialist):**
- Unbox and configure HA voice pucks
- Test wake word detection quality
- Measure audio quality and response latency
- Document hardware capabilities and limitations
- Test multi-room scenarios

**Tasks - Part 2 (Agent B - Integration Specialist):**
- Integrate voice puck with Home Assistant
- Connect voice input to LLM pipeline
- Implement minimal personality responses
- Add voice feedback for confirmations
- Test end-to-end flow (wake word → command → action → confirmation)

**Tasks - Part 3 (Agent A + B - Quality Assurance):**
- Handle failed recognition gracefully
- Optimize response latency (target: ≤1 second)
- Test all existing features via voice
- Multi-room coordination if multiple pucks
- User acceptance testing

**Success Criteria:**
- Wake word response ≤1 second
- Command accuracy ≥90%
- All existing features voice-controllable
- Daily usage ≥3 commands/day

#### 🟠 Stream 2: Cost Optimization (Agent C) - PARALLEL
**REQ-005: Request Caching & Optimization**
- **Complexity:** L
- **Dependencies:** Phase 1 Stream 1 complete, can run parallel to voice work
- **PRIORITY:** HIGH - Must complete before voice scales usage
- **Can start while voice testing continues**

**Tasks - Part 1:**
- Identify common command patterns from logs
- Design caching architecture (rule-based parser)
- Implement cache for top 20 common commands
- Add cache hit rate monitoring

**Tasks:**
- Implement learning mechanism for new patterns
- Add manual cache invalidation
- Optimize LLM routing (cache first, then LLM)
- Test cost reduction (target: 30-50% savings)

**Success Criteria:**
- Cache hit rate ≥30%
- API costs ≤$2.50/day average
- Response time improvement for cached commands

#### 🟢 Stream 3: UI Enhancement (Agent D) - PARALLEL
**REQ-017: Mobile-Optimized Web Interface**
- **Complexity:** M
- **Dependencies:** Phase 1 Stream 3 complete
- **Can run fully parallel to voice work**

**Tasks:**
- Implement responsive CSS for mobile
- Optimize touch controls
- Test iOS Safari voice input (native browser API)
- Implement web notifications or push notifications
- Test on iPhone and Android
- Performance optimization for mobile

**Success Criteria:**
- Fully functional on mobile browsers
- Voice input working on iOS Safari
- Touch-optimized controls

#### 🟡 Stream 4: Quick Wins (Agent D)
**REQ-024: Time & Date Queries**
- **Complexity:** S
- **Dependencies:** Stream 1 complete (voice needed to test)
- **Can start after voice complete**

**Tasks:**
- Implement time/date query tools
- Add timezone awareness
- Test voice responses
- Feature parity with commercial assistants

**⚡ PARALLELIZATION:**
- Stream 1 (Voice) is critical path
- Stream 2 (Caching) can run parallel, depends only on Phase 1 Stream 1
- Stream 3 (Mobile) can run parallel, depends only on Phase 1 Stream 3
- Stream 4 (Time) starts after Stream 1 complete

**🚨 GATE CHECK:**
- **PERSEVERE IF:** Voice working reliably, daily usage happening, costs reasonable
- **PIVOT IF:** Voice quality poor → browser-only voice; Costs too high → accelerate local LLM

---

### Phase 4A: Essential Intelligence

**Critical Path:** Feature parity with commercial assistants
**Parallelization Level:** HIGH (3-4 agents on independent streams)

#### 🔵 Stream 1: Productivity - Todos (Agent A)
**REQ-028: Todo List & Reminders**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-015 (✅), REQ-016 (✅)
- **PRIORITY:** HIGH - Highest RICE score (80.8)

**Tasks:**
- Design data model for todos/reminders
- Implement voice capture ("add X to todo list")
- Create multiple list support (todos, shopping, etc.)
- Add deadline/reminder system

**Tasks:**
- Build UI for viewing/editing lists
- Implement voice/UI notifications
- Add mark complete functionality
- Test reminder timing accuracy

**Follow-on:**
**REQ-029: Shopping List Management**
- **Dependencies and parallelization below**
- **Complexity:** S
- **Dependencies:** REQ-028
- Dedicated shopping list with categorization
- Voice capture while cooking (primary use case)

#### 🟢 Stream 2: Music - Spotify (Agent B)
**REQ-025: Spotify Playback Control**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-003 (✅), REQ-015 (✅)
- **PRIORITY:** HIGH - RICE score 60.8, frequent use case

**Tasks:**
- Integrate Spotify API (authentication, OAuth)
- Implement basic play/pause/skip controls
- Add volume control
- Test on multiple speakers

**Tasks:**
- Implement search and play ("play X by Y")
- Add queue management
- Speaker target selection (Alexa/Google as Spotify Connect endpoints)
- Multi-room audio exploration

**Tasks:**
- Natural language requests ("play something like X")
- Voice puck audio output fallback
- Test complex scenarios
- Performance optimization

#### 🟡 Stream 3: Automation Creation (Agent C)
**REQ-022: Simple Automation Creation**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-003 (✅), REQ-015 (✅)
- **PRIORITY:** HIGH - Core AI value proposition

**Tasks:**
- Design automation storage (local, not HA)
- Implement "Do X at time Y" automations
- LLM natural language parsing
- Central automation registry

**Tasks:**
- Implement "When X happens, do Y" automations
- Build edit/delete interface in UI
- Test various automation patterns
- Document automation capabilities

#### 🟣 Stream 4: Timers & Alarms (Agent D)
**REQ-023: Timers & Alarms**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-016 (✅), REQ-015 (✅)

**Tasks:**
- Implement timer system (multiple simultaneous)
- Add alarm system with specific times
- Voice notifications via puck + UI notifications
- Cancel/snooze functionality
- Named timers ("pizza timer")

**⚡ PARALLELIZATION:**
-  Streams 1, 2, 3 fully parallel (3 agents)
-  Streams 3, 4 fully parallel (2 agents)
- Stream 1 agent can assist other streams when dependencies complete

**Timeline:** Based on dependencies, no fixed duration

**🚨 GATE CHECK (Phase complete):**
- **PERSEVERE IF:** Daily usage ≥5 commands/day, voice adoption ≥70%, satisfaction ≥4/5
- **PIVOT IF:** Reverting to device apps for music/todos → feature gaps exist

---

### Phase 5: Advanced Intelligence

**Critical Path:** Build reliability and trust
**Parallelization Level:** HIGH (4 agents on independent streams)

#### 🔴 Stream 1: Self-Monitoring & Self-Healing (Agent A + B)
**REQ-021: Self-Monitoring & Self-Healing**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-001 (✅), REQ-002 (✅), REQ-036 (✅)
- **PRIORITY:** HIGH - Trust foundation

**Tasks - Agent A - Monitoring:**
- Health checks for all critical services
- Device connectivity monitoring (periodic pings)
- Connection quality monitoring (response times)
- Alert threshold definitions

**Tasks - Agent B - Self-Healing:**
- Automatic service restart logic
- Network issue detection and recovery
- API failure handling
- Log all issues and resolutions

**Tasks - Agent A + B - Integration:**
- Alert user only when auto-heal fails
- Helpful error messages (no silent failures)
- Test failure scenarios
- Validate auto-heal success rate (target: ≥80%)

#### 🟢 Stream 2: Device Organization (Agent C) - PARALLEL
**REQ-019: Device Organization Assistant**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-003 (✅), REQ-015 (✅)

**Tasks:**
- Design device registry schema
- Build contextual question system for new devices
- LLM-powered room assignment suggestions

**Tasks:**
- Naming consistency validation
- Bulk reorganization interface
- Test with existing devices
- Documentation

#### 🟡 Stream 3: Location Awareness (Agent D) - PARALLEL
**REQ-018: Location-Aware Commands**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-016 (✅)

**Tasks:**
- Infer location from voice puck used
- Implement clarification prompts ("Which room?")
- Manual room override handling

**Tasks:**
- Test multi-user scenarios
- Graceful degradation when location unknown
- Optional phone location tracking exploration

#### 🟠 Stream 4: Continuous Improvement (Agent A) - PARALLEL
**REQ-034: Continuous Improvement & Self-Optimization**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-003 (✅), REQ-021 (depends on Stream 1)

**Tasks:**
- Design periodic scanning system (periodic)
- Implement best practices research (lighting, automation)
- Generate improvement proposals

**Tasks:**
- User approval workflow
- Version control for updates
- Rollback capability
- Learning from accepted/rejected improvements

#### 🔵 Stream 5: Music Context (Agent C) - PARALLEL
**REQ-027: Music Education & Context**
- **Dependencies and parallelization below**
- **Complexity:** S
- **Dependencies:** REQ-025 (✅), REQ-015 (✅), REQ-003 (✅)

**Tasks:**
- Maintain current playback context
- "Tell me about this artist" using LLM general knowledge
- Display information in UI
- Optional voice readout

**⚡ PARALLELIZATION:**
-  Stream 1 (2 agents), Streams 2-5 all parallel (3 agents)
-  Streams 3, 4, 5 fully parallel

**Timeline:** Based on dependencies, no fixed duration

**🚨 GATE CHECK (Phase complete):**
- **PERSEVERE IF:** Uptime ≥99.5%, self-healing ≥80%, no manual restarts in 30 days
- **PIVOT IF:** Frequent manual intervention → defer community launch

---

### Phase 6: Community Preparation

**Critical Path:** Documentation quality determines adoption
**Parallelization Level:** MEDIUM (2-3 agents, coordination needed)

#### 🔴 Stream 1: CI/CD Pipeline (Agent A + B)
**REQ-037: CI/CD Pipeline & Multi-Agent Deployment System**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-032 (parallel), REQ-034 (✅)

**Tasks - Agent A - Testing:**
- Automated testing framework (unit, integration, e2e)
- Pre-deployment validation checks
- Health checks post-deployment

**Tasks - Agent B - Deployment:**
- Multi-agent deployment orchestration
- Rollback capability on failures
- Deployment notifications
- Version tagging and release management

#### 🟢 Stream 2: Repository & Logging (Agent C) - PARALLEL
**REQ-036: Comprehensive Logging (Enhancement)**
**REQ-032: Public Repository for Community Use**
- **Dependencies and parallelization below**
- **Complexity:** M

**Once ready - Logging Enhancement:**
- Enhance existing logging system
- Add user-facing log viewer in UI (filtering/search)
- Log export functionality
- Privacy-aware logging (no sensitive data)

**Once ready - Repository Preparation:**
- Remove hardcoded personal data/API keys
- Create configuration template file
- Add example configuration
- Prepare public GitHub repository
- Architecture documentation

#### 🟡 Stream 3: Documentation (Agent D + User)
**REQ-033: Setup & Installation Documentation**
- **Dependencies and parallelization below**
- **Complexity:** M
- **Dependencies:** REQ-032 (✅)
- **CRITICAL:** Quality determines community adoption

**Tasks:**
- Step-by-step installation guide
- Prerequisites documentation
- Environment setup instructions
- First-time configuration walkthrough

**Tasks:**
- Device integration guides (each device type)
- Troubleshooting section
- FAQ from development experience
- Common issues and resolutions

**Tasks:**
- Architecture deep-dive documentation
- Contributing guidelines
- Code examples and patterns
- API reference

#### 🔵 Stream 4: Community Testing (Dependencies complete)
**Beta Testing & Refinement**
- **Dependencies and parallelization below**
- **All hands on deck**

**Tasks:**
- Internal testing on fresh machine
- Identify documentation gaps
- Fix installation issues

**Tasks:**
- Recruit 2-3 beta testers
- Support first external installations
- Document new issues discovered

**Tasks:**
- Incorporate beta feedback
- Final documentation polish
- Public release preparation
- Community launch

**⚡ PARALLELIZATION:**
-  Streams 1, 2 fully parallel (3 agents)
-  Stream 3 (1-2 agents, user involvement)
-  Coordinated testing (all hands)

**Timeline:** Based on dependencies, no fixed duration

**🚨 GATE CHECK (Phase complete):**
- **PERSEVERE IF:** ≥5 external deployments, ≥1 contributor, positive feedback
- **PIVOT IF:** Zero external interest → personal project, reduce documentation effort

---

### Phase 7: Deferred Device Integrations & Advanced Features (Post-launch)

**Parallelization Level:** HIGH (community-driven, priority by feedback)

These features are deferred until community validation. Execute based on user demand:

#### Deferred Device Integrations (Moved from Phase 2)

**REQ-012: Smart Plug Control**
- **Complexity:** S
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **Deferred Reason:** Simplify Phase 2 focus, can be added later as needed
- **Tasks:**
  - Integrate smart plug API with Home Assistant
  - Implement basic on/off control
  - Add scheduling support
  - Add safety checks for high-power devices
- **Deliverable:** Voice/UI control of plugs for lamps, heater, toaster oven, speaker

**REQ-011: Smart Thermostat Control**
- **Complexity:** M
- **Dependencies:** Phase 1 Streams 1 & 2 complete
- **Deferred Reason:** User requested deferral, can be done "way later"
- **Tasks:**
  - Research open-source thermostat alternatives to Google Nest
  - Select and order hardware if needed
  - Integrate with Home Assistant
  - Implement temperature control and scheduling
- **Deliverable:** Voice-controlled thermostat (privacy-compliant)

#### Advanced Features

#### High-Complexity, Defer Until Validated
**REQ-020: Pattern Learning & Routine Discovery**
- **Dependencies and parallelization below**
- **Complexity:** XL (break down into sub-requirements)
- **DEFER REASON:** Unvalidated complexity, test simpler approaches first
- **Reconsider:** Phase+ if user demand is clear

**Potential Breakdown:**
- REQ-020a: Data collection infrastructure 
- REQ-020b: Simple pattern detection 
- REQ-020c: Suggestion generation 
- REQ-020d: Feedback loop 

#### Security & Access
**REQ-007: Secure Remote Access**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-001 (✅), REQ-015 (✅)
- **When:** User needs remote access

**REQ-008: Multi-User Support**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-007, REQ-015
- **When:** Household adoption with guests

#### Cost Reduction
**REQ-004: Future Local LLM Support**
- **Dependencies and parallelization below**
- **Complexity:** L
- **Dependencies:** REQ-003 (✅)
- **When:** API costs become unsustainable or offline operation needed

#### Additional Integrations
**REQ-014: Ring Camera Integration**
- **Dependencies and parallelization below**
- **Complexity:** L
- **When:** Presence detection needs exceed phone-based solutions

**REQ-026: Music Discovery Agent**
- **Dependencies and parallelization below**
- **Complexity:** L
- **When:** Community requests it

**REQ-031: Proactive Todo Assistance**
- **Dependencies and parallelization below**
- **Complexity:** L
- **When:** Todo system is validated and users want proactive help
- **Risk:** High annoyance potential, design carefully

#### ❌ DEFERRED INDEFINITELY
**REQ-030: Automated Order Management**
**REQ-035: Secure E-Commerce Integration**
- **DESCOPED:** High risk, legal liability, low user value
- **Reconsider:** Phase+ IF community demand emerges

---

## Agent Allocation Strategy

### Recommended Team Composition

**Agent Profiles:**
- **Agent A (Hardware/Infrastructure Specialist):** Voice pucks, device integrations, monitoring
- **Agent B (Integration Specialist):** APIs, Home Assistant, external services
- **Agent C (Intelligence Specialist):** LLM features, caching, automation logic
- **Agent D (UI/UX Specialist):** Web interface, mobile optimization, user experience

### Peak Parallelization Periods

**Maximum 4 agents:**
- Phase 2: 4 agents on device integrations + 1 user on hardware validation
- Phase 4A: 3-4 agents on features
- Phase 5: 3-4 agents on intelligence features

**Coordination needed (2-3 agents):**
- Phase 3: Voice is critical path, others support
- Phase 6: Documentation quality is critical

**Single agent acceptable:**
- Phase 7+ (Post-launch): Prioritize by community feedback

---

## Critical Path & Dependencies Diagram

```
CRITICAL PATH (Cannot ship without):
 ✅ Foundation (REQ-001, 002, 003, 006) - COMPLETE

 Device Integrations (REQ-010, 013) + Hue Hardware Validation (REQ-009)
  ↓ (3 parallel streams: 2 agent + 1 user)
  ↓ (REQ-011, REQ-012 deferred to Phase 7)

 🔴 VOICE CONTROL (REQ-016) ← MAKE OR BREAK
  ↓ (Must complete)

 Cost Caching (REQ-005) ← Prevents cost overrun
  ↓

 Gate Check #1
  ↓ (PERSEVERE decision)

 Feature Parity (REQ-022, 023, 025, 028, 029)
  ↓ (3-4 parallel streams)

 Gate Check #2
  ↓ (PERSEVERE decision)

 Intelligence & Reliability (REQ-018, 019, 021, 027, 034)
  ↓ (4 parallel streams)

 Gate Check #3
  ↓ (PERSEVERE decision)

 Community Launch (REQ-032, 033, 036, 037)
  ↓ (2-3 coordinated agents)

 🎉 PUBLIC RELEASE
  ↓

Post-launch : Community-Driven Features (REQ-004, 007, 008, 014, 020, 026, 031)
```

---

## Risk Management & Mitigation

### Top Risks with Parallel Mitigation

| Risk | Probability | Impact | Mitigation | Agent Responsible |
|------|-------------|---------|------------|-------------------|
| Voice control delay | HIGH | CRITICAL | Purchase hardware Upon readiness, dedicate 2 agents Sequential or parallel | Agent A + B |
| Cost overrun | MEDIUM | HIGH | Implement caching as soon as needed, daily monitoring | Agent C |
| Feature creep | HIGH | MEDIUM | Strict gate checks, defer REQ-030/035 indefinitely | User + All |
| Developer burnout | HIGH | MEDIUM | Parallelization, community as soon as needed | User |
| HA competitive response | MEDIUM | HIGH | Differentiate (multi-agent, self-optimization), contribute to HA | Agent C |

---

## Success Metrics by Phase

### Phase 2
- ✅ All 3 device workstreams complete (2 integrations + 1 hardware validation)
- ✅ Voice/UI control for vacuum and blinds
- ✅ Natural language working for all integrated devices
- ✅ Physical Hue hardware validated with real-world testing
- Note: Smart Plugs (REQ-012) and Thermostat (REQ-011) deferred to Phase 7

### Phase 3 - CRITICAL
- ✅ Voice wake word response ≤1 second
- ✅ Command accuracy ≥90%
- ✅ Daily usage ≥3 commands/day
- ✅ API costs ≤$2.50/day with caching
- ✅ Cache hit rate ≥30%

### Phase 4A
- ✅ Daily usage ≥5 commands/day
- ✅ Voice adoption ≥70% of commands
- ✅ User satisfaction ≥4/5 stars
- ✅ Music control working reliably
- ✅ Todos captured daily via voice

### Phase 5
- ✅ System uptime ≥99.5%
- ✅ Self-healing resolves ≥80% of failures
- ✅ No manual restarts in 30 days
- ✅ Location awareness working

### Phase 6
- ✅ ≥5 external deployments
- ✅ CI/CD operational with automated tests
- ✅ Documentation rated ≥4/5 by first users
- ✅ ≥1 community contributor

---

## Appendix: Parallelization Cheat Sheet

### What CAN Run in Parallel

✅ **USER hardware validation + AGENT coding** (Phase 2 - All 3 streams)
- User Stream C: Physical Hue hardware validation (room mapping, testing)
- Agent Stream A: Vacuum integration
- Agent Stream B: Smart blinds integration
- Completely independent - no blocking between user and agent work

✅ **All device integrations** (Phase 2)
- Streams A, B, C - all independent work streams

✅ **UI + Voice** (Phase 3, 
- Mobile UI work doesn't block voice development

✅ **Caching + Time queries** (Phase 3, 
- Independent features

✅ **Music + Todos + Automation** (Phase 4A)
- Completely independent work streams

✅ **All intelligence features** (Phase 5)
- Self-monitoring, device org, location, improvements - independent

### What CANNOT Run in Parallel (Hard Dependencies)

❌ **Voice before caching testing**
- Need voice usage data to optimize caching

❌ **Todos before shopping lists**
- REQ-029 depends on REQ-028 data model

❌ **Continuous improvement before self-monitoring**
- REQ-034 needs REQ-021 health data

❌ **Public repository before documentation**
- REQ-033 depends on REQ-032 being ready

### Coordination Points (Need Sync)

🔄 **Phase 3 Complete:** Gate Check #1 - Voice quality decision
🔄 **Phase 4A Complete:** Gate Check #2 - Feature parity decision
🔄 **Phase 5 Complete:** Gate Check #3 - Community readiness decision
🔄 **Phase 6 Complete:** Public launch - all hands for support

---

**Last reviewed:** 2025-12-09
**Next review:** After Phase 2 or Phase 3 completion

---

*This roadmap is a living document. Update based on actual progress, blockers, and user priorities.*
