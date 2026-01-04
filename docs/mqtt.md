# MQTT Integration

WP-10.28: MQTT Support for custom device integration.

## Overview

The Smart Home Assistant supports MQTT (Message Queuing Telemetry Transport) for integrating custom devices that aren't natively supported by Home Assistant. This enables:

- **Device Discovery**: Automatic detection of MQTT-based devices
- **State Tracking**: Real-time device state monitoring
- **Device Control**: Publish commands to control devices
- **Custom Integrations**: Connect DIY sensors and actuators

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# MQTT Broker Connection
MQTT_BROKER_HOST=localhost      # MQTT broker hostname
MQTT_BROKER_PORT=1883           # MQTT broker port (default: 1883)
MQTT_USERNAME=                  # Optional: MQTT username
MQTT_PASSWORD=                  # Optional: MQTT password
MQTT_TOPIC_PREFIX=smarthome     # Topic prefix for all messages
```

### Broker Setup

You need an MQTT broker running. Common options:

**1. Mosquitto (Recommended)**

Install on Ubuntu/Debian:
```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

**2. Home Assistant Add-on**

If using Home Assistant OS, install the "Mosquitto broker" add-on from the Add-on Store.

**3. Docker**

```bash
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto
```

## Topic Structure

The MQTT client uses this topic structure:

```
smarthome/<device_type>/<device_id>/<action>
```

Where:
- `device_type`: Type of device (light, switch, sensor, etc.)
- `device_id`: Unique device identifier
- `action`: One of:
  - `set` - Command topic (send commands)
  - `state` - State topic (receive state updates)
  - `availability` - Online/offline status

### Example Topics

```
smarthome/light/living_room/set       # Turn living room light on/off
smarthome/light/living_room/state     # Current state of living room light
smarthome/sensor/temperature/state    # Temperature sensor reading
smarthome/switch/fan/set              # Control fan switch
```

## Usage

### Basic Usage

```python
from src.mqtt_client import MQTTClient

# Create and connect
client = MQTTClient(
    broker_host="localhost",
    broker_port=1883,
    username="user",      # optional
    password="secret"     # optional
)
client.connect()

# Publish a message
client.publish("smarthome/light/kitchen/set", '{"state": "on"}')

# Subscribe to state updates
def on_message(topic, payload):
    print(f"Received on {topic}: {payload}")

client.subscribe("smarthome/+/state", callback=on_message)

# Disconnect when done
client.disconnect()
```

### Context Manager

```python
from src.mqtt_client import MQTTClient

with MQTTClient(broker_host="localhost") as client:
    client.publish_json("smarthome/light/bedroom/set", {
        "state": "on",
        "brightness": 80
    })
```

### Device Discovery

The client supports Home Assistant MQTT Discovery protocol:

```python
from src.mqtt_client import MQTTClient

with MQTTClient(broker_host="localhost") as client:
    # Start listening for device discovery messages
    client.start_device_discovery()

    # Wait for devices to announce themselves...
    import time
    time.sleep(5)

    # Get discovered devices
    devices = client.get_discovered_devices()
    for device in devices:
        print(f"Found: {device['name']} ({device['unique_id']})")

    client.stop_device_discovery()
```

### Device Control

Once devices are discovered, control them by ID:

```python
# Set device state
client.set_device_state("light_kitchen", {
    "state": "on",
    "brightness": 100,
    "color_temp": 4000
})

# Get current state
state = client.get_device_state("light_kitchen")
print(f"Kitchen light is {state['state']}")
```

## Home Assistant Integration

### Publishing Discovery Messages

To make your custom device discoverable by Home Assistant:

```python
import json
from src.mqtt_client import MQTTClient

with MQTTClient(broker_host="localhost") as client:
    # Announce a light device
    discovery_payload = {
        "name": "Custom Kitchen Light",
        "unique_id": "custom_kitchen_light_001",
        "device": {
            "identifiers": ["custom_kitchen_light_001"],
            "name": "Kitchen Light",
            "manufacturer": "DIY"
        },
        "command_topic": "smarthome/light/kitchen/set",
        "state_topic": "smarthome/light/kitchen/state",
        "schema": "json",
        "brightness": True,
        "color_mode": True,
        "supported_color_modes": ["color_temp", "rgb"]
    }

    client.publish_json(
        "homeassistant/light/custom_kitchen_light/config",
        discovery_payload,
        retain=True
    )
```

### Subscribing to Commands

Listen for commands from Home Assistant:

```python
def handle_command(topic, payload):
    if payload.get("state") == "on":
        # Turn on your device
        pass
    elif payload.get("state") == "off":
        # Turn off your device
        pass

    # Publish new state back
    client.publish_json("smarthome/light/kitchen/state", {
        "state": payload.get("state", "off"),
        "brightness": payload.get("brightness", 100)
    })

client.subscribe("smarthome/light/kitchen/set", callback=handle_command)
```

## Error Handling

The module defines these exceptions:

- `MQTTError`: Base exception for all MQTT errors
- `MQTTConnectionError`: Connection to broker failed
- `MQTTPublishError`: Message publish failed

```python
from src.mqtt_client import MQTTClient, MQTTConnectionError, MQTTPublishError

try:
    client = MQTTClient(broker_host="mqtt.example.com")
    client.connect()
except MQTTConnectionError as e:
    print(f"Could not connect: {e}")

try:
    client.publish("topic", "message")
except MQTTPublishError as e:
    print(f"Publish failed: {e}")
```

## Quality of Service (QoS)

MQTT supports three QoS levels:

- **QoS 0**: At most once (fire and forget)
- **QoS 1**: At least once (acknowledged delivery)
- **QoS 2**: Exactly once (guaranteed delivery)

```python
# Critical command - use QoS 2
client.publish("smarthome/security/alarm/set", '{"state": "arm"}', qos=2)

# Sensor reading - QoS 0 is fine
client.publish("smarthome/sensor/temp/state", "22.5", qos=0)

# Subscribe with QoS 1
client.subscribe("smarthome/+/state", qos=1, callback=handler)
```

## Retained Messages

Use retained messages for state that should persist:

```python
# This message will be delivered to new subscribers immediately
client.publish("smarthome/light/living_room/state", '{"state": "on"}', retain=True)
```

## Troubleshooting

### Connection Refused

1. Verify broker is running: `systemctl status mosquitto`
2. Check firewall allows port 1883: `sudo ufw status`
3. Verify credentials if using authentication

### Messages Not Received

1. Check topic subscription matches publication topic
2. Verify QoS levels are appropriate
3. Check client is connected: `client.is_connected()`

### Discovery Not Working

1. Ensure you're subscribed to `homeassistant/#`
2. Check discovery messages are retained
3. Verify JSON payload format matches Home Assistant schema

## Testing

Run MQTT tests:

```bash
pytest tests/unit/test_mqtt_client.py -v
```

## References

- [MQTT Specification](https://mqtt.org/mqtt-specification/)
- [Home Assistant MQTT Discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery)
- [Paho MQTT Client](https://eclipse.dev/paho/index.php?page=clients/python/docs/index.php)
