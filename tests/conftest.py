"""
Shared test fixtures for the Smart Home project.

Provides fixtures for mocking external dependencies:
- Home Assistant API (via responses library)
- Anthropic API (for agent tests)
- In-memory SQLite database
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up test environment variables for all tests."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("HA_URL", "http://test-ha.local:8123")
    monkeypatch.setenv("HA_TOKEN", "test-ha-token")
    monkeypatch.setenv("DAILY_COST_TARGET", "2.00")
    monkeypatch.setenv("DAILY_COST_ALERT", "5.00")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Patch DATA_DIR in config module
    monkeypatch.setattr("src.config.DATA_DIR", data_dir)
    monkeypatch.setattr("src.config.LOGS_DIR", data_dir / "logs")
    (data_dir / "logs").mkdir()

    return data_dir


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def test_db(temp_data_dir, monkeypatch):
    """
    Create an isolated test database in the temp directory.

    Returns the database path and handles cleanup.
    """
    db_path = temp_data_dir / "test_smarthome.db"

    # Patch the database path before importing database module
    monkeypatch.setattr("src.database.DATABASE_PATH", db_path)

    # Force re-initialization of the database
    from src import database
    database.DATABASE_PATH = db_path
    database.initialize_database()

    yield db_path

    # Cleanup is automatic with tmp_path


@pytest.fixture
def sample_devices():
    """Sample device data for testing."""
    return [
        {
            "entity_id": "light.living_room",
            "device_type": "light",
            "friendly_name": "Living Room Light",
            "room": "living_room",
            "capabilities": ["brightness", "color_temp"],
        },
        {
            "entity_id": "light.bedroom",
            "device_type": "light",
            "friendly_name": "Bedroom Light",
            "room": "bedroom",
            "capabilities": ["brightness", "color_temp", "rgb"],
        },
        {
            "entity_id": "switch.office_fan",
            "device_type": "switch",
            "friendly_name": "Office Fan",
            "room": "office",
            "capabilities": ["on_off"],
        },
    ]


# =============================================================================
# Home Assistant Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_ha_api():
    """
    Mock Home Assistant API using responses library.

    Provides common HA API response mocking. Call add() to add custom responses.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Default: connection check succeeds
        rsps.add(
            responses.GET,
            "http://test-ha.local:8123/api/",
            json={"message": "API running."},
            status=200,
        )
        yield rsps


@pytest.fixture
def ha_light_states():
    """Sample Home Assistant light states."""
    return [
        {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room",
                "brightness": 255,
                "color_temp": 370,
                "supported_color_modes": ["color_temp"],
            },
        },
        {
            "entity_id": "light.living_room_2",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room 2",
                "brightness": 200,
                "color_temp": 300,
                "rgb_color": [255, 200, 150],
                "supported_color_modes": ["color_temp", "rgb"],
            },
        },
        {
            "entity_id": "light.bedroom",
            "state": "off",
            "attributes": {
                "friendly_name": "Bedroom",
                "supported_color_modes": ["color_temp", "rgb"],
            },
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen",
                "brightness": 128,
                "color_temp": 400,
            },
        },
    ]


@pytest.fixture
def ha_scene_states():
    """Sample Home Assistant Hue scene states."""
    return [
        {
            "entity_id": "scene.living_room_arctic_aurora",
            "state": "scening",
            "attributes": {
                "friendly_name": "Living Room Arctic Aurora",
                "group_name": "Living Room",
                "is_dynamic": True,
            },
        },
        {
            "entity_id": "scene.living_room_tropical_twilight",
            "state": "scening",
            "attributes": {
                "friendly_name": "Living Room Tropical Twilight",
                "group_name": "Living Room",
                "is_dynamic": True,
            },
        },
        {
            "entity_id": "scene.bedroom_savanna_sunset",
            "state": "scening",
            "attributes": {
                "friendly_name": "Bedroom Savanna Sunset",
                "group_name": "Bedroom",
                "is_dynamic": True,
            },
        },
    ]


