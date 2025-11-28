# Quick Start - Phase 1

Get your home automation agent running in 5 minutes!

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Configure Environment

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your credentials
# - Get Anthropic API key from: https://console.anthropic.com
# - Get HA token from: Profile → Long-Lived Access Tokens
```

## 3. Check Your Setup

```bash
python utils.py --check
```

This will verify:
- ✓ Your Anthropic API key works
- ✓ Home Assistant is accessible
- ✓ Both services are responding correctly

## 4. Configure Your Rooms

```bash
# List all available lights
python utils.py --list-lights
```

Edit `tools/lights.py` and update the `room_entity_map` with your entity IDs:

```python
room_entity_map = {
    "living_room": "light.living_room",  # ← Change these to match your lights
    "bedroom": "light.bedroom",
    # ... add more rooms
}
```

## 5. Test It!

```bash
# Try the classic "fire" problem
python agent.py "turn living room to fire"

# Try other scenes
python agent.py "make bedroom cozy"
python agent.py "set office to energizing"
```

## 6. Run Test Suite

```bash
# Interactive test suite
python tests/test_lights.py

# Quick automated test
python tests/test_lights.py --quick
```

## What's Next?

- **Iterate on prompts**: Edit `prompts/system_prompt.txt` to fine-tune interpretations
- **Test edge cases**: Try ambiguous commands and see how the agent handles them
- **Add more rooms**: Expand your `room_entity_map` as you add more lights
- **Move to Phase 2**: Add voice control with Alexa

## Troubleshooting

**Command not working?**
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

**See full setup guide**: `SETUP.md`

## Example Commands to Try

```bash
# Warm scenes
python agent.py "campfire vibes in the living room"
python agent.py "romantic lighting in the bedroom"
python agent.py "cozy movie night in the living room"

# Cool scenes
python agent.py "ocean atmosphere in the bedroom"
python agent.py "energizing office lighting"
python agent.py "bright focus mode in the kitchen"

# Activity-based
python agent.py "reading light in the office"
python agent.py "dinner party ambiance in the dining room"
python agent.py "wake up lighting in the bedroom"
```

Have fun experimenting! 🔥💡
