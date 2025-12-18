# Smart Home Test Suite

This directory contains comprehensive tests for the Smart Home Assistant system.

## Quick Start

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock responses requests-mock faker

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov=tools --cov-report=html

# Run specific suite
pytest tests/integration/test_ha_integration.py

# Run with verbose output
pytest -v

# Run in parallel (after installing pytest-xdist)
pytest -n auto
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures for all tests
├── fixtures/                # Test data and mock responses
│   ├── ha_responses.py     # Home Assistant API responses
│   ├── anthropic_responses.py  # Claude API responses
│   └── sample_data.py      # Sample devices, rooms, commands
├── integration/             # Integration tests (test real component interactions)
│   ├── test_ha_integration.py      # Home Assistant client tests
│   ├── test_light_controls.py      # Light tool integration tests
│   ├── test_agent_loop.py          # Agent orchestration tests
│   ├── test_database.py            # Database operation tests
│   ├── test_device_sync.py         # Device sync tests
│   └── test_effects.py             # Effects module tests
├── unit/                    # Unit tests (focused, minimal mocking)
│   ├── test_config.py      # Configuration tests
│   └── test_utils.py       # Utility function tests
├── api/                     # Web API tests
│   └── test_server_endpoints.py
└── ui/                      # UI tests (Playwright)
    ├── test_web_ui.py
    └── screenshots/
```

## Testing Philosophy

Following project guidelines from CLAUDE.md:

### Do: Integration Testing
✓ Test real component interactions
✓ Mock only at boundaries (external APIs)
✓ Test actual code paths users execute
✓ Use in-memory database for fast tests

### Don't: Heavy Mocking
✗ Don't mock internal components
✗ Don't test isolated units with lots of mocks
✗ Don't mock database (use `:memory:` SQLite)

## What We Mock

### External APIs (Required)
- **Home Assistant REST API** - Use `responses` library
- **Anthropic API** - Use `responses` library

### Example:
```python
import responses

@responses.activate
def test_ha_connection(mock_ha_api):
    # Mock external HTTP call
    responses.add(
        responses.GET,
        "http://localhost:8123/api/",
        json={"message": "API running"},
        status=200
    )

    # Test actual client code
    client = HomeAssistantClient()
    assert client.check_connection() == True
```

## Shared Fixtures

Located in `conftest.py`:

### Database Fixtures
```python
def test_database_operations(test_db):
    # test_db is in-memory SQLite with full schema
    register_device(entity_id="light.test", device_type="light")
    device = get_device("light.test")
    assert device is not None
```

### API Mocking Fixtures
```python
def test_light_control(mock_ha_api):
    # mock_ha_api automatically mocks common HA endpoints
    result = turn_on_light("light.living_room", brightness_pct=50)
    assert result["success"] == True
```

### Flask Test Client
```python
def test_api_endpoint(client):
    # client is Flask test client
    response = client.post("/api/command", json={"command": "turn on lights"})
    assert response.status_code == 200
```

## Writing Tests

### Integration Test Example
```python
# tests/integration/test_light_controls.py

def test_set_room_ambiance_with_color(mock_ha_api):
    """Test setting room to specific color."""
    # Arrange
    mock_ha_api.add_light_state("light.living_room", state="off")

    # Act
    result = set_room_ambiance(
        room="living room",
        action="set",
        color="blue"
    )

    # Assert
    assert result["success"] == True
    assert result["rgb_color"] == (0, 0, 255)
    mock_ha_api.assert_service_called(
        "light", "turn_on",
        entity_id="light.living_room_2",
        rgb_color=[0, 0, 255]
    )
```

### Unit Test Example
```python
# tests/unit/test_config.py

def test_kelvin_to_mireds_conversion():
    """Test color temperature conversion."""
    # Warm white (2700K)
    assert kelvin_to_mireds(2700) == 370

    # Cool white (6500K)
    assert kelvin_to_mireds(6500) == 153
```

## Test Data

### Fixture Data Files
```python
# tests/fixtures/sample_data.py

SAMPLE_LIGHT_STATE = {
    "entity_id": "light.living_room",
    "state": "on",
    "attributes": {
        "brightness": 128,
        "color_temp": 370,
        "friendly_name": "Living Room Light"
    }
}

