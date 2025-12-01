# Development Guide

Guide for contributing to, testing, and debugging the Home Automation Agent.

## Table of Contents

- [Setup Development Environment](#setup-development-environment)
- [Code Patterns](#code-patterns)
- [Testing](#testing)
- [Debugging](#debugging)
- [Adding Features](#adding-features)
- [Performance Guidelines](#performance-guidelines)

## Setup Development Environment

### 1. Clone and Setup

```bash
# Clone repository
git clone <repo-url>
cd Smarthome

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your keys
```

### 2. Start Home Assistant

```bash
# Start HA container
docker compose up -d

# Check it's running
docker ps

# View logs
docker logs -f homeassistant
```

### 3. Verify Setup

```bash
python utils.py --check
```

## Code Patterns

### Conventional Commits

Use Conventional Commits format for all git commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Add/update tests
- `chore`: Maintenance tasks

**Examples**:
```bash
git commit -m "feat(lights): add fire flickering effect"
git commit -m "fix(specialist): handle missing scene gracefully"
git commit -m "docs: update API reference with new tools"
```

### Anti-Over-Engineering

Follow these principles (from [.claude/README.md](../.claude/README.md)):

**DON'T**:
- ❌ Add features beyond what's requested
- ❌ Refactor code that isn't being changed
- ❌ Add docstrings/comments to untouched code
- ❌ Add error handling for impossible scenarios
- ❌ Create helpers for one-time operations
- ❌ Use backwards-compatibility shims

**DO**:
- ✅ Make changes directly requested
- ✅ Keep solutions simple and focused
- ✅ Trust internal code and framework guarantees
- ✅ Only validate at system boundaries

### Performance-First

**Always check native capabilities before building custom solutions!**

```python
# BAD: Software emulation (11 API calls)
for step in range(11):
    send_api_request(brightness=random(), color=random())

# GOOD: Native capability (1 API call)
activate_dynamic_scene(scene="Fire", dynamic=True)
```

**When designing features, ask**:
1. Can the device/system handle this natively?
2. How many API calls does this require?
3. Does this loop need to run, or can it be event-driven?
4. Am I using the right model? (Haiku vs Sonnet)
5. Will this scale if usage increases 10x?

### Code Style

**Write for humans first**:

```python
# Bad - cryptic
def proc_sc(r, ct, b):
    return {"entity_id": f"light.{r}_lamp", "color_temp": 1000000/ct}

# Good - clear
def set_room_color_temp(room: str, kelvin: int, brightness_pct: int):
    """Set room lighting with specific color temperature."""
    mireds = 1000000 / kelvin
    return {
        "entity_id": f"light.{room}_lamp",
        "color_temp": mireds,
        "brightness_pct": brightness_pct
    }
```

**Use type hints**:
```python
from typing import Dict, List, Optional

def get_hue_scenes(room: str) -> Dict:
    """Get available scenes for room."""
    ...

def suggest_effect(description: str, scenes: List[str]) -> Optional[Dict]:
    """Map description to best scene."""
    ...
```

## Testing

### Manual Testing

```bash
# Test basic ambiance
python agent.py "turn living room to fire"

# Test abstract effects
python agent.py "make me feel like I'm under the sea"

# Test flickering
python agent.py "flickering fire in living room"
```

### Test Suite

```bash
# Interactive test suite
python tests/test_lights.py

# Quick automated test
python tests/test_lights.py --quick
```

### Utility Commands

```bash
# Check setup
python utils.py --check

# List all lights
python utils.py --list-lights

# Test HA connection
python utils.py --test-ha

# Test API key
python utils.py --test-api
```

### Testing Without Lights

To iterate on prompts/logic without controlling actual lights:

```python
# In tools/lights.py, comment out the actual API call:
# response = requests.post(url, headers=headers, json=payload, timeout=10)

# Replace with mock success:
return {
    "success": True,
    "message": f"[MOCK] Would set {room} to {color_temp_kelvin}K, {brightness_pct}%"
}
```

## Debugging

### View Agent Decisions

Agent runs in verbose mode by default, showing:
- Tool calls and parameters
- HA API responses
- Specialist agent reasoning

```bash
python agent.py "turn living room to fire"
```

Output:
```
============================================================
User: turn living room to fire
============================================================

[Iteration 1] Stop reason: tool_use

[Tool Call: set_room_ambiance]
Input: {
  "room": "living_room",
  "color_temp_kelvin": 2200,
  "brightness_pct": 50,
  "description": "fire"
}
Result: {
  "success": true,
  "mireds": 454,
  ...
}
```

### Debug Specialist Agent

Add logging to [tools/hue_specialist.py](../tools/hue_specialist.py):

```python
def suggest_effect_for_description(self, description: str, available_scenes: List[str]) -> Dict:
    print(f"[Specialist] Analyzing: '{description}'")
    print(f"[Specialist] Available scenes: {available_scenes}")

    response = self.client.messages.create(...)

    print(f"[Specialist] Response: {response.content[0].text}")
    return recommendation
```

### Test HA API Directly

```bash
# Test light control
curl -X POST http://localhost:8123/api/services/light/turn_on \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "light.living_room",
    "color_temp": 370,
    "brightness_pct": 50
  }'

# Test scene activation
curl -X POST http://localhost:8123/api/services/hue/activate_scene \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "scene.living_room_arctic_aurora",
    "dynamic": true,
    "speed": 25
  }'

# Get all scenes
curl http://localhost:8123/api/states/light.living_room \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Check Home Assistant Logs

```bash
# View logs in real-time
docker logs -f homeassistant

# Search for errors
docker logs homeassistant 2>&1 | grep -i error

# Check specific integration
docker logs homeassistant 2>&1 | grep -i hue
```

### Common Issues

**Agent not calling tools**:
- Check system prompt clarity
- Verify tool descriptions are clear
- Look for errors in agent response

**Tools returning errors**:
- Verify HA is running: `docker ps`
- Check `HA_TOKEN` is valid
- Test HA API directly with curl

**Lights not responding**:
- Verify lights support color temperature
- Check entity IDs in `room_entity_map`
- Test in HA UI first

**Scene not found**:
```python
# List available scenes
from tools.effects import get_hue_scenes
import json
print(json.dumps(get_hue_scenes("living_room"), indent=2))
```

## Adding Features

### Adding a New Tool

1. **Implement the function** in `tools/`:

```python
# tools/vacuum.py
def start_vacuum(room: str) -> dict:
    """Start vacuum cleaning in specified room."""
    # Implementation
    return {"success": True, "message": f"Started cleaning {room}"}
```

2. **Import in agent.py**:

```python
from tools.vacuum import start_vacuum
```

3. **Add to tool definitions**:

```python
tools = [
    {
        "name": "start_vacuum",
        "description": "Start robot vacuum in a specific room",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {"type": "string", "description": "Room to clean"}
            },
            "required": ["room"]
        }
    },
    # ... other tools
]
```

4. **Add to tool handler**:

```python
def process_tool_call(tool_name: str, tool_input: dict) -> dict:
    if tool_name == "start_vacuum":
        return start_vacuum(room=tool_input["room"])
    # ... other tools
```

5. **Update system prompt** if needed:

```
# prompts/config.json
You can also control the robot vacuum...
```

6. **Test**:

```bash
python agent.py "clean the living room"
```

### Adding a Specialist Agent

1. **Create specialist class** in `tools/`:

```python
# tools/vacuum_specialist.py
class VacuumSpecialist:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.knowledge = """[Domain knowledge here]"""

    def plan_cleaning_route(self, rooms: List[str]) -> List[Dict]:
        """Plan optimal cleaning route."""
        # Consult LLM
        return plan

# Singleton
_specialist = None
def get_vacuum_specialist() -> VacuumSpecialist:
    global _specialist
    if _specialist is None:
        _specialist = VacuumSpecialist()
    return _specialist
```

2. **Use in main tool**:

```python
from .vacuum_specialist import get_vacuum_specialist

def start_vacuum_optimized(rooms: List[str]) -> dict:
    specialist = get_vacuum_specialist()
    route = specialist.plan_cleaning_route(rooms)
    # Execute route
    return {"success": True, "route": route}
```

### Modifying System Prompt

Edit [prompts/config.json](../prompts/config.json):

```
You are a home automation assistant...

When users describe lighting scenes:
- "fire" → 2000-2500K, 40-60% brightness
- "ocean" → 5000-6500K, 50-70% brightness
[Add new interpretations here]

Use your judgment...
```

Test changes:
```bash
python agent.py "your test command"
```

## Performance Guidelines

### Minimize API Calls

```python
# BAD: N+1 queries
for room in rooms:
    get_room_state(room)  # N API calls

# GOOD: Single batch query
states = get_all_room_states()  # 1 API call
for room in rooms:
    state = states[room]
```

### Use Appropriate Models

```python
# For complex reasoning (scene interpretation)
model = "claude-sonnet-4-20250514"

# For simple tasks (parameter extraction)
model = "claude-haiku-3-5-20250514"  # 10x cheaper!
```

### Cache When Possible

```python
# BAD: Query every time
scenes = get_hue_scenes(room)  # API call

# GOOD: Cache for duration
_scenes_cache = {}
def get_hue_scenes_cached(room: str) -> List[str]:
    if room not in _scenes_cache:
        _scenes_cache[room] = get_hue_scenes(room)
    return _scenes_cache[room]
```

### Prefer Event-Driven

```python
# BAD: Polling
while True:
    if motion_detected():
        turn_on_lights()
    sleep(1)  # Wasteful!

# GOOD: Event-driven
def on_motion_event(event):
    turn_on_lights()
```

## File Organization

```
Smarthome/
├── agent.py              # Main coordinator - keep under 300 lines
├── utils.py              # Setup/debug utilities
│
├── tools/
│   ├── lights.py         # Lighting control
│   ├── effects.py        # Advanced effects
│   ├── hue_specialist.py # Hue domain expert
│   └── [new_domain].py   # Add new domains here
│
├── prompts/
│   └── system_prompt.txt # Main agent behavior
│
├── tests/
│   ├── test_lights.py
│   └── test_[feature].py # Add tests for new features
│
└── docs/                 # All documentation
    ├── README.md
    ├── getting-started.md
    ├── architecture.md
    ├── api-reference.md
    ├── development.md    # ← You are here
    └── session-log.md
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feat/vacuum-control

# Make changes
# ... edit files ...

# Commit with conventional format
git add .
git commit -m "feat(vacuum): add room-specific cleaning"

# Push
git push origin feat/vacuum-control

# Create PR
```

## Documentation Updates

After significant changes, update docs:

1. **API changes** → Update [api-reference.md](api-reference.md)
2. **Architecture changes** → Update [architecture.md](architecture.md)
3. **New features** → Update [getting-started.md](getting-started.md)
4. **Session progress** → Update [session-log.md](session-log.md)

**Docs should live in `docs/` folder** - ask before creating new documentation files.

## Need Help?

- **Setup issues**: See [getting-started.md](getting-started.md)
- **How it works**: See [architecture.md](architecture.md)
- **API reference**: See [api-reference.md](api-reference.md)
- **Project history**: See [session-log.md](session-log.md)
