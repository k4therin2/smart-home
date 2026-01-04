"""
Smart Home Assistant - MQTT Integration Module

Provides MQTT broker connectivity for device discovery and control.
Supports Home Assistant MQTT discovery protocol.

WP-10.28: MQTT Support
"""

import json
import logging
import re
import time
import uuid
from typing import Any, Callable

import paho.mqtt.client as mqtt


logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class MQTTError(Exception):
    """Base exception for MQTT errors."""

    pass


class MQTTConnectionError(MQTTError):
    """Raised when connection to MQTT broker fails."""

    pass


class MQTTPublishError(MQTTError):
    """Raised when message publishing fails."""

    pass


# =============================================================================
# Topic Utilities
# =============================================================================


TOPIC_PREFIX = "smarthome"


def get_command_topic(device_type: str, device_id: str) -> str:
    """
    Generate command topic for a device.

    Args:
        device_type: Type of device (e.g., 'light', 'switch')
        device_id: Unique device identifier

    Returns:
        MQTT command topic string
    """
    return f"{TOPIC_PREFIX}/{device_type}/{device_id}/set"


def get_state_topic(device_type: str, device_id: str) -> str:
    """
    Generate state topic for a device.

    Args:
        device_type: Type of device (e.g., 'light', 'switch')
        device_id: Unique device identifier

    Returns:
        MQTT state topic string
    """
    return f"{TOPIC_PREFIX}/{device_type}/{device_id}/state"


def get_availability_topic(device_type: str, device_id: str) -> str:
    """
    Generate availability topic for a device.

    Args:
        device_type: Type of device (e.g., 'light', 'switch')
        device_id: Unique device identifier

    Returns:
        MQTT availability topic string
    """
    return f"{TOPIC_PREFIX}/{device_type}/{device_id}/availability"


def parse_topic(topic: str) -> dict[str, str]:
    """
    Parse an MQTT topic into its components.

    Args:
        topic: MQTT topic string

    Returns:
        Dictionary with topic components (prefix, device_type, device_id, action)
    """
    parts = topic.split("/")
    result = {
        "prefix": parts[0] if len(parts) > 0 else "",
        "device_type": parts[1] if len(parts) > 1 else "",
        "device_id": parts[2] if len(parts) > 2 else "",
        "action": parts[3] if len(parts) > 3 else "",
    }
    return result


def _topic_matches_pattern(topic: str, pattern: str) -> bool:
    """
    Check if a topic matches a subscription pattern.

    Supports MQTT wildcards:
    - + matches a single level
    - # matches multiple levels (at end only)

    Args:
        topic: Actual topic to check
        pattern: Subscription pattern with wildcards

    Returns:
        True if topic matches pattern
    """
    if pattern == topic:
        return True

    pattern_parts = pattern.split("/")
    topic_parts = topic.split("/")

    if "#" in pattern:
        # # matches everything after
        hash_idx = pattern_parts.index("#")
        if len(topic_parts) < hash_idx:
            return False
        return pattern_parts[:hash_idx] == topic_parts[:hash_idx]

    if len(pattern_parts) != len(topic_parts):
        return False

    for pattern_part, topic_part in zip(pattern_parts, topic_parts):
        if pattern_part == "+":
            continue
        if pattern_part != topic_part:
            return False

    return True


# =============================================================================
# MQTT Client
# =============================================================================


