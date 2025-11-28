# Phase 1 Setup Guide

This guide will help you get Phase 1 of the Home Automation Agent running.

## Prerequisites

Before starting, make sure you have:
- [ ] Python 3.8 or higher installed
- [ ] Home Assistant running and accessible
- [ ] Philips Hue lights connected to Home Assistant
- [ ] Anthropic API key (from https://console.anthropic.com)

## Step 1: Install Dependencies

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

## Step 2: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and fill in your credentials:
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

## Step 3: Configure Room Mappings

Edit `tools/lights.py` and update the `room_entity_map` dictionary to match your Home Assistant setup:

```python
room_entity_map = {
    "living_room": "light.living_room",  # Change to your entity ID
    "bedroom": "light.bedroom",
    "kitchen": "light.kitchen",
    "office": "light.office",
}
```

To find your entity IDs:
1. Open Home Assistant UI
2. Go to Developer Tools → States
3. Look for entities starting with `light.`
4. Use the entity_id (not the friendly name)

Alternatively, run this helper script:
```bash
python -c "from tools.lights import get_available_rooms; import json; print(json.dumps(get_available_rooms(), indent=2))"
```

## Step 4: Test the Setup

### Quick Test
Run a simple command to verify everything works:

```bash
python agent.py "turn living room to fire"
```

You should see:
1. The agent processing your request
2. A tool call to `set_room_ambiance`
3. Your lights changing to warm orange/yellow tones
4. A response message from the agent

### Run Full Test Suite
Test multiple scenarios:

```bash
python tests/test_lights.py
```

Or run a quick automated test:
```bash
python tests/test_lights.py --quick
```

## Step 5: Test Different Descriptions

Try various commands to see how the agent interprets them:

```bash
# Warm, cozy scenes
python agent.py "make the bedroom cozy"
python agent.py "set living room to romantic"
python agent.py "campfire vibes in the living room"

# Cool, energizing scenes
python agent.py "make the office energizing"
python agent.py "set kitchen to bright and focused"
python agent.py "ocean vibes in the bedroom"

# Specific activities
python agent.py "reading light in the office"
python agent.py "movie time in the living room"
```

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
- Make sure you created a `.env` file (not `.env.example`)
- Verify the API key is correct and starts with `sk-ant-api`

### "HA_TOKEN not set"
- Make sure your `.env` file has the `HA_TOKEN` variable
- Verify the token is a long-lived access token from Home Assistant

### "Failed to communicate with Home Assistant"
- Check that Home Assistant is running and accessible
- Verify the `HA_URL` in your `.env` file is correct
- Try accessing the URL in a browser
- Check Home Assistant logs: `docker logs homeassistant`

### "Unknown room: [room name]"
- Update the `room_entity_map` in `tools/lights.py`
- Make sure the entity IDs match what's in Home Assistant
- Use the `get_available_rooms()` function to see what's available

### Lights don't change color temperature
- Some bulbs (especially older ones) may not support color temperature
- Check if your bulbs support "white ambiance" or "white and color"
- Try controlling them manually in Home Assistant first

## Next Steps

Once Phase 1 is working:

1. **Iterate on the system prompt** (`prompts/system_prompt.txt`)
   - Adjust temperature ranges
   - Add new scene types
   - Fine-tune brightness levels

2. **Test edge cases**
   - Ambiguous descriptions
   - Multiple rooms in one command
   - Rooms that don't exist

3. **Move to Phase 2** - Add voice integration with Alexa

## Development Tips

### Viewing Agent Decisions
The agent runs in verbose mode by default, showing:
- What tools it decides to call
- The parameters it chooses
- The results from Home Assistant

### Testing Without Lights
If you want to test the agent logic without actually controlling lights:
- Comment out the `requests.post()` call in `tools/lights.py`
- Just return a success response
- This lets you iterate on prompts faster

### Adjusting System Prompt
The system prompt is in `prompts/system_prompt.txt`. You can:
- Add new scene examples
- Adjust temperature/brightness guidance
- Add constraints (e.g., "never go below 20% brightness")

## File Structure Reference

```
Smarthome/
├── .env                    # Your API keys (don't commit!)
├── .env.example           # Template for .env
├── requirements.txt       # Python dependencies
├── agent.py              # Main agent code
├── tools/
│   └── lights.py         # Hue/HA integration
├── prompts/
│   └── system_prompt.txt # Agent's instructions
└── tests/
    └── test_lights.py    # Test scenarios
```
