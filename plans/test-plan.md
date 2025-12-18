# Smart Home Test Plan

**Created:** 2025-12-18
**Status:** Draft
**Version:** 1.0

## Overview

This document outlines the comprehensive testing strategy for the Smart Home Assistant system. Following TDD principles and project guidelines, we prioritize integration tests over heavily mocked unit tests.

---

## Testing Philosophy

### Core Principles (from CLAUDE.md)
1. **Integration over Unit Tests** - Test real component interactions
2. **Mock at Boundaries Only** - Mock external APIs/services, not internal components
3. **Test Real Code Paths** - Exercise what users actually use
4. **Avoid Heavy Mocking** - Don't mock internal components

### What to Mock
- ✓ Home Assistant HTTP API (external service)
- ✓ Anthropic API (external service)
- ✓ File system (when needed)
- ✗ Internal modules (ha_client, database, utils)
- ✗ Internal business logic

### What NOT to Mock
- Internal component interactions
- Database operations (use in-memory SQLite)
- Configuration loading
- Business logic methods

---

## Test Infrastructure

### Required Dependencies
```txt
# Testing Framework
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0

# HTTP Mocking
responses>=0.24.0
requests-mock>=1.11.0

# Test Data
faker>=20.0.0

# Already have for UI tests
playwright>=1.40.0
```

### Directory Structure
```
tests/
├── __init__.py
├── conftest.py                     # Shared fixtures
├── fixtures/
│   ├── __init__.py
│   ├── ha_responses.py            # Mock HA API responses
│   ├── anthropic_responses.py     # Mock Claude responses
│   └── sample_data.py             # Sample devices, rooms, etc.
│
├── integration/                    # Integration test suites
│   ├── __init__.py
│   ├── test_ha_integration.py
│   ├── test_light_controls.py
│   ├── test_agent_loop.py
│   └── test_device_sync.py
│
├── unit/                          # Unit tests (minimal, focused)
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_utils.py
│   └── test_conversions.py
│
├── api/                           # Web API tests
│   ├── __init__.py
│   └── test_server_endpoints.py
│
└── ui/                            # UI tests (existing Playwright)
    ├── __init__.py
    ├── test_web_ui.py
    └── screenshots/
```

---

## Test Suites

### Suite 1: Home Assistant Integration Tests

**File:** `tests/integration/test_ha_integration.py`

**Purpose:** Test interaction with Home Assistant API without requiring running HA instance.

**Scope:**
- Connection handling (success, auth failure, timeout, connection error)
- Service call construction and execution
- Entity state parsing
- Light control operations
- Scene activation
- Error handling and recovery

**Mocking Strategy:**
- Mock `requests.Session` using `responses` library
- Provide realistic HA API response fixtures
- Test actual ha_client.py and homeassistant.py logic

**Test Cases:**
```python
def test_connection_success(mock_ha_api)
def test_connection_auth_failure(mock_ha_api)
def test_connection_timeout(mock_ha_api)
def test_get_states_returns_all_entities(mock_ha_api)
def test_get_state_single_entity(mock_ha_api)
def test_get_lights_filters_correctly(mock_ha_api)
def test_turn_on_light_basic(mock_ha_api)
def test_turn_on_light_with_brightness(mock_ha_api)
def test_turn_on_light_with_color_temp(mock_ha_api)
def test_turn_on_light_with_rgb(mock_ha_api)
def test_activate_scene(mock_ha_api)
def test_activate_hue_scene_with_dynamic(mock_ha_api)
def test_call_service_constructs_correct_payload(mock_ha_api)
def test_error_handling_404(mock_ha_api)
def test_error_handling_500(mock_ha_api)
```

**Fixtures Needed:**
- `mock_ha_api` - Configurable mock for HA API responses
- `sample_light_state` - Realistic light entity state
- `sample_all_states` - Collection of various entity states

---

### Suite 2: Light Control Integration Tests

**File:** `tests/integration/test_light_controls.py`

**Purpose:** Test end-to-end light control from tool execution through HA client.

**Scope:**
- Room ambiance setting (on/off/set)
- Color name to RGB conversion
- Vibe preset application
- Scene activation
- Light status queries
- Room name normalization

**Mocking Strategy:**
- Mock HA API responses
- Test actual tools/lights.py logic
- Test integration with ha_client

**Test Cases:**
```python
def test_set_room_ambiance_turn_on(mock_ha_api)
def test_set_room_ambiance_turn_off(mock_ha_api)
def test_set_room_ambiance_with_brightness(mock_ha_api)
def test_set_room_ambiance_with_color_name(mock_ha_api)
def test_set_room_ambiance_with_color_temp(mock_ha_api)
def test_set_room_ambiance_with_vibe_preset(mock_ha_api)
def test_set_room_ambiance_unknown_room(mock_ha_api)
def test_color_name_to_rgb_conversion()
def test_color_name_unknown()
def test_vibe_preset_application()
def test_rgb_excludes_color_temp(mock_ha_api)
def test_get_light_status(mock_ha_api)
def test_activate_hue_scene(mock_ha_api)
def test_list_available_rooms()
def test_execute_light_tool_dispatcher()
```

