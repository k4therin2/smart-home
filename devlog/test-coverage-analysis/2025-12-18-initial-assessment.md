# Test Coverage Analysis - Initial Assessment

**Date:** 2025-12-18
**Machine:** colby (home server)
**Author:** TDD Workflow Engineer Agent

## Executive Summary

Analyzed the smart home codebase to assess current test coverage and identify gaps. The system has **minimal test coverage** despite having substantial implemented functionality across 9 core modules and 4 tool modules.

### Current State
- **Existing Tests:** 2 Playwright UI tests, 1 integration script
- **Production Code:** ~2,800 lines across 13 Python modules
- **Test Coverage:** Estimated <5% (UI only)
- **Critical Gap:** Zero unit/integration tests for core business logic

---

## Implemented Functionality

### 1. Core Agent System (`agent.py` - 288 lines)
**What it does:**
- Agentic loop using Claude Sonnet 4 with max 5 iterations
- Tool orchestration (system tools + light tools)
- CLI and interactive modes
- API usage tracking
- Command logging

**Current Testing:** None

**Needs Testing:**
- Agent loop execution with various command types
- Tool selection and execution logic
- Error handling for API failures
- Max iteration limit behavior
- Command parsing edge cases
- Cost tracking accuracy

---

### 2. Web Server (`src/server.py` - 240 lines)
**What it does:**
- Flask web interface on port 5050
- Command processing endpoint (`/api/command`)
- Status endpoint (`/api/status`) - returns HA connection, devices, daily cost
- History endpoint (`/api/history`) - recent commands from usage DB
- Security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- Debug mode conditional error detail leaking

**Current Testing:**
- ✓ Playwright UI tests (page loads, status display, command submission)

**Needs Testing:**
- POST `/api/command` with valid/invalid payloads
- POST `/api/command` with empty/missing command field
- GET `/api/status` when HA is connected vs disconnected
- GET `/api/history` with empty database
- Security header presence
- Error handling when agent fails
- Debug mode vs production mode error responses

---

### 3. Home Assistant Client (`src/ha_client.py` - 299 lines)
**What it does:**
- REST API wrapper for Home Assistant
- Connection checking
- Device state queries (lights, switches, sensors)
- Service calls (turn_on, turn_off, toggle)
- Light controls (brightness, color temp, RGB)
- Hue scene activation with dynamic mode

**Current Testing:** None

**Needs Testing:**
- Connection success/failure scenarios
- Authentication errors (401)
- Network timeouts
- Light control parameter validation
- Color temperature Kelvin to mireds conversion
- RGB color handling
- Scene activation with various parameters
- Error recovery on connection loss

---

### 4. Home Assistant Integration (`src/homeassistant.py` - 557 lines)
**What it does:**
- Enhanced HA client with custom exceptions
- Domain-based entity filtering
- Service call abstraction
- Light, switch, scene helpers
- Hue-specific scene activation
- Connection health checking

**Current Testing:**
- ✓ Integration script (`scripts/test_ha_integration.py`) - manual testing only

**Needs Testing:**
- Exception hierarchy (HomeAssistantError, ConnectionError, AuthError)
- Entity domain filtering accuracy
- Service call payload construction
- HTTP error code handling (401, 404, timeouts)
- Session management
- Color temperature conversions
- RGB color validation

---

### 5. Light Control Tools (`tools/lights.py` - 447 lines)
**What it does:**
- 4 tools exposed to Claude agent
- Room ambiance setting (on/off/set with brightness, color, color_temp, vibe)
- Light status queries
- Hue scene activation
- Room listing
- Color name to RGB mapping (24 colors)
- Vibe preset application

**Current Testing:** None

**Needs Testing:**
- Color name to RGB conversion accuracy
- Vibe preset application logic
- Room name normalization and aliases
- Parameter validation (brightness 0-100, color_temp 2200-6500)
- RGB vs color_temp mutual exclusivity
- Unknown room handling
- Entity ID construction for scenes
- Tool execution dispatcher

---

### 6. Hue Specialist (`tools/hue_specialist.py` - 295 lines)
**What it does:**
- Abstract vibe interpretation using Claude
- Scene mapping (fire, ocean, aurora, party, etc.)
- LLM fallback for complex requests
- JSON response parsing from LLM
- Fallback keyword matching when LLM unavailable
- Scene suggestions

**Current Testing:** None

**Needs Testing:**
- Vibe preset exact matching
- Scene keyword matching
- LLM interpretation (requires mocking Anthropic API)
- JSON extraction from markdown code blocks
- Fallback interpretation keyword matching
- API error handling
- Cost tracking for specialist calls
- Scene suggestions accuracy

---

### 7. Effects Module (`tools/effects.py` - 199 lines)
**What it does:**
- High-level vibe application
- Coordinates between basic lights and Hue specialist
- Scene entity ID construction
- Vibe preview (dry-run)
- List available vibes

**Current Testing:** None

