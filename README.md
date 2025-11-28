# Home Automation Agent Project

## Overview
Building a custom voice-controlled home automation system using agentic AI patterns. This project replaces Alexa's built-in intelligence with a custom LLM-powered agent that provides more nuanced control over smart home devices.

## The Problem We're Solving
Current issue: "Alexa, turn living room to fire" results in aggressive red lighting instead of a warm, flickering campfire ambiance. We want natural language commands to be interpreted intelligently and create the intended atmosphere.

## Goals

### Immediate Goals (Phase 1-3)
- Control Philips Hue lights with nuanced, natural language descriptions
- Run Dreamehome vacuum via voice commands or triggers
- Set and edit routines/automations via voice

### Future Goals
- Search and order products with human-in-the-loop approval
- Location-based automations (e.g., run vacuum when leaving house)
- Learn preferences over time
- Eventually run entirely locally (migrate from cloud LLMs to local models like Qwen)

## Architecture

```
┌──────────────┐
│    ALEXA     │ (Voice Input/Output - Phase 2)
└──────┬───────┘
       │ Alexa Skill forwards text
       ↓
┌──────────────────────────────────┐
│     YOUR AGENT (Python)          │
│  ┌────────────────────────────┐  │
│  │  System Prompt             │  │
│  │  "You control smart home..." │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │  Tools/Functions:          │  │
│  │  - set_room_ambiance()     │  │
│  │  - control_vacuum()        │  │
│  │  - create_automation()     │  │
│  │  - query_device_state()    │  │
│  └────────────────────────────┘  │
│         ↓ calls                  │
│  ┌────────────────────────────┐  │
│  │  Claude/GPT API            │  │
│  │  (eventually: local LLM)   │  │
│  └────────────────────────────┘  │
└──────────────┬───────────────────┘
               │ REST API calls
               ↓
┌──────────────────────────────────┐
│    HOME ASSISTANT                │
│  - Hue Integration               │
│  - Dreame Integration            │
│  - Automation Engine             │
│  - State Storage                 │
│  - REST API                      │
└──────────────────────────────────┘
```

## Tech Stack

### Current
- **Home Assistant**: Device control and automation platform (runs in Docker on old laptop)
- **Claude API**: LLM for agent intelligence (Anthropic)
- **Python**: Agent implementation
- **Alexa Custom Skill**: Voice interface (Phase 2)
- **Philips Hue**: Smart lighting
- **Dreamehome**: Robot vacuum

### Future Migration Path
- Replace Claude API with local LLM (Ollama + Qwen)
- Replace Alexa with local voice (Home Assistant Wyoming protocol + Whisper)

## Project Phases

### Phase 0: Foundation (Setup - ~30 minutes)
**Goal:** Get Home Assistant running and connected to devices

**Tasks:**
- [ ] Install Home Assistant via Docker on old laptop
- [ ] Complete HA onboarding wizard
- [ ] Connect Philips Hue bridge (auto-discovery)
- [ ] Verify manual light control in HA UI
- [ ] Generate Long-Lived Access Token for API access
- [ ] Test HA REST API with curl/Postman

**Success Criteria:** Can turn lights on/off via HA UI and REST API

---

### Phase 1: The "Fire" Problem (CURRENT - Week 1)
**Goal:** Agent interprets natural language descriptions and creates appropriate lighting ambiance

**Learning Objectives:**
- Basic request-response agent pattern (syllabus week 1)
- Tool use and function calling
- Natural language → structured parameters
- System prompt engineering

**Tasks:**
- [x] Set up basic agent with Claude API
- [x] Define system prompt for lighting interpretation
- [x] Implement `set_room_ambiance()` tool
  - [x] Query HA for lights in specified room
  - [x] Convert color temperature (Kelvin) to Hue settings
  - [x] Call HA `light.turn_on` service with parameters
- [ ] Test with various descriptions:
  - [ ] "fire" → warm (2000-2500K), medium brightness (40-60%)
  - [ ] "ocean" → cool blue (5000-6500K), medium-bright (50-70%)
  - [ ] "cozy" → warm (2200-2700K), dim (30-50%)
  - [ ] "energizing" → cool white (4000-5000K), bright (80-100%)
- [ ] Refine system prompt until outputs feel right
- [ ] (Optional) Add subtle flickering effect for "fire" scene

**Success Criteria:** 
```bash
python agent.py "turn living room to fire"
# → Lights turn warm orange with appropriate brightness
# → Agent responds: "I've set the living room to a warm, fire-like glow"
```

**Key Design Decisions:**
1. **Scene Interpretation:** Let Claude interpret descriptions dynamically vs pre-defined mappings
2. **Tool Granularity:** Start with mid-level `set_room_ambiance()`, not raw `set_light_color()`
3. **Room Identification:** Hardcode entity IDs initially, make dynamic later