**Fixtures Needed:**
- `mock_ha_api`
- `sample_rooms` - Room entity mappings
- `all_color_names` - RGB mapping test data

---

### Suite 3: Agent Loop Integration Tests

**File:** `tests/integration/test_agent_loop.py`

**Purpose:** Test agentic loop orchestration and tool execution.

**Scope:**
- Agent loop execution
- Tool selection
- Tool execution
- Multi-turn conversations
- Max iterations handling
- Error recovery
- API usage tracking

**Mocking Strategy:**
- Mock Anthropic API using `responses`
- Mock HA API
- Test actual agent.py logic

**Test Cases:**
```python
def test_agent_simple_command(mock_anthropic, mock_ha_api)
def test_agent_tool_use_single_turn(mock_anthropic, mock_ha_api)
def test_agent_tool_use_multi_turn(mock_anthropic, mock_ha_api)
def test_agent_max_iterations_reached(mock_anthropic)
def test_agent_system_tool_get_time(mock_anthropic)
def test_agent_system_tool_get_status(mock_anthropic, mock_ha_api)
def test_agent_light_tool_execution(mock_anthropic, mock_ha_api)
def test_agent_error_handling_api_failure(mock_anthropic)
def test_agent_cost_tracking(mock_anthropic, test_db)
def test_agent_command_logging(test_db)
def test_agent_no_api_key()
```

**Fixtures Needed:**
- `mock_anthropic` - Mock Claude API with tool use responses
- `mock_ha_api`
- `test_db` - In-memory database for usage tracking

---

### Suite 4: Database Operations Tests

**File:** `tests/integration/test_database.py`

**Purpose:** Test database CRUD operations and data integrity.

**Scope:**
- Device registration and updates
- Command history recording
- API usage tracking
- Settings CRUD
- Device state history
- Query operations

**Mocking Strategy:**
- Use in-memory SQLite (`:memory:`)
- No mocking - test actual database.py logic
- Isolated test database per test

**Test Cases:**
```python
def test_database_initialization(test_db)
def test_register_device_new(test_db)
def test_register_device_update_existing(test_db)
def test_get_device_by_entity_id(test_db)
def test_get_all_devices(test_db)
def test_get_devices_by_room(test_db)
def test_get_devices_by_type(test_db)
def test_delete_device(test_db)
def test_record_command(test_db)
def test_get_command_history(test_db)
def test_track_api_usage(test_db)
def test_get_daily_usage_aggregation(test_db)
def test_get_usage_for_period(test_db)
def test_set_setting(test_db)
def test_get_setting_with_default(test_db)
def test_record_device_state(test_db)
def test_get_device_state_history(test_db)
def test_json_field_serialization(test_db)
```

**Fixtures Needed:**
- `test_db` - In-memory database with schema
- `sample_devices` - Device test data
- `sample_commands` - Command history test data

---

### Suite 5: Device Sync Integration Tests

**File:** `tests/integration/test_device_sync.py`

**Purpose:** Test device synchronization from HA to local database.

**Scope:**
- Capability extraction per domain
- Room inference
- New vs updated device detection
- Stale device removal
- Sync statistics

**Mocking Strategy:**
- Mock HA API get_states() response
- Use in-memory database
- Test actual device_sync.py logic

**Test Cases:**
```python
def test_sync_devices_from_ha(mock_ha_api, test_db)
def test_capability_extraction_light(test_db)
def test_capability_extraction_climate(test_db)
def test_capability_extraction_media_player(test_db)
def test_room_inference_from_entity_id(test_db)
def test_room_inference_from_friendly_name(test_db)
def test_new_device_detection(mock_ha_api, test_db)
def test_updated_device_detection(mock_ha_api, test_db)
def test_sync_statistics(mock_ha_api, test_db)
def test_domain_filtering(mock_ha_api, test_db)
def test_remove_stale_devices(mock_ha_api, test_db)
def test_sync_single_device(mock_ha_api, test_db)
def test_get_device_summary(test_db)
```

**Fixtures Needed:**
- `mock_ha_api` with diverse entity types
- `test_db`
- `sample_ha_states` - Various entity states

---

### Suite 6: Configuration Tests

**File:** `tests/unit/test_config.py`

**Purpose:** Test configuration loading and utilities.

**Scope:**
- Room name normalization
- Room entity lookup
- Kelvin/mireds conversion
- Config validation

**Mocking Strategy:**
- Mock environment variables
- Test pure functions
- Minimal mocking

