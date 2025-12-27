# Philips Hue Integration

This guide covers setting up Philips Hue lights with the Smart Home Assistant.

## Overview

The Philips Hue integration enables:
- Voice control of lights ("turn on the living room lights")
- Brightness and color temperature adjustment
- Vibe presets (cozy, focus, energize, sleep)
- Dynamic scenes (fire, ocean, aurora)
- RGB color control

## Prerequisites

- Philips Hue Bridge (required for all Hue products)
- Philips Hue light bulbs or light strips
- Home Assistant with Hue integration
- Smart Home Assistant installed

## Hardware Setup

### Step 1: Hue Bridge Installation

1. Connect the Hue Bridge to your router via Ethernet
2. Plug in the power adapter
3. Wait for all three lights on the bridge to turn on

### Step 2: Light Installation

1. Install Hue bulbs in your fixtures
2. Turn on power to the fixtures
3. Bulbs should appear in the Hue app within 1 minute

### Step 3: Hue App Configuration

1. Download the Philips Hue app (iOS/Android)
2. Create or sign into your Hue account
3. Add the bridge (follow in-app instructions)
4. Add lights and assign them to rooms
5. Create any custom scenes you want

## Home Assistant Integration

### Step 1: Add Hue Integration

1. Go to Home Assistant Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Philips Hue"
4. Press the link button on your Hue Bridge when prompted
5. Click "Submit" within 30 seconds

### Step 2: Verify Entities

After integration, verify entities appear:
```
light.living_room
light.bedroom
light.kitchen
# etc.
```

Check via Home Assistant Developer Tools > States.

### Step 3: Note Entity IDs

Record the entity IDs for your rooms. You'll need these for configuration.

## Smart Home Assistant Configuration

### Step 1: Update Room Mappings

Edit `src/config.py` to match your Home Assistant entity IDs:

```python
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": ["light.living_room", "light.living_room_lamp"],
        "aliases": ["lounge", "main room", "living area"],
    },
    "bedroom": {
        "lights": ["light.bedroom", "light.bedside_lamp"],
        "aliases": ["master bedroom", "main bedroom"],
    },
    "kitchen": {
        "lights": ["light.kitchen"],
        "aliases": ["cooking area"],
    },
    # Add more rooms as needed
}
```

### Step 2: Configure Hue Bridge (for scenes)

If you want to use dynamic Hue scenes (fire, ocean, aurora):

```python
# In src/config.py
HUE_BRIDGE_ID = "your_bridge_id_here"  # Find in HA integration
```

The bridge ID appears in Home Assistant under Settings > Devices & Services > Philips Hue > 1 device.

## Available Commands

### Basic Control

```
"Turn on the living room lights"
"Turn off bedroom lights"
"Set kitchen to 50% brightness"
"Dim the lights"
"Brighten the living room"
```

### Color Temperature

```
"Make the bedroom warm"
"Set living room to cool white"
"Warm yellow in the office"
```

### Vibe Presets

Built-in vibe presets:

| Vibe | Brightness | Color Temp | Description |
|------|------------|------------|-------------|
| cozy | 40% | 2700K | Warm, relaxed atmosphere |
| romantic | 30% | 2200K | Dim, warm candlelight |
| focus | 80% | 4000K | Bright, neutral for concentration |
| energize | 100% | 5000K | Bright, cool for alertness |
| relax | 50% | 3000K | Comfortable, warm-white |
| sleep | 20% | 2200K | Very dim, warm for bedtime |
| movie | 25% | 2700K | Dim for screen viewing |
| reading | 70% | 4000K | Good task lighting |
| party | 80% | Various | Colorful, dynamic |
| morning | 60% | 4000K | Gradually energizing |

**Example commands:**
```
"Make the living room cozy"
"Set bedroom to sleep mode"
"Focus mode in the office"
"Party vibe in the kitchen"
```

### Dynamic Scenes

Hue scenes with animated effects:

