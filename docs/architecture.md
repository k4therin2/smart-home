# Architecture

This document explains how the Home Automation Agent system works.

## System Overview

```
┌──────────────┐
│    ALEXA     │ (Voice Input/Output - Phase 2, planned)
└──────┬───────┘
       │ Alexa Skill forwards text
       ↓
┌──────────────────────────────────┐
│     MAIN AGENT (Python)          │
│  ┌────────────────────────────┐  │
│  │  System Prompt             │  │
│  │  "You control smart home..." │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │  Tools/Functions:          │  │
│  │  - set_room_ambiance()     │  │
│  │  - apply_fire_flicker()    │  │
│  │  - apply_abstract_effect() │  │
│  │  - get_available_rooms()   │  │
│  └────────────────────────────┘  │
│         ↓ consults               │
│  ┌────────────────────────────┐  │
│  │  SPECIALIST AGENTS         │  │
│  │  - Hue Specialist          │  │
│  │  (plans effects, maps      │  │
│  │   descriptions to scenes)  │  │
│  └────────────────────────────┘  │
│         ↓ calls                  │
│  ┌────────────────────────────┐  │
│  │  Claude API (Sonnet 4)     │  │
│  └────────────────────────────┘  │
└──────────────┬───────────────────┘
               │ REST API calls
               ↓
┌──────────────────────────────────┐
│    HOME ASSISTANT                │
│  - Hue Integration               │
│  - Scene Management              │
│  - REST API                      │
└──────────────┬───────────────────┘
               │ Controls
               ↓
┌──────────────────────────────────┐
│    PHILIPS HUE BRIDGE            │
│  - 25 Hue lights                 │
│  - Dynamic scenes                │
│  - Native effects                │
└──────────────────────────────────┘
```

## Multi-Agent Design

### Main Agent (Coordinator)
**File**: [agent.py](../agent.py)

Responsibilities:
- Receives natural language commands
- Selects appropriate tools based on intent
- Coordinates with specialist agents when needed
- Returns user-friendly responses

Example flow:
```python
User: "make me feel like I'm under the sea"
  ↓
Main Agent: Recognizes abstract effect request
  ↓
Main Agent: Calls apply_abstract_effect() tool
  ↓
Tool: Consults Hue Specialist
  ↓
Specialist: Maps "under the sea" → "Arctic aurora" scene
  ↓
Tool: Activates dynamic scene on Hue bridge
  ↓
Main Agent: Responds "Perfect! I've activated a dynamic underwater effect..."
```

### Specialist Agent (Hue Expert)
**File**: [tools/hue_specialist.py](../tools/hue_specialist.py)

Responsibilities:
- Deep knowledge of Philips Hue API capabilities
- Plans complex lighting effects (flickering, fading, etc.)
- Maps abstract descriptions to optimal Hue scenes
- Optimizes for performance (native capabilities > API calls)

Knowledge base includes:
- Hue service calls and parameters
- Dynamic scene capabilities
- Color temperature ranges
- Best practices for realistic effects

## Request-Response Flow

### 1. Simple Ambiance Request

```
User: "turn living room to fire"
  ↓
Main Agent (Claude Sonnet 4)
  ├─ Interprets: warm, flickering ambiance
  ├─ Selects tool: set_room_ambiance()
  └─ Parameters:
      - room: "living_room"
      - color_temp_kelvin: 2200
      - brightness_pct: 50
  ↓
tools/lights.py
  ├─ Converts Kelvin → mireds
  ├─ Maps room → entity_id
  └─ HTTP POST to Home Assistant API
  ↓
Home Assistant
  ├─ Routes to Hue integration
  └─ Sends command to Hue bridge
  ↓
Philips Hue Lights
  └─ Change to warm orange, 50% brightness
```

**Performance**: 1 API call, ~1-2 second response time

### 2. Abstract Effect Request

```
User: "make me feel like I'm under the sea"
  ↓
Main Agent (Claude Sonnet 4)
  ├─ Recognizes abstract/creative description
  ├─ Selects tool: apply_abstract_effect()
  └─ Parameters:
      - description: "under the sea"
      - room: "living_room"
  ↓
tools/effects.py
  ├─ Gets available Hue scenes
  └─ Consults Hue Specialist Agent
  ↓
Hue Specialist (Claude Sonnet 4)
  ├─ Analyzes: "under the sea" mood
  ├─ Available scenes: [Arctic aurora, Nebula, Fire, ...]
  ├─ Recommendation:
  │   - scene: "Arctic aurora"
  │   - speed: 25
  │   - brightness_pct: 60
  │   - reasoning: "Cool blues/greens simulate underwater light"
  └─ Returns JSON
  ↓
tools/effects.py
  └─ Calls activate_dynamic_scene()
  ↓
Home Assistant (hue.activate_scene service)
  └─ Parameters: {entity_id: "scene.living_room_arctic_aurora", dynamic: true, speed: 25}
  ↓
Philips Hue Bridge
  └─ Activates scene with looping animation (runs indefinitely!)
```

**Performance**: 1 API call to HA, effect loops forever on hardware

### 3. Fire Flicker Effect (API-based)

```
User: "turn living room to fire" (with flickering requested)
  ↓
Main Agent
  ├─ Selects tool: apply_fire_flicker()
  └─ Parameters: {room: "living_room", duration_seconds: 15}
  ↓
tools/lights.py
  └─ Consults Hue Specialist Agent
  ↓
Hue Specialist
  ├─ Plans realistic flicker sequence
  ├─ Creates 11 steps over 15 seconds
  └─ Returns: [
      {delay: 0, brightness: 55, color_temp: 2200, transition: 0.8},
      {delay: 1.5, brightness: 48, color_temp: 2100, transition: 0.5},
      ...
    ]
  ↓
tools/lights.py
  ├─ Spawns background thread
  └─ Executes sequence:
      - Waits delay_seconds
      - Calls set_room_ambiance()
      - Repeats for each step
  ↓
Home Assistant (multiple API calls)
  └─ 11 requests over 15 seconds
  ↓
Philips Hue Lights
  └─ Flickers with varying brightness/color
```

**Performance**: 11 API calls over 15 seconds (less efficient than scenes)

## Two Effect Approaches

### Approach 1: API-Based Effects (Custom Flickering)
**Pros**:
- Full control over timing and parameters
- Can create custom sequences
- Flexible and programmable

**Cons**:
- Multiple API calls (11+ requests)
- Network bandwidth intensive
- Finite duration (effect stops after sequence completes)
- Higher cost (multiple LLM calls if planning dynamically)

**Use case**: When you need precise control or custom patterns not available as Hue scenes

### Approach 2: Native Hue Scenes (Dynamic Mode)
**Pros**:
- Single API call (1 request)
- Loops indefinitely on hardware
- Very efficient (no continuous API calls)
- Lower latency

**Cons**:
- Limited to pre-built Hue scenes
- Less customization
- Can't control individual bulb timing

**Use case**: When a Hue scene matches the desired effect (preferred approach!)

## Performance Optimization Patterns

### 1. Check Native Capabilities First

```python
# BAD: Software-emulated fire flicker
for step in range(11):
    send_api_request(brightness=random(), color=random())
    sleep(1.5)
# Result: 11 HTTP requests, 15 seconds duration, then stops

# GOOD: Native Hue scene
activate_dynamic_scene(scene="Fire", dynamic=True)
# Result: 1 HTTP request, loops indefinitely!
```

### 2. Specialist Agent Optimization

The Hue Specialist has deep knowledge of Hue capabilities, so it can:
- Recommend native scenes when available
- Plan efficient effect sequences
- Optimize for minimal API calls

### 3. Tool Descriptions Guide Selection

```python
{
    "name": "apply_abstract_effect",
    "description": "... PREFER THIS over fire_flicker for abstract/creative descriptions."
}
```

Tool descriptions tell the main agent when to use which approach.

## Tech Stack