@pytest.fixture
def mock_ha_full(mock_ha_api, ha_light_states, ha_scene_states):
    """
    Fully mocked HA API with lights and scenes.

    Use this fixture for integration tests that need complete HA mock.
    """
    # Reset the HA client singleton before each test
    import src.ha_client as ha_module
    ha_module._client = None

    all_states = ha_light_states + ha_scene_states

    # Add additional entity states for rooms used in tests
    additional_states = [
        {
            "entity_id": "light.bedroom_2",
            "state": "off",
            "attributes": {"friendly_name": "Bedroom 2", "brightness": 128, "color_temp": 300},
        },
        {
            "entity_id": "light.kitchen_2",
            "state": "on",
            "attributes": {"friendly_name": "Kitchen 2", "brightness": 200, "color_temp": 350},
        },
        {
            "entity_id": "light.office_pendant",
            "state": "on",
            "attributes": {"friendly_name": "Office Pendant", "brightness": 255, "color_temp": 400},
        },
    ]
    all_states = all_states + additional_states

    # GET /api/states - all states (allow multiple calls)
    mock_ha_api.add(
        responses.GET,
        "http://test-ha.local:8123/api/states",
        json=all_states,
        status=200,
    )

    # GET /api/states/{entity_id} - individual states (allow multiple calls)
    for state in all_states:
        mock_ha_api.add(
            responses.GET,
            f"http://test-ha.local:8123/api/states/{state['entity_id']}",
            json=state,
            status=200,
        )

    # POST /api/services/light/turn_on (allow multiple calls)
    mock_ha_api.add(
        responses.POST,
        "http://test-ha.local:8123/api/services/light/turn_on",
        json=[{"entity_id": "light.living_room"}],
        status=200,
    )

    # POST /api/services/light/turn_off (allow multiple calls)
    mock_ha_api.add(
        responses.POST,
        "http://test-ha.local:8123/api/services/light/turn_off",
        json=[{"entity_id": "light.living_room"}],
        status=200,
    )

    # POST /api/services/hue/activate_scene (allow multiple calls)
    mock_ha_api.add(
        responses.POST,
        "http://test-ha.local:8123/api/services/hue/activate_scene",
        json=[{"entity_id": "scene.living_room_arctic_aurora"}],
        status=200,
    )

    yield mock_ha_api

    # Clean up singleton after test
    ha_module._client = None


# =============================================================================
# HA Client Fixtures
# =============================================================================

@pytest.fixture
def ha_client(mock_ha_full):
    """
    Create a HomeAssistantClient with mocked API.

    Use with mock_ha_full fixture for complete mocking.
    """
    from src.ha_client import HomeAssistantClient

    client = HomeAssistantClient(
        url="http://test-ha.local:8123",
        token="test-ha-token"
    )
    return client


# =============================================================================
# Config Fixtures
# =============================================================================

@pytest.fixture
def room_config():
    """Room configuration for tests."""
    return {
        "living_room": {
            "lights": ["light.living_room", "light.living_room_2"],
            "default_light": "light.living_room_2",
        },
        "bedroom": {
            "lights": ["light.bedroom", "light.bedroom_2"],
            "default_light": "light.bedroom_2",
        },
        "kitchen": {
            "lights": ["light.kitchen", "light.kitchen_2"],
            "default_light": "light.kitchen_2",
        },
    }


@pytest.fixture
def vibe_presets():
    """Vibe preset configuration for tests."""
    return {
        "cozy": {"brightness": 40, "color_temp_kelvin": 2700},
        "focus": {"brightness": 80, "color_temp_kelvin": 4000},
        "romantic": {"brightness": 25, "color_temp_kelvin": 2200},
        "movie": {"brightness": 15, "color_temp_kelvin": 2700},
    }


# =============================================================================
# Anthropic API Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_anthropic():
    """
    Mock Anthropic client for agent tests.

    Returns a MagicMock that can be configured for specific test scenarios.
    """
    mock_client = MagicMock()

    # Default response - simple text completion
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Test response")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client.messages.create.return_value = mock_response

    return mock_client


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def capture_logs(caplog):
    """Capture log output for assertions."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog
