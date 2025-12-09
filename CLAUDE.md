# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Self-hosted, AI-powered smart home assistant built on Home Assistant. Uses Claude Sonnet 4 via Anthropic API for natural language processing with multi-agent architecture. Replaces commercial ecosystems (Alexa/Google) with privacy-focused, open-source automation.

**Core Philosophy**: Minimal personality, wake-word activated, self-monitoring, LLM-powered natural language understanding.

**CURRENT STATUS (2025-12-09):** Starting from scratch. Previous implementation has been deleted. We have comprehensive planning documents (REQUIREMENTS.md, priorities.md, BUSINESS_VALUE_ANALYSIS.md, PARALLEL_EXECUTION_ROADMAP.md) but NO CODE yet. Ready to begin Phase 1 implementation.

## Development Commands

**NOTE:** These commands will work once we build the system. Currently nothing is implemented.

### Setup (Future)
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Required: ANTHROPIC_API_KEY, HA_TOKEN, HA_URL
```

### Running the System (Future)
```bash
# CLI mode (single command)
python agent.py "turn living room to fire"

# Web server (persistent UI)
python server.py
# Access at http://localhost:5000

# Docker deployment (Home Assistant + Agent)
docker-compose up -d
docker-compose logs agent
docker-compose logs homeassistant
```

### Testing (Future)
```bash
# Manual test scenarios
python tests/test_lights.py

# End-to-end tests
python test_e2e.py
```

## Architecture (Planned)

**NOTE:** This describes the target architecture. Nothing is implemented yet.

### Multi-Agent System

**Main Agent** (`agent.py` - TO BUILD):
- Coordinates all user requests
- Interprets natural language → tool calls
- Uses Claude Sonnet 4 with function calling
- 5-iteration max loop

**Specialist Agents** (`tools/hue_specialist.py` - TO BUILD):
- Deep domain expertise (Philips Hue API knowledge)
- Maps abstract descriptions → optimal Hue scenes
- Consulted by tools, not directly by user
- Example: "under the sea" → Arctic aurora scene with dynamic mode

### Request Flow

```
User Command
  ↓
Main Agent (agent.py) - interprets intent
  ↓
Tool Selection (set_room_ambiance, apply_abstract_effect, etc.)
  ↓
Specialist Consultation (if needed) - HueSpecialist recommends scene
  ↓
Home Assistant API call
  ↓
Device Control (Philips Hue Bridge)
```

### Key Design Patterns

1. **Native Over Software**: Always prefer device-native capabilities (Hue dynamic scenes) over API-emulated effects (software flickering)
   - Good: 1 API call, loops indefinitely on hardware
   - Bad: 11+ API calls, finite duration, network-intensive

2. **Tool Descriptions Guide Selection**: Tool metadata tells main agent when to use which approach

3. **Specialist Pattern**: Domain expertise separated into specialist agents, keeping main agent focused on coordination

## File Structure

**CURRENT (Week 0):**
```
Smarthome/
├── CLAUDE.md             # This file - development guide
├── plans/
│   ├── REQUIREMENTS.md   # 37 requirements document
│   ├── priorities.md     # Strategic priorities analysis
│   ├── BUSINESS_VALUE_ANALYSIS.md  # Value analysis
│   └── PARALLEL_EXECUTION_ROADMAP.md  # Implementation roadmap
└── (everything else to be built)
```

**TARGET (Once Built):**
```
Smarthome/
├── agent.py              # Main coordinator agent (Claude Sonnet 4)
├── server.py             # Flask web UI server
├── config.py             # Shared constants (ROOM_ENTITY_MAP, etc.)
├── utils.py              # Setup checks, prompt loading, usage tracking
├── tools/
│   ├── lights.py         # set_room_ambiance, apply_fire_flicker
│   ├── effects.py        # apply_abstract_effect, activate_dynamic_scene
│   ├── hue_specialist.py # HueSpecialist agent class
│   ├── review_agent.py   # Prompt review assistant
│   └── prompt_improvement_agent.py  # Chatbot for prompt tuning
├── prompts/
│   └── config.json       # System prompts (main_agent, hue_specialist)
├── tests/
│   └── test_lights.py    # Manual test scenarios
├── test_e2e.py           # End-to-end API tests
├── docs/                 # Architecture, API reference, guides
└── logs/                 # Server and tunnel logs
```

## Critical Technical Details

### Color Temperature Conversion
Philips Hue uses **mireds** (micro reciprocal degrees), not Kelvin:
```python
mireds = 1000000 / kelvin
# 2700K (warm) = 370 mireds
# 5000K (cool) = 200 mireds
# Valid range: 153-500 mireds (~2000K-6500K)
```

### Home Assistant API Authentication
All requests require:
```python
headers = {"Authorization": f"Bearer {HA_TOKEN}"}
```

### Service Calls

**Basic lighting**:
```python
POST /api/services/light/turn_on
{
  "entity_id": "light.living_room",
  "color_temp": 370,
  "brightness_pct": 50
}
```

**Dynamic Hue scenes** (preferred):
```python
POST /api/services/hue/activate_scene
{
  "entity_id": "scene.living_room_arctic_aurora",
  "dynamic": true,
  "speed": 25,  # 0=slow, 100=fast
  "brightness": 60
}
```

### Agent Loop Pattern
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
        # Execute tools, add results to messages, continue
```