**Test Cases:**
```python
def test_kelvin_to_mireds_conversion()
def test_mireds_to_kelvin_conversion()
def test_get_room_entity_exact_match()
def test_get_room_entity_with_alias()
def test_get_room_entity_with_spaces()
def test_get_room_entity_unknown_room()
def test_validate_config_all_present(monkeypatch)
def test_validate_config_missing_api_key(monkeypatch)
def test_validate_config_missing_ha_token(monkeypatch)
def test_room_aliases_mapping()
```

**Fixtures Needed:**
- Environment variable mocks via `monkeypatch`

---

### Suite 7: Hue Specialist Tests

**File:** `tests/integration/test_hue_specialist.py`

**Purpose:** Test vibe interpretation and scene mapping.

**Scope:**
- Vibe preset matching
- Scene keyword matching
- LLM interpretation
- Fallback logic
- JSON parsing

**Mocking Strategy:**
- Mock Anthropic API for LLM tests
- Test actual hue_specialist.py logic
- Test fallback without API key

**Test Cases:**
```python
def test_interpret_vibe_preset_exact_match()
def test_interpret_vibe_scene_keyword_match()
def test_interpret_vibe_llm_basic(mock_anthropic)
def test_interpret_vibe_llm_json_extraction(mock_anthropic)
def test_interpret_vibe_llm_with_markdown_code_block(mock_anthropic)
def test_interpret_vibe_fallback_warm_keywords()
def test_interpret_vibe_fallback_cool_keywords()
def test_interpret_vibe_fallback_dim_keywords()
def test_interpret_vibe_no_api_key_uses_fallback()
def test_get_scene_suggestions()
def test_list_available_effects()
```

**Fixtures Needed:**
- `mock_anthropic` with various JSON response formats
- Sample vibe descriptions

---

### Suite 8: Server API Tests

**File:** `tests/api/test_server_endpoints.py`

**Purpose:** Test Flask web API endpoints.

**Scope:**
- Command endpoint validation
- Status endpoint
- History endpoint
- Security headers
- Error handling

**Mocking Strategy:**
- Use Flask test client
- Mock agent execution
- Mock HA client
- Test actual server.py logic

**Test Cases:**
```python
def test_index_route_renders(client)
def test_api_command_success(client, mock_agent)
def test_api_command_missing_field(client)
def test_api_command_empty_command(client)
def test_api_command_agent_error(client, mock_agent)
def test_api_status_ha_connected(client, mock_ha_api)
def test_api_status_ha_disconnected(client, mock_ha_api)
def test_api_status_includes_devices(client, mock_ha_api)
def test_api_status_includes_daily_cost(client, test_db)
def test_api_history_with_data(client, test_db)
def test_api_history_empty_database(client)
def test_security_headers_present(client)
def test_debug_mode_error_detail(client)
def test_production_mode_error_hiding(client)
```

**Fixtures Needed:**
- `client` - Flask test client
- `mock_agent` - Mock run_agent function
- `mock_ha_api`
- `test_db`

---

### Suite 9: Effects Module Tests

**File:** `tests/integration/test_effects.py`

**Purpose:** Test high-level effect application.

**Scope:**
- Vibe application routing
- Scene vs basic light selection
- Preview mode
- List vibes

**Mocking Strategy:**
- Mock HA client
- Mock hue_specialist (or use real with fixtures)
- Test actual effects.py logic

**Test Cases:**
```python
def test_apply_vibe_basic_light(mock_ha_api)
def test_apply_vibe_scene(mock_ha_api)
def test_apply_vibe_unknown_room(mock_ha_api)
def test_apply_vibe_error_handling(mock_ha_api)
def test_get_vibe_preview()
def test_list_vibes()
def test_scene_entity_id_construction()
```

**Fixtures Needed:**
- `mock_ha_api`
- Sample vibe descriptions

---

### Suite 10: Utils Module Tests

**File:** `tests/unit/test_utils.py`

**Purpose:** Test utility functions.

**Scope:**
- Logging setup
- Prompt loading
- API usage tracking
- Cost calculations

**Mocking Strategy:**
- Mock file system for prompt loading
- Use in-memory database for usage tracking
- Minimal mocking

**Test Cases:**
```python
def test_setup_logging_creates_handlers()
def test_load_prompts_valid_json(tmp_path)
def test_load_prompts_invalid_json(tmp_path)
def test_load_prompts_missing_file(tmp_path)
def test_get_default_prompts()
def test_track_api_usage_cost_calculation(test_db)
def test_track_api_usage_daily_aggregation(test_db)
def test_get_daily_usage(test_db)
def test_get_usage_stats(test_db)
def test_cost_alert_threshold(test_db)
def test_check_setup_all_valid()
def test_check_setup_missing_directories(tmp_path)
```