| Scene Command | Hue Scene | Description |
|---------------|-----------|-------------|
| "fire" | Savanna Sunset | Warm flickering effect |
| "ocean" | Tropical Twilight | Blue-green water effect |
| "aurora" | Arctic Aurora | Northern lights effect |
| "forest" | Spring Blossom | Green nature effect |
| "sunset" | Savanna Sunset | Warm sunset colors |
| "party" | Tokyo | Colorful dynamic effect |

**Example commands:**
```
"Set living room to fire"
"Make the bedroom like an ocean"
"Aurora in the office"
"Turn on the fireplace scene"
```

### RGB Colors

```
"Set bedroom to red"
"Make the kitchen blue"
"Purple lights in the office"
"Living room to orange"
```

## Troubleshooting

### Lights Not Responding

1. **Check Home Assistant connection:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states/light.living_room
   ```

2. **Verify entity ID matches config:**
   - Check `src/config.py` ROOM_ENTITY_MAP
   - Entity IDs are case-sensitive

3. **Check Hue Bridge connectivity:**
   - Ensure bridge has solid blue light
   - Try controlling lights via Hue app

### Scenes Not Activating

1. **Verify bridge ID in config:**
   ```python
   # src/config.py
   HUE_BRIDGE_ID = "001788fffe123456"  # Your bridge ID
   ```

2. **Check scene exists in Hue:**
   - Open Hue app > Scenes
   - Verify scene name matches

3. **Enable scene service in HA:**
   - Some scenes require `hue.activate_scene` service
   - Check HA Developer Tools > Services

### Color Temperature Issues

1. **Bulb must support color temperature:**
   - Hue White Ambiance or Color bulbs
   - Basic Hue White bulbs only support brightness

2. **Color temp range:**
   - Min: 2000K (very warm)
   - Max: 6500K (very cool)
   - Most comfortable: 2700K-4000K

### Slow Response

1. **Check network latency:**
   ```bash
   ping homeassistant.local
   ```

2. **Reduce API calls:**
   - Cache is enabled by default
   - Check cache stats at `/api/health`

## Best Practices

### Room Naming

- Use simple, speakable names
- Avoid abbreviations
- Add aliases for natural variations

### Scene Organization

- Create room-specific scenes in Hue app
- Name scenes descriptively
- Test scenes via Hue app first

### Performance

- The system uses native Hue scenes when possible (1 API call)
- Fallback to individual bulb control if needed
- Dynamic scenes run on Hue Bridge hardware, not API-controlled

## Example Configurations

### Studio Apartment

```python
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": ["light.main_ceiling", "light.floor_lamp", "light.tv_strip"],
        "aliases": ["main room", "living area", "apartment"],
    },
    "bedroom": {
        "lights": ["light.bed_ceiling", "light.nightstand"],
        "aliases": ["sleeping area", "bed"],
    },
}
```

### Multi-Story House

```python
ROOM_ENTITY_MAP = {
    "living_room": {
        "lights": ["light.living_room_main", "light.living_room_accent"],
        "aliases": ["lounge", "family room"],
    },
    "kitchen": {
        "lights": ["light.kitchen_ceiling", "light.under_cabinet"],
        "aliases": ["cooking area"],
    },
    "master_bedroom": {
        "lights": ["light.master_ceiling", "light.master_left", "light.master_right"],
        "aliases": ["bedroom", "main bedroom"],
    },
    "office": {
        "lights": ["light.office_ceiling", "light.desk_lamp"],
        "aliases": ["study", "home office", "work room"],
    },
    "upstairs_hall": {
        "lights": ["light.upstairs_hallway"],
        "aliases": ["hallway", "upstairs"],
    },
}
```

## References

- [Philips Hue Developer Portal](https://developers.meethue.com/)
- [Home Assistant Hue Integration](https://www.home-assistant.io/integrations/hue/)
- [Hue Bridge API](https://developers.meethue.com/develop/hue-api-v2/)