def load_fixture(name: str):
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent / f"{name}.json"
    with open(fixture_path) as f:
        return json.load(f)
```

## Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov=tools --cov-report=html

# View report
open htmlcov/index.html
```

### Coverage Goals
- Overall: 85%+
- Critical modules (agent, ha_client, database): 90%+
- Tool modules: 80%+
- Config/utils: 75%+

## Running Specific Tests

```bash
# Single test file
pytest tests/integration/test_ha_integration.py

# Single test function
pytest tests/integration/test_ha_integration.py::test_connection_success

# Tests matching pattern
pytest -k "test_light"

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf
```

## Performance

Target execution times:
- Full test suite: <30 seconds
- Integration tests: <20 seconds
- Unit tests: <5 seconds

Tips for fast tests:
- Use in-memory SQLite (`:memory:`)
- Mock external HTTP calls
- Minimize file I/O
- Use pytest-xdist for parallel execution

## Debugging Tests

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Enter debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# See full diff on assertion errors
pytest -vv
```

## CI/CD Integration

Tests run automatically on:
- Pre-commit (unit + integration tests)
- Pull requests (full suite)
- Main branch pushes (full suite + coverage)

### Pre-commit Hook
```bash
# Install
pre-commit install

# Run manually
pre-commit run --all-files
```

## Common Patterns

### Testing Error Handling
```python
def test_ha_connection_timeout(mock_ha_api):
    """Test timeout handling."""
    mock_ha_api.add_timeout("/api/")

    client = HomeAssistantClient()
    with pytest.raises(HomeAssistantConnectionError):
        client.check_connection()
```

### Testing With Database
```python
def test_device_registration(test_db):
    """Test device CRUD operations."""
    # Register device
    register_device(entity_id="light.test", device_type="light")

    # Verify
    device = get_device("light.test")
    assert device["entity_id"] == "light.test"
    assert device["device_type"] == "light"
```

### Testing Flask Endpoints
```python
def test_command_endpoint(client, mock_agent):
    """Test POST /api/command."""
    mock_agent.return_value = "Lights turned on"

    response = client.post(
        "/api/command",
        json={"command": "turn on living room"}
    )

    assert response.status_code == 200
    assert response.json["success"] == True
```

## Troubleshooting

### Tests fail with "No module named pytest"
```bash
pip install pytest pytest-cov pytest-mock
```

### Mock not working
Check that you're mocking at the right boundary:
```python
# Good - mock external HTTP
@responses.activate
def test_ha_client(mock_ha_api):
    ...

# Bad - don't mock internal components
@patch('src.ha_client.HomeAssistantClient')  # ✗ Don't do this
```

### Database tests interfere with each other
Use the `test_db` fixture - it creates a fresh database for each test:
```python
def test_devices(test_db):
    # Fresh database for this test
    ...
```

### Slow tests
- Check for real HTTP calls (should be mocked)
- Check for file I/O (use in-memory or tmp_path)
- Run tests in parallel: `pytest -n auto`

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [responses library](https://github.com/getsentry/responses)
- [Flask testing](https://flask.palletsprojects.com/en/latest/testing/)
- [Project test plan](../plans/test-plan.md)
- [Coverage analysis](../devlog/test-coverage-analysis/)

## Contributing Tests

When adding tests:

1. **Choose the right type:**
   - Integration test if testing component interactions
   - Unit test if testing pure functions
   - API test if testing web endpoints

2. **Follow naming convention:**
   - File: `test_<module>.py`
   - Function: `test_<feature>_<scenario>`

3. **Write clear docstrings:**
   ```python
   def test_turn_on_light_with_brightness(mock_ha_api):
       """Test turning on light with specific brightness level."""
   ```

4. **Use arrange-act-assert pattern:**
   ```python
   # Arrange
   mock_ha_api.add_light("light.test", state="off")

   # Act
   result = turn_on_light("light.test", brightness_pct=75)

   # Assert
   assert result["success"] == True
   ```

5. **Test edge cases:**
   - Empty inputs
   - Invalid inputs
   - Boundary values
   - Error conditions

## Questions?

See the full test plan in `/plans/test-plan.md` or the coverage analysis in `/devlog/test-coverage-analysis/`.
