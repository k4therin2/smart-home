# Quick Start

## When You Return

```bash
cd ~/Documents/Smarthome
./start.sh
```

This starts:
- ✅ Home Assistant (http://localhost:8123)
- ✅ Agent Server (http://localhost:5001)
- ✅ Cloudflare Tunnel (https://random-url.trycloudflare.com)

**Note the tunnel URL** - you may need to update Lambda if it changed!

## Daily Commands

```bash
./start.sh          # Start everything
./start.sh status   # Check what's running
./start.sh logs     # View recent logs
./start.sh stop     # Stop everything
```

## Test It

```bash
# Command line
python agent.py "turn living room to fire"

# Web UI
open http://localhost:5001

# Voice (if Alexa set up)
"Alexa, ask home brain to make me feel like I'm under the sea"
```

## If Tunnel URL Changed

1. Get new URL: `./start.sh status`
2. Update Lambda:
   - AWS Console → Lambda → Environment variables
   - `AGENT_URL` = new tunnel URL
3. Test Alexa again

## Full Docs

- **Setup**: [docs/getting-started.md](docs/getting-started.md)
- **Startup**: [docs/startup-guide.md](docs/startup-guide.md)
- **Alexa**: [docs/alexa-integration.md](docs/alexa-integration.md)
- **API**: [docs/api-reference.md](docs/api-reference.md)

## Logs

```bash
./start.sh logs                    # Recent logs
tail -f logs/server.log           # Live server logs
tail -f logs/tunnel.log           # Live tunnel logs
docker logs -f homeassistant      # HA logs
```

## Help

```bash
./start.sh help
```

---

**Current Status:** Phase 2 - Alexa integration ready to deploy!
