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

## Docker Deployment (Recommended)

Run everything in Docker for easy deployment on any machine (Mac, Linux, **Windows**):

**→ Windows users**: See [WINDOWS_DEPLOYMENT.md](WINDOWS_DEPLOYMENT.md) for detailed guide
**→ Auto-deployment**: See [CI_CD_SETUP.md](CI_CD_SETUP.md) to auto-deploy on git push

```bash
# 1. Clone the repo
git clone https://github.com/k4therin2/smart-home.git
cd smart-home

# 2. Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and HA_TOKEN

# 3. Start both services (Home Assistant + Agent)
docker-compose up -d

# 4. Access the services
# Home Assistant: http://localhost:8123
# Agent Web UI: http://localhost:5000
```

**What this runs:**
- **Home Assistant** on port 8123 (smart home platform)
- **Home Automation Agent** on port 5000 (AI control interface)
- **Automatic networking** between services
- **Persistent data** for configs, logs, and prompts

**Check status:**
```bash
docker-compose ps              # View running containers
docker-compose logs agent      # View agent logs
docker-compose logs homeassistant  # View Home Assistant logs
docker-compose down            # Stop all services
```

## What This Does

Transforms vague lighting requests into precisely orchestrated scenes:

**Before** (Standard voice assistants):
```
"turn living room to fire"
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
- **Mobile Web UI**: Control from any device on your local network

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

**Phase 1**: ✅ Complete - Multi-agent effects system
**Phase 2**: ✅ Complete - Web UI with mobile phone access
**Phase 3**: 🔜 Future - Voice control (waiting for HA voice puck hardware, Dec 2025)

Access the web UI: http://192.168.254.12:5001/ (local network)

**→ Detailed progress**: [PHONE_ACCESS.md](PHONE_ACCESS.md)

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
├── server.py                # Flask web UI server
├── config.py                # Shared configuration constants
├── utils.py                 # Utility functions
├── tools/
│   ├── lights.py           # Lighting control
│   ├── effects.py          # Dynamic effects
│   ├── hue_specialist.py   # Hue domain expert
│   ├── review_agent.py     # Prompt review AI
│   └── prompt_improvement_agent.py  # Prompt improvement chatbot
├── prompts/
│   └── config.json         # Agent prompts configuration
├── docs/                   # All documentation
│   ├── README.md
│   ├── getting-started.md
│   ├── architecture.md
│   ├── api-reference.md
│   ├── development.md
│   ├── startup-guide.md
│   └── session-log.md
├── QUICKSTART.md           # Quick reference guide
├── PHONE_ACCESS.md         # Mobile UI guide
├── Dockerfile              # Agent container image
├── docker-compose.yml      # Full stack deployment (HA + Agent)
└── test_e2e.py             # End-to-end tests
```

## Contributing

See [docs/development.md](docs/development.md) for:
- Code patterns and conventions
- Testing guidelines
- How to add new features
- Debugging tips

## License

MIT