**Needs Testing:**
- Vibe routing (basic vs scene)
- Room entity lookup
- Scene entity ID construction format
- Preview mode accuracy
- Error handling when specialist fails
- Integration between ha_client and hue_specialist

---

### 8. Database Module (`src/database.py` - 653 lines)
**What it does:**
- SQLite schema with 5 tables (devices, command_history, api_usage, settings, device_state_history)
- Device registry CRUD operations
- Command history recording
- API usage tracking with date aggregation
- Settings key-value store
- Device state snapshots

**Current Testing:** None

**Needs Testing:**
- Table creation and schema validation
- Device registration and upsert logic
- JSON field serialization/deserialization
- Command history recording
- API usage daily aggregation
- Settings get/set operations
- Device filtering (by room, by type)
- State history queries
- Database initialization on first run
- Concurrent access handling

---

### 9. Device Sync (`src/device_sync.py` - 346 lines)
**What it does:**
- Sync devices from HA to local database
- Capability extraction per domain (lights, climate, cover, vacuum, media_player)
- Room inference from entity IDs and friendly names
- Stale device removal
- Device summary statistics

**Current Testing:**
- ✓ Integration script calls sync_devices_from_ha()

**Needs Testing:**
- Capability extraction logic per domain
- Room inference patterns
- Device info extraction from HA states
- New vs updated device detection
- Stale device removal logic
- Device summary aggregations
- Domain filtering
- State recording during sync

---

### 10. Utils Module (`src/utils.py` - 345 lines)
**What it does:**
- Centralized logging setup (console + file + error file)
- Prompt loading from JSON
- Default prompts fallback
- API usage tracking to SQLite
- Daily cost alerts ($2 target, $5 alert)
- Setup validation
- Usage statistics (7-day aggregation)

**Current Testing:** None

**Needs Testing:**
- Logging configuration (handlers, formatters, levels)
- Prompt loading with missing/invalid JSON
- Default prompt fallback
- API usage cost calculation (input/output token pricing)
- Daily cost aggregation
- Cost threshold alerts
- Setup validation checks
- Usage stats period queries

---

### 11. Config Module (`src/config.py` - 192 lines)
**What it does:**
- Environment variable loading (.env)
- Room entity mappings (8 rooms)
- Room aliases for NLU
- Color temperature presets
- Brightness presets
- Vibe presets (11 vibes)
- Kelvin/mireds conversion
- Room entity lookup with normalization
- Configuration validation

**Current Testing:** None

**Needs Testing:**
- Environment variable parsing
- Room name normalization (spaces, underscores)
- Room alias resolution
- Entity lookup for rooms
- Kelvin to mireds conversion accuracy
- Mireds to kelvin conversion accuracy
- Config validation error collection
- Default values for missing env vars

---

## Existing Tests

### 1. Playwright Web UI Tests (`tests/test_web_ui.py`)
**Coverage:**
- Page loading
- Header presence
- Status indicator
- Device grid rendering
- Command input interaction
- Voice button presence
- Command submission
- Response display
- History list updates

**Limitations:**
- Requires running server
- Tests UI only, not business logic
- No mocking - depends on real HA connection
- Manual verification via screenshots

### 2. Integration Test Script (`scripts/test_ha_integration.py`)
**Coverage:**
- Config validation
- HA connection
- Device queries (lights, switches)
- Device sync statistics
- Database operations

**Limitations:**
- Not automated test suite
- Requires real HA instance
- Manual execution only
- No assertions - print-based verification
- Not integrated with CI/CD

---

## Test Infrastructure Gaps

### Missing Components
1. **pytest.ini** - No pytest configuration
2. **conftest.py** - No shared fixtures
3. **Unit tests** - Zero coverage of business logic
4. **Integration tests** - Only manual scripts
5. **Mocking framework** - No pytest-mock or unittest.mock usage
6. **Test requirements** - pytest, pytest-mock, faker not in requirements.txt
7. **CI/CD integration** - No test automation

### Missing Test Data
1. Mock HA API responses
2. Fixture databases with sample devices
3. Sample .env configurations for testing
4. Mock Anthropic API responses

---

## Recommended Test Suites

Following TDD principles and project guidelines (prefer integration tests over heavily mocked unit tests), here are the test suites needed:

### Priority 1: Critical Path Integration Tests

#### A. Home Assistant Integration Suite
**File:** `tests/test_ha_integration.py`
- Test HA client connection handling
- Test service call construction
- Test entity state parsing
- Mock only the HTTP layer (requests.Session)
- Test real error scenarios (401, 404, timeout)

#### B. Light Control Integration Suite
**File:** `tests/test_light_controls.py`
- Test room ambiance setting end-to-end
- Test color name to RGB conversion
- Test vibe application (preset → HA call)
- Test scene activation
- Mock only HA API responses, test actual tool logic

#### C. Agent Loop Integration Suite
**File:** `tests/test_agent_loop.py`
- Test agent loop with various commands
- Test tool selection and execution
- Test max iterations handling
- Mock only Anthropic API, test actual orchestration

