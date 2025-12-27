# Installation Guide

This guide walks you through setting up Smart Home Assistant from scratch. Choose the quick start path for basic setup, or follow the detailed path for complete configuration.

## Quick Start (Minimal Setup)

Get up and running in 5 minutes with basic functionality.

```bash
# Clone the repository
git clone https://github.com/yourusername/smarthome.git
cd smarthome

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example configuration
cp .env.example .env

# Edit .env with your API keys (minimum required):
# - OPENAI_API_KEY (or set LLM_PROVIDER for other options)
# - HA_URL
# - HA_TOKEN

# Generate SSL certificate (optional but recommended)
python scripts/generate_cert.py

# Generate secret key and add to .env
echo "FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env

# Start the server
python server.py
```

Access the web interface at `https://localhost:5050` (or `http://localhost:5050` if not using HTTPS).

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.12+ | Runtime environment |
| pip | Latest | Package management |
| Git | Any | Repository cloning |

### Required Accounts & Services

| Service | Purpose | Where to Get |
|---------|---------|--------------|
| OpenAI API | LLM for natural language (default) | [platform.openai.com](https://platform.openai.com) |
| Home Assistant | Smart home platform | [home-assistant.io](https://www.home-assistant.io/installation/) |

**Alternative LLM Providers:**
- Anthropic API (Claude) - Set `LLM_PROVIDER=anthropic`
- Local LLM (Ollama, LM Studio) - Set `LLM_PROVIDER=local` and `LLM_BASE_URL`

### Optional Services

| Service | Purpose | Where to Get |
|---------|---------|--------------|
| Spotify Premium | Music playback | [developer.spotify.com](https://developer.spotify.com/dashboard) |
| Slack Webhooks | Monitoring alerts | [api.slack.com](https://api.slack.com/apps) |

---

## Detailed Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/smarthome.git
cd smarthome
```

### Step 2: Set Up Python Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Verify Python version:**
```bash
python --version  # Should be 3.12 or higher
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `openai` - OpenAI API client (default LLM provider)
- `anthropic` - Anthropic API client (optional LLM provider)
- `flask` - Web framework
- `spotipy` - Spotify API client
- `flask-login`, `flask-wtf`, `flask-limiter` - Security packages
- Testing and development tools

### Step 4: Configure Environment Variables

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` with your values. See [Environment Variable Reference](#environment-variable-reference) for all options.

**Minimum required variables:**
```bash
# LLM Configuration (default: OpenAI)
OPENAI_API_KEY=sk-...                  # From platform.openai.com
OPENAI_MODEL=gpt-4o-mini               # Model selection

# Home Assistant
HA_URL=http://homeassistant.local:8123 # Your Home Assistant URL
HA_TOKEN=eyJ0eXAiOiJKV1QiLCJhb...      # HA long-lived access token
```

**Alternative LLM providers:**
```bash
# For Anthropic (Claude)
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-api03-...           # From console.anthropic.com
LLM_MODEL=claude-sonnet-4-20250514

# For local LLM (Ollama, LM Studio, etc.)
LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

### Step 5: Get Home Assistant Token

1. Open Home Assistant web interface
2. Click your profile (bottom-left)
3. Scroll to "Long-Lived Access Tokens"
4. Click "Create Token"
5. Name it "Smart Home Assistant"
6. Copy the token immediately (it won't be shown again)

### Step 6: Generate Security Keys

**Flask Secret Key** (required for sessions):
```bash
python -c "import secrets; print(secrets.token_hex(32))"
# Copy output to FLASK_SECRET_KEY in .env
```

**Voice Webhook Token** (optional, for HA voice integration):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output to VOICE_WEBHOOK_TOKEN in .env
```

### Step 7: Generate SSL Certificate

For HTTPS support (recommended):
```bash
python scripts/generate_cert.py
```

This creates self-signed certificates in `data/ssl/`. Your browser will show a warning on first visit - this is normal for self-signed certificates on a local network.

### Step 8: Start the Server

**Development mode:**
```bash
python server.py
```

**With HTTPS enabled:**
```bash
USE_HTTPS=true python server.py
```

The server runs on:
- HTTPS: `https://localhost:5050`
- HTTP redirect: `http://localhost:5049` (redirects to HTTPS)

### Step 9: Initial Setup

1. Navigate to `https://localhost:5050`
2. Accept the self-signed certificate warning
3. Create your admin account on the setup page
4. Log in and start using the assistant

---

## Environment Variable Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (default provider) | `sk-...` |
| `OPENAI_MODEL` | Model name | `gpt-4o-mini` |
| `HA_URL` | Home Assistant base URL | `http://homeassistant.local:8123` |
| `HA_TOKEN` | HA long-lived access token | `eyJ0eXAiOi...` |

### LLM Provider Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | LLM provider: `openai`, `anthropic`, or `local` |
| `LLM_API_KEY` | Uses OPENAI_API_KEY | Alternative API key for non-OpenAI providers |
| `LLM_MODEL` | Uses OPENAI_MODEL | Model name for alternative providers |
| `LLM_BASE_URL` | None | Base URL for local LLMs (Ollama, LM Studio) |

### Security Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | Auto-generated | Session encryption key (sessions won't persist across restarts without this) |
| `FLASK_ENV` | `development` | Set to `production` for secure cookies |
| `FLASK_DEBUG` | `false` | Never set to true in production |
| `VOICE_WEBHOOK_TOKEN` | None | Bearer token for HA voice webhook authentication |

### HTTPS/SSL Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_HTTPS` | `true` | Enable HTTPS (falls back to HTTP if no certificates) |
| `HTTP_REDIRECT` | `true` | Redirect HTTP to HTTPS |
| `SSL_COMMON_NAME` | `smarthome.local` | Certificate common name |
| `SSL_ORGANIZATION` | `Smart Home Assistant` | Certificate organization |

### Spotify Variables (Optional)

| Variable | Description |
|----------|-------------|
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | OAuth redirect (default: `http://localhost:8888/callback`) |

### Monitoring Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_COST_TARGET` | `2.00` | Daily API cost target in USD |
| `DAILY_COST_ALERT` | `5.00` | Alert threshold in USD |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Slack Webhook Variables (Optional)

| Variable | Description |
|----------|-------------|
| `SLACK_SECURITY_WEBHOOK` | Security alerts (#colby-server-security) |
| `SLACK_COST_WEBHOOK` | Cost alerts (#smarthome-costs) |
| `SLACK_HEALTH_WEBHOOK` | Health alerts (#smarthome-health) |
| `SLACK_SERVER_HEALTH_WEBHOOK` | Server health (#colby-server-health) |

---

## Docker Installation

### Using Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  smarthome:
    build: .
    ports:
      - "5050:5050"
      - "5049:5049"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
    environment:
      - USE_HTTPS=true
    restart: unless-stopped
```

Create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p data/ssl data/logs

# Generate SSL certificate if not mounted
RUN python scripts/generate_cert.py || true

# Expose ports
EXPOSE 5050 5049

# Run server
CMD ["python", "server.py"]
```

**Build and run:**
```bash
# Create .env file first
cp .env.example .env
# Edit .env with your configuration

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Docker with External Volumes

For persistent data:

```yaml
version: '3.8'

services:
  smarthome:
    build: .
    ports:
      - "5050:5050"
    volumes:
      - smarthome_data:/app/data
      - smarthome_logs:/app/data/logs
    env_file:
      - .env
    restart: unless-stopped

volumes:
  smarthome_data:
  smarthome_logs:
```

---

## Systemd Service (Linux)

For automatic startup on Linux systems:

Create `/etc/systemd/system/smarthome.service`:

```ini
[Unit]
Description=Smart Home Assistant
After=network.target

[Service]
Type=simple
User=homeassistant
Group=homeassistant
WorkingDirectory=/opt/smarthome
Environment="PATH=/opt/smarthome/venv/bin"
ExecStart=/opt/smarthome/venv/bin/python server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable smarthome
sudo systemctl start smarthome

# Check status
sudo systemctl status smarthome

# View logs
sudo journalctl -u smarthome -f
```

---

## Verifying Installation

### Check Server Health

```bash
curl -k https://localhost:5050/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "components": {
    "home_assistant": "healthy",
    "cache": "healthy",
    "database": "healthy",
    "api": "healthy"
  }
}
```

### Test a Command

Via CLI:
```bash
source venv/bin/activate
python agent.py "what time is it?"
```

Via API:
```bash
curl -k -X POST https://localhost:5050/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "list available rooms"}'
```

### Run Test Suite

```bash
pytest tests/ -v
```

---

## Next Steps

After basic installation:

1. **Add device integrations** - See [Integration Guides](integrations/):
   - [Philips Hue Lights](integrations/philips-hue.md)
   - [Spotify Music](integrations/spotify.md)
   - [Dreame Vacuum](integrations/dreame-vacuum.md)
   - [Smart Blinds](integrations/smart-blinds.md)

2. **Configure voice control** - See [Voice Puck Setup](integrations/voice-puck.md)

3. **Set up monitoring** - Configure Slack webhooks for alerts

4. **Review troubleshooting** - See [Troubleshooting Guide](troubleshooting.md)

---

## Updating

To update to the latest version:

```bash
cd smarthome
git pull origin main
source venv/bin/activate
pip install -r requirements.txt

# Restart server
# If using systemd:
sudo systemctl restart smarthome

# If running directly:
# Stop current server (Ctrl+C) and restart
python server.py
```

---

## Uninstalling

```bash
# Stop the service
sudo systemctl stop smarthome
sudo systemctl disable smarthome

# Remove files
rm -rf /opt/smarthome

# Remove systemd service
sudo rm /etc/systemd/system/smarthome.service
sudo systemctl daemon-reload
```