class MQTTClient:
    """
    Client for communicating with MQTT brokers.

    Supports:
    - Connection management with auto-reconnect
    - Publishing messages (string and JSON)
    - Subscribing to topics with callbacks
    - Home Assistant MQTT discovery protocol
    - Device state tracking
    """

    def __init__(
        self,
        broker_host: str | None = None,
        broker_port: int = 1883,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        keepalive: int = 60,
    ):
        """
        Initialize MQTT client.

        Args:
            broker_host: MQTT broker hostname or IP
            broker_port: MQTT broker port (default 1883)
            client_id: Client identifier (auto-generated if not provided)
            username: Optional username for authentication
            password: Optional password for authentication
            keepalive: Keepalive interval in seconds
        """
        if not broker_host:
            raise MQTTError("Broker host not configured")

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id or f"smarthome-{uuid.uuid4().hex[:8]}"
        self.username = username
        self.password = password
        self.keepalive = keepalive

        # Reconnection settings
        self.max_reconnect_attempts = 5
        self._reconnect_count = 0
        self._reconnect_delay = 5  # seconds

        # Internal state
        self._topic_callbacks: dict[str, Callable] = {}
        self._discovered_devices: dict[str, dict] = {}
        self._device_states: dict[str, dict] = {}
        self._discovery_active = False

        # Create Paho MQTT client
        self._client = mqtt.Client(
            client_id=self.client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # Set up callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        logger.debug(f"Initialized MQTT client: {self.client_id}")

    def connect(self) -> bool:
        """
        Connect to the MQTT broker.

        Returns:
            True on successful connection

        Raises:
            MQTTConnectionError: If connection fails
        """
        try:
            # Set credentials if provided
            if self.username:
                self._client.username_pw_set(self.username, self.password)

            self._client.connect(
                self.broker_host,
                self.broker_port,
                keepalive=self.keepalive,
            )
            self._client.loop_start()

            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            return True

        except Exception as error:
            logger.error(f"Failed to connect to MQTT broker: {error}")
            raise MQTTConnectionError(f"Failed to connect to {self.broker_host}: {error}") from error

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("Disconnected from MQTT broker")
        except Exception as error:
            logger.warning(f"Error during disconnect: {error}")

    def is_connected(self) -> bool:
        """
        Check if client is connected to broker.

        Returns:
            True if connected
        """
        return self._client.is_connected()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    # -------------------------------------------------------------------------
    # Publishing
    # -------------------------------------------------------------------------

    def publish(
        self,
        topic: str,
        payload: str,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """
        Publish a message to a topic.

        Args:
            topic: MQTT topic
            payload: Message payload (string)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message

        Returns:
            True on successful publish

        Raises:
            MQTTError: If not connected
            MQTTPublishError: If publish fails
        """
        if not self.is_connected():
            raise MQTTError("Not connected to MQTT broker")

        try:
            result = self._client.publish(topic, payload, qos=qos, retain=retain)

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise MQTTPublishError(f"Publish failed with code {result.rc}")

            logger.debug(f"Published to {topic}: {payload[:100]}...")
            return True

        except MQTTError:
            raise
        except Exception as error:
            logger.error(f"Publish error: {error}")
            raise MQTTPublishError(f"Failed to publish to {topic}: {error}") from error

    def publish_json(
        self,
        topic: str,
        data: dict,
        qos: int = 0,
        retain: bool = False,
    ) -> bool:
        """
        Publish a JSON message to a topic.

        Args:
            topic: MQTT topic
            data: Dictionary to serialize as JSON
            qos: Quality of Service level
            retain: Whether to retain the message

        Returns:
            True on successful publish
        """
        payload = json.dumps(data)
        return self.publish(topic, payload, qos=qos, retain=retain)

    # -------------------------------------------------------------------------
    # Subscribing
    # -------------------------------------------------------------------------

    def subscribe(
        self,
        topic: str,
        qos: int = 0,
        callback: Callable | None = None,
    ) -> bool:
        """
        Subscribe to a topic.

        Args:
            topic: MQTT topic (supports wildcards + and #)
            qos: Quality of Service level
            callback: Optional callback function(topic, payload)

        Returns:
            True on successful subscription
        """
        result, mid = self._client.subscribe(topic, qos=qos)

        if callback:
            self._topic_callbacks[topic] = callback

        logger.debug(f"Subscribed to {topic} with QoS {qos}")
        return result == mqtt.MQTT_ERR_SUCCESS

    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic.

        Args:
            topic: MQTT topic

        Returns:
            True on successful unsubscription
        """
        self._client.unsubscribe(topic)

        if topic in self._topic_callbacks:
            del self._topic_callbacks[topic]

        logger.debug(f"Unsubscribed from {topic}")
        return True

    # -------------------------------------------------------------------------
    # Device Discovery
    # -------------------------------------------------------------------------

    def start_device_discovery(self) -> None:
        """
        Start listening for Home Assistant MQTT discovery messages.

        Subscribes to the homeassistant/# discovery topic.
        """
        self._discovery_active = True
        self.subscribe("homeassistant/#", callback=self._handle_discovery_message)
        logger.info("Started MQTT device discovery")

    def stop_device_discovery(self) -> None:
        """Stop device discovery."""
        self._discovery_active = False
        self.unsubscribe("homeassistant/#")
        logger.info("Stopped MQTT device discovery")

    def get_discovered_devices(self) -> list[dict]:
        """
        Get list of discovered devices.

        Returns:
            List of device configuration dictionaries
        """
        return list(self._discovered_devices.values())

    def _handle_discovery_message(self, topic: str, payload: Any) -> None:
        """Handle a Home Assistant discovery message."""
        if not isinstance(payload, dict):
            return

        # Extract device info from topic
        # Format: homeassistant/<component>/<node_id>/<object_id>/config
        topic_parts = topic.split("/")
        if len(topic_parts) < 4 or topic_parts[-1] != "config":
            return

        device_id = payload.get("unique_id") or f"{topic_parts[1]}_{topic_parts[2]}"
        self._discovered_devices[device_id] = payload

        # Subscribe to state topic if present
        if "state_topic" in payload:
            self.subscribe(
                payload["state_topic"],
                callback=lambda t, p: self._update_device_state(device_id, p),
            )

        logger.info(f"Discovered device: {payload.get('name', device_id)}")

    # -------------------------------------------------------------------------
    # Device Control
    # -------------------------------------------------------------------------

    def set_device_state(self, device_id: str, state: dict) -> bool:
        """
        Set device state via MQTT.

        Args:
            device_id: Device unique identifier
            state: State dictionary to send

        Returns:
            True on successful publish

        Raises:
            MQTTError: If device not found
        """
        if device_id not in self._discovered_devices:
            raise MQTTError(f"Unknown device: {device_id}")

        device = self._discovered_devices[device_id]
        command_topic = device.get("command_topic")

        if not command_topic:
            raise MQTTError(f"Device {device_id} has no command topic")

        return self.publish_json(command_topic, state)

    def get_device_state(self, device_id: str) -> dict | None:
        """
        Get cached device state.

        Args:
            device_id: Device unique identifier

        Returns:
            State dictionary or None if not available
        """
        return self._device_states.get(device_id)

    def _update_device_state(self, device_id: str, state: Any) -> None:
        """Update cached device state."""
        if isinstance(state, dict):
            self._device_states[device_id] = state
        else:
            self._device_states[device_id] = {"state": state}

        logger.debug(f"Updated state for {device_id}: {state}")

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Handle connection established."""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self._reconnect_count = 0
        else:
            logger.warning(f"Connection failed with code: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """Handle disconnection."""
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")

        # Attempt reconnection if unexpected disconnect
        if reason_code != 0:
            self._attempt_reconnect()

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to the broker."""
        self._reconnect_count += 1

        if self._reconnect_count > self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return

        try:
            logger.info(f"Attempting reconnection ({self._reconnect_count}/{self.max_reconnect_attempts})")
            time.sleep(self._reconnect_delay)
            self._client.reconnect()
        except Exception as error:
            logger.error(f"Reconnection failed: {error}")

    def _on_message(self, client, userdata, message):
        """Handle incoming message."""
        topic = message.topic
        try:
            # Try to parse as JSON
            payload = json.loads(message.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = message.payload.decode()

        logger.debug(f"Received message on {topic}")

        # Find matching callbacks (copy dict to avoid modification during iteration)
        callbacks_to_invoke = []
        for pattern, callback in list(self._topic_callbacks.items()):
            if _topic_matches_pattern(topic, pattern):
                callbacks_to_invoke.append(callback)

        # Invoke callbacks outside the iteration
        for callback in callbacks_to_invoke:
            try:
                callback(topic, payload)
            except Exception as error:
                logger.error(f"Callback error for {topic}: {error}")


# =============================================================================
# Module-level convenience functions
# =============================================================================


_default_client: MQTTClient | None = None


def get_client() -> MQTTClient:
    """
    Get or create the default MQTT client.

    Uses environment variables for configuration:
    - MQTT_BROKER_HOST
    - MQTT_BROKER_PORT
    - MQTT_USERNAME
    - MQTT_PASSWORD

    Returns:
        MQTTClient instance
    """
    import os

    global _default_client
    if _default_client is None:
        _default_client = MQTTClient(
            broker_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
            broker_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
        )
    return _default_client