### Priority 2: Data Layer Tests

#### D. Database Operations Suite
**File:** `tests/test_database.py`
- Test device registration and updates
- Test command history recording
- Test API usage tracking
- Test settings CRUD
- Use in-memory SQLite for fast tests

#### E. Device Sync Suite
**File:** `tests/test_device_sync.py`
- Test capability extraction per domain
- Test room inference logic
- Test sync statistics
- Use fixture HA states, test actual sync logic

### Priority 3: Business Logic Unit Tests

#### F. Configuration Suite
**File:** `tests/test_config.py`
- Test room name normalization
- Test Kelvin/mireds conversion
- Test entity lookup
- Test config validation

#### G. Hue Specialist Suite
**File:** `tests/test_hue_specialist.py`
- Test vibe preset matching
- Test scene keyword matching
- Test fallback interpretation
- Mock only Anthropic API

### Priority 4: Web API Tests

#### H. Server API Suite
**File:** `tests/test_server_api.py`
- Test Flask endpoints with test client
- Test command processing
- Test status endpoint
- Test security headers
- Mock agent execution

---

## Testing Strategy

### Integration Testing Principles (per CLAUDE.md)
1. **Mock at boundaries only** - Mock external APIs (HA, Anthropic), not internal components
2. **Test real code paths** - Exercise actual user flows
3. **Avoid heavy mocking** - Test component interactions
4. **Mock external dependencies:**
   - Home Assistant HTTP API
   - Anthropic API
   - File system (for some tests)

### Tools and Frameworks
```python
# Add to requirements.txt
pytest>=7.4.0
pytest-mock>=3.12.0
pytest-cov>=4.1.0
faker>=20.0.0
responses>=0.24.0  # for mocking requests
```

### Test Structure
```
tests/
├── __init__.py
├── conftest.py                  # Shared fixtures
├── fixtures/
│   ├── ha_states.json          # Mock HA API responses
│   ├── anthropic_responses.json
│   └── sample_db.sql
├── test_ha_integration.py
├── test_light_controls.py
├── test_agent_loop.py
├── test_database.py
├── test_device_sync.py
├── test_config.py
├── test_hue_specialist.py
└── test_server_api.py
```

### Fixture Strategy

#### Shared Fixtures (conftest.py)
- `mock_ha_client` - Mocked HA API responses
- `mock_anthropic_client` - Mocked Claude API
- `test_db` - In-memory SQLite database
- `sample_devices` - Fixture device data
- `sample_rooms` - Room configurations

#### Per-Test Fixtures
- Specific HA state responses
- Specific agent commands
- Specific device configurations

---

## Metrics and Coverage Goals

### Initial Goals
- **Unit test coverage:** 80% of core logic
- **Integration test coverage:** 90% of critical paths
- **Test execution time:** <30 seconds for full suite
- **CI/CD integration:** Run on every commit

### Success Criteria
- All existing functionality has test coverage
- No regressions when adding new features
- Tests run automatically
- Test failures block deployment

---

## Implementation Plan

### Phase 1: Foundation (Days 1-2)
1. Set up pytest infrastructure
2. Create conftest.py with shared fixtures
3. Add test requirements to requirements.txt
4. Create fixture data files

### Phase 2: Critical Path (Days 3-5)
1. Implement HA integration tests
2. Implement light control tests
3. Implement agent loop tests

### Phase 3: Data Layer (Days 6-7)
1. Implement database tests
2. Implement device sync tests

### Phase 4: Remaining Coverage (Days 8-9)
1. Implement config tests
2. Implement Hue specialist tests
3. Implement server API tests

### Phase 5: CI/CD Integration (Day 10)
1. Add pytest to CI pipeline
2. Configure coverage reporting
3. Set up pre-commit hooks

---

## Risk Assessment

### High-Risk Untested Areas
1. **Agent loop logic** - Core orchestration, zero coverage
2. **HA service calls** - Critical functionality, only manual testing
3. **Database operations** - Data persistence, no validation
4. **Cost tracking** - Financial tracking, needs accuracy

### Medium-Risk Areas
1. **Configuration validation** - Could fail silently
2. **Device sync** - Could miss devices or create duplicates
3. **Web API** - Security headers, error handling

### Low-Risk Areas
1. **Color name mapping** - Static data
2. **Vibe presets** - Static configuration
3. **Logging setup** - External library usage

---

## Next Steps

1. **Immediate:** Create `conftest.py` and test infrastructure
2. **Week 1:** Implement Priority 1 integration tests
3. **Week 2:** Implement Priority 2 and 3 tests
4. **Week 3:** CI/CD integration and coverage reporting

---

## Notes

- Current system is functional but **brittle without tests**
- Web UI has some coverage via Playwright, but business logic has none
- Following project guideline: prefer integration tests over mocked unit tests
- Mock boundaries: HA API, Anthropic API, file system (when needed)
- Test actual code paths users execute
- Avoid testing isolated units with heavy mocking
