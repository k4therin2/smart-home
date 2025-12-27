# Smart Home Assistant

[![Tests](https://github.com/k4therin2/smart-home/actions/workflows/test.yml/badge.svg)](https://github.com/k4therin2/smart-home/actions/workflows/test.yml)

A self-hosted, AI-powered smart home assistant built on Home Assistant. Uses OpenAI API (gpt-4o-mini by default) for natural language processing, enabling voice and text control of your smart home devices. Supports multiple LLM providers via unified abstraction layer.

## Features

- **Natural Language Control**: Control your smart home with plain English commands
- **Voice Input**: Browser-based speech recognition for hands-free control
- **Multi-Device Support**: Philips Hue, blinds, vacuum, Spotify, and more
- **Privacy-Focused**: Self-hosted, no cloud dependencies for core functionality
- **Mobile-Optimized**: PWA support for installation on mobile devices
- **Automations**: Create simple automations through natural language
- **Todo Lists & Reminders**: Manage tasks and get reminded
- **Self-Monitoring**: Health checks and automatic self-healing

## Quick Start

### Prerequisites

- Python 3.12+
- Home Assistant instance with API access
- OpenAI API key (or Anthropic/local LLM - see Configuration)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/smarthome.git
cd smarthome

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and Home Assistant URL
```

### Configuration

Edit `.env` with your configuration:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key    # Default LLM provider
OPENAI_MODEL=gpt-4o-mini              # Model selection
HA_URL=http://your-home-assistant:8123
HA_TOKEN=your_long_lived_access_token

# LLM Provider Selection (optional - defaults to OpenAI)
LLM_PROVIDER=openai                   # Options: openai, anthropic, local
# LLM_API_KEY=...                     # Alternative API key (if not using OPENAI_API_KEY)
# LLM_BASE_URL=http://localhost:11434/v1  # For local LLMs (Ollama, etc.)

# Optional
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
```

### Running

```bash
# Start the web server
python server.py

# Or run a single command via CLI
python agent.py "turn on the living room lights"
```

Access the web interface at `http://localhost:5050`

## Usage Examples

```
"Turn on the living room lights"
"Set the bedroom to 50% brightness"
"Make the kitchen cozy"
"Play some jazz on Spotify"
"Set a timer for 15 minutes"
"Add milk to my shopping list"
"Create an automation to turn off all lights at midnight"
```

## Architecture

The system uses a multi-agent architecture:

- **Main Agent** (`agent.py`): Coordinates requests and routes to specialists
- **Specialist Agents** (`tools/`): Domain-specific handlers for devices, music, etc.
- **Web Server** (`src/server.py`): Flask-based REST API and web UI
- **Home Assistant Client** (`src/ha_client.py`): Communicates with HA API

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_log_reader.py -v
```

### Code Quality

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run linter
ruff check src/ tools/

# Run formatter
ruff format src/ tools/
```

### Project Structure

```
smarthome/
├── agent.py           # Main agent entry point
├── server.py          # Web server (also in src/)
├── src/               # Core application code
│   ├── config.py      # Configuration management
│   ├── ha_client.py   # Home Assistant API client
│   ├── server.py      # Flask web server
│   └── ...
├── tools/             # Specialist agent tools
│   ├── lights.py      # Philips Hue control
│   ├── spotify.py     # Spotify integration
│   └── ...
├── tests/             # Test suites
│   ├── unit/          # Unit tests
│   └── integration/   # Integration tests
├── static/            # Web UI assets
├── templates/         # HTML templates
├── plans/             # Project planning docs
└── devlog/            # Development logs
```

## Configuration Reference

See [.env.example](.env.example) for all available configuration options.

### Key Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key (default provider) |
| `OPENAI_MODEL` | No | Model name (default: gpt-4o-mini) |
| `LLM_PROVIDER` | No | LLM provider: openai, anthropic, local (default: openai) |
| `LLM_BASE_URL` | No | Base URL for local LLMs (Ollama, LM Studio) |
| `HA_URL` | Yes | Home Assistant URL |
| `HA_TOKEN` | Yes | HA long-lived access token |
| `SPOTIFY_CLIENT_ID` | No | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | No | Spotify app client secret |
| `FLASK_SECRET_KEY` | No | Session encryption key |

## Device Support

- **Lights**: Philips Hue (native scenes, color control)
- **Blinds**: Tuya/Hapadif motorized shades
- **Vacuum**: Dreame robot vacuums via HA
- **Media**: Spotify (requires Premium)
- **Sensors**: Any HA-compatible sensor

## Security

- All endpoints require authentication
- CSRF protection on forms
- Rate limiting on API endpoints
- HTTPS support with auto-generated certificates
- No hardcoded credentials

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [OpenAI](https://openai.com) for GPT models (default LLM provider)
- [Home Assistant](https://home-assistant.io) for the smart home platform
- [Flask](https://flask.palletsprojects.com) for the web framework
- Support for multiple LLM providers via unified abstraction layer