## Configuration

### Room Entity Mapping
Edit `config.py` to map room names to Home Assistant entity IDs:
```python
ROOM_ENTITY_MAP = {
    "living_room": "light.living_room",
    "bedroom": "light.bedroom"
}
```

### System Prompts
Edit `prompts/config.json` to modify agent behavior:
- `main_agent.system`: Main coordinator instructions
- `hue_specialist.system`: Hue scene mapping knowledge

## Cost Tracking

- Daily average target: ≤ $2/day
- Alert threshold: $5/day
- Token usage tracked via `utils.track_api_usage()`
- Check usage: `utils.get_daily_usage()`

## Requirements & Planning Documents

Full project documentation in `plans/` directory:
- **REQUIREMENTS.md** - 37 requirements across 8 phases
- **priorities.md** - Strategic priorities and ROI analysis
- **BUSINESS_VALUE_ANALYSIS.md** - Value analysis for each requirement
- **PARALLEL_EXECUTION_ROADMAP.md** - Multi-agent execution plan

**Current status:** Week 0 - Nothing implemented yet, starting Phase 1
**Next steps:** Build foundation (REQ-001, 002, 003, 006, 015) - Weeks 1-6

## Performance Metrics

- Response time: 1-2 seconds typical
- Scene activation: 1 API call, runs indefinitely
- API flickering: 11+ calls over 15 seconds (avoid when possible)
- Token usage per command: 300-500 tokens typical

## Known Patterns

### Abstract Effect Request
User says "make me feel like I'm under the sea":
1. Main agent recognizes abstract description
2. Calls `apply_abstract_effect(description="under the sea", room="living_room")`
3. Tool consults HueSpecialist agent
4. Specialist recommends: `{"scene": "Arctic aurora", "dynamic": true, "speed": 25, "reasoning": "Cool blues simulate underwater"}`
5. Tool activates scene via `hue.activate_scene` service
6. Effect loops indefinitely on Hue bridge hardware

### Simple Ambiance Request
User says "turn living room to fire":
1. Main agent interprets mood
2. Calls `set_room_ambiance(room="living_room", color_temp_kelvin=2200, brightness_pct=50)`
3. Tool converts Kelvin → mireds, makes single HA API call
4. Lights change instantly

## Adding New Devices

1. Integrate device in Home Assistant
2. Add entity ID to `config.py` ROOM_ENTITY_MAP (for lights) or create new tool
3. Create tool function in `tools/` if new device type
4. Add tool to agent's available tools in `agent.py`
5. Update system prompt if specialized knowledge needed

## Git Workflow

**Fresh Start (2025-12-09):**
- Previous implementation completely deleted
- All planning documents created (REQUIREMENTS.md, priorities.md, etc.)
- Clean slate for systematic rebuild
- Starting from Week 0 with no code

**Git commit structure:**
- e29e890: "Final commit before fresh start" - deleted all previous code
- Now: Building from scratch based on comprehensive requirements

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY`: Claude API access
- `HA_TOKEN`: Home Assistant long-lived access token
- `HA_URL`: Home Assistant URL (default: http://localhost:8123)

## Future Migration Paths

1. **Local LLM**: Replace Claude API with Ollama + Qwen
2. **Local Voice**: Replace Alexa with HA Wyoming protocol + Whisper
3. **Multi-user**: Guest mode with permission levels (Phase 2)
4. **Pattern Learning**: Suggest automations based on usage (Phase 6)
