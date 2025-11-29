# Startup Guide

How to start, stop, and manage the Home Automation Agent services.

## Quick Commands

```bash
# Start everything
./start.sh

# Check status
./start.sh status

# View logs
./start.sh logs

# Stop everything
./start.sh stop

# Restart everything
./start.sh restart
```

## What Gets Started

When you run `./start.sh`, three services start:

### 1. Home Assistant (Docker)
- **URL**: http://localhost:8123
- **Purpose**: Device control platform
- **Auto-starts**: Yes (Docker restart policy)

### 2. Agent Web Server
- **URL**: http://localhost:5001
- **Purpose**: HTTP API and web UI
- **Runs in background**: Yes

### 3. Cloudflare Tunnel
- **URL**: https://random-words.trycloudflare.com (changes each start)
- **Purpose**: Public HTTPS access for Alexa
- **Runs in background**: Yes

## First Time Setup

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Cloudflare Tunnel
brew install cloudflared

# Install Docker Desktop (if not already)
# Download from: https://www.docker.com/products/docker-desktop
```

### 2. Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit with your keys
nano .env
```

Required variables:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
HA_URL=http://localhost:8123
HA_TOKEN=eyJ...  # From HA Profile → Long-Lived Access Tokens
```

### 3. Start Services

```bash
./start.sh
```

You'll see:
```
🏠 Starting Home Automation Services...

[✓] Starting Home Assistant...
[✓] Home Assistant started
[✓] Access at: http://localhost:8123
[✓] Starting agent server...
[✓] Agent server started on port 5001
[✓] Web UI: http://localhost:5001
[✓] Starting Cloudflare Tunnel...
[✓] Waiting for tunnel to initialize...
[✓] Tunnel created: https://your-unique-url.trycloudflare.com
[!] ⚠️  Free tunnel URL changes on restart!
[!] ⚠️  Update Lambda env var AGENT_URL if needed

═══════════════════════════════════════════════════════
  Home Automation Agent - Service Status
═══════════════════════════════════════════════════════

[✓] Home Assistant: RUNNING (http://localhost:8123)
[✓] Agent Server: RUNNING (http://localhost:5001)
[✓] Cloudflare Tunnel: RUNNING (https://...)

═══════════════════════════════════════════════════════

[✓] All services started!

[!] Logs:
  Server: /Users/you/Smarthome/logs/server.log
  Tunnel: /Users/you/Smarthome/logs/tunnel.log
```

## Daily Usage

### Starting Your System

```bash
cd ~/Documents/Smarthome
./start.sh
```

**Note the tunnel URL!** If you have Alexa integration set up, you may need to update the Lambda environment variable if the URL changed.

### Checking Status

```bash
./start.sh status
```

Shows which services are running.

### Viewing Logs

```bash
# Recent logs from all services
./start.sh logs

# Live server logs
tail -f logs/server.log

# Live tunnel logs
tail -f logs/tunnel.log

# Home Assistant logs
docker logs -f homeassistant
```

### Stopping Services

```bash
./start.sh stop
```

Stops all three services cleanly.

## Troubleshooting

### "Permission denied" when running ./start.sh

```bash
chmod +x start.sh
./start.sh
```

### Port 5001 already in use

```bash
# Find what's using it
lsof -i :5001

# Kill it
kill -9 <PID>

# Or change port in start.sh
```

### Tunnel URL changed, Alexa not working

1. Run `./start.sh status` to get new URL
2. Update Lambda environment variable:
   - AWS Console → Lambda → Configuration → Environment variables
   - `AGENT_URL` = new tunnel URL
3. Test Alexa again

### Home Assistant not starting

```bash
# Check Docker is running
docker ps

# View HA logs
docker logs homeassistant

# Restart Docker Desktop
# Then run: ./start.sh restart
```

### Agent server errors

```bash
# Check logs
cat logs/server.log

# Common issues:
# - Missing .env file
# - Invalid HA_TOKEN
# - Home Assistant not running
```

## Production Setup (Old Laptop)

When moving to production on your old laptop:

### Option 1: Run on Boot (macOS)

Create a LaunchAgent to start on login:

```bash
# Create plist file
nano ~/Library/LaunchAgents/com.smarthome.agent.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smarthome.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/Documents/Smarthome/start.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Documents/Smarthome/logs/startup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Documents/Smarthome/logs/startup.error.log</string>
</dict>
</plist>
```

```bash
# Load it
launchctl load ~/Library/LaunchAgents/com.smarthome.agent.plist

# Unload it
launchctl unload ~/Library/LaunchAgents/com.smarthome.agent.plist
```

### Option 2: Use systemd (Linux)

If you move to Linux laptop:

```bash
sudo nano /etc/systemd/system/smarthome-agent.service
```

```ini
[Unit]
Description=Home Automation Agent
After=network.target docker.service

[Service]
Type=forking
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/Smarthome
ExecStart=/home/YOUR_USERNAME/Smarthome/start.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable smarthome-agent
sudo systemctl start smarthome-agent
```

### Option 3: Cloudflare Named Tunnel

For production, upgrade to a **named tunnel** (free, static URL):

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create named tunnel
cloudflared tunnel create home-automation

# Route DNS (if you have a domain)
cloudflared tunnel route dns home-automation home.yourdomain.com

# Run tunnel
cloudflared tunnel run home-automation
```

Update `start.sh` to use named tunnel instead of quick tunnel.

## Logs Location

All logs are in `/logs/` directory:

```
logs/
├── server.log      # Agent web server
├── tunnel.log      # Cloudflare Tunnel
├── startup.log     # LaunchAgent output (if using)
└── startup.error.log
```

## Environment Variables

The startup script uses these from `.env`:

```bash
ANTHROPIC_API_KEY    # Claude API
HA_URL               # Home Assistant URL
HA_TOKEN             # HA Long-Lived Access Token
PORT                 # Optional: Override server port (default 5001)
```

## Advanced: Running Services Separately

If you need to run services individually:

```bash
# Just Home Assistant
docker compose up -d

# Just Agent Server
source venv/bin/activate
python server.py

# Just Tunnel
cloudflared tunnel --url http://localhost:5001
```

## Next Steps

- **Alexa Integration**: See [alexa-integration.md](alexa-integration.md)
- **Development**: See [development.md](development.md)
- **API Reference**: See [api-reference.md](api-reference.md)