---

### Phase 2: Voice Integration (Week 2)
**Goal:** Control via actual voice commands through Alexa

**Learning Objectives:**
- Integration points and webhooks
- Async request handling
- End-to-end system testing

**Tasks:**
- [ ] Create custom Alexa skill in AWS console
- [ ] Set up ngrok or similar tunnel to laptop
- [ ] Create webhook endpoint in agent code
- [ ] Forward Alexa intent → agent → HA
- [ ] Handle async responses
- [ ] Test end-to-end: voice → action

**Success Criteria:** "Alexa, ask home brain to make the living room cozy" → lights adjust

---

### Phase 3: Vacuum Control (Week 2-3)
**Goal:** Add second device type to demonstrate multi-tool agents

**Learning Objectives:**
- Multi-tool agent coordination
- Different device APIs/capabilities
- Command interpretation variety

**Tasks:**
- [ ] Add Dreame vacuum integration to HA
- [ ] Implement `control_vacuum()` tool
  - [ ] Start/stop/pause cleaning
  - [ ] Room-specific cleaning
  - [ ] Return to dock
- [ ] Update system prompt for vacuum commands
- [ ] Test: "clean the living room" → vacuum runs

**Success Criteria:** Can control both lights and vacuum via natural language

---

### Phase 4: Context & Memory (Week 4 - Reflection)
**Goal:** Agent learns and remembers user preferences

**Learning Objectives:**
- Reflection pattern (syllabus week 4)
- Note-taking agents
- Preference learning

**Tasks:**
- [ ] Implement note-taking system (SQLite or JSON)
- [ ] Agent records observations: "user prefers 'fire' = 2200K, 50% brightness"
- [ ] Agent queries notes before responding
- [ ] Add `remember_preference()` and `recall_preference()` tools
- [ ] Test learning loop: correct agent → it remembers for next time

**Success Criteria:** After using "fire" scene a few times and tweaking it, agent learns your preferred settings

---

### Phase 5: Automation Creation (Week 5-6)
**Goal:** Create routines/automations via voice

**Learning Objectives:**
- Complex structured output generation
- YAML/config file manipulation
- Multi-step task completion

**Tasks:**
- [ ] Study HA automation YAML format
- [ ] Implement `create_automation()` tool
  - [ ] Parse trigger descriptions (time, location, device state)
  - [ ] Parse action descriptions
  - [ ] Generate valid HA automation YAML
  - [ ] Write to HA config or use HA API
- [ ] Test: "When I leave the house, run the vacuum"
- [ ] Test: "Every weekday at 7am, turn bedroom lights to energizing"

**Success Criteria:** Voice-created automations appear in HA and execute correctly

---

### Phase 6: Location-Based Triggers (Week 6-7)
**Goal:** Autonomous agents responding to real-world events

**Learning Objectives:**
- Event-driven agent patterns
- Autonomous agents (syllabus week 5-6)
- State monitoring

**Tasks:**
- [ ] Install HA Companion App on phone
- [ ] Set up location tracking in HA
- [ ] Agent monitors location state changes
- [ ] Trigger automations based on location
- [ ] Test: Leave house → vacuum starts automatically

**Success Criteria:** Automations trigger without voice commands based on context

---

### Phase 7: Local LLM Migration (Future)
**Goal:** Run everything locally without cloud APIs

**Tasks:**
- [ ] Set up Ollama on laptop
- [ ] Download Qwen model
- [ ] Modify agent code to use local LLM
- [ ] Test performance vs Claude
- [ ] Replace Alexa with Wyoming protocol voice

**Success Criteria:** System works identically but entirely offline

---

## System Prompt (Starting Point - Phase 1)

```
You are a home lighting assistant that controls Philips Hue smart lights.

When users describe a mood, scene, or atmosphere, you interpret it into specific 
lighting parameters. Consider:

- Color temperature (warm = 2000-2700K, neutral = 3000-4000K, cool = 5000-6500K)
- Brightness percentage (0-100%)
- The emotional quality they're trying to create

Examples of interpretations:
- "fire/campfire/warm glow" → very warm, medium brightness
- "ocean/water/beach" → cool blue tones, medium-bright
- "cozy/relaxing/intimate" → warm, dimmer
- "energizing/focus/productive" → cool white, bright
- "romantic" → very warm, very dim
- "reading" → neutral-warm, bright

Use your judgment. Prioritize comfort and the user's aesthetic preferences.
When unsure, you can ask clarifying questions.
```

## Key Technical Details

### Home Assistant API Basics

