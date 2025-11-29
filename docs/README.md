# Home Automation Agent - Documentation

Welcome to the Home Automation Agent project! This system uses AI to interpret natural language commands and control your smart home devices.

## Quick Links

- **[Getting Started](getting-started.md)** - New here? Start with this 5-minute guide
- **[Architecture](architecture.md)** - How the system works
- **[API Reference](api-reference.md)** - Tools, endpoints, and integrations
- **[Development](development.md)** - Contributing and extending the system
- **[Session Log](session-log.md)** - Cross-session progress tracking

## What This Project Does

Transform vague voice commands like "make it feel like a campfire" into precise smart home control. Instead of Alexa turning your lights aggressive red, this system creates a warm, flickering, natural fire ambiance.

### Current Capabilities

- **Natural Language Lighting**: Interpret abstract descriptions ("under the sea", "cozy", "fire")
- **Multi-Agent System**: Specialist agents for domain expertise (Hue API knowledge)
- **Efficient Effects**: Native device capabilities (1 API call) vs software emulation (11+ calls)
- **Dynamic Scenes**: Looping effects that run indefinitely on hardware

### Example Commands

```bash
python agent.py "turn living room to fire"
python agent.py "make me feel like I'm under the sea"
python agent.py "cozy reading light in the bedroom"
```

## Project Status

**Current Phase**: Phase 1 Complete (Multi-Agent Effects System)
**Next Phase**: Phase 2 - Alexa Lambda Integration

See [session-log.md](session-log.md) for detailed progress tracking.

## Documentation Structure

```
docs/
├── README.md              # You are here - overview and navigation
├── getting-started.md     # Quick setup guide (5 minutes)
├── architecture.md        # System design and patterns
├── api-reference.md       # Tools, endpoints, schemas
├── development.md         # Contributing, testing, debugging
└── session-log.md         # Cross-session progress tracking
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Test it!
python agent.py "turn living room to fire"
```

For detailed setup instructions, see [getting-started.md](getting-started.md).

## Architecture Overview

```
User Command
    ↓
Main Agent (coordinator)
    ↓
Specialist Agents (Hue expert)
    ↓
Home Assistant API
    ↓
Smart Devices (Philips Hue, etc.)
```

For full architecture details, see [architecture.md](architecture.md).

## Contributing

See [development.md](development.md) for:
- Code patterns and conventions
- Testing guidelines
- How to add new features
- Debugging tips

## Questions?

- Check [getting-started.md](getting-started.md) for setup help
- See [development.md](development.md) for troubleshooting
- Review [session-log.md](session-log.md) for project history and decisions
