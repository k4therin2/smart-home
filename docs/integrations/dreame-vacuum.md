# Dreame Vacuum Integration

This guide covers setting up Dreame robot vacuums with the Smart Home Assistant.

## Overview

The Dreame vacuum integration enables:
- Voice control of vacuum operations
- Start, stop, pause, and dock commands
- Room-specific cleaning
- Suction power adjustment
- Status queries (battery, cleaning progress)

## Supported Models

This integration uses the [Tasshack/dreame-vacuum](https://github.com/Tasshack/dreame-vacuum) HACS component, which supports:

- Dreame L10 Pro / L10s Pro / L10s Ultra
- Dreame D9 / D9 Pro / D10 Plus
- Dreame Z10 Pro
- Dreame W10 / W10 Pro
- Dreame L20 Ultra
- And other Dreame vacuums via Dreame app integration

## Prerequisites

- Dreame robot vacuum connected to WiFi
- Home Assistant with HACS installed
- Vacuum registered in Dreame/Xiaomi Home app
- Smart Home Assistant installed

## Step 1: Install HACS Integration

### Via HACS (Recommended)

1. Open Home Assistant
2. Go to HACS > Integrations
3. Click "Explore & Download Repositories"
4. Search for "Dreame Vacuum"
5. Click "Download"
6. Restart Home Assistant

### Manual Installation

```bash
wget -O - https://raw.githubusercontent.com/Tasshack/dreame-vacuum/master/install | bash -
```

Then restart Home Assistant.

## Step 2: Configure Integration

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Dreame Vacuum"
4. Enter your Dreame/Xiaomi account credentials
5. Select your vacuum from the list
6. Click "Submit"

### Required Information

- **Xiaomi/Dreame Account:** Your Xiaomi Home or Dreame app login
- **Password:** Account password
- **Server Region:** Select based on your account region

## Step 3: Note Entity ID

After setup, find your vacuum entity:

1. Go to Developer Tools > States
2. Search for "vacuum"
3. Note the entity ID (e.g., `vacuum.dreame_l10s`)

## Step 4: Configure Smart Home Assistant

Add the entity ID to your `.env` file:

```bash
VACUUM_ENTITY_ID=vacuum.dreame_l10s
```

Or update `src/config.py`:

```python
VACUUM_ENTITY_ID = os.getenv("VACUUM_ENTITY_ID", "vacuum.dreame_l10s")
```

## Available Commands

### Basic Control

```
"Start the vacuum"
"Stop vacuuming"
"Pause the vacuum"
"Resume cleaning"
"Send the robot home"
"Dock the vacuum"
```

### Status Queries

```
"What's the vacuum status?"
"Where is the vacuum?"
"What's the vacuum battery level?"
"Is the vacuum cleaning?"
```

### Room Cleaning

```
"Vacuum the living room"
"Clean the kitchen"
"Clean the bedroom and office"
"Vacuum just the kitchen and bathroom"
```

### Suction Power

```
"Set vacuum to turbo mode"
"Quiet vacuum mode"
"Standard suction power"
"Strong cleaning mode"
```

Suction levels:
| Level | Description |
|-------|-------------|
| quiet | Low noise, light cleaning |
| standard | Normal operation |
| strong | Increased suction |
| turbo | Maximum power |

### Locate

```
"Where's the vacuum?"
"Find the robot"
"Beep the vacuum"
```

## Room Configuration

### Room Segment IDs

For room-specific cleaning, you need to map room names to segment IDs:

1. **Find room segment IDs:**
   - Open Dreame/Xiaomi Home app
   - View the saved map
   - Note room numbers or use HA Developer Tools

2. **Map rooms in config** (if needed):

```python
# In src/config.py
VACUUM_ROOM_MAP = {
    "living_room": 1,
    "bedroom": 2,
    "kitchen": 3,
    "bathroom": 4,
    "office": 5,
}
```

### Multi-Room Cleaning

The system supports cleaning multiple rooms:
```
"Clean the kitchen and living room"
"Vacuum bedroom and office"
```

## Troubleshooting

### Vacuum Not Responding

1. **Check HA entity status:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states/vacuum.dreame_l10s
   ```

2. **Verify vacuum is online:**
   - Open Dreame/Xiaomi Home app
   - Check vacuum shows as online

3. **Check HACS integration:**
   - Settings > Devices & Services
   - Verify Dreame Vacuum integration is running

### Room Cleaning Not Working

1. **Verify room IDs:**
   - Room segment IDs must match the vacuum's saved map
   - IDs can change if map is re-created

2. **Check map is saved:**
   - Vacuum must have completed at least one full clean
   - Map should be saved in the app

### "Entity Not Found"

1. **Verify entity ID:**
   - Check Developer Tools > States
   - Entity ID is case-sensitive

2. **Update configuration:**
   ```bash
   VACUUM_ENTITY_ID=vacuum.your_actual_entity_id
   ```

### Authentication Issues

1. **Re-authenticate:**
   - Settings > Devices & Services
   - Click on Dreame Vacuum
   - Options > Re-authenticate

2. **Check account:**
   - Verify login works in Dreame/Xiaomi app
   - Password may have changed

## Advanced Features

### Automation Examples

**Daily cleaning schedule:**
```yaml
automation:
  - alias: "Daily Vacuum at 10am"
    trigger:
      - platform: time
        at: "10:00:00"
    condition:
      - condition: state
        entity_id: vacuum.dreame_l10s
        state: "docked"
    action:
      - service: vacuum.start
        target:
          entity_id: vacuum.dreame_l10s
```

**Vacuum when leaving home:**
```yaml
automation:
  - alias: "Vacuum When Everyone Leaves"
    trigger:
      - platform: state
        entity_id: group.family
        from: "home"
        to: "not_home"
    action:
      - service: vacuum.start
        target:
          entity_id: vacuum.dreame_l10s
```

### Integration with Smart Home Assistant

Create voice automation:
```
"When I leave home, start the vacuum"
```

The automation system (Phase 4) can create these based on voice commands.

## Status Information

The vacuum provides these status attributes:

| Attribute | Description |
|-----------|-------------|
| `state` | docked, cleaning, paused, returning, error |
| `battery_level` | 0-100% |
| `fan_speed` | quiet, standard, strong, turbo |
| `cleaning_count` | Total cleaning sessions |
| `total_cleaning_time` | Total minutes cleaned |
| `total_cleaned_area` | Total square meters cleaned |
| `last_cleaning_area` | Last session area |
| `last_cleaning_time` | Last session duration |

Query via:
```
"What's the vacuum status?"
```

## References

- [Tasshack/dreame-vacuum GitHub](https://github.com/Tasshack/dreame-vacuum)
- [Home Assistant Vacuum Integration](https://www.home-assistant.io/integrations/vacuum/)
- [HACS (Home Assistant Community Store)](https://hacs.xyz/)
