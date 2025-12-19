"""
Unit tests for HueBridgeClient.

Tests the Philips Hue Bridge v2 API client including
room management and device mapping.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, Mock
from urllib.error import HTTPError, URLError

from src.hue_bridge import (
    HueBridgeClient,
    HueBridgeError,
    HueRoom,
    get_hue_bridge_client,
    HUE_ROOM_ARCHETYPES,
)


class TestHueBridgeClientInitialization:
    """Tests for HueBridgeClient initialization."""

    def test_create_client_with_env_vars(self, monkeypatch):
        """Client should read config from environment variables."""
        monkeypatch.setenv("HUE_BRIDGE_IP", "192.168.1.100")
        monkeypatch.setenv("HUE_BRIDGE_KEY", "test-api-key")

        client = HueBridgeClient()

        assert client.bridge_ip == "192.168.1.100"
        assert client.application_key == "test-api-key"

    def test_create_client_with_explicit_params(self):
        """Client should accept explicit parameters."""
        client = HueBridgeClient(
            bridge_ip="10.0.0.1",
            application_key="explicit-key",
        )

        assert client.bridge_ip == "10.0.0.1"
        assert client.application_key == "explicit-key"

    def test_base_url_format(self):
        """Base URL should use HTTPS and API v2 path."""
        client = HueBridgeClient(bridge_ip="192.168.1.1", application_key="key")

        assert client.base_url == "https://192.168.1.1/clip/v2"

    def test_is_configured_true(self):
        """is_configured should return True when both values set."""
        client = HueBridgeClient(bridge_ip="192.168.1.1", application_key="key")
        assert client.is_configured() is True

    def test_is_configured_false_missing_ip(self):
        """is_configured should return False when IP missing."""
        client = HueBridgeClient(bridge_ip=None, application_key="key")
        assert client.is_configured() is False

    def test_is_configured_false_missing_key(self):
        """is_configured should return False when key missing."""
        client = HueBridgeClient(bridge_ip="192.168.1.1", application_key=None)
        assert client.is_configured() is False


class TestMakeRequest:
    """Tests for HTTP request handling."""

    @pytest.fixture
    def configured_client(self):
        """Create a configured client."""
        return HueBridgeClient(
            bridge_ip="192.168.1.1",
            application_key="test-key",
        )

    def test_request_includes_auth_header(self, configured_client):
        """Request should include hue-application-key header."""
        with patch("src.hue_bridge.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b'{"data": []}'
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            configured_client._make_request("GET", "/resource/room")

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_header("Hue-application-key") == "test-key"

    def test_request_not_configured_raises(self):
        """Request should raise when not configured."""
        client = HueBridgeClient(bridge_ip=None, application_key=None)

        with pytest.raises(HueBridgeError, match="not configured"):
            client._make_request("GET", "/resource/room")

    def test_http_error_wrapped(self, configured_client):
        """HTTP errors should be wrapped in HueBridgeError."""
        with patch("src.hue_bridge.urlopen") as mock_urlopen:
            error = HTTPError(
                url="https://test",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=MagicMock(read=lambda: b'{"error": "invalid key"}'),
            )
            mock_urlopen.side_effect = error

            with pytest.raises(HueBridgeError, match="API error 401"):
                configured_client._make_request("GET", "/resource/room")

    def test_url_error_wrapped(self, configured_client):
        """URL errors should be wrapped in HueBridgeError."""
        with patch("src.hue_bridge.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = URLError("Connection refused")

            with pytest.raises(HueBridgeError, match="Connection failed"):
                configured_client._make_request("GET", "/resource/room")


class TestDeviceDiscovery:
    """Tests for device discovery methods."""

    @pytest.fixture
    def client_with_mock(self):
        """Create a client with mocked requests."""
        client = HueBridgeClient(
            bridge_ip="192.168.1.1",
            application_key="test-key",
        )
        return client

    def test_get_devices(self, client_with_mock):
        """Should return list of devices."""
        mock_response = {
            "data": [
                {"id": "device-1", "metadata": {"name": "Living Room Lamp"}},
                {"id": "device-2", "metadata": {"name": "Bedroom Light"}},
            ]
        }

        with patch.object(client_with_mock, "_make_request", return_value=mock_response):
            devices = client_with_mock.get_devices()

        assert len(devices) == 2
        assert devices[0]["id"] == "device-1"

    def test_get_lights(self, client_with_mock):
        """Should return list of light resources."""
        mock_response = {
            "data": [
                {"id": "light-1", "on": {"on": True}},
            ]
        }

        with patch.object(client_with_mock, "_make_request", return_value=mock_response):
            lights = client_with_mock.get_lights()

        assert len(lights) == 1
        assert lights[0]["id"] == "light-1"

    def test_find_device_by_name_found(self, client_with_mock):
        """Should find device by partial name match."""
        mock_devices = [
            {"id": "device-1", "metadata": {"name": "Living Room Lamp"}},
            {"id": "device-2", "metadata": {"name": "Bedroom Light"}},
        ]

        with patch.object(client_with_mock, "get_devices", return_value=mock_devices):
            device = client_with_mock.find_device_by_name("living room")

        assert device is not None
        assert device["id"] == "device-1"

    def test_find_device_by_name_not_found(self, client_with_mock):
        """Should return None when device not found."""
        mock_devices = [
            {"id": "device-1", "metadata": {"name": "Living Room Lamp"}},
        ]

        with patch.object(client_with_mock, "get_devices", return_value=mock_devices):
            device = client_with_mock.find_device_by_name("kitchen")

        assert device is None

    def test_get_device_id_from_ha_entity(self, client_with_mock):
        """Should map HA entity ID to Hue device ID."""
        mock_device = {"id": "hue-uuid-123", "metadata": {"name": "Living Room Lamp"}}

        with patch.object(client_with_mock, "find_device_by_name", return_value=mock_device):
            device_id = client_with_mock.get_device_id_from_ha_entity("light.living_room_lamp")

        assert device_id == "hue-uuid-123"


class TestRoomManagement:
    """Tests for room CRUD operations."""

    @pytest.fixture
    def client(self):
        """Create a configured client."""
        return HueBridgeClient(
            bridge_ip="192.168.1.1",
            application_key="test-key",
        )

    def test_get_rooms(self, client):
        """Should return list of HueRoom objects."""
        mock_response = {
            "data": [
                {
                    "id": "room-1",
                    "metadata": {"name": "Living Room", "archetype": "living_room"},
                    "children": [{"rid": "device-1"}, {"rid": "device-2"}],
                },
            ]
        }

        with patch.object(client, "_make_request", return_value=mock_response):
            rooms = client.get_rooms()

        assert len(rooms) == 1
        assert rooms[0].id == "room-1"
        assert rooms[0].name == "Living Room"
        assert rooms[0].archetype == "living_room"
        assert len(rooms[0].children) == 2

    def test_find_room_by_name_found(self, client):
        """Should find room by name match."""
        mock_rooms = [
            HueRoom(id="room-1", name="Living Room", archetype="living_room", children=[]),
            HueRoom(id="room-2", name="Bedroom", archetype="bedroom", children=[]),
        ]

        with patch.object(client, "get_rooms", return_value=mock_rooms):
            room = client.find_room_by_name("living_room")

        assert room is not None
        assert room.id == "room-1"

    def test_find_room_by_name_not_found(self, client):
        """Should return None when room not found."""
        mock_rooms = [
            HueRoom(id="room-1", name="Living Room", archetype="living_room", children=[]),
        ]

        with patch.object(client, "get_rooms", return_value=mock_rooms):
            room = client.find_room_by_name("kitchen")

        assert room is None

    def test_create_room(self, client):
        """Should create room with correct payload."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"data": [{"id": "new-room-id"}]}

            result = client.create_room("living_room", ["device-1", "device-2"])

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/resource/room"

        payload = call_args[0][2]
        assert payload["metadata"]["name"] == "Living Room"
        assert payload["metadata"]["archetype"] == "living_room"
        assert len(payload["children"]) == 2

    def test_create_room_uses_archetype_mapping(self, client):
        """Should use correct archetype from mapping."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"data": [{"id": "new-room-id"}]}

            client.create_room("dining_room", ["device-1"])

        payload = mock_request.call_args[0][2]
        assert payload["metadata"]["archetype"] == "dining"

    def test_update_room(self, client):
        """Should update room with PUT request."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"data": []}

            client.update_room("room-id", device_ids=["device-1"], name="New Name")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "PUT"
        assert "/resource/room/room-id" in call_args[0][1]

    def test_add_devices_to_room(self, client):
        """Should merge device lists when adding to room."""
        existing_room = HueRoom(
            id="room-1",
            name="Living Room",
            archetype="living_room",
            children=["device-1"],
        )

        with patch.object(client, "get_rooms", return_value=[existing_room]):
            with patch.object(client, "update_room") as mock_update:
                client.add_devices_to_room("room-1", ["device-2", "device-3"])

        # Should have all three devices
        call_args = mock_update.call_args
        device_ids = call_args[1]["device_ids"]
        assert set(device_ids) == {"device-1", "device-2", "device-3"}

    def test_add_devices_to_nonexistent_room_raises(self, client):
        """Should raise error when room not found."""
        with patch.object(client, "get_rooms", return_value=[]):
            with pytest.raises(HueBridgeError, match="not found"):
                client.add_devices_to_room("nonexistent", ["device-1"])

    def test_delete_room(self, client):
        """Should delete room with DELETE request."""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"data": []}

            client.delete_room("room-id")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "DELETE"
        assert "/resource/room/room-id" in call_args[0][1]


