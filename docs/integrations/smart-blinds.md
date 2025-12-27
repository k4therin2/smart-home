# Smart Blinds Integration

This guide covers setting up Hapadif smart blinds (via Tuya) with the Smart Home Assistant.

## Overview

The smart blinds integration enables:
- Voice control of motorized blinds/shades
- Open, close, and partial positioning
- Scene presets (morning, movie, work)
- Multi-room blind control
- Status queries

## Supported Devices

This integration supports Tuya-compatible motorized blinds, including:

- Hapadif Smart Blinds (via MH100 Smart Bridge Hub)
- Tuya-compatible motorized shades
- Smart Life app compatible blinds
- Zemismart, MOES, and other Tuya-based blinds

## Prerequisites

- Motorized blinds with Tuya compatibility
- Hapadif Smart Bridge Hub (MH100) or direct WiFi blinds
- Smart Life or Tuya Smart app account
- Home Assistant with Tuya integration
- Smart Home Assistant installed

## Integration Path

```
Motorized Blinds → Hapadif Smart Bridge Hub → Tuya Cloud → Home Assistant Tuya Integration
```

Or for direct WiFi blinds:
```
Motorized Blinds → Tuya Cloud → Home Assistant Tuya Integration
```

## Step 1: Hardware Setup

### Hapadif Smart Bridge Hub (MH100)

1. **Unpack the bridge:**
   - Bridge hub
   - USB power cable
   - Power adapter

2. **Connect to power:**
   - Plug USB cable into hub
   - Connect to power adapter
   - LED indicator lights up

3. **Connect to WiFi:**
   - Open Smart Life app (or Tuya Smart)
   - Add Device > Add Bridge
   - Follow in-app instructions
   - Must use 2.4GHz WiFi (not 5GHz)

4. **Pair blinds to bridge:**
   - Put blinds in pairing mode (see blinds manual)
   - Usually: hold remote button until LED flashes
   - In Smart Life app: Add sub-device
   - Select blinds from device list

### Direct WiFi Blinds

1. Put blinds in pairing mode
2. Open Smart Life/Tuya app
3. Add Device > Cover/Curtain
4. Follow pairing instructions

## Step 2: Home Assistant Tuya Integration

### Method 1: Cloud Integration (Easier)

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Tuya"
4. Select "Tuya" (cloud-based)
5. Enter your Tuya/Smart Life credentials
6. Authorize Home Assistant access

### Method 2: Local Integration (Faster)

For local control without cloud dependency:

