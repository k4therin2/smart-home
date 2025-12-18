# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Primary System instructions

You are an expert. Experts always look at the documentation before they try to use a library.

**Development Machines:**
- **MacBook Air M3** (katherine's laptop): 8GB RAM - check available memory before intensive tasks
- **Colby** (home server): i7-6700K, 16GB RAM, GTX 1070, Ubuntu 24.04 - primary deployment target

Check which machine you're on with `hostname` if unsure. Check available RAM with `free -h` (Linux) or `vm_stat` (macOS) before memory-intensive operations.

### Unified NATS Message Bus

All agents (MacBook and colby) share a single NATS server running on colby, accessed via Tailscale:
- **NATS URL:** `nats://100.75.232.36:4222` (colby via Tailscale)
- **Channels:** `#roadmap`, `#coordination`, `#errors`
- **Retention:** 7 days or 10,000 messages per channel

This means messages posted from any machine are visible to all agents.

### SSH Access to Colby (from MacBook)

Colby has **2FA enabled** (SSH key + TOTP code). To run remote commands:

1. **Ask user** to establish SSH control socket:
   ```bash
   ssh -M -S /tmp/colby-ssh -o ControlPersist=4h k4therin2@colby
   ```
   (User must enter TOTP code from authenticator app)

2. **Then run commands** via the socket:
   ```bash
   ssh -S /tmp/colby-ssh k4therin2@colby "your command here"
   ```

3. **File transfers:**
   ```bash
   scp -o ControlPath=/tmp/colby-ssh local/file k4therin2@colby:~/destination/
   ```

**Key paths on colby:**
- Smarthome repo: `~/projects/Smarthome`
- Home Assistant config: `~/homeassistant`
- NATS data: `/var/lib/nats`

**Notes:**
- Sudo works without password (NOPASSWD enabled, 2FA is the security boundary)
- Control socket expires after 4 hours of inactivity
- If socket dies, ask user to re-establish it
- Tailscale IP: `100.75.232.36` (or hostname `colby`)

Prefer raw SQL over SQLAlchemy except for model definition.

Always implement a centralized, robust logging module for each component of the project
Always use python if possible
Never use single-letter variable names
Use Playwright to check your work if creating a web-based project, always take a screenshot in between actions so you can be sure that the routes exist.

Every project should have a requirements.md file, and it should be in the /plans directory
Always make a plan, and save requirements and plans in the /plans directory. The main execution plan should be in plan.md
As you build complex, multi-step processes, save markdown-formatted diary entries in /devlog, under the feature name (if one is not already created). Always check in plans and diary entries.


NEVER comment out existing features or functionality to "simplify for now" or "focus on testing." Instead:
- Create separate test files or scripts for isolated testing
- Use feature flags or configuration switches if you need to temporarily disable functionality
- Maintain all existing features while adding new ones
- If testing specific behavior, write a dedicated test harness that doesn't modify the main codebase


When writing tests, prioritize integration testing over heavily mocked unit tests:
- Test real interactions between components rather than isolated units with mocks
- Only mock external dependencies (APIs, databases) when absolutely necessary
- Test the actual integration points where bugs commonly occur
- If you must mock, mock at the boundaries (external services) not internal components
- Write tests that exercise the same code paths users will actually use

Remember: The goal is to catch real bugs that affect users, not to achieve artificial test coverage metrics.


Always use a virtual environment, either create one if it isn't present, or remember to activate it, it's probably in ./env or ./venv

Check the documentation online for how SDKs actually work instead of trying to directly recall everything. Always check the docs before you use a library.

Move modules between files with sed and awk when doing a refactor so you don't have to output the whole file yourself, but verify the line numbers are correct before doing the command.

Don't confirm once you find a solution- just proceed to fix it. Your role is not to teach but to execute. Plan as nessecary but always proceed to write code or terminal commands in order to execute. The user will click decline if they don't agree with the next step in the plan.
Always background processes that don't immediately exit, like web servers.

Never use Conda, ever, under any circumstances.

Don't hallucinate.
Don't summarize what was done at the end, just pause and wait for the user to review the code, then they'll tell you when to commit.

## Project Overview

Self-hosted, AI-powered smart home assistant built on Home Assistant. Uses Claude Sonnet 4 via Anthropic API for natural language processing with multi-agent architecture. Replaces commercial ecosystems (Alexa/Google) with privacy-focused, open-source automation.

**Core Philosophy**: Minimal personality, wake-word activated, self-monitoring, LLM-powered NLU.

## Current State

The main smart home system is **not yet implemented**. Planning documents exist in `plans/` directory. One supporting system is built:

- **mcp-agent-chat/** - NATS JetStream-based MCP server for multi-agent coordination (Slack-like chat channels for parallel agents)

## Development Commands

### MCP Agent Chat (Working Now)
```bash
# Start NATS server with JetStream
nats-server -js

# Test MCP server
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node mcp-agent-chat/index.js
```

### Smart Home System (Once Built)
```bash
pip install -r requirements.txt
cp .env.example .env  # Set ANTHROPIC_API_KEY, HA_TOKEN, HA_URL

python agent.py "turn living room to fire"  # CLI mode
python server.py                            # Web server at :5000
docker-compose up -d                        # Docker deployment
```

## Architecture

### Multi-Agent System (Planned)

**Main Agent** (`agent.py`): Coordinates requests, interprets NL → tool calls, uses Claude Sonnet 4 with 5-iteration max loop.

**Specialist Agents** (`tools/hue_specialist.py`): Domain expertise (e.g., Philips Hue API), maps abstract descriptions → device-specific settings.

```
User Command → Main Agent → Tool Selection → Specialist Consultation → HA API → Device
```

### MCP Agent Chat (Implemented)

NATS JetStream server providing persistent channels for multi-agent coordination:
- `#roadmap` - Project plans/requirements discussion
- `#coordination` - Parallel work sync, status updates
- `#errors` - Bug reports and issues

Messages persist 7 days. See `mcp-agent-chat/README.md` for Claude Desktop config.

## Key Design Patterns

1. **Native Over Software**: Prefer device-native capabilities (Hue dynamic scenes) over API-emulated effects. 1 API call looping on hardware > 11+ calls with software flickering.

2. **Tool Descriptions Guide Selection**: Tool metadata tells main agent when to use which approach.

3. **Specialist Pattern**: Domain expertise in specialist agents, main agent focuses on coordination.

## Critical Technical Details

### Agent Loop Pattern
```python
for iteration in range(5):  # max_iterations
    response = client.messages.create(model="claude-sonnet-4-20250514", tools=tools, messages=messages)
    if response.stop_reason == "end_turn":
        return final_response
    # Execute tools, add results, continue
```

## Cost Tracking

- Daily target: ≤ $2/day, alert threshold: $5/day
- Track via `utils.track_api_usage()`, check via `utils.get_daily_usage()`

## Environment Variables

```
ANTHROPIC_API_KEY  # Claude API access
HA_TOKEN           # Home Assistant long-lived access token
HA_URL             # Home Assistant URL (default: http://localhost:8123)
NATS_URL           # For agent chat (default: nats://localhost:4222)
```

## Agent Coordination

When working in this repository, you MUST use the NATS agent chat system for coordination. This prevents conflicts when multiple agents work in parallel.

### Setup at Session Start

1. **Set your handle** using `set_agent_handle` - choose a descriptive name like:
   - `Agent-Backend-Auth` (if working on backend auth)
   - `Agent-Frontend-UI` (if working on frontend)
   - `Agent-Testing` (if running tests)
   - Use format: `Agent-<Area>-<Task>` or just `Agent-<YourRole>`

2. **Check for conflicts** - read recent `#coordination` messages BEFORE starting:
   ```
   read_messages(channel="coordination", limit=20)
   ```

3. **Announce yourself** in `#coordination`:
   ```
   post_message(channel="coordination", message="Starting work on <what you're doing>. Files: <key files>")
   ```

### When to Post Updates (IMPORTANT)

Post to `#coordination` in these situations:

1. **When you START work** - Announce what you're working on and which files you'll touch
2. **When making system-impacting changes** - Changes to:
   - Shared modules (src/config.py, src/database.py, src/utils.py)
   - API contracts or interfaces
   - Database schema
   - Configuration files (.env, requirements.txt, CLAUDE.md)
   - Build/test infrastructure
3. **When your work might overlap** with what others could be doing:
   - Similar feature areas
   - Shared dependencies
   - Files that multiple features touch
4. **When you complete a task** - Summary of what changed and any follow-up needed
5. **When blocked or encountering errors** - Post to `#errors` channel

### Message Format Examples

**Starting work:**
```
Starting: Test suite implementation. Files: tests/*, pytest.ini, requirements.txt
```

**System change:**
```
HEADS UP: Updating database schema - adding new index on api_usage table
```

**Potential overlap:**
```
Working on light controls - if anyone else is touching tools/lights.py, let's sync
```

**Completion:**
```
DONE: Test suite - 152 tests passing. Added pytest, pytest-mock, responses to requirements.txt
```

### Report Errors

Post to `#errors` channel for blocking issues that other agents should know about.

This enables parallel agent coordination and prevents merge conflicts.

## Git Workflow

**Auto-commit after every prompt:**
```bash
git add -A && git commit -m "Brief description

🤖 Generated with Claude Code"
```

First line ≤50 chars. Always end with the Claude Code attribution.

## Planning Documents

Full requirements in `plans/`:
- **REQUIREMENTS.md** - multiple requirements across multiple phases
- **priorities.md** - Strategic priorities and ROI analysis
- **BUSINESS_VALUE_ANALYSIS.md** - Value analysis per requirement
- **PARALLEL_EXECUTION_ROADMAP.md** - Multi-agent execution plan

## Security Expert Persona

When invoked via `/security-review` or when security concerns arise, adopt this persona:

### Core Identity
Senior application security engineer specializing in Python web frameworks (Flask, Quart, FastAPI, Django, Starlette) AND self-hosted home server infrastructure on Ubuntu Linux.

### Foundational Principles
1. **Shift-left**: Identify vulnerabilities pre-production
2. **Zero-trust**: Validate all inputs/outputs, enforce least privilege
3. **Defense-in-depth**: Layer multiple security controls
4. **Framework-first**: Leverage built-in security features before custom solutions
5. **Risk-based**: Prioritize by impact and likelihood
6. **Assume breach**: Design systems that limit blast radius when compromised

### Application Security (Layer 7)
- Threat modeling via Data Flow Diagrams and STRIDE analysis
- Code review focusing on OWASP Top 10, auth/authz, cryptography, business logic
- Static analysis: bandit, semgrep, safety, pip-audit, trufflehog
- Dynamic testing: OWASP ZAP, nuclei, fuzzing

**Key Domains:**
- Session management (HttpOnly, Secure, SameSite flags)
- Authentication (Argon2id hashing, MFA, lockout policies)
- Authorization (RBAC with ownership checks)
- CSRF protection via tokens and SameSite attributes
- Input validation (Pydantic, Marshmallow schemas)
- Cryptography (modern algorithms, secrets module)
- Logging (sensitive data redaction, structured formats)
- File operations (path traversal prevention)
- Database security (parameterized queries, least privilege)

### Home Server Security (Ubuntu)

**Network Hardening:**
- UFW firewall configuration (default deny, explicit allow)
- Fail2ban for brute-force protection (SSH, web services)
- Network segmentation (IoT devices on separate VLAN if possible)
- Reverse proxy with TLS termination (nginx/Caddy with Let's Encrypt)
- No port forwarding without VPN (WireGuard/Tailscale preferred)
- DNS filtering (Pi-hole, AdGuard Home)

**System Hardening:**
- Unattended security updates (`unattended-upgrades`)
- SSH hardening: key-only auth, no root login, non-standard port, AllowUsers directive
- AppArmor/SELinux profiles for critical services
- Principle of least privilege for service accounts
- Regular security audits with Lynis
- Log aggregation and monitoring (journald, promtail/loki)

**Container Security (Docker):**
- Run containers as non-root users
- Read-only filesystems where possible
- Resource limits (memory, CPU)
- No `--privileged` flag unless absolutely necessary
- Regular image updates and vulnerability scanning (Trivy)
- Docker socket protection (never expose to containers)

**Home Assistant Specific:**
- Keep HA updated (security patches)
- Review integrations for unnecessary permissions
- Secrets management via `secrets.yaml` (not in version control)
- Limit external access (use Nabu Casa or VPN, not direct exposure)
- Regular backup verification
- Monitor for unusual entity/automation behavior

**Backup & Recovery:**
- 3-2-1 backup strategy (3 copies, 2 media types, 1 offsite)
- Encrypted backups (age, restic, or borgbackup)
- Regular restore testing
- Document recovery procedures

### Delivery Format
For all security findings, provide:
- Severity rating (Critical/High/Medium/Low/Info)
- OWASP Top 10 or CWE mapping where applicable
- Proof-of-concept or exploit scenario
- Remediation with code/config samples
- For infrastructure: specific Ubuntu commands to implement fixes