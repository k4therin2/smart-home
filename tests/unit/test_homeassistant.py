"""
Tests for src/homeassistant.py - Home Assistant Integration Module

These tests cover the HomeAssistantClient class and module-level
convenience functions for communicating with Home Assistant REST API.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
import requests

from src.homeassistant import (
    HomeAssistantClient,
    HomeAssistantError,
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    get_client,
    check_connection,
    get_state,
    call_service,
    turn_on_light,
    turn_off_light,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    with patch('src.homeassistant.requests.Session') as mock:
        session = MagicMock()
        mock.return_value = session
        yield session


@pytest.fixture
def ha_client(mock_session):
    """Create a HomeAssistantClient with mocked session."""
    return HomeAssistantClient(
        base_url="http://localhost:8123",
        token="test-token-12345"
    )


@pytest.fixture
def mock_response():
    """Create a mock response factory."""
    def _create_response(status_code=200, json_data=None, text=""):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.text = text or (str(json_data) if json_data else "")
        return response
    return _create_response


# =============================================================================
# HomeAssistantClient Initialization Tests
# =============================================================================


class TestHomeAssistantClientInit:
    """Tests for HomeAssistantClient initialization."""

    def test_init_with_valid_params(self, mock_session):
        """Test successful initialization with valid parameters."""
        client = HomeAssistantClient(
            base_url="http://localhost:8123",
            token="test-token"
        )

        assert client.base_url == "http://localhost:8123"
        assert client.token == "test-token"
        assert client._timeout == 10

    def test_init_strips_trailing_slash(self, mock_session):
        """Test that trailing slashes are removed from base_url."""
        client = HomeAssistantClient(
            base_url="http://localhost:8123/",
            token="test-token"
        )

        assert client.base_url == "http://localhost:8123"

    def test_init_without_url_raises_error(self, mock_session):
        """Test that missing URL raises HomeAssistantError."""
        with patch('src.homeassistant.HA_URL', None):
            with pytest.raises(HomeAssistantError, match="URL not configured"):
                HomeAssistantClient(base_url=None, token="test-token")

    def test_init_without_token_raises_error(self, mock_session):
        """Test that missing token raises HomeAssistantAuthError."""
        with patch('src.homeassistant.HA_TOKEN', None):
            with pytest.raises(HomeAssistantAuthError, match="token not configured"):
                HomeAssistantClient(base_url="http://localhost:8123", token=None)

    def test_init_sets_headers(self, mock_session):
        """Test that authorization headers are set correctly."""
        HomeAssistantClient(
            base_url="http://localhost:8123",
            token="test-token"
        )

        mock_session.headers.update.assert_called_once_with({
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
        })


# =============================================================================
# Request Making Tests
# =============================================================================


class TestMakeRequest:
    """Tests for the _make_request method."""

    def test_successful_get_request(self, ha_client, mock_session, mock_response):
        """Test successful GET request."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data={"message": "success"}
        )

        result = ha_client._make_request("GET", "/api/")

        mock_session.request.assert_called_once()
        assert result == {"message": "success"}

    def test_successful_post_request(self, ha_client, mock_session, mock_response):
        """Test successful POST request with data."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[{"entity_id": "light.test"}]
        )

        result = ha_client._make_request("POST", "/api/services/light/turn_on", data={"brightness": 50})

        call_args = mock_session.request.call_args
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"brightness": 50}

    def test_401_raises_auth_error(self, ha_client, mock_session, mock_response):
        """Test that 401 status raises HomeAssistantAuthError."""
        mock_session.request.return_value = mock_response(status_code=401)

        with pytest.raises(HomeAssistantAuthError, match="Invalid or expired access token"):
            ha_client._make_request("GET", "/api/")

    def test_404_raises_error(self, ha_client, mock_session, mock_response):
        """Test that 404 status raises HomeAssistantError."""
        mock_session.request.return_value = mock_response(status_code=404)

        with pytest.raises(HomeAssistantError, match="Endpoint not found"):
            ha_client._make_request("GET", "/api/nonexistent")

    def test_connection_error_raises_connection_error(self, ha_client, mock_session):
        """Test that connection errors are wrapped in HomeAssistantConnectionError."""
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with pytest.raises(HomeAssistantConnectionError, match="Cannot connect"):
            ha_client._make_request("GET", "/api/")

    def test_timeout_raises_connection_error(self, ha_client, mock_session):
        """Test that timeout errors are wrapped in HomeAssistantConnectionError."""
        mock_session.request.side_effect = requests.exceptions.Timeout("Timed out")

        with pytest.raises(HomeAssistantConnectionError, match="timed out"):
            ha_client._make_request("GET", "/api/")

    def test_request_exception_raises_error(self, ha_client, mock_session):
        """Test that other request exceptions are wrapped in HomeAssistantError."""
        mock_session.request.side_effect = requests.exceptions.RequestException("Unknown error")

        with pytest.raises(HomeAssistantError, match="API request failed"):
            ha_client._make_request("GET", "/api/")

    def test_empty_response_returns_empty_dict(self, ha_client, mock_session, mock_response):
        """Test that empty responses return empty dict."""
        response = mock_response(status_code=200)
        response.text = ""
        mock_session.request.return_value = response

        result = ha_client._make_request("POST", "/api/services/test/test")

        assert result == {}


# =============================================================================
# Connection & Health Tests
# =============================================================================


class TestConnectionAndHealth:
    """Tests for connection checking methods."""

    def test_check_connection_success(self, ha_client, mock_session, mock_response):
        """Test successful connection check."""
        mock_session.request.return_value = mock_response(status_code=200, json_data={})

        result = ha_client.check_connection()

        assert result is True

    def test_check_connection_failure_propagates(self, ha_client, mock_session):
        """Test that connection check propagates errors."""
        mock_session.request.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(HomeAssistantConnectionError):
            ha_client.check_connection()

    def test_get_config(self, ha_client, mock_session, mock_response):
        """Test getting HA configuration."""
        config_data = {
            "location_name": "Home",
            "version": "2024.1.0",
            "unit_system": "metric"
        }
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=config_data
        )

        result = ha_client.get_config()

        assert result == config_data

    def test_is_running_returns_true_when_connected(self, ha_client, mock_session, mock_response):
        """Test is_running returns True when connected."""
        mock_session.request.return_value = mock_response(status_code=200, json_data={})

        assert ha_client.is_running() is True

    def test_is_running_returns_false_when_not_connected(self, ha_client, mock_session):
        """Test is_running returns False when not connected."""
        mock_session.request.side_effect = requests.exceptions.ConnectionError()

        assert ha_client.is_running() is False


# =============================================================================
# State Query Tests
# =============================================================================


class TestStateQueries:
    """Tests for state query methods."""

    def test_get_states(self, ha_client, mock_session, mock_response):
        """Test getting all entity states."""
        states = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "switch.kitchen", "state": "off"},
        ]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=states
        )

        result = ha_client.get_states()

        assert result == states

    def test_get_state(self, ha_client, mock_session, mock_response):
        """Test getting single entity state."""
        state = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255}
        }
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=state
        )

        result = ha_client.get_state("light.living_room")

        assert result == state

    def test_get_entity_state_value(self, ha_client, mock_session, mock_response):
        """Test getting just the state value."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data={"entity_id": "light.test", "state": "on"}
        )

        result = ha_client.get_entity_state_value("light.test")

        assert result == "on"

    def test_get_entity_state_value_missing_returns_unknown(self, ha_client, mock_session, mock_response):
        """Test that missing state returns 'unknown'."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data={"entity_id": "light.test"}
        )

        result = ha_client.get_entity_state_value("light.test")

        assert result == "unknown"

    def test_get_entities_by_domain(self, ha_client, mock_session, mock_response):
        """Test filtering entities by domain."""
        all_states = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "light.bedroom", "state": "off"},
            {"entity_id": "switch.kitchen", "state": "on"},
            {"entity_id": "sensor.temperature", "state": "22"},
        ]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=all_states
        )

        result = ha_client.get_entities_by_domain("light")

        assert len(result) == 2
        assert all(s["entity_id"].startswith("light.") for s in result)

    def test_get_lights(self, ha_client, mock_session, mock_response):
        """Test get_lights convenience method."""
        all_states = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "switch.kitchen", "state": "on"},
        ]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=all_states
        )

        result = ha_client.get_lights()

        assert len(result) == 1
        assert result[0]["entity_id"] == "light.living_room"

    def test_get_switches(self, ha_client, mock_session, mock_response):
        """Test get_switches convenience method."""
        all_states = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "switch.kitchen", "state": "on"},
        ]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=all_states
        )

        result = ha_client.get_switches()

        assert len(result) == 1
        assert result[0]["entity_id"] == "switch.kitchen"

    def test_get_sensors(self, ha_client, mock_session, mock_response):
        """Test get_sensors convenience method."""
        all_states = [
            {"entity_id": "sensor.temperature", "state": "22"},
            {"entity_id": "light.living_room", "state": "on"},
        ]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=all_states
        )

        result = ha_client.get_sensors()

        assert len(result) == 1
        assert result[0]["entity_id"] == "sensor.temperature"


# =============================================================================
# Service Call Tests
# =============================================================================


class TestServiceCalls:
    """Tests for service call methods."""

    def test_call_service_basic(self, ha_client, mock_session, mock_response):
        """Test basic service call without data or target."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[]
        )

        result = ha_client.call_service("homeassistant", "restart")

        call_args = mock_session.request.call_args
        assert "/api/services/homeassistant/restart" in call_args.kwargs["url"]
        assert result == []

    def test_call_service_with_target(self, ha_client, mock_session, mock_response):
        """Test service call with target."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[{"entity_id": "light.test"}]
        )

        ha_client.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.test"}
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["entity_id"] == "light.test"

    def test_call_service_with_data(self, ha_client, mock_session, mock_response):
        """Test service call with data."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[{"entity_id": "light.test"}]
        )

        ha_client.call_service(
            domain="light",
            service="turn_on",
            data={"brightness_pct": 50}
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness_pct"] == 50

    def test_call_service_with_data_and_target(self, ha_client, mock_session, mock_response):
        """Test service call with both data and target."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[]
        )

        ha_client.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.test"},
            data={"brightness_pct": 75}
        )

        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["entity_id"] == "light.test"
        assert payload["brightness_pct"] == 75

    def test_call_service_non_list_response(self, ha_client, mock_session, mock_response):
        """Test that non-list response returns empty list."""
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data={"result": "success"}
        )

        result = ha_client.call_service("test", "test")

        assert result == []


# =============================================================================
# Light Control Tests
# =============================================================================


class TestLightControl:
    """Tests for light control helper methods."""

    def test_turn_on_light_basic(self, ha_client, mock_session, mock_response):
        """Test basic light turn on."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_light("light.living_room")

        call_args = mock_session.request.call_args
        assert "/api/services/light/turn_on" in call_args.kwargs["url"]

    def test_turn_on_light_with_brightness(self, ha_client, mock_session, mock_response):
        """Test light turn on with brightness."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_light("light.living_room", brightness_pct=75)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness_pct"] == 75

    def test_turn_on_light_clamps_brightness(self, ha_client, mock_session, mock_response):
        """Test that brightness is clamped to 0-100."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        # Test over 100
        ha_client.turn_on_light("light.test", brightness_pct=150)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness_pct"] == 100

        # Test under 0
        ha_client.turn_on_light("light.test", brightness_pct=-10)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness_pct"] == 0

    def test_turn_on_light_with_color_temp(self, ha_client, mock_session, mock_response):
        """Test light turn on with color temperature."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_light("light.living_room", color_temp_kelvin=3000)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["color_temp_kelvin"] == 3000

    def test_turn_on_light_with_rgb(self, ha_client, mock_session, mock_response):
        """Test light turn on with RGB color."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_light("light.living_room", rgb_color=(255, 128, 0))

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["rgb_color"] == [255, 128, 0]

    def test_turn_on_light_with_transition(self, ha_client, mock_session, mock_response):
        """Test light turn on with transition."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_light("light.living_room", transition=2.0)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["transition"] == 2.0

    def test_turn_off_light_basic(self, ha_client, mock_session, mock_response):
        """Test basic light turn off."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_off_light("light.living_room")

        call_args = mock_session.request.call_args
        assert "/api/services/light/turn_off" in call_args.kwargs["url"]

    def test_turn_off_light_with_transition(self, ha_client, mock_session, mock_response):
        """Test light turn off with transition."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_off_light("light.living_room", transition=3.0)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["transition"] == 3.0

    def test_toggle_light(self, ha_client, mock_session, mock_response):
        """Test light toggle."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.toggle_light("light.living_room")

        call_args = mock_session.request.call_args
        assert "/api/services/light/toggle" in call_args.kwargs["url"]


# =============================================================================
# Switch Control Tests
# =============================================================================


class TestSwitchControl:
    """Tests for switch control helper methods."""

    def test_turn_on_switch(self, ha_client, mock_session, mock_response):
        """Test switch turn on."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_on_switch("switch.kitchen")

        call_args = mock_session.request.call_args
        assert "/api/services/switch/turn_on" in call_args.kwargs["url"]

    def test_turn_off_switch(self, ha_client, mock_session, mock_response):
        """Test switch turn off."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.turn_off_switch("switch.kitchen")

        call_args = mock_session.request.call_args
        assert "/api/services/switch/turn_off" in call_args.kwargs["url"]

    def test_toggle_switch(self, ha_client, mock_session, mock_response):
        """Test switch toggle."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.toggle_switch("switch.kitchen")

        call_args = mock_session.request.call_args
        assert "/api/services/switch/toggle" in call_args.kwargs["url"]


# =============================================================================
# Scene Control Tests
# =============================================================================


class TestSceneControl:
    """Tests for scene control methods."""

    def test_activate_scene(self, ha_client, mock_session, mock_response):
        """Test basic scene activation."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.activate_scene("scene.movie_time")

        call_args = mock_session.request.call_args
        assert "/api/services/scene/turn_on" in call_args.kwargs["url"]

    def test_activate_hue_scene_basic(self, ha_client, mock_session, mock_response):
        """Test basic Hue scene activation."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.activate_hue_scene("scene.living_room_relax")

        call_args = mock_session.request.call_args
        assert "/api/services/hue/activate_scene" in call_args.kwargs["url"]

    def test_activate_hue_scene_dynamic(self, ha_client, mock_session, mock_response):
        """Test Hue scene with dynamic mode."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.activate_hue_scene("scene.test", dynamic=True)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["dynamic"] is True

    def test_activate_hue_scene_with_speed(self, ha_client, mock_session, mock_response):
        """Test Hue scene with speed setting."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.activate_hue_scene("scene.test", speed=50)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["speed"] == 50

    def test_activate_hue_scene_clamps_speed(self, ha_client, mock_session, mock_response):
        """Test that speed is clamped to 1-100."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        # Test over 100
        ha_client.activate_hue_scene("scene.test", speed=150)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["speed"] == 100

        # Test under 1
        ha_client.activate_hue_scene("scene.test", speed=0)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["speed"] == 1

    def test_activate_hue_scene_with_brightness(self, ha_client, mock_session, mock_response):
        """Test Hue scene with brightness setting."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.activate_hue_scene("scene.test", brightness=75)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness"] == 75

    def test_activate_hue_scene_clamps_brightness(self, ha_client, mock_session, mock_response):
        """Test that brightness is clamped to 0-100."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        # Test over 100
        ha_client.activate_hue_scene("scene.test", brightness=150)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness"] == 100

        # Test under 0
        ha_client.activate_hue_scene("scene.test", brightness=-10)
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"]["brightness"] == 0


# =============================================================================
# Utility Method Tests
# =============================================================================


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_get_available_services(self, ha_client, mock_session, mock_response):
        """Test getting available services."""
        services = {
            "light": ["turn_on", "turn_off", "toggle"],
            "switch": ["turn_on", "turn_off"],
        }
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=services
        )

        result = ha_client.get_available_services()

        assert result == services

    def test_get_history_basic(self, ha_client, mock_session, mock_response):
        """Test getting history without filters."""
        history = [{"entity_id": "light.test", "state": "on"}]
        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=history
        )

        result = ha_client.get_history()

        assert result == history
        call_args = mock_session.request.call_args
        assert "/api/history/period" in call_args.kwargs["url"]

    def test_get_history_with_entity_filter(self, ha_client, mock_session, mock_response):
        """Test getting history with entity filter."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.get_history(entity_id="light.test")

        call_args = mock_session.request.call_args
        assert "filter_entity_id=light.test" in call_args.kwargs["url"]

    def test_get_history_with_start_time(self, ha_client, mock_session, mock_response):
        """Test getting history with start time."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.get_history(start_time="2024-01-01T00:00:00")

        call_args = mock_session.request.call_args
        assert "/api/history/period/2024-01-01T00:00:00" in call_args.kwargs["url"]

    def test_get_history_with_end_time(self, ha_client, mock_session, mock_response):
        """Test getting history with end time."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.get_history(end_time="2024-01-02T00:00:00")

        call_args = mock_session.request.call_args
        assert "end_time=2024-01-02T00:00:00" in call_args.kwargs["url"]

    def test_get_history_with_all_params(self, ha_client, mock_session, mock_response):
        """Test getting history with all parameters."""
        mock_session.request.return_value = mock_response(status_code=200, json_data=[])

        ha_client.get_history(
            entity_id="light.test",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-02T00:00:00"
        )

        call_args = mock_session.request.call_args
        url = call_args.kwargs["url"]
        assert "/api/history/period/2024-01-01T00:00:00" in url
        assert "filter_entity_id=light.test" in url
        assert "end_time=2024-01-02T00:00:00" in url

    def test_close_session(self, ha_client, mock_session):
        """Test closing the HTTP session."""
        ha_client.close()

        mock_session.close.assert_called_once()

    def test_context_manager(self, mock_session, mock_response):
        """Test using client as context manager."""
        mock_session.request.return_value = mock_response(status_code=200, json_data={})

        with HomeAssistantClient(
            base_url="http://localhost:8123",
            token="test-token"
        ) as client:
            assert client is not None

        # Session should be closed after context exit
        mock_session.close.assert_called()


# =============================================================================
# Module-Level Function Tests
# =============================================================================


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_client_creates_singleton(self, mock_session):
        """Test that get_client returns a singleton."""
        # Reset the module-level client
        import src.homeassistant as ha_module
        ha_module._default_client = None

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                client1 = get_client()
                client2 = get_client()

                assert client1 is client2

    def test_check_connection_uses_default_client(self, mock_session, mock_response):
        """Test check_connection uses default client."""
        import src.homeassistant as ha_module
        ha_module._default_client = None

        mock_session.request.return_value = mock_response(status_code=200, json_data={})

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                result = check_connection()

                assert result is True

    def test_get_state_uses_default_client(self, mock_session, mock_response):
        """Test get_state uses default client."""
        import src.homeassistant as ha_module
        ha_module._default_client = None

        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data={"entity_id": "light.test", "state": "on"}
        )

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                result = get_state("light.test")

                assert result["state"] == "on"

    def test_call_service_uses_default_client(self, mock_session, mock_response):
        """Test call_service uses default client."""
        import src.homeassistant as ha_module
        ha_module._default_client = None

        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[]
        )

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                result = call_service("light", "turn_on", target={"entity_id": "light.test"})

                assert result == []

    def test_turn_on_light_module_function(self, mock_session, mock_response):
        """Test module-level turn_on_light function."""
        import src.homeassistant as ha_module
        ha_module._default_client = None

        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[]
        )

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                result = turn_on_light("light.test", brightness_pct=50)

                assert result == []

    def test_turn_off_light_module_function(self, mock_session, mock_response):
        """Test module-level turn_off_light function."""
        import src.homeassistant as ha_module
        ha_module._default_client = None

        mock_session.request.return_value = mock_response(
            status_code=200,
            json_data=[]
        )

        with patch.object(ha_module, 'HA_URL', 'http://localhost:8123'):
            with patch.object(ha_module, 'HA_TOKEN', 'test-token'):
                result = turn_off_light("light.test", transition=2.0)

                assert result == []
