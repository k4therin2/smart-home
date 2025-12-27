"""
Tests for src/ha_client.py - Home Assistant Client

Tests Home Assistant REST API client including connection handling,
state queries, service calls, and error scenarios.
"""

import pytest
import responses
from requests.exceptions import ConnectionError, Timeout


class TestHomeAssistantClientInit:
    """Test HomeAssistantClient initialization."""

    def test_client_uses_config_defaults(self, mock_ha_api):
        """Client should use config values when not specified."""
        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        assert "test-ha.local:8123" in client.url
        assert client.token == "test-ha-token"

    def test_client_uses_custom_url(self, mock_ha_api):
        """Client should accept custom URL."""
        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient(url="http://custom:9123")
        assert client.url == "http://custom:9123"

    def test_client_strips_trailing_slash(self, mock_ha_api):
        """Client should strip trailing slash from URL."""
        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient(url="http://test:8123/")
        assert client.url == "http://test:8123"

    def test_client_sets_auth_header(self, mock_ha_api):
        """Client should set Bearer token in headers."""
        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient(token="my-token")
        assert client.headers["Authorization"] == "Bearer my-token"


class TestConnectionCheck:
    """Test Home Assistant connection checking."""

    def test_check_connection_success(self, mock_ha_api):
        """Should return True when HA is reachable."""
        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        assert client.check_connection() is True

    def test_check_connection_failure_no_message(self, mock_ha_api):
        """Should return False when response lacks message field."""
        mock_ha_api.replace(
            responses.GET,
            "http://test-ha.local:8123/api/",
            json={"error": "unauthorized"},
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        assert client.check_connection() is False

    def test_check_connection_timeout(self, mock_ha_api):
        """Should return False on connection timeout."""
        mock_ha_api.replace(
            responses.GET,
            "http://test-ha.local:8123/api/",
            body=Timeout("Connection timed out"),
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        assert client.check_connection() is False

    def test_check_connection_refused(self, mock_ha_api):
        """Should return False when connection is refused."""
        mock_ha_api.replace(
            responses.GET,
            "http://test-ha.local:8123/api/",
            body=ConnectionError("Connection refused"),
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        assert client.check_connection() is False


class TestGetState:
    """Test entity state retrieval."""

    def test_get_state_success(self, ha_client, mock_ha_full):
        """Should return state dict for existing entity."""
        state = ha_client.get_state("light.living_room")

        assert state is not None
        assert state["entity_id"] == "light.living_room"
        assert state["state"] == "on"

    def test_get_state_with_attributes(self, ha_client, mock_ha_full):
        """Should include attributes in state response."""
        state = ha_client.get_state("light.living_room")

        assert "attributes" in state
        assert state["attributes"]["brightness"] == 255

    def test_get_state_not_found(self, ha_client, mock_ha_full):
        """Should return None for nonexistent entity."""
        mock_ha_full.add(
            responses.GET,
            "http://test-ha.local:8123/api/states/light.nonexistent",
            json={"message": "Entity not found"},
            status=404,
        )

        state = ha_client.get_state("light.nonexistent")
        assert state is None


class TestGetAllStates:
    """Test bulk state retrieval."""

    def test_get_all_states(self, ha_client, mock_ha_full):
        """Should return list of all entity states."""
        states = ha_client.get_all_states()

        assert isinstance(states, list)
        assert len(states) > 0

        entity_ids = [s["entity_id"] for s in states]
        assert "light.living_room" in entity_ids

    def test_get_all_states_empty(self, mock_ha_api):
        """Should return empty list when no entities."""
        mock_ha_api.add(
            responses.GET,
            "http://test-ha.local:8123/api/states",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient
        from src.cache import get_cache

        # Clear cache to ensure isolation from previous tests
        cache = get_cache()
        cache.clear()

        client = HomeAssistantClient()
        states = client.get_all_states()
        assert states == []


class TestCallService:
    """Test service call functionality."""

    def test_call_service_success(self, ha_client, mock_ha_full):
        """Should return True on successful service call."""
        result = ha_client.call_service(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.living_room"},
        )

        assert result is True

    def test_call_service_with_target(self, mock_ha_api):
        """Should include target in service data."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[{"entity_id": "light.test"}],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        result = client.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.test"},
        )

        assert result is True
        # Verify request body
        request = mock_ha_api.calls[-1].request
        assert b"light.test" in request.body

    def test_call_service_failure(self, mock_ha_api):
        """Should return False on service call failure."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json={"message": "Service not found"},
            status=400,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        result = client.call_service("light", "turn_on")
        assert result is False


class TestLightControls:
    """Test light-specific control methods."""

    def test_turn_on_light_simple(self, ha_client, mock_ha_full):
        """Should turn on light with just entity_id."""
        result = ha_client.turn_on_light("light.living_room")
        assert result is True

    def test_turn_on_light_with_brightness(self, mock_ha_api):
        """Should include brightness_pct in service data."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_on_light("light.test", brightness_pct=75)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["brightness_pct"] == 75

    def test_turn_on_light_brightness_clamping(self, mock_ha_api):
        """Should clamp brightness to 0-100 range."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_on_light("light.test", brightness_pct=150)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["brightness_pct"] == 100  # Clamped to max

    def test_turn_on_light_with_color_temp(self, mock_ha_api):
        """Should convert Kelvin to mireds for color_temp."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_on_light("light.test", color_temp_kelvin=4000)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        # 4000K = 250 mireds
        assert body["color_temp"] == 250

    def test_turn_on_light_color_temp_clamping(self, mock_ha_api):
        """Should clamp color_temp mireds to valid range (153-500)."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        # 10000K = 100 mireds, below minimum
        client.turn_on_light("light.test", color_temp_kelvin=10000)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["color_temp"] == 153  # Clamped to min

    def test_turn_on_light_with_rgb(self, mock_ha_api):
        """Should include RGB color as list."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_on_light("light.test", rgb_color=(255, 128, 64))

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["rgb_color"] == [255, 128, 64]

    def test_turn_on_light_with_transition(self, mock_ha_api):
        """Should include transition time."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_on_light("light.test", transition=2.5)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["transition"] == 2.5

    def test_turn_off_light(self, ha_client, mock_ha_full):
        """Should turn off light."""
        result = ha_client.turn_off_light("light.living_room")
        assert result is True

    def test_turn_off_light_with_transition(self, mock_ha_api):
        """Should include transition when turning off."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_off",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.turn_off_light("light.test", transition=1.0)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["transition"] == 1.0

    def test_set_light_brightness(self, mock_ha_api):
        """Should set brightness via turn_on_light."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        result = client.set_light_brightness("light.test", 50)

        assert result is True


class TestHueSceneActivation:
    """Test Philips Hue scene activation."""

    def test_activate_hue_scene_basic(self, ha_client, mock_ha_full):
        """Should activate a Hue scene."""
        result = ha_client.activate_hue_scene("scene.living_room_arctic_aurora")
        assert result is True

    def test_activate_hue_scene_with_dynamic(self, mock_ha_api):
        """Should include dynamic flag in service data."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/hue/activate_scene",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.activate_hue_scene("scene.test", dynamic=True)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["dynamic"] is True

    def test_activate_hue_scene_with_speed(self, mock_ha_api):
        """Should include speed in service data."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/hue/activate_scene",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.activate_hue_scene("scene.test", speed=75)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["speed"] == 75

    def test_activate_hue_scene_speed_clamping(self, mock_ha_api):
        """Should clamp speed to 0-100."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/hue/activate_scene",
            json=[],
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        client.activate_hue_scene("scene.test", speed=150)

        request = mock_ha_api.calls[-1].request
        import json
        body = json.loads(request.body)
        assert body["speed"] == 100


class TestLightQueries:
    """Test light-specific query methods."""

    def test_get_lights(self, ha_client, mock_ha_full):
        """Should return only light entities."""
        lights = ha_client.get_lights()

        assert isinstance(lights, list)
        for light in lights:
            assert light["entity_id"].startswith("light.")

    def test_get_hue_scenes(self, ha_client, mock_ha_full):
        """Should return only scene entities."""
        scenes = ha_client.get_hue_scenes()

        assert isinstance(scenes, list)
        for scene in scenes:
            assert scene["entity_id"].startswith("scene.")

    def test_get_light_state(self, ha_client, mock_ha_full):
        """Should return formatted light state."""
        state = ha_client.get_light_state("light.living_room")

        assert state is not None
        assert state["entity_id"] == "light.living_room"
        assert state["state"] == "on"
        assert "brightness" in state
        assert "color_temp" in state
        assert "friendly_name" in state

    def test_get_light_state_not_found(self, ha_client, mock_ha_full):
        """Should return None for nonexistent light."""
        mock_ha_full.add(
            responses.GET,
            "http://test-ha.local:8123/api/states/light.nonexistent",
            json={"message": "Not found"},
            status=404,
        )

        state = ha_client.get_light_state("light.nonexistent")
        assert state is None


class TestErrorHandling:
    """Test error handling in HA client."""

    def test_http_401_unauthorized(self, mock_ha_api):
        """Should handle 401 unauthorized gracefully."""
        mock_ha_api.replace(
            responses.GET,
            "http://test-ha.local:8123/api/",
            json={"message": "Unauthorized"},
            status=401,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        result = client.check_connection()
        assert result is False

    def test_http_500_server_error(self, mock_ha_api):
        """Should handle 500 server error gracefully."""
        mock_ha_api.add(
            responses.GET,
            "http://test-ha.local:8123/api/states/light.test",
            json={"error": "Internal server error"},
            status=500,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        state = client.get_state("light.test")
        assert state is None

    def test_empty_response_body(self, mock_ha_api):
        """Should handle empty response body."""
        mock_ha_api.add(
            responses.POST,
            "http://test-ha.local:8123/api/services/light/turn_on",
            body="",
            status=200,
        )

        from src.ha_client import HomeAssistantClient

        client = HomeAssistantClient()
        # Should not raise, should return empty dict
        result = client.call_service("light", "turn_on")
        assert result is True


class TestSingletonClient:
    """Test singleton client pattern."""

    def test_get_ha_client_returns_same_instance(self, mock_ha_api):
        """Should return same client instance."""
        # Reset the singleton first
        import src.ha_client as ha_module
        ha_module._client = None

        from src.ha_client import get_ha_client

        client1 = get_ha_client()
        client2 = get_ha_client()

        assert client1 is client2

        # Clean up
        ha_module._client = None
