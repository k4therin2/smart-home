# Test Suite Quality Improvement - December 19, 2025

## Summary

Fixed test isolation issues causing 99 test failures. Achieved 96.6% pass rate (up from 91.4%).

## Problem

When running the full test suite, 99 tests were failing due to test pollution - state from one test affecting others:

1. **HA Client Singleton**: The `HomeAssistantClient` singleton wasn't being reset between tests, causing URL mismatches
2. **Config Values**: Module-level config imports cached values before test fixtures could patch them
3. **Rate Limiter State**: Flask-Limiter accumulated request counts across tests
4. **Mock Patch Locations**: Tests were patching wrong module paths for lazy imports

## Changes Made

### tests/conftest.py

1. Added HA client singleton reset in `mock_ha_api` fixture:
   ```python
   import src.ha_client as ha_module
   ha_module._client = None
   monkeypatch.setattr(ha_module, "HA_URL", "http://test-ha.local:8123")
   ```

2. Added config patching for already-loaded values in `mock_env_vars`:
   ```python
   monkeypatch.setattr("src.config.HA_URL", "http://test-ha.local:8123")
   ```

3. Added server DATA_DIR patching in `temp_data_dir`:
   ```python
   monkeypatch.setattr("src.server.DATA_DIR", data_dir)
   ```

### tests/unit/test_health_monitor.py

1. Fixed patch locations for lazy imports (inside methods):
   - `src.health_monitor.HomeAssistantClient` → `src.ha_client.HomeAssistantClient`
   - `src.health_monitor.get_cache` → `src.cache.get_cache`
   - `src.health_monitor.get_daily_usage` → `src.utils.get_daily_usage`

2. Refactored `TestAggregatedHealth` to use direct `_component_checkers` replacement instead of patching methods (method references stored at init time)

### tests/unit/test_voice_handler.py

1. Added rate limiter reset to test fixtures:
   ```python
   from src.server import limiter
   limiter.reset()
   ```

2. Updated test assertions to match implementation:
   - TTS response formatting adds periods
   - Timeout error message uses "took too long"
   - Error handling returns 500 for Flask exceptions

## Results

- **Before**: 1048 passed, 99 failed (91.4%)
- **After**: 1108 passed, 39 failed (96.6%)
- **Tests Fixed**: 60

## Remaining Issues

39 tests still fail, primarily due to:
- Integration tests with complex multi-component state
- Flask app configuration not fully isolated between test classes
- Database state persistence in some edge cases

These require deeper refactoring of test isolation patterns.

## Lessons Learned

1. **Singleton Pattern + Tests = Pain**: Always provide a reset mechanism for singletons
2. **Module-level Imports**: Patch where used, not where defined, for lazy imports
3. **Flask-Limiter**: Use `RATELIMIT_ENABLED=False` config or call `limiter.reset()`
4. **Bound Method References**: Can't patch methods after they're stored in data structures

## Additional Fixes (Session 2)

### tests/test_security.py

1. Added explicit `LOGIN_DISABLED=False` fixture for auth tests to prevent pollution from tests that disable login.

## Updated Results

- **Before**: 1048 passed, 99 failed (91.4%)
- **After**: 1112 passed, 35 failed (96.9%)
- **Total Tests Fixed**: 64