class TestSyncRoomsFromMappings:
    """Tests for the main sync operation."""

    @pytest.fixture
    def client(self):
        """Create a configured client."""
        return HueBridgeClient(
            bridge_ip="192.168.1.1",
            application_key="test-key",
        )

    def test_sync_not_configured(self):
        """Should return error when not configured."""
        client = HueBridgeClient(bridge_ip=None, application_key=None)

        result = client.sync_rooms_from_mappings([
            {"entity_id": "light.test", "room_name": "bedroom"},
        ])

        assert result["success"] is False
        assert "not configured" in result["error"]

    def test_sync_creates_new_room(self, client):
        """Should create room when it doesn't exist."""
        mappings = [
            {"entity_id": "light.bedroom_lamp", "room_name": "bedroom"},
        ]

        with patch.object(client, "get_device_id_from_ha_entity", return_value="device-1"):
            with patch.object(client, "find_room_by_name", return_value=None):
                with patch.object(client, "create_room") as mock_create:
                    result = client.sync_rooms_from_mappings(mappings)

        assert result["success"] is True
        assert result["created"] == 1
        mock_create.assert_called_once()

    def test_sync_updates_existing_room(self, client):
        """Should add devices to existing room."""
        existing_room = HueRoom(
            id="room-1",
            name="Bedroom",
            archetype="bedroom",
            children=[],
        )
        mappings = [
            {"entity_id": "light.bedroom_lamp", "room_name": "bedroom"},
        ]

        with patch.object(client, "get_device_id_from_ha_entity", return_value="device-1"):
            with patch.object(client, "find_room_by_name", return_value=existing_room):
                with patch.object(client, "add_devices_to_room") as mock_add:
                    result = client.sync_rooms_from_mappings(mappings)

        assert result["success"] is True
        assert result["updated"] == 1
        mock_add.assert_called_once()

    def test_sync_tracks_unmapped_entities(self, client):
        """Should track entities that couldn't be mapped."""
        mappings = [
            {"entity_id": "light.unknown_lamp", "room_name": "bedroom"},
        ]

        with patch.object(client, "get_device_id_from_ha_entity", return_value=None):
            result = client.sync_rooms_from_mappings(mappings)

        assert "light.unknown_lamp" in result["unmapped"]

    def test_sync_handles_api_errors(self, client):
        """Should handle API errors gracefully."""
        mappings = [
            {"entity_id": "light.bedroom_lamp", "room_name": "bedroom"},
        ]

        with patch.object(client, "get_device_id_from_ha_entity", return_value="device-1"):
            with patch.object(client, "find_room_by_name", return_value=None):
                with patch.object(client, "create_room", side_effect=HueBridgeError("API error")):
                    result = client.sync_rooms_from_mappings(mappings)

        assert result["success"] is False
        assert len(result["errors"]) == 1


