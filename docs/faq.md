# Frequently Asked Questions

## General Questions

### What is Smart Home Assistant?

Smart Home Assistant is a self-hosted, AI-powered smart home controller built on Home Assistant. It uses Claude (Anthropic's LLM) for natural language processing, enabling voice and text control of your smart home devices without relying on commercial cloud services.

### How is this different from Alexa or Google Home?

| Feature | Smart Home Assistant | Commercial Assistants |
|---------|---------------------|----------------------|
| Privacy | Self-hosted, no cloud recording | Voice data sent to cloud |
| Customization | Full control over behavior | Limited customization |
| Dependencies | Requires Home Assistant | Standalone |
| Cost | One-time setup + API costs | Subscription or device purchase |
| Offline | Partial (needs LLM API) | Requires internet |
| Personality | Minimal, business-like | Pre-defined personality |

### What smart home devices are supported?

Any device that works with Home Assistant is supported, including:
- **Lights:** Philips Hue, LIFX, Z-Wave, Zigbee
- **Blinds:** Tuya/Smart Life compatible, Z-Wave, Zigbee
- **Vacuum:** Dreame, Roborock, iRobot (via HA integrations)
- **Media:** Spotify (Premium), Chromecast
- **Climate:** Any HA-compatible thermostat
- **Sensors:** Temperature, motion, door/window sensors

### What are the ongoing costs?

| Cost Item | Typical Amount |
|-----------|---------------|
| Anthropic API | $0.50-2.00/day for moderate use |
| Spotify (optional) | Premium subscription required |
| Hardware | One-time cost for devices |
| Hosting | Free (self-hosted) |

The system tracks API costs and can alert you at configurable thresholds.

---

## Setup & Installation

### What are the minimum requirements?

- **Hardware:** Any computer that can run Python (Raspberry Pi 4+, old laptop, server)
- **Software:** Python 3.12+, Home Assistant
- **Accounts:** Anthropic API key
- **Network:** Local network access to Home Assistant

### Can I run this on a Raspberry Pi?

Yes, Raspberry Pi 4 or newer is recommended. Raspberry Pi 3 may work but could be slow.

```bash
# Recommended: Raspberry Pi 4 with 4GB+ RAM
# OS: Raspberry Pi OS 64-bit (Bookworm)
```

### Do I need Home Assistant?

Yes, Home Assistant is required. It serves as the integration layer for your smart devices. Smart Home Assistant sends commands to Home Assistant, which then controls your devices.

### Can I use this without an Anthropic API key?

No, the Anthropic API (Claude) is required for natural language processing. There's no built-in fallback to other LLMs, though this could be added in the future.

### How do I get an Anthropic API key?

1. Visit [console.anthropic.com](https://console.anthropic.com)
2. Create an account
3. Add payment method
4. Generate API key
5. Copy to your `.env` file

---

## Usage & Commands

### What commands can I use?

Natural language commands for:
- **Lights:** "Turn on the living room lights", "Make it cozy", "Set bedroom to 50%"
- **Music:** "Play some jazz", "Volume up", "Skip this song"
- **Climate:** "What's the temperature?", "Set thermostat to 72"
- **Productivity:** "Add milk to shopping list", "Set a timer for 10 minutes"
- **Automation:** "Turn on lights at sunset", "When I leave, start vacuum"
- **Status:** "What time is it?", "What's playing?"

### Why doesn't the assistant understand my command?

Try being more specific:
- Instead of: "lights" → "turn on the living room lights"
- Instead of: "music" → "play jazz on living room speaker"
- Instead of: "turn it on" → "turn on the bedroom lamp"

### Can I create custom commands?

Yes, through the automation system:
```
"Create an automation called movie time that dims lights and closes blinds"
```

### How do I see what devices are available?

```
"List available rooms"
"What devices do you have access to?"
"What lights can you control?"
```

---

## Privacy & Security

### Is my voice data stored?

If using local STT (Whisper), voice audio is processed locally and not stored.

Commands processed by the LLM are sent to Anthropic's API. Review [Anthropic's privacy policy](https://www.anthropic.com/privacy) for their data handling practices.

### Is the web interface secure?

Yes, with these protections:
- HTTPS encryption (self-signed by default)
- Session-based authentication
- CSRF protection
- Rate limiting
- Security headers (HSTS, CSP, X-Frame-Options)

### Can others on my network access this?

By default, the server is accessible on your local network. For additional security:
1. Use strong password
2. Enable HTTPS
3. Consider network segmentation/VLAN
4. Use firewall rules

### Should I expose this to the internet?

Not recommended without additional security measures:
- VPN access (preferred)
- Reverse proxy with proper authentication
- Strong passwords
- Regular updates

---

## Integrations

### How do I add a new device?

1. Add device to Home Assistant first
2. Verify entity appears in HA
3. Update `src/config.py` with entity mapping
4. Restart Smart Home Assistant

### Why isn't my device responding?

Check in order:
1. Does device work in Home Assistant directly?
2. Is entity ID correct in configuration?
3. Is Home Assistant connection healthy? (`/api/health`)
4. Check logs for specific errors

### Can I use Alexa/Google devices with this?

Partially:
- You cannot fully bypass their built-in assistants
- You can trigger Home Assistant automations from them
- You can use them as Spotify Connect targets
- Consider dedicated voice pucks for best experience

### Does Spotify work with my Echo?

Yes! The system uses Spotify Connect, which works with:
- Amazon Echo devices
- Sonos speakers
- Google Home/Nest
- Any Spotify Connect-enabled device

Requirements:
- Spotify Premium account
- Device linked to same Spotify account
- Device must be "awake" (play something via Spotify app first)

---

## Troubleshooting

### Why do I see "Connection refused"?

Most common causes:
1. Server not running → `python server.py`
2. Wrong port → Check if using 5050 (HTTPS) or 5049 (HTTP)
3. Firewall blocking → Check firewall rules
4. Home Assistant URL wrong → Verify `HA_URL` in `.env`

### Why is it slow?

Common causes and solutions:
1. **First request is slow:** Normal, cache is empty
2. **LLM latency:** Network issue or API load
3. **Large model:** Whisper `small` is slower than `tiny`
4. **Network issues:** Check ping times to Home Assistant

### Why won't it turn on my lights?

Troubleshooting steps:
1. Check room name matches configuration
2. Verify entity ID is correct
3. Test light via Home Assistant directly
4. Check Home Assistant connection health

### How do I reset everything?

```bash
# Stop server
# Remove databases and cache
rm -rf data/*.db data/cache/* data/spotify_cache/*

# Optionally remove SSL certs
rm -rf data/ssl/*

# Restart and reconfigure
python server.py
```

---

## Performance & Costs

### How much does it cost to run?

Typical costs:
- **Light use (10-20 commands/day):** $0.20-0.50/day
- **Medium use (50-100 commands/day):** $0.50-1.50/day
- **Heavy use (200+ commands/day):** $2.00-5.00/day

Configure alerts in `.env`:
```bash
DAILY_COST_TARGET=2.00
DAILY_COST_ALERT=5.00
```

### How can I reduce API costs?

1. **Use caching:** Enabled by default for HA state queries
2. **Simpler commands:** More specific commands need fewer tokens
3. **Batch operations:** "Turn on all lights" vs individual commands
4. **Check usage:** Monitor via cost tracking alerts

### Why is the response cache not working?

The cache only works for:
- Home Assistant state queries (device status)
- Repeated identical commands within TTL

LLM responses are not cached (each command needs fresh processing).

---

## Development

### How do I contribute?

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines. Key steps:
1. Fork the repository
2. Create feature branch
3. Write tests
4. Submit pull request

### How do I add a new device type?

1. Create tool module in `tools/`:
   ```python
   # tools/new_device.py
   def get_tool_definitions():
       return [...]

   def handle_tool_call(name, arguments, ha_client):
       ...
   ```

2. Register in `tools/__init__.py`

3. Add to agent.py imports and tool list

### How do I run tests?

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/unit/test_cache.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Where are the logs?

```
data/logs/
├── smarthome.log          # Main application log
├── smarthome_YYYY-MM-DD.log  # Daily rotated logs
├── errors.log             # Errors only
└── api_calls.log          # API usage tracking
```

---

## Updates & Maintenance

### How do I update?

```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart smarthome  # if using systemd
```

### Is there automatic updates?

No, updates are manual. Check the repository regularly for new releases.

### How do I backup my configuration?

Backup these directories:
```bash
# Configuration
cp .env .env.backup

# Data
tar -czvf smarthome-backup.tar.gz data/

# Don't backup (regenerated):
# - data/ssl/ (certificates)
# - data/cache/ (temporary)
# - venv/ (recreated from requirements.txt)
```

### How do I restore from backup?

```bash
# Restore .env
cp .env.backup .env

# Restore data
tar -xzvf smarthome-backup.tar.gz

# Regenerate certificates
python scripts/generate_cert.py

# Restart
python server.py
```