**Authentication:**
```bash
# All requests need this header:
Authorization: Bearer YOUR_LONG_LIVED_TOKEN
```

**Turn on lights with color temp:**
```bash
curl -X POST http://localhost:8123/api/services/light/turn_on \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "light.living_room_lamp",
    "color_temp": 370,
    "brightness_pct": 50
  }'
```

**Get all lights in an area:**
```bash
curl http://localhost:8123/api/states \
  -H "Authorization: Bearer YOUR_TOKEN"
# Filter response for entities in specific area
```

### Color Temperature Notes
- Hue uses "mireds" not Kelvin
- Conversion: `mireds = 1000000 / kelvin`
- Example: 2700K = 370 mireds (warm white)
- Example: 5000K = 200 mireds (cool white)

### Agent Tool Signature (Phase 1)

```python
tools = [
    {
        "name": "set_room_ambiance",
        "description": "Set lighting ambiance for a room based on mood/description",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string", 
                    "description": "Room name (e.g., 'living_room')"
                },
                "color_temp_kelvin": {
                    "type": "integer", 
                    "description": "Color temperature in Kelvin (2000-6500)"
                },
                "brightness_pct": {
                    "type": "integer", 
                    "description": "Brightness percentage (0-100)"
                },
                "description": {
                    "type": "string", 
                    "description": "What this ambiance represents (e.g., 'fire', 'ocean')"
                }
            },
            "required": ["room", "color_temp_kelvin", "brightness_pct"]
        }
    }
]
```

## Development Workflow

### Phase 1 Testing Loop
1. Run agent with text input: `python agent.py "turn living room to fire"`
2. Observe light output in real room
3. Tweak system prompt or tool parameters
4. Repeat until satisfied
5. Test with different descriptions
6. Build up a test suite of descriptions → expected outputs

### Debugging Tips
- Test HA API calls directly with curl first
- Print all LLM tool calls to see what agent is deciding
- Start with single light before multi-light rooms
- Use HA Developer Tools → Services to test service calls
- Check HA logs if integration isn't working: `docker logs homeassistant`

## File Structure (Proposed)

```
home-agent/
├── README.md (this file)
├── requirements.txt
├── .env (API keys, tokens)
├── agent.py (main agent loop)
├── tools/
│   ├── lights.py (Hue control via HA)
│   ├── vacuum.py (Dreame control)
│   └── automations.py (automation creation)
├── prompts/
│   └── system_prompt.txt
├── tests/
│   ├── test_lights.py
│   └── test_vacuum.py
└── data/
    ├── preferences.json (learned preferences - Phase 4)
    └── automations.yaml (generated automations - Phase 5)
```

## Resources

### Documentation
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)
- [Anthropic Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Philips Hue API](https://developers.meethue.com/)
- [Home Assistant Hue Integration](https://www.home-assistant.io/integrations/hue/)

### Course Alignment
This project maps to your Agentic Design syllabus:
- **Week 1 (Request-Response):** Phase 1-3
- **Week 2 (RAG):** Phase 5 (reading HA automation docs)
- **Week 4 (Reflection/Notes):** Phase 4
- **Week 5-6 (Autonomous Agents):** Phase 6
- **Week 7 (Multi-Process/Swarm):** Future expansion

## Next Steps

**Right Now:**
1. Complete Phase 0 setup (30 minutes)
2. Start Phase 1 implementation
3. Get first successful "fire" scene working

**This Week:**
- Iterate on Phase 1 until lighting feels right
- Test with 5-10 different scene descriptions
- Document what works well vs what doesn't

**Next Week:**
- Add voice integration (Phase 2)
- Begin vacuum control (Phase 3)

## Notes & Learnings

### Design Decisions Log
- **Why HA instead of direct Hue API?** HA provides abstraction layer that makes it easy to add other devices later. Also handles device discovery, state management, and automations.
- **Why Claude over local LLM initially?** Better quality for learning/prototyping. Will migrate to local later once patterns are established.
- **Why Alexa for voice initially?** Already have the hardware, good microphones. Local voice requires additional hardware/setup.

### Things to Figure Out
- How granular should tool definitions be?
- Should agent create one-off scenes or persistent HA scenes?
- How to handle multi-light coordination for realistic "fire" effect?
- What's the best way to store/version system prompts?

### Future Ideas
- Agent analyzes time of day and suggests appropriate lighting
- "Learn my morning routine" - agent watches and offers to automate
- Integration with calendar for context-aware automations
- Music-reactive lighting
- Agent explains its reasoning for debugging

---

**Last Updated:** November 27, 2024
**Current Phase:** Phase 0 → Phase 1
**Next Milestone:** First successful "fire" scene interpretation