class TestHueRoomArchetypes:
    """Tests for room archetype mapping."""

    def test_living_room_archetype(self):
        """Living room should map correctly."""
        assert HUE_ROOM_ARCHETYPES["living_room"] == "living_room"

    def test_dining_room_archetype(self):
        """Dining room should map to 'dining'."""
        assert HUE_ROOM_ARCHETYPES["dining_room"] == "dining"

    def test_laundry_archetype(self):
        """Laundry should map to 'laundry_room'."""
        assert HUE_ROOM_ARCHETYPES["laundry"] == "laundry_room"

    def test_other_archetype_fallback(self):
        """Unknown rooms should use 'other'."""
        assert HUE_ROOM_ARCHETYPES["other"] == "other"


class TestSingletonPattern:
    """Tests for the singleton getter."""

    def test_get_hue_bridge_client_returns_instance(self, monkeypatch):
        """Should return a HueBridgeClient instance."""
        # Reset singleton
        import src.hue_bridge
        src.hue_bridge._hue_bridge_client = None

        monkeypatch.setenv("HUE_BRIDGE_IP", "192.168.1.1")
        monkeypatch.setenv("HUE_BRIDGE_KEY", "test-key")

        client = get_hue_bridge_client()

        assert isinstance(client, HueBridgeClient)

        # Cleanup
        src.hue_bridge._hue_bridge_client = None

    def test_get_hue_bridge_client_returns_same_instance(self, monkeypatch):
        """Should return the same instance on repeated calls."""
        import src.hue_bridge
        src.hue_bridge._hue_bridge_client = None

        monkeypatch.setenv("HUE_BRIDGE_IP", "192.168.1.1")
        monkeypatch.setenv("HUE_BRIDGE_KEY", "test-key")

        client1 = get_hue_bridge_client()
        client2 = get_hue_bridge_client()

        assert client1 is client2

        # Cleanup
        src.hue_bridge._hue_bridge_client = None
