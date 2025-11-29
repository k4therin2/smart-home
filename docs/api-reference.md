# API Reference

Complete reference for all tools, functions, and integrations in the Home Automation Agent system.

## Table of Contents

- [Agent Tools](#agent-tools)
- [Python Functions](#python-functions)
- [Home Assistant API](#home-assistant-api)
- [Environment Variables](#environment-variables)

## Agent Tools

These are the tools available to the main Claude agent via function calling.

### set_room_ambiance

Set lighting ambiance for a room based on mood/description.

**When to use**: Simple color/brightness changes based on mood

**Parameters**:
```python
{
    "room": str,               # Room name (e.g., 'living_room', 'bedroom')
    "color_temp_kelvin": int,  # Color temperature in Kelvin (2000-6500)
    "brightness_pct": int,     # Brightness percentage (0-100)
    "description": str         # Optional: what this represents (e.g., 'fire', 'ocean')
}
```

**Returns**:
```python
{
    "success": bool,
    "room": str,
    "entity_id": str,          # HA entity that was controlled
    "color_temp_kelvin": int,
    "mireds": int,             # Converted color temperature
    "brightness_pct": int,
    "message": str             # Human-readable confirmation
}
```

**Example**:
```python
set_room_ambiance(
    room="living_room",
    color_temp_kelvin=2200,
    brightness_pct=50,
    description="fire"
)
# → Warm orange glow in living room
```

### apply_fire_flicker

Apply a realistic fire flickering effect using API-based sequence.

**When to use**: When user explicitly wants flickering fire effect

**Performance**: 11 API calls over 15 seconds

**Parameters**:
```python
{
    "room": str,                # Room name
    "duration_seconds": int     # Optional: how long effect runs (default: 15)
}
```

**Returns**:
```python
{
    "success": bool,
    "room": str,
    "num_steps": int,           # How many flicker steps planned
    "duration_seconds": int,
    "message": str,
    "implementation": str       # "api_sequence"
}
```

**How it works**:
1. Consults Hue Specialist agent
2. Specialist plans 11-step flicker sequence
3. Executes in background thread
4. Each step varies brightness (40-65%) and color temp (2000-2400K)

**Example**:
```python
apply_fire_flicker(room="living_room", duration_seconds=20)
# → 15-second flickering effect, then stops
```

### apply_abstract_effect

Apply a looping effect based on abstract description.

**When to use**: Abstract/creative descriptions like "under the sea", "swamp", "strobing green"

**Performance**: 1 API call, loops indefinitely

**Parameters**:
```python
{
    "description": str,  # Abstract atmosphere description
    "room": str          # Room name
}
```

**Returns**:
```python
{
    "success": bool,
    "room": str,
    "scene": str,                    # Hue scene that was selected
    "scene_entity_id": str,
    "dynamic": bool,                 # True = looping animation
    "speed": int,                    # Animation speed 0-100
    "brightness_pct": int,           # Optional brightness override
    "specialist_reasoning": str,     # Why specialist chose this scene
    "description": str,              # Original description
    "message": str
}
```

**How it works**:
1. Gets available Hue scenes for room
2. Consults Hue Specialist agent
3. Specialist maps description → best scene
4. Activates scene with dynamic=true (loops forever!)

**Example**:
```python
apply_abstract_effect(
    description="under the sea",
    room="living_room"
)
# → Arctic aurora scene (cool blues/greens), loops indefinitely
```

### get_available_rooms

Query Home Assistant to see what lights/rooms are available.

**When to use**: When unsure what rooms exist

**Parameters**: None

**Returns**:
```python
{
    "success": bool,
    "rooms": [
        {
            "name": str,       # Room name (e.g., "living_room")
            "entity_id": str,  # HA entity (e.g., "light.living_room")
            "state": str,      # "on" or "off"
            "friendly_name": str
        },
        ...
    ]
}
```

## Python Functions

### tools/lights.py

#### set_room_ambiance()
See [Agent Tools](#set_room_ambiance) above.

#### apply_fire_flicker()
See [Agent Tools](#apply_fire_flicker) above.

#### get_available_rooms()
See [Agent Tools](#get_available_rooms) above.

### tools/effects.py

#### get_hue_scenes()

Get available Hue scenes for a room.

**Parameters**:
```python
room: str  # Room name
```

**Returns**:
```python
{
    "success": bool,
    "room": str,
    "entity_id": str,
    "available_scenes": List[str]  # List of scene names
}
```

**Example**:
```python
get_hue_scenes("living_room")
# → {"available_scenes": ["Arctic aurora", "Nebula", "Fire", ...]}
```

#### activate_dynamic_scene()

Activate a Hue scene with dynamic (looping) mode.

**Parameters**:
```python
room: str
scene_name: str
speed: Optional[int] = None              # Animation speed 0-100
brightness_pct: Optional[int] = None     # Override brightness
```

**Returns**:
```python
{
    "success": bool,
    "room": str,
    "scene": str,                    # Matched scene name
    "scene_entity_id": str,
    "dynamic": bool,
    "speed": Optional[int],
    "brightness_pct": Optional[int],
    "message": str
}
```

#### apply_abstract_effect()
See [Agent Tools](#apply_abstract_effect) above.

### tools/hue_specialist.py

#### HueSpecialist class

Specialist agent with deep Hue API knowledge.

##### plan_fire_flicker()

Ask specialist to plan a fire flickering effect.

**Parameters**:
```python
room: str
duration_seconds: int = 15
```

**Returns**:
```python
List[Dict]  # List of flicker steps

# Each step:
{
    "delay_seconds": float,      # Wait time before executing
    "brightness_pct": int,       # 40-65
    "color_temp_kelvin": int,    # 2000-2400
    "transition": float          # 0.4-1.2 seconds
}
```

##### suggest_effect_for_description()

Map abstract description to best Hue scene.

**Parameters**:
```python
description: str             # User's abstract description
available_scenes: List[str]  # Available Hue scenes
```

**Returns**:
```python
{
    "success": bool,
    "scene": str,           # Recommended scene name
    "speed": int,           # 0-100
    "brightness_pct": int,  # Optional override
    "reasoning": str        # Why this scene fits
}
```

**Example**:
```python
specialist = get_hue_specialist()
recommendation = specialist.suggest_effect_for_description(
    "under the sea",
    ["Arctic aurora", "Nebula", "Fire", ...]
)
# → {"scene": "Arctic aurora", "speed": 25, "reasoning": "Cool blues/greens..."}
```

## Home Assistant API

### Base URL
Default: `http://localhost:8123`

### Authentication
All requests require header:
```
Authorization: Bearer YOUR_LONG_LIVED_TOKEN
```

### Endpoints Used

#### POST /api/services/light/turn_on

Turn on lights with specific parameters.

**Request**:
```json
{
  "entity_id": "light.living_room",
  "color_temp": 370,        // mireds (converted from Kelvin)
  "brightness_pct": 50,
  "transition": 1           // optional, seconds
}
```

**Response**: `200 OK` or error

#### POST /api/services/hue/activate_scene

Activate a Hue scene with dynamic mode.

**Request**:
```json
{
  "entity_id": "scene.living_room_arctic_aurora",
  "dynamic": true,          // Enable looping animation
  "speed": 25,              // 0-100 animation speed
  "brightness": 60          // Optional brightness override
}
```

**Response**: `200 OK` or error

#### GET /api/states

Get all entity states (used for light discovery).

**Response**:
```json
[
  {
    "entity_id": "light.living_room",
    "state": "on",
    "attributes": {
      "friendly_name": "Living Room",
      "brightness": 128,
      "color_temp": 370,
      "hue_scenes": ["Arctic aurora", "Nebula", "Fire", ...]
    }
  },
  ...
]
```

#### GET /api/states/{entity_id}

Get specific entity state.

**Response**:
```json
{
  "entity_id": "light.living_room",
  "state": "on",
  "attributes": {
    "friendly_name": "Living Room",
    "hue_scenes": ["Arctic aurora", ...]
  }
}
```

## Environment Variables

### Required

#### ANTHROPIC_API_KEY
Your Anthropic API key for Claude.

**Where to get**: https://console.anthropic.com
**Format**: `sk-ant-api03-...`
**Example**: `ANTHROPIC_API_KEY=sk-ant-api03-abc123...`

#### HA_TOKEN
Home Assistant long-lived access token.

**Where to get**:
1. Home Assistant UI → Profile (bottom left)
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"

**Format**: Long JWT-like string
**Example**: `HA_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

#### HA_URL
Home Assistant base URL.

**Default**: `http://localhost:8123`
**Example**: `HA_URL=http://192.168.1.100:8123`

## Room Entity Mapping

**File**: [tools/lights.py](../tools/lights.py)

Edit this dictionary to match your Home Assistant setup:

```python
room_entity_map = {
    "living_room": "light.living_room",
    "bedroom": "light.bedroom",
    "kitchen": "light.kitchen",
    "office": "light.office",
}
```

**To find entity IDs**:
```bash
python utils.py --list-lights
```

Or in Home Assistant:
1. Developer Tools → States
2. Look for entities starting with `light.`
3. Use the entity_id, not friendly name

## Hue Scene Names

Common dynamic scenes available (depends on your setup):

- **Arctic aurora**: Cool blues/greens, flowing like northern lights
- **Nebula**: Deep space colors, purples/blues, cosmic
- **Fire**: Warm oranges/reds, flickering
- **Nighttime**: Calm, dim, relaxing blues
- **Sleepy**: Very dim, warm, bedtime
- **City of love**: Romantic pinks/reds
- **Tokyo**: Vibrant, energetic, bright colors
- **Motown**: Warm, groovy, retro vibes
- **Scarlet dream**: Deep reds, dramatic
- **Ruby glow**: Red tones, warm

**To list your scenes**:
```bash
python -c "from tools.effects import get_hue_scenes; import json; print(json.dumps(get_hue_scenes('living_room'), indent=2))"
```

## Color Temperature Reference

### Kelvin to Mireds Conversion
```python
mireds = 1000000 / kelvin
```

### Common Values

| Description | Kelvin | Mireds | Hue |
|-------------|--------|--------|-----|
| Candlelight | 2000K | 500 | Very warm orange |
| Fire/Warm | 2200K | 454 | Warm orange |
| Warm white | 2700K | 370 | Soft white |
| Neutral | 3500K | 286 | Neutral white |
| Cool white | 5000K | 200 | Bright white |
| Daylight | 6500K | 154 | Cool blue-white |

## Error Codes

### Common Errors

**"HA_TOKEN not set"**
- Missing or invalid `.env` file
- Token not configured

**"Unknown room: {room}"**
- Room not in `room_entity_map`
- Update [tools/lights.py](../tools/lights.py)

**"Failed to communicate with Home Assistant"**
- HA not running
- Wrong `HA_URL`
- Network issue

**"Scene '{scene}' not found"**
- Scene doesn't exist for this room
- Check available scenes with `get_hue_scenes()`

**"ANTHROPIC_API_KEY not set"**
- Missing API key in `.env`
- Get key from https://console.anthropic.com

## Rate Limits

### Anthropic API
- No specific limit for paid tier
- Reasonable use expected

### Home Assistant API
- No specific limit
- Avoid sending commands faster than 100ms

### Philips Hue Bridge
- Recommended: Max 1 command per 100ms per light
- Our scenes approach: 1 command total (most efficient!)

## See Also

- [Architecture](architecture.md) - How the system works
- [Getting Started](getting-started.md) - Setup guide
- [Development](development.md) - Contributing and debugging