1. Install "Local Tuya" from HACS
2. Get device keys using one of:
   - [Tuya IoT Platform](https://iot.tuya.com/)
   - TinyTuya library
3. Configure local integration with device keys

## Step 3: Verify Entities

After integration setup:

1. Go to Developer Tools > States
2. Search for "cover"
3. Note entity IDs (e.g., `cover.living_room_blinds`)

Expected entities:
```
cover.living_room_blinds
cover.bedroom_blinds
cover.office_blinds
```

## Step 4: Configure Smart Home Assistant

Update `src/config.py` with your blind entities:

```python
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": ["light.living_room"],
        "blinds": "cover.living_room_blinds",
        "aliases": ["lounge", "main room"],
    },
    "bedroom": {
        "lights": ["light.bedroom"],
        "blinds": "cover.bedroom_blinds",
        "aliases": ["master bedroom"],
    },
    "office": {
        "lights": ["light.office"],
        "blinds": "cover.office_blinds",
        "aliases": ["study", "home office"],
    },
}
```

## Available Commands

### Basic Control

```
"Open the living room blinds"
"Close bedroom blinds"
"Stop the blinds"
"Open all blinds"
```

### Partial Positioning

```
"Set office blinds to 50%"
"Lower the blinds halfway"
"Open blinds to 75%"
"Close blinds to 25%"
```

Position values:
- 0% = Fully closed
- 50% = Half open
- 100% = Fully open

### Status Queries

```
"What's the blinds position?"
"Are the bedroom blinds open?"
"Check living room blinds"
```

### Scene Presets

Built-in scene presets coordinate blinds with lighting:

| Scene | Position | Description |
|-------|----------|-------------|
| morning | 100% | Fully open for natural light |
| day | 75% | Mostly open, balanced light |
| evening | 25% | Mostly closed for privacy |
| night | 0% | Fully closed |
| movie | 0% | Fully closed for dark room |
| work | 50% | Half open to reduce screen glare |

**Example commands:**
```
"Set blinds for morning"
"Movie mode blinds"
"Evening blinds in the living room"
"Work mode in the office"
```

### Multi-Room Control

```
"Close all blinds"
"Open blinds everywhere"
"Set all blinds to 50%"
```

## Troubleshooting

### Blinds Not Responding

1. **Check Home Assistant entity:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states/cover.living_room_blinds
   ```

2. **Verify Tuya integration:**
   - Settings > Devices & Services > Tuya
   - Check for error messages
   - Re-authenticate if needed

3. **Check bridge connectivity:**
   - Hapadif bridge LED should be solid
   - Bridge must be on same network

4. **Test via Smart Life app:**
   - If app works, issue is HA integration
   - If app fails, issue is bridge/blinds

### Wrong Position Values

Different blinds may report position differently:

1. **Inverted values:**
   Some blinds report 0% as open, 100% as closed

   If your blinds are inverted, add to `src/config.py`:
   ```python
   BLINDS_INVERTED = ["cover.bedroom_blinds"]
   ```

2. **Calibration:**
   - Use Smart Life app to calibrate limits
   - Set fully open and fully closed positions

### Slow Response

1. **Cloud latency:**
   - Tuya cloud integration has ~1-2 second delay
   - Consider Local Tuya for faster response

2. **Bridge issues:**
   - Restart Hapadif bridge
   - Check WiFi signal strength

### Bridge Offline

1. **Power cycle:**
   - Unplug bridge for 30 seconds
   - Reconnect and wait for LED

2. **Re-pair to WiFi:**
   - Reset bridge (hold button 5+ seconds)
   - Re-add in Smart Life app

3. **Network issues:**
   - Ensure 2.4GHz WiFi is active
   - Check router hasn't changed
   - Bridge may not support 5GHz

## Scene Integration

### Coordinating with Lights

Create combined scenes:

```
"Make it cozy"
# Agent interprets: dim lights to warm, close blinds partially
```

The system automatically coordinates:
- Vibe presets adjust both lights and blinds
- "Movie mode" dims lights AND closes blinds
- "Morning mode" opens blinds AND adjusts lights

### Automation Examples

**Sunrise automation:**
```yaml
automation:
  - alias: "Open Blinds at Sunrise"
    trigger:
      - platform: sun
        event: sunrise
        offset: "+00:30:00"
    action:
      - service: cover.set_cover_position
        target:
          entity_id: cover.living_room_blinds
        data:
          position: 100
```

**Close at sunset:**
```yaml
automation:
  - alias: "Close Blinds at Sunset"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: cover.close_cover
        target:
          entity_id:
            - cover.living_room_blinds
            - cover.bedroom_blinds
```

### Voice-Created Automations

Use the automation system:
```
"Create an automation to open blinds at sunrise"
"When the sun sets, close all blinds"
```

## Position Reference

Understanding blind positions:

```
100% ████████████ Fully Open
 75% ████████░░░░ Mostly Open
 50% ██████░░░░░░ Half Open
 25% ████░░░░░░░░ Mostly Closed
  0% ░░░░░░░░░░░░ Fully Closed
```

## Hardware Recommendations

### Hapadif Smart Bridge Hub

- **Model:** MH100
- **Protocol:** Tuya WiFi + RF
- **Supports:** Up to 32 blinds per hub
- **Purchase:** [Amazon](https://www.amazon.com/Hapadif-Bridge-Compatible-Motorized-Realize/dp/B0CK4T67PG)

### Compatible Blinds

- Hapadif motorized blinds (roller, cellular, roman)
- Tuya-compatible motors (AM25, AM43)
- Zemismart motors
- MOES WiFi motors

## References

- [Home Assistant Tuya Integration](https://www.home-assistant.io/integrations/tuya/)
- [Home Assistant Cover Integration](https://www.home-assistant.io/integrations/cover/)
- [Local Tuya HACS Integration](https://github.com/rospogriern/localtuya)
- [Tuya IoT Platform](https://iot.tuya.com/)
