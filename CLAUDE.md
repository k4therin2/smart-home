# CLAUDE.md - Smarthome Project

This file provides guidance to Claude Code when working with this repository.

**This project participates in the agent culture.** See `~/projects/agent-automation/orchestrator/agents/AGENT_CULTURE.md`.

**For global agent infrastructure (NATS, coordination, coding standards):** See `~/projects/agent-automation/CLAUDE.md`

---

## Project Overview

Self-hosted, AI-powered smart home assistant built on Home Assistant. Uses Claude Sonnet 4 via Anthropic API for natural language processing with multi-agent architecture. Replaces commercial ecosystems (Alexa/Google) with privacy-focused, open-source automation.

**Core Philosophy**: Minimal personality, wake-word activated, self-monitoring, LLM-powered NLU.

---

## Quick Reference

**NATS Coordination:** `nats://100.75.232.36:4222` (colby via Tailscale)

**Key Paths on Colby:**
- Smarthome repo: `~/projects/Smarthome`
- Home Assistant config: `~/homeassistant`
- Agent automation: `~/projects/agent-automation`

**Virtual Environment:** `./venv` (activate before running Python)

---

## Development Commands

### Smart Home System
```bash
# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env  # Set ANTHROPIC_API_KEY, HA_TOKEN, HA_URL

# Run CLI mode
python agent.py "turn living room to fire"

# Run web server (backgrounds automatically)
python server.py &  # Web server at :5000

# Run tests
pytest tests/ -v

# Docker deployment
docker-compose up -d
```

### Useful Commands
```bash
# Check test coverage
pytest --cov=src --cov-report=term-missing

# Run security scan
bandit -r src/

# Check dependencies for vulnerabilities
pip-audit
```

---

## Architecture

### Multi-Agent System

**Main Agent** (`agent.py`): Coordinates requests, interprets NL → tool calls, uses Claude Sonnet 4 with 5-iteration max loop.

**Specialist Agents** (`tools/`): Domain expertise for specific integrations:
- `tools/lights.py` - Philips Hue control
- `tools/blinds.py` - Blind/shade control
- `tools/spotify.py` - Music playback
- `tools/timers.py` - Timers and alarms
- `tools/productivity.py` - Todo lists, reminders
- `tools/automation.py` - HA automation creation

```
User Command → Main Agent → Tool Selection → Specialist → HA API → Device
```

### Agent Loop Pattern
```python
for iteration in range(5):  # max_iterations
    response = client.messages.create(model="claude-sonnet-4-20250514", tools=tools, messages=messages)
    if response.stop_reason == "end_turn":
        return final_response
    # Execute tools, add results, continue
```

---

## Key Design Patterns

1. **Native Over Software**: Prefer device-native capabilities (Hue dynamic scenes) over API-emulated effects. 1 API call looping on hardware > 11+ calls with software flickering.

2. **Tool Descriptions Guide Selection**: Tool metadata tells main agent when to use which approach.

3. **Specialist Pattern**: Domain expertise in specialist agents, main agent focuses on coordination.

---

## Cost Tracking

- Daily target: ≤ $2/day, alert threshold: $5/day
- Track via `utils.track_api_usage()`, check via `utils.get_daily_usage()`

---

## Environment Variables

```
ANTHROPIC_API_KEY     # Claude API access
HA_TOKEN              # Home Assistant long-lived access token
HA_URL                # Home Assistant URL (default: http://localhost:8123)
NATS_URL              # Agent coordination (default: nats://100.75.232.36:4222)

# Slack Webhooks (optional)
SLACK_SECURITY_WEBHOOK
SLACK_COST_WEBHOOK
SLACK_HEALTH_WEBHOOK

# Spotify (optional)
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
```

---

## Device Testing Rules (CRITICAL)

**NEVER run tests that send commands to real home devices without explicit approval.**

Before running ANY test that might affect real Home Assistant devices (lights, blinds, vacuum, speakers):

1. Post to `#smarthome`: "REQUEST: Permission to run [test name] which will [describe effects]. Reply 'approved' to proceed."
2. Wait for user response (handle != Agent-*)
3. Only proceed with explicit approval

**NO Quiet Hours - Permission-Based System (24/7):**
Physical device tests require explicit user permission at any time of day.
Post permission request to `#smarthome` and wait for user approval before proceeding.

---

## Planning Documents

Full requirements in `plans/`:
- **roadmap.md** - Current work packages and status
- **REQUIREMENTS.md** - Feature requirements by phase
- **priorities.md** - Strategic priorities and ROI analysis

Devlogs in `devlog/` - Implementation diaries by feature.

---

## Home Assistant Specific Security

- Keep HA updated (security patches)
- Review integrations for unnecessary permissions
- Secrets management via `secrets.yaml` (not in version control)
- Limit external access (use Nabu Casa or VPN, not direct exposure)
- Regular backup verification
- Monitor for unusual entity/automation behavior

---

## Agent Coordination

This project uses the agent-automation system for multi-agent coordination.

**Connection:** NATS at `nats://100.75.232.36:4222`

**Key contacts:**
- **Henry (Project Manager)** - Route roadmap/requirements changes to him
- **Kemo (Business Analyst)** - Route priority/ROI questions to him
- **Grace (Team Manager)** - Routes Slack messages to appropriate team member

**Gatekeeper Workflow (MANDATORY - all sessions):**
1. **Announce on NATS** - Post intent to `#coordination` before starting
2. **Check the roadmap** - Is this task in `plans/roadmap.md`?
3. **Check prior work** - Search devlogs for similar work
4. **If NOT in roadmap** - Route to Henry (Project Manager) to add it first
5. Set your handle with `set_agent_handle`
6. Post completion to `#coordination` when done
7. Post to NATS on shutdown/restart with final status

**On shared code changes:**
Post to `#coordination` BEFORE and AFTER modifying shared modules.

See `~/projects/agent-automation/CLAUDE.md` for full coordination protocol.
