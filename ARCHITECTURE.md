# Smart Home Assistant Architecture

This document describes the high-level architecture of the Smart Home Assistant system.

## Overview

The Smart Home Assistant is a multi-agent system that provides natural language control over smart home devices. It uses OpenAI API (gpt-4o-mini by default) for natural language understanding and routes commands to specialized agents for execution.

**LLM Provider:** The system uses a unified LLM abstraction layer (`src/llm_client.py`) that supports:
- OpenAI API (current default: gpt-4o-mini)
- Anthropic API (claude-sonnet-4, etc.)
- Local LLMs via OpenAI-compatible API (Ollama, LM Studio, vLLM)

**Future Migration:** Planned migration to local LLM for cost reduction (from $730/year to $36/year) and enhanced privacy.

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Web UI     │  │  Voice Input │  │   CLI (agent.py)      │  │
│  │  (PWA/Mobile)│  │  (HA Webhook)│  │                       │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                       │              │
└─────────┼─────────────────┼───────────────────────┼──────────────┘
          │                 │                       │
          ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Web Server                            │
│                      (src/server.py)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ /api/command│  │/api/voice_  │  │ /api/logs, /api/todos  │  │
│  │             │  │   command   │  │ /api/automations, etc. │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     │
┌─────────────────────────────────────────────┐ │
│              Main Agent                      │ │
│              (agent.py)                      │ │
│  ┌─────────────────────────────────────┐    │ │
│  │  LLM Client (src/llm_client.py)     │    │ │
│  │  Provider: OpenAI (gpt-4o-mini)     │    │ │
│  │  - Interprets natural language      │    │ │
│  │  - Selects appropriate tools        │    │ │
│  │  - Orchestrates multi-step tasks    │    │ │
│  └─────────────────────────────────────┘    │ │
│                    │                         │ │
│         ┌──────────┼──────────┐              │ │
│         ▼          ▼          ▼              │ │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐  │ │
│  │  Lights   │ │  Spotify  │ │  Timers   │  │ │
│  │ (tools/)  │ │ (tools/)  │ │ (tools/)  │  │ │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  │ │
└────────┼─────────────┼─────────────┼────────┘ │
         │             │             │          │
         ▼             ▼             │          │
┌─────────────────────────────────────┼─────────┼────────────────┐
│           Home Assistant Client     │         │                 │
│           (src/ha_client.py)        │         │                 │
│  ┌────────────────────────────────┐ │         │                 │
│  │    REST API Communication      │ │         ▼                 │
│  │    - Light control             │ │    ┌─────────────┐       │
│  │    - Blinds control            │ │    │   Spotify   │       │
│  │    - Vacuum control            │ │    │    API      │       │
│  │    - State queries             │ │    └─────────────┘       │
│  └────────────────────────────────┘ │                          │
└─────────────────────────────────────┼──────────────────────────┘
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │   Home Assistant    │
                           │   (External)        │
                           │   - Zigbee devices  │
                           │   - WiFi devices    │
                           │   - Integrations    │
                           └─────────────────────┘
```

## Components

### 1. User Interfaces

#### Web UI (`templates/index.html`, `static/app.js`)
- Mobile-optimized PWA
- Voice input via Web Speech API
- Real-time device status
- Command history
- Todo list management
- Log viewer

#### CLI (`agent.py`)
- Direct command execution
- Debugging and development

#### Voice Webhook (`/api/voice_command`)
- Home Assistant conversation agent integration
- Bearer token authentication
- Speech-to-text result processing

### 2. Web Server (`src/server.py`)

Flask-based REST API providing:

- **Command Processing**: `/api/command`, `/api/voice_command`
- **Status & Health**: `/api/status`, `/api/health`
- **Data Management**: `/api/todos`, `/api/reminders`, `/api/automations`
- **Logging**: `/api/logs`, `/api/logs/export`
- **Authentication**: Session-based with Flask-Login

Security features:
- CSRF protection
- Rate limiting
- HTTPS with auto-redirect
- Security headers (CSP, HSTS, etc.)

### 3. Main Agent (`agent.py`)

The core intelligence layer using the LLM abstraction:

```python
# Agent loop pattern using unified LLM client
from src.llm_client import get_llm_client

llm_client = get_llm_client()

for iteration in range(5):  # max_iterations
    text, tool_calls = llm_client.complete_with_tools(
        prompt=user_message,
        tools=tool_definitions,
        system_prompt=system_instructions,
        max_tokens=4096
    )

    if not tool_calls:
        return text  # Final response

    # Execute tools, add results, continue
```

**LLM Configuration:**
- Default provider: OpenAI (gpt-4o-mini)
- Switch providers via `LLM_PROVIDER` environment variable
- All LLM calls abstracted through `src/llm_client.py`

Responsibilities:
- Natural language interpretation
- Tool selection and orchestration
- Multi-step task handling
- Error recovery

### 4. Specialist Tools (`tools/`)

Domain-specific handlers:

| Tool | Description |
|------|-------------|
| `tools/lights.py` | Philips Hue control, scenes, colors |
| `tools/blinds.py` | Motorized shade control |
| `tools/spotify.py` | Music playback via Spotify API |
| `tools/timers.py` | Timer and alarm management |
| `tools/productivity.py` | Todo lists, reminders |
| `tools/automation.py` | Simple automation creation |
| `tools/devices.py` | Generic device queries |
| `tools/location.py` | Location-based features |

Each tool provides:
- `get_tool_definitions()`: Tool metadata for Claude
- `handle_tool_call()`: Execution logic

### 5. Home Assistant Client (`src/ha_client.py`)

REST API wrapper for Home Assistant:

```python
class HAClient:
    def get_light_state(entity_id)
    def turn_on_light(entity_id, brightness, color_temp, ...)
    def call_service(domain, service, data)
    def get_states()
