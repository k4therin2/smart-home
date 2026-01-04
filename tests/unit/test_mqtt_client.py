"""
Tests for src/mqtt_client.py - MQTT Integration Module

These tests cover the MQTTClient class for communicating with
MQTT brokers for device discovery and control.

WP-10.28: MQTT Support
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import json


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_paho_client():
    """Create a mock Paho MQTT client."""
    with patch('src.mqtt_client.mqtt.Client') as MockClient:
        client = MagicMock()
        client.connect.return_value = 0
        client.disconnect.return_value = 0
        client.loop_start.return_value = None
        client.loop_stop.return_value = None
        client.subscribe.return_value = (0, 1)
        client.publish.return_value = MagicMock(rc=0, mid=1)
        client.is_connected.return_value = True
        MockClient.return_value = client
        yield client


@pytest.fixture
def mqtt_client(mock_paho_client):
    """Create an MQTTClient with mocked Paho client."""
    from src.mqtt_client import MQTTClient
    return MQTTClient(
        broker_host="localhost",
        broker_port=1883,
        client_id="test-smarthome-client"
    )


# =============================================================================
# MQTTClient Initialization Tests
# =============================================================================


class TestMQTTClientInit:
    """Tests for MQTTClient initialization."""

    def test_init_with_valid_params(self, mock_paho_client):
        """Test successful initialization with valid parameters."""
        from src.mqtt_client import MQTTClient

        client = MQTTClient(
            broker_host="localhost",
            broker_port=1883,
            client_id="test-client"
        )

        assert client.broker_host == "localhost"
        assert client.broker_port == 1883
        assert client.client_id == "test-client"

    def test_init_uses_default_port(self, mock_paho_client):
        """Test that default MQTT port 1883 is used if not specified."""
        from src.mqtt_client import MQTTClient

        client = MQTTClient(broker_host="localhost")

        assert client.broker_port == 1883

    def test_init_generates_client_id_if_not_provided(self, mock_paho_client):
        """Test that a client ID is auto-generated if not provided."""
        from src.mqtt_client import MQTTClient

        client = MQTTClient(broker_host="localhost")

        assert client.client_id is not None
        assert client.client_id.startswith("smarthome-")

    def test_init_without_host_raises_error(self, mock_paho_client):
        """Test that missing broker host raises MQTTError."""
        from src.mqtt_client import MQTTClient, MQTTError

        with pytest.raises(MQTTError, match="Broker host not configured"):
            MQTTClient(broker_host=None)


# =============================================================================
# Connection Tests
# =============================================================================


class TestMQTTClientConnection:
    """Tests for MQTT connection management."""

    def test_connect_success(self, mqtt_client, mock_paho_client):
        """Test successful connection to broker."""
        result = mqtt_client.connect()

        assert result is True
        mock_paho_client.connect.assert_called_once_with(
            "localhost", 1883, keepalive=60
        )
        mock_paho_client.loop_start.assert_called_once()

    def test_connect_with_credentials(self, mock_paho_client):
        """Test connection with username and password."""
        from src.mqtt_client import MQTTClient

        client = MQTTClient(
            broker_host="localhost",
            username="user",
            password="secret"
        )
        client.connect()

        mock_paho_client.username_pw_set.assert_called_once_with("user", "secret")
        mock_paho_client.connect.assert_called_once()

    def test_connect_failure_raises_error(self, mqtt_client, mock_paho_client):
        """Test that connection failure raises MQTTConnectionError."""
        from src.mqtt_client import MQTTConnectionError

        mock_paho_client.connect.side_effect = Exception("Connection refused")

        with pytest.raises(MQTTConnectionError, match="Failed to connect"):
            mqtt_client.connect()

    def test_disconnect(self, mqtt_client, mock_paho_client):
        """Test disconnection from broker."""
        mqtt_client.connect()
        mqtt_client.disconnect()

        mock_paho_client.loop_stop.assert_called_once()
        mock_paho_client.disconnect.assert_called_once()

    def test_is_connected(self, mqtt_client, mock_paho_client):
        """Test connection status check."""
        mock_paho_client.is_connected.return_value = True

        assert mqtt_client.is_connected() is True
        mock_paho_client.is_connected.assert_called_once()

    def test_context_manager(self, mock_paho_client):
        """Test that client can be used as context manager."""
        from src.mqtt_client import MQTTClient

        with MQTTClient(broker_host="localhost") as client:
            assert client is not None
            mock_paho_client.connect.assert_called_once()

        mock_paho_client.disconnect.assert_called_once()


# =============================================================================
# Publishing Tests
# =============================================================================


class TestMQTTClientPublish:
    """Tests for MQTT message publishing."""

    def test_publish_string_message(self, mqtt_client, mock_paho_client):
        """Test publishing a string message."""
        mqtt_client.connect()
        result = mqtt_client.publish("smarthome/test", "Hello World")

        assert result is True
        mock_paho_client.publish.assert_called_once()
        args, kwargs = mock_paho_client.publish.call_args
        assert args[0] == "smarthome/test"
        assert args[1] == "Hello World"

    def test_publish_json_message(self, mqtt_client, mock_paho_client):
        """Test publishing a JSON message."""
        mqtt_client.connect()
        data = {"state": "on", "brightness": 100}
        result = mqtt_client.publish_json("smarthome/light/set", data)

        assert result is True
        mock_paho_client.publish.assert_called_once()
        args, kwargs = mock_paho_client.publish.call_args
        assert args[0] == "smarthome/light/set"
        # Verify JSON payload
        payload = args[1]
        assert json.loads(payload) == data

    def test_publish_with_qos(self, mqtt_client, mock_paho_client):
        """Test publishing with specific QoS level."""
        mqtt_client.connect()
        mqtt_client.publish("smarthome/test", "message", qos=2)

        args, kwargs = mock_paho_client.publish.call_args
        assert kwargs.get("qos") == 2

    def test_publish_retained_message(self, mqtt_client, mock_paho_client):
        """Test publishing a retained message."""
        mqtt_client.connect()
        mqtt_client.publish("smarthome/test", "message", retain=True)

        args, kwargs = mock_paho_client.publish.call_args
        assert kwargs.get("retain") is True

    def test_publish_when_disconnected_raises_error(self, mqtt_client, mock_paho_client):
        """Test that publishing when disconnected raises error."""
        from src.mqtt_client import MQTTError

        mock_paho_client.is_connected.return_value = False

        with pytest.raises(MQTTError, match="Not connected"):
            mqtt_client.publish("smarthome/test", "message")


# =============================================================================
# Subscription Tests
# =============================================================================


class TestMQTTClientSubscribe:
    """Tests for MQTT topic subscription."""

    def test_subscribe_single_topic(self, mqtt_client, mock_paho_client):
        """Test subscribing to a single topic."""
        mqtt_client.connect()
        result = mqtt_client.subscribe("smarthome/+/state")

        assert result is True
        mock_paho_client.subscribe.assert_called_once_with("smarthome/+/state", qos=0)

    def test_subscribe_with_qos(self, mqtt_client, mock_paho_client):
        """Test subscribing with specific QoS level."""
        mqtt_client.connect()
        mqtt_client.subscribe("smarthome/test", qos=1)

        mock_paho_client.subscribe.assert_called_with("smarthome/test", qos=1)

    def test_subscribe_with_callback(self, mqtt_client, mock_paho_client):
        """Test subscribing with a message callback."""
        mqtt_client.connect()
        callback = Mock()
        mqtt_client.subscribe("smarthome/test", callback=callback)

        # Verify callback is registered
        assert "smarthome/test" in mqtt_client._topic_callbacks
        assert mqtt_client._topic_callbacks["smarthome/test"] == callback

    def test_unsubscribe(self, mqtt_client, mock_paho_client):
        """Test unsubscribing from a topic."""
        mqtt_client.connect()
        mqtt_client.subscribe("smarthome/test")
        mqtt_client.unsubscribe("smarthome/test")

        mock_paho_client.unsubscribe.assert_called_once_with("smarthome/test")


# =============================================================================
# Message Handling Tests
# =============================================================================


class TestMQTTClientMessageHandling:
    """Tests for MQTT message handling."""

    def test_on_message_callback_invoked(self, mqtt_client, mock_paho_client):
        """Test that message callbacks are invoked."""
        mqtt_client.connect()
        callback = Mock()
        mqtt_client.subscribe("smarthome/light/state", callback=callback)

        # Simulate receiving a message
        mock_message = Mock()
        mock_message.topic = "smarthome/light/state"
        mock_message.payload = b'{"state": "on"}'

        mqtt_client._on_message(None, None, mock_message)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "smarthome/light/state"
        assert args[1] == {"state": "on"}

    def test_on_message_with_plain_text(self, mqtt_client, mock_paho_client):
        """Test handling plain text message payloads."""
        mqtt_client.connect()
        callback = Mock()
        mqtt_client.subscribe("smarthome/test", callback=callback)

        mock_message = Mock()
        mock_message.topic = "smarthome/test"
        mock_message.payload = b'plain text message'

        mqtt_client._on_message(None, None, mock_message)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[1] == "plain text message"

    def test_on_message_wildcard_matching(self, mqtt_client, mock_paho_client):
        """Test that wildcard subscriptions are matched."""
        mqtt_client.connect()
        callback = Mock()
        mqtt_client.subscribe("smarthome/+/state", callback=callback)

        mock_message = Mock()
        mock_message.topic = "smarthome/light123/state"
        mock_message.payload = b'{"state": "on"}'

        mqtt_client._on_message(None, None, mock_message)

        callback.assert_called_once()


# =============================================================================
# Device Discovery Tests
# =============================================================================


class TestMQTTClientDeviceDiscovery:
    """Tests for MQTT device discovery."""

    def test_discover_devices_subscribes_to_discovery_topic(self, mqtt_client, mock_paho_client):
        """Test that device discovery subscribes to discovery topic."""
        mqtt_client.connect()
        mqtt_client.start_device_discovery()

        # Should subscribe to Home Assistant discovery topic
        mock_paho_client.subscribe.assert_called()
        topics_subscribed = [call[0][0] for call in mock_paho_client.subscribe.call_args_list]
        assert any("homeassistant/" in topic for topic in topics_subscribed)

    def test_get_discovered_devices(self, mqtt_client, mock_paho_client):
        """Test retrieving discovered devices."""
        mqtt_client.connect()
        mqtt_client.start_device_discovery()

        # Simulate device discovery message
        discovery_payload = {
            "name": "Kitchen Light",
            "unique_id": "light_kitchen_001",
            "device": {
                "identifiers": ["kitchen_light_001"],
                "name": "Kitchen Light",
                "manufacturer": "SmartHome"
            },
            "command_topic": "smarthome/light/kitchen/set",
            "state_topic": "smarthome/light/kitchen/state"
        }

        mock_message = Mock()
        mock_message.topic = "homeassistant/light/kitchen_light/config"
        mock_message.payload = json.dumps(discovery_payload).encode()

        mqtt_client._on_message(None, None, mock_message)

        devices = mqtt_client.get_discovered_devices()
        assert len(devices) == 1
        assert devices[0]["name"] == "Kitchen Light"
        assert devices[0]["unique_id"] == "light_kitchen_001"

    def test_stop_device_discovery(self, mqtt_client, mock_paho_client):
        """Test stopping device discovery."""
        mqtt_client.connect()
        mqtt_client.start_device_discovery()
        mqtt_client.stop_device_discovery()

        mock_paho_client.unsubscribe.assert_called()


# =============================================================================
# Device Control Tests
# =============================================================================


class TestMQTTClientDeviceControl:
    """Tests for MQTT device control."""

    def test_set_device_state(self, mqtt_client, mock_paho_client):
        """Test setting device state via MQTT."""
        mqtt_client.connect()

        # Register a device with command topic
        mqtt_client._discovered_devices["light_kitchen"] = {
            "command_topic": "smarthome/light/kitchen/set",
            "state_topic": "smarthome/light/kitchen/state"
        }

        mqtt_client.set_device_state("light_kitchen", {"state": "on", "brightness": 100})

        mock_paho_client.publish.assert_called_once()
        args, kwargs = mock_paho_client.publish.call_args
        assert args[0] == "smarthome/light/kitchen/set"
        payload = json.loads(args[1])
        assert payload["state"] == "on"
        assert payload["brightness"] == 100

    def test_get_device_state(self, mqtt_client, mock_paho_client):
        """Test getting device state from MQTT."""
        mqtt_client.connect()

        # Register a device
        mqtt_client._discovered_devices["light_kitchen"] = {
            "command_topic": "smarthome/light/kitchen/set",
            "state_topic": "smarthome/light/kitchen/state"
        }
        mqtt_client._device_states["light_kitchen"] = {"state": "on", "brightness": 80}

        state = mqtt_client.get_device_state("light_kitchen")

        assert state["state"] == "on"
        assert state["brightness"] == 80

    def test_set_state_for_unknown_device_raises_error(self, mqtt_client, mock_paho_client):
        """Test that setting state for unknown device raises error."""
        from src.mqtt_client import MQTTError

        mqtt_client.connect()

        with pytest.raises(MQTTError, match="Unknown device"):
            mqtt_client.set_device_state("unknown_device", {"state": "on"})


# =============================================================================
# Topic Structure Tests
# =============================================================================


class TestMQTTTopicStructure:
    """Tests for MQTT topic structure and naming."""

    def test_get_command_topic(self, mqtt_client, mock_paho_client):
        """Test generating command topic for device type."""
        from src.mqtt_client import get_command_topic

        topic = get_command_topic("light", "living_room")
        assert topic == "smarthome/light/living_room/set"

    def test_get_state_topic(self, mqtt_client, mock_paho_client):
        """Test generating state topic for device type."""
        from src.mqtt_client import get_state_topic

        topic = get_state_topic("light", "living_room")
        assert topic == "smarthome/light/living_room/state"

    def test_get_availability_topic(self, mqtt_client, mock_paho_client):
        """Test generating availability topic."""
        from src.mqtt_client import get_availability_topic

        topic = get_availability_topic("light", "living_room")
        assert topic == "smarthome/light/living_room/availability"

    def test_parse_topic(self, mqtt_client, mock_paho_client):
        """Test parsing topic into components."""
        from src.mqtt_client import parse_topic

        result = parse_topic("smarthome/light/living_room/state")

        assert result["prefix"] == "smarthome"
        assert result["device_type"] == "light"
        assert result["device_id"] == "living_room"
        assert result["action"] == "state"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestMQTTClientErrors:
    """Tests for error handling."""

    def test_reconnect_on_disconnect(self, mqtt_client, mock_paho_client):
        """Test automatic reconnection on disconnect."""
        mqtt_client.connect()

        # Simulate unexpected disconnect
        mqtt_client._on_disconnect(None, None, 0, None)

        # Should attempt reconnection
        assert mqtt_client._reconnect_count >= 0

    def test_max_reconnect_attempts(self, mqtt_client, mock_paho_client):
        """Test that reconnection stops after max attempts."""
        from src.mqtt_client import MQTTConnectionError

        mqtt_client.connect()
        mock_paho_client.reconnect.side_effect = Exception("Connection refused")

        for _ in range(10):  # More than max attempts
            mqtt_client._on_disconnect(None, None, 1, None)

        # Should eventually give up
        assert mqtt_client._reconnect_count >= mqtt_client.max_reconnect_attempts