**Fixtures Needed:**
- `tmp_path` - pytest temporary directory
- `test_db`

---

## Shared Fixtures (conftest.py)

### Database Fixtures
```python
@pytest.fixture
def test_db():
    """In-memory SQLite database with schema."""
    # Initialize database in :memory:
    # Yield connection
    # Teardown

@pytest.fixture
def sample_devices():
    """Sample device data for testing."""
    # Return list of device dicts

@pytest.fixture
def sample_commands():
    """Sample command history data."""
    # Return list of command dicts
```

### API Mocking Fixtures
```python
@pytest.fixture
def mock_ha_api():
    """Mock Home Assistant API using responses library."""
    # Set up request mocks
    # Yield
    # Clean up

@pytest.fixture
def mock_anthropic():
    """Mock Anthropic API."""
    # Set up API mocks
    # Yield
    # Clean up
```

### Flask Fixtures
```python
@pytest.fixture
def client():
    """Flask test client."""
    # Create test client
    # Yield
    # Clean up

@pytest.fixture
def mock_agent(monkeypatch):
    """Mock agent.run_agent function."""
    # Patch run_agent
    # Return mock
```

### Data Fixtures
```python
@pytest.fixture
def sample_light_state():
    """Realistic light entity state."""
    # Return dict

@pytest.fixture
def sample_all_states():
    """Collection of various entity states."""
    # Return list of dicts

@pytest.fixture
def sample_rooms():
    """Room configuration for testing."""
    # Return ROOM_ENTITY_MAP subset
```

---

## Test Execution

### Running Tests
```bash
# All tests
pytest

# Specific suite
pytest tests/integration/test_ha_integration.py

# With coverage
pytest --cov=src --cov=tools --cov-report=html

# Parallel execution
pytest -n auto

# Verbose
pytest -v

# Show print statements
pytest -s
```

### Coverage Goals
- **Overall:** 85%+
- **Critical modules (agent, ha_client, database):** 90%+
- **Tool modules:** 80%+
- **Config/utils:** 75%+

### Performance Goals
- Full test suite: <30 seconds
- Integration tests: <20 seconds
- Unit tests: <5 seconds
- UI tests (Playwright): Allow up to 60 seconds

---

## CI/CD Integration

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit tests/integration
        language: system
        pass_filenames: false
        always_run: true
```

### GitHub Actions (if using)
```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

---

## Test Data Management

### Fixture Data Location
```
tests/fixtures/
├── ha_responses/
│   ├── states_all.json          # Full state response
│   ├── state_light_on.json
│   ├── state_light_off.json
│   └── error_responses.json
├── anthropic_responses/
│   ├── tool_use_single.json
│   ├── tool_use_multi.json
│   └── max_iterations.json
└── sample_data/
    ├── devices.json
    ├── rooms.json
    └── commands.json
```

### Fixture Loading
```python
import json
from pathlib import Path

def load_fixture(name: str) -> dict:
    """Load JSON fixture by name."""
    fixture_path = Path(__file__).parent / "fixtures" / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)
```

---

## Success Metrics

### Test Quality Indicators
- ✓ All critical paths have integration tests
- ✓ Test execution is fast (<30s)
- ✓ Tests are reliable (no flaky tests)
- ✓ Tests document expected behavior
- ✓ Tests catch regressions

### Code Quality Indicators
- ✓ 85%+ code coverage
- ✓ All public APIs tested
- ✓ Error paths tested
- ✓ Edge cases covered

### Development Velocity Indicators
- ✓ Tests run automatically
- ✓ Failures block merges
- ✓ Easy to add new tests
- ✓ Clear test failure messages

---

## Implementation Timeline

### Week 1: Foundation
- Day 1: Set up pytest infrastructure, conftest.py, fixtures
- Day 2: Implement Suite 1 (HA Integration)
- Day 3: Implement Suite 2 (Light Controls)

### Week 2: Core Tests
- Day 4: Implement Suite 3 (Agent Loop)
- Day 5: Implement Suite 4 (Database)
- Day 6: Implement Suite 5 (Device Sync)

### Week 3: Coverage Completion
- Day 7: Implement Suite 6 (Config), Suite 7 (Hue Specialist)
- Day 8: Implement Suite 8 (Server API), Suite 9 (Effects)
- Day 9: Implement Suite 10 (Utils)

### Week 4: Polish and CI/CD
- Day 10: Coverage analysis and gap filling
- Day 11: CI/CD integration
- Day 12: Documentation and test data

---

## Notes

- This plan follows the project guideline: "prefer integration tests over heavily mocked unit tests"
- We mock at boundaries (HA API, Anthropic API) but test real component interactions
- In-memory SQLite allows fast database testing without mocking
- Fixture data should be realistic to catch edge cases
- Tests should be self-documenting with clear names and docstrings