```

Features:
- Connection pooling
- Retry logic
- State caching
- Error handling

### 6. Supporting Services

#### Cache (`src/cache.py`)
- State caching for performance
- TTL-based expiration
- Memory management

#### Database (`src/database.py`)
- SQLite for local storage
- Usage tracking
- Todo/reminder persistence
- Automation storage

#### Health Monitor (`src/health_monitor.py`)
- Component health checks
- Metrics collection
- Alert generation

#### Self-Healer (`src/self_healer.py`)
- Automatic recovery actions
- Connection restoration
- Cache cleanup

## Data Flow

### Command Processing

```
1. User Input
   └── "Turn on the living room lights to 50%"

2. Web Server
   └── Validate input
   └── Rate limit check
   └── Log command

3. Main Agent
   └── Claude analyzes: "User wants to adjust living room lights"
   └── Selects tool: turn_on_light(entity_id="light.living_room", brightness=127)

4. Tool Execution
   └── lights.py receives call
   └── Calls ha_client.turn_on_light()

5. Home Assistant
   └── API call to /api/services/light/turn_on
   └── Device receives command

6. Response
   └── Tool returns success
   └── Agent generates response
   └── "I've set the living room lights to 50%"
```

### Multi-Step Commands

```
1. User Input
   └── "Create a cozy evening scene"

2. Agent Processing (Multiple Iterations)
   └── Iteration 1: Set living room warm (2700K)
   └── Iteration 2: Dim bedroom to 30%
   └── Iteration 3: Close blinds
   └── Iteration 4: Start relaxing music

3. Consolidated Response
   └── "I've created a cozy evening atmosphere..."
```

## Security Architecture

### Authentication Flow

```
┌─────────┐    ┌─────────────┐    ┌──────────┐
│  User   │───▶│ Login Form  │───▶│  Session │
└─────────┘    └─────────────┘    └──────────┘
                     │                  │
                     ▼                  ▼
              ┌─────────────┐    ┌──────────────┐
              │  Validate   │───▶│ Flask-Login  │
              │  Password   │    │   Session    │
              └─────────────┘    └──────────────┘
```

### API Security Layers

1. **Transport**: HTTPS with TLS 1.2+
2. **Authentication**: Session cookies + optional Bearer tokens
3. **Authorization**: Flask-Login decorators
4. **Rate Limiting**: Flask-Limiter
5. **CSRF**: Flask-WTF
6. **Input Validation**: Pydantic models

## Performance Considerations

### Caching Strategy

- Device states: 30-second TTL
- API responses: Based on endpoint
- Session data: In-memory with disk backup

### Optimization Techniques

1. **Native over Software**: Use device-native features
   - Hue dynamic scenes vs API-controlled loops
   - Single API call vs multiple updates

2. **Lazy Loading**: Load specialist tools on demand

3. **Connection Pooling**: Reuse HTTP connections

### Cost Management

- Daily usage tracking
- Alert thresholds ($2/day target, $5/day alert)
- Per-command cost logging

## Deployment Options

### Local Development
```bash
python server.py  # Debug mode
```

### Production (Direct)
```bash
USE_HTTPS=true python server.py
```

### Docker
```bash
docker-compose up -d
```

### Systemd Service
```ini
[Unit]
Description=Smart Home Assistant
After=network.target

[Service]
Type=simple
User=homeassistant
WorkingDirectory=/opt/smarthome
ExecStart=/opt/smarthome/venv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Extension Points

### Adding New Device Types

1. Create tool in `tools/`:
   ```python
   # tools/new_device.py
   def get_tool_definitions():
       return [...]

   def handle_tool_call(name, arguments, ha_client):
       ...
   ```

2. Register in `tools/__init__.py`

3. The LLM automatically discovers and uses new tools

### Switching LLM Providers

To switch between OpenAI, Anthropic, or local LLMs:

1. Set environment variables in `.env`:
   ```bash
   # For OpenAI (default)
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini

   # For Anthropic
   LLM_PROVIDER=anthropic
   LLM_API_KEY=sk-ant-...
   LLM_MODEL=claude-sonnet-4-20250514

   # For local LLM (Ollama, LM Studio, etc.)
   LLM_PROVIDER=local
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=llama3.1
   ```

2. The `src/llm_client.py` abstraction handles provider-specific API calls

3. No code changes required - provider switching is configuration-driven

### Adding New API Endpoints

1. Add route to `src/server.py`
2. Add decorators for auth, rate limiting
3. Add tests in `tests/`

### Custom Integrations

Implement custom integrations via:
- Direct Home Assistant integration
- Custom tool handlers
- WebSocket extensions

## Monitoring & Observability

### Logging Structure

```
data/logs/
├── smarthome.log      # Main application log
├── smarthome_YYYY-MM-DD.log  # Daily rotation
├── errors.log         # Error-only log
└── api_calls.log      # API call tracking
```

### Health Endpoints

- `/api/health`: System health status
- `/api/health/history`: Historical health data
- `/api/logs`: Log viewer API

### Metrics

- API usage and costs
- Response times
- Error rates
- Device states