### Current
- **Python 3.9.6**: Agent implementation
- **Claude Sonnet 4** (`claude-sonnet-4-20250514`): LLM for both main and specialist agents
- **Anthropic API**: Tool use and function calling
- **Home Assistant**: Device control platform (Docker)
- **Philips Hue**: Smart lighting (25 bulbs)
- **Flask** (planned): HTTP webhook wrapper for Lambda

### Planned Phase 2
- **AWS Lambda**: Lightweight request forwarder
- **Alexa Custom Skill**: Voice interface
- **ngrok**: Local tunneling for development

### Future Migration Path
- Replace Claude API with local LLM (Ollama + Qwen)
- Replace Alexa with local voice (Home Assistant Wyoming protocol + Whisper)

## File Structure

```
Smarthome/
├── agent.py                 # Main coordinator agent
├── utils.py                 # Setup check & debugging utilities
├── requirements.txt         # Python dependencies
│
├── .env                     # API keys (gitignored)
├── .env.example            # Template
├── .gitignore
│
├── tools/
│   ├── __init__.py
│   ├── lights.py           # set_room_ambiance, apply_fire_flicker
│   ├── effects.py          # apply_abstract_effect, activate_dynamic_scene
│   └── hue_specialist.py   # HueSpecialist agent class
│
├── prompts/
│   └── system_prompt.txt   # Main agent's behavior instructions
│
├── tests/
│   └── test_lights.py      # Manual test scenarios
│
├── data/                   # For future phases
│   └── .gitkeep
│
├── docs/                   # All documentation
│   ├── README.md
│   ├── getting-started.md
│   ├── architecture.md     # ← You are here
│   ├── api-reference.md
│   ├── development.md
│   └── session-log.md
│
├── docker-compose.yml      # Home Assistant container
│
└── .claude/
    └── README.md           # Custom Claude Code system prompt
```

## Design Patterns Established

### 1. Specialist Agents for Domain Expertise
Rather than giving the main agent all knowledge, specialist agents have deep expertise in specific domains (Hue API).

### 2. Performance-First Optimization
Always check if native device capabilities exist before building custom solutions.

### 3. Multi-Tool Approach
Keep both efficient (scenes) and flexible (API) options available. Let tool descriptions guide selection.

### 4. Tool Use for Function Calling
Main agent uses Anthropic's tool use feature to call Python functions with structured parameters.

### 5. System Prompt Engineering
System prompt guides interpretation of natural language → structured parameters.

## Key Technical Details

### Color Temperature Conversion

Hue uses "mireds" (micro reciprocal degrees), not Kelvin:

```python
mireds = 1000000 / kelvin

# Examples:
# 2700K (warm white) = 370 mireds
# 5000K (cool white) = 200 mireds
```

### Home Assistant API

**Authentication**:
All requests need header: `Authorization: Bearer YOUR_LONG_LIVED_TOKEN`

**Turn on lights**:
```bash
POST http://localhost:8123/api/services/light/turn_on
{
  "entity_id": "light.living_room",
  "color_temp": 370,
  "brightness_pct": 50
}
```

**Activate Hue scene**:
```bash
POST http://localhost:8123/api/services/hue/activate_scene
{
  "entity_id": "scene.living_room_arctic_aurora",
  "dynamic": true,
  "speed": 25,
  "brightness": 60
}
```

### Agent Loop

```python
max_iterations = 5
for iteration in range(max_iterations):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        tools=tools,
        messages=messages
    )

    if response.stop_reason == "end_turn":
        return final_response

    elif response.stop_reason == "tool_use":
        # Execute tools
        # Add results to messages
        # Continue loop
```

## Performance Metrics

### Response Times
- API flickering: ~11 requests / 15 seconds
- Scene activation: 1 request / ∞ duration
- Typical command: 1-2 seconds end-to-end

### Cost
- Complex command: ~$0.01-0.02 (Sonnet 4)
- Simple command: ~$0.005-0.01

### Token Usage
- System prompt: ~250 tokens
- Tool definitions: ~150 tokens per tool
- Typical command: 300-500 tokens total

## Next Steps

See [session-log.md](session-log.md) for:
- Phase 2: Alexa Lambda integration
- Phase 3+: Future enhancements
- Known issues and TODOs
