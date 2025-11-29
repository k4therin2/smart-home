# Getting Started

Get your home automation agent running in 5 minutes!

## Prerequisites

Before starting, make sure you have:
- Python 3.8 or higher installed
- Home Assistant running and accessible
- Philips Hue lights connected to Home Assistant
- Anthropic API key (from https://console.anthropic.com)

## 1. Install Dependencies

```bash
# Create and activate virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
# Copy the example file
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Get your API key from: https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-api03-...

# Your Home Assistant URL (usually http://localhost:8123 if running locally)
HA_URL=http://localhost:8123

# Get a long-lived token from Home Assistant:
# 1. Go to your Home Assistant UI
# 2. Click your profile (bottom left)
# 3. Scroll down to "Long-Lived Access Tokens"
# 4. Click "Create Token"
# 5. Give it a name like "Home Automation Agent"
# 6. Copy the token and paste it here
HA_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 3. Verify Setup

```bash
python utils.py --check
```

This will verify:
- ✓ Your Anthropic API key works
- ✓ Home Assistant is accessible
- ✓ Both services are responding correctly

## 4. Configure Rooms

Find your Home Assistant entity IDs:

```bash
# List all available lights
python utils.py --list-lights
```

Edit [tools/lights.py](../tools/lights.py) and update the `room_entity_map` with your entity IDs:

```python
room_entity_map = {
    "living_room": "light.living_room",  # ← Change these to match your lights
    "bedroom": "light.bedroom",
    "kitchen": "light.kitchen",
    "office": "light.office",
}
```

## 5. Test It!

```bash
# Try the classic "fire" problem
python agent.py "turn living room to fire"

# Try other scenes
python agent.py "make bedroom cozy"
python agent.py "make me feel like I'm under the sea"
```

## 6. Run Test Suite

```bash
# Interactive test suite
python tests/test_lights.py

# Quick automated test
python tests/test_lights.py --quick
```

## Example Commands to Try

```bash
# Warm scenes
python agent.py "campfire vibes in the living room"
python agent.py "romantic lighting in the bedroom"
python agent.py "cozy movie night"

# Cool scenes
python agent.py "ocean atmosphere in the bedroom"
python agent.py "energizing office lighting"
python agent.py "make it feel like I'm underwater"

# Activity-based
python agent.py "reading light in the office"
python agent.py "dinner party ambiance"
python agent.py "wake up lighting in the bedroom"
```

## What's Next?

- **Iterate on prompts**: Edit `prompts/system_prompt.txt` to fine-tune interpretations
- **Test edge cases**: Try ambiguous commands and see how the agent handles them
- **Add more rooms**: Expand your `room_entity_map` as you add more lights
- **Explore architecture**: Read [architecture.md](architecture.md) to understand how it works
- **Phase 2**: Add voice control with Alexa (see [session-log.md](session-log.md))

## Troubleshooting

### Command not working?

```bash
# Check your setup
python utils.py --check

# List available lights
python utils.py --list-lights

# Test HA connection
python utils.py --test-ha

# Test API key
python utils.py --test-api
```

### Common Issues

**"ANTHROPIC_API_KEY not set"**
- Make sure you created a `.env` file (not `.env.example`)
- Verify the API key is correct and starts with `sk-ant-api`

**"HA_TOKEN not set"**
- Make sure your `.env` file has the `HA_TOKEN` variable
- Verify the token is a long-lived access token from Home Assistant

**"Failed to communicate with Home Assistant"**
- Check that Home Assistant is running and accessible
- Verify the `HA_URL` in your `.env` file is correct
- Try accessing the URL in a browser
- Check Home Assistant logs: `docker logs homeassistant`

**"Unknown room: [room name]"**
- Update the `room_entity_map` in `tools/lights.py`
- Make sure the entity IDs match what's in Home Assistant
- Use the `get_available_rooms()` function to see what's available

**Lights don't change color temperature**
- Some bulbs (especially older ones) may not support color temperature
- Check if your bulbs support "white ambiance" or "white and color"
- Try controlling them manually in Home Assistant first

For more help, see [development.md](development.md) for debugging tips.

## Need More Detail?

- **Architecture**: See [architecture.md](architecture.md)
- **API Reference**: See [api-reference.md](api-reference.md)
- **Development**: See [development.md](development.md)
