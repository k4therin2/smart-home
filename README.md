# Home Automation Agent

AI-powered natural language control for smart home devices. Turn vague commands like "make it feel like a campfire" into precisely orchestrated lighting scenes.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start everything
./start.sh

# 4. Test it!
python agent.py "turn living room to fire"
```

**→ Full setup guide**: [docs/getting-started.md](docs/getting-started.md)

## What This Does

Replaces simple voice assistant responses with intelligent scene interpretation:

**Before** (Standard Alexa):
```
"Alexa, turn living room to fire"
→ Harsh red lights at 100% brightness
```

**After** (This System):
```
"turn living room to fire"
→ Warm orange glow (2200K), 50% brightness, subtle flickering
→ Uses native Hue scenes for realistic fire effect (loops indefinitely)
```

## Features

- **Natural Language Lighting**: Interpret abstract descriptions ("under the sea", "cozy", "fire")
- **Multi-Agent Architecture**: Specialist agents provide domain expertise (Hue API)
- **Performance Optimized**: Native device capabilities (1 API call) vs software emulation (11+ calls)
- **Dynamic Effects**: Looping scenes that run indefinitely on hardware

## Example Commands

```bash
python agent.py "turn living room to fire"
python agent.py "make me feel like I'm under the sea"
python agent.py "cozy reading light in the bedroom"
python agent.py "energizing office lighting"
```

## Architecture

```
User Command
    ↓
Main Agent (coordinator)
    ↓
Specialist Agents (Hue expert)
    ↓
Home Assistant API
    ↓
Smart Devices (Philips Hue, 25 bulbs)
```

**→ Full architecture details**: [docs/architecture.md](docs/architecture.md)

## Current Status

**Phase 1**: ✅ Complete - Multi-agent effects system working
**Phase 2**: 🔜 Next - Alexa Lambda integration for voice control

**→ Detailed progress**: [docs/session-log.md](docs/session-log.md)

## Documentation

- **[Getting Started](docs/getting-started.md)** - 5-minute setup guide
- **[Architecture](docs/architecture.md)** - How the system works
- **[API Reference](docs/api-reference.md)** - Tools, endpoints, schemas
- **[Development](docs/development.md)** - Contributing and debugging
- **[Session Log](docs/session-log.md)** - Cross-session progress tracking

## Tech Stack

- **Python 3.9.6**: Agent implementation
- **Claude Sonnet 4**: LLM for main and specialist agents
- **Home Assistant**: Device control platform (Docker)
- **Philips Hue**: Smart lighting (25 bulbs)

## Project Structure

```
Smarthome/
├── agent.py                 # Main coordinator agent
├── tools/
│   ├── lights.py           # Lighting control
│   ├── effects.py          # Dynamic effects
│   └── hue_specialist.py   # Hue domain expert
├── prompts/
│   └── system_prompt.txt   # Agent behavior
├── docs/                   # All documentation
│   ├── README.md
│   ├── getting-started.md
│   ├── architecture.md
│   ├── api-reference.md
│   ├── development.md
│   └── session-log.md
└── docker-compose.yml      # Home Assistant container
```

## Contributing

See [docs/development.md](docs/development.md) for:
- Code patterns and conventions
- Testing guidelines
- How to add new features
- Debugging tips

## License

MIT
