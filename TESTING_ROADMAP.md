# Smart Home Testing Roadmap

**Status:** Ready for Implementation
**Coverage Target:** 85%+
**Timeline:** 4 weeks
**Current Coverage:** <5%

---

## Executive Summary

Analyzed 2,800+ lines of production code across 13 modules. Created comprehensive test plan with 10 test suites and 121+ test cases using integration-first approach.

### Current State
- ✗ Agent loop: No tests (288 lines)
- ✗ HA integration: No tests (856 lines)
- ✗ Database: No tests (653 lines)
- ✓ Web UI: Playwright tests only

### Deliverables
- [x] Codebase analysis
- [x] Test plan (10 suites, 121+ tests)
- [x] Implementation roadmap
- [x] Test infrastructure design

---

## Test Suites Overview

| Suite | Priority | Tests | Lines Covered | Status |
|-------|----------|-------|---------------|--------|
| HA Integration | P1 | 15 | 856 | Not Started |
| Light Controls | P1 | 13 | 447 | Not Started |
| Agent Loop | P1 | 11 | 288 | Not Started |
| Database | P2 | 18 | 653 | Not Started |
| Device Sync | P2 | 12 | 346 | Not Started |
| Configuration | P3 | 9 | 192 | Not Started |
| Hue Specialist | P3 | 11 | 295 | Not Started |
| Server API | P3 | 13 | 240 | Not Started |
| Effects | P3 | 7 | 199 | Not Started |
| Utils | P3 | 12 | 345 | Not Started |

**Total:** 121+ tests covering ~3,861 lines

---

## Testing Philosophy (Per CLAUDE.md)

### Do ✓
- Write integration tests testing real component interactions
- Mock only at boundaries (HA API, Anthropic API)
- Test actual code paths users execute
- Use in-memory SQLite for fast database tests

### Don't ✗
- Don't mock internal components
- Don't write isolated unit tests with heavy mocking
- Don't test components in isolation unless pure functions
- Don't mock the database

---

## Week-by-Week Plan

### Week 1: Foundation + Critical Path
**Days 1-2: Infrastructure**
- Set up pytest, conftest.py, fixtures
- Add test dependencies to requirements.txt
- Create mock HA and Anthropic API fixtures

**Day 3: HA Integration Tests (P1)**
- 15 tests covering connection, state queries, service calls
- Mock: HTTP layer only
- Coverage: ha_client.py, homeassistant.py (856 lines)

**Days 4-5: Light Controls + Agent Loop (P1)**
- 13 tests for light controls
- 11 tests for agent orchestration
- Coverage: tools/lights.py (447 lines), agent.py (288 lines)

### Week 2: Data Layer
**Days 6-7: Database Tests (P2)**
- 18 tests for CRUD, queries, aggregations
- Use in-memory SQLite
- Coverage: src/database.py (653 lines)

**Days 8-9: Device Sync Tests (P2)**
- 12 tests for sync logic, capability extraction
- Coverage: src/device_sync.py (346 lines)

### Week 3: Remaining Coverage
**Day 10: Config + Utils (P3)**
- 9 config tests (conversions, validation)
- 12 utils tests (logging, cost tracking)
- Coverage: src/config.py (192 lines), src/utils.py (345 lines)

**Day 11: Specialist + Effects (P3)**
- 11 Hue specialist tests
- 7 effects tests
- Coverage: tools/hue_specialist.py (295 lines), tools/effects.py (199 lines)

**Day 12: Server API Tests (P3)**
- 13 tests for Flask endpoints
- Security header verification
- Coverage: src/server.py (240 lines)

### Week 4: Polish + CI/CD
**Days 13-14: Gap Analysis**
- Run coverage report
- Fill gaps to reach 85%+
- Edge case testing

**Day 15: CI/CD Integration**
- Pre-commit hooks
- GitHub Actions / CI pipeline
- Coverage reporting

---

## Quick Start

### Install Test Dependencies
```bash
pip install pytest pytest-cov pytest-mock responses requests-mock faker
```

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov=tools --cov-report=html

# Specific suite
pytest tests/integration/test_ha_integration.py
```

---

## Key Files

### Documentation
- `/plans/test-plan.md` - Complete test plan (10 suites, detailed)
- `/tests/README.md` - Quick reference for writing tests
- `/devlog/test-coverage-analysis/` - Analysis reports

### Test Code (To Be Created)
```
tests/
├── conftest.py                     # Shared fixtures
├── fixtures/                       # Mock data
├── integration/                    # Integration tests (P1-P2)
│   ├── test_ha_integration.py
│   ├── test_light_controls.py
│   ├── test_agent_loop.py
│   ├── test_database.py
│   └── test_device_sync.py
├── unit/                          # Unit tests (P3)
│   ├── test_config.py
│   └── test_utils.py
└── api/                           # API tests
    └── test_server_endpoints.py
```

---

## Coverage Goals

| Module | Target | Rationale |
|--------|--------|-----------|
| agent.py | 90% | Critical orchestration logic |
| ha_client.py, homeassistant.py | 90% | External integration, high risk |
| database.py | 90% | Data integrity critical |
| tools/lights.py | 85% | User-facing functionality |
| device_sync.py | 85% | Sync logic complexity |
| hue_specialist.py | 80% | LLM fallback, lower risk |
| effects.py | 80% | High-level coordination |
| config.py, utils.py | 75% | Utility functions |

**Overall Target:** 85%+

---

## Mocking Strategy

### Mock These (External Boundaries)
```python
# Home Assistant API
@responses.activate
def test_ha_client(mock_ha_api):
    responses.add(responses.GET, "http://ha/api/states", json=[...])
    ...

# Anthropic API
@responses.activate
def test_agent(mock_anthropic):
    responses.add(responses.POST, "https://api.anthropic.com/...", json={...})
    ...
```

### Don't Mock These (Internal Components)
```python
# ✓ Good - test real interactions
def test_light_control(mock_ha_api):
    result = set_room_ambiance(room="living room", action="on")
    assert result["success"] == True

# ✗ Bad - heavy mocking
@patch('tools.lights.get_ha_client')
@patch('tools.lights.get_room_entity')
def test_light_control(mock_client, mock_entity):
    # Don't do this!
```

---

## Success Metrics

### Test Quality
- ✓ All critical paths have integration tests
- ✓ Tests execute in <30 seconds
- ✓ No flaky tests
- ✓ Tests document expected behavior

### Code Quality
- ✓ 85%+ coverage achieved
- ✓ All public APIs tested
- ✓ Error paths tested
- ✓ Edge cases covered

### Development Velocity
- ✓ Tests run automatically (CI/CD)
- ✓ Test failures block merges
- ✓ Easy to add new tests
- ✓ Clear failure messages

---

## Next Steps

1. **Review test plan:** See `/plans/test-plan.md` for full details
2. **Begin Week 1:** Set up infrastructure and P1 tests
3. **Daily progress:** Track in devlog as implementation proceeds
4. **Coverage monitoring:** Run `pytest --cov` regularly

---

## Questions?

- **Detailed test cases:** `/plans/test-plan.md`
- **How to write tests:** `/tests/README.md`
- **Coverage analysis:** `/devlog/test-coverage-analysis/2025-12-18-initial-assessment.md`
- **Summary:** `/devlog/test-coverage-analysis/SUMMARY.md`

---

**Ready to proceed with Week 1 implementation?**
