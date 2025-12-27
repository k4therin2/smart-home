# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the Smart Home Assistant.

## Quick Diagnostics

### Health Check

Run the health check to identify system issues:

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

If any component shows `unhealthy`, check the specific section below.

### View Logs

```bash
# Recent logs
tail -100 data/logs/smarthome.log

# Error logs only
tail -100 data/logs/errors.log

# Follow logs in real-time
tail -f data/logs/smarthome.log
```

Or view in web UI: Navigate to the Logs tab.

---

## Installation Issues

### "Python version X.X is not supported"

**Cause:** Python version is below 3.12

**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.12+
# On Ubuntu:
sudo apt install python3.12 python3.12-venv

# On macOS:
brew install python@3.12

# Create venv with specific version
python3.12 -m venv venv
```

### "pip install" fails

**Cause:** Various dependency issues

**Solutions:**

1. **Upgrade pip:**
   ```bash
   pip install --upgrade pip
   ```

2. **Install build dependencies (Linux):**
   ```bash
   sudo apt install python3-dev build-essential libffi-dev libssl-dev
   ```

3. **Install specific package separately:**
   ```bash
   pip install argon2-cffi  # If argon2 fails
   pip install pyOpenSSL    # If SSL fails
   ```

### "Module not found" errors

**Cause:** Virtual environment not activated or dependencies not installed

**Solution:**
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Verify activation
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Server Issues

### Server Won't Start

**Check 1: Port already in use**
```bash
# Find process using port 5050
lsof -i :5050

# Kill process if needed
kill -9 <PID>
```

**Check 2: SSL certificate issues**
```bash
# Regenerate certificates
python scripts/generate_cert.py --force

# Or disable HTTPS temporarily
USE_HTTPS=false python server.py
```

**Check 3: Environment variables**
```bash
# Verify .env exists and is readable
cat .env | grep -v SECRET | grep -v TOKEN

# Ensure required variables are set
grep ANTHROPIC_API_KEY .env
grep HA_URL .env
grep HA_TOKEN .env
```

### "Address already in use"

```bash
# Find and kill existing process
lsof -i :5050
kill -9 <PID>

# Or use different port
PORT=5051 python server.py
```

### SSL Certificate Errors

**Browser shows warning:**
- This is normal for self-signed certificates
- Click "Advanced" > "Proceed anyway"
- Add exception for localhost

**Certificates expired:**
```bash
python scripts/generate_cert.py --force
# Restart server
```

**Certificate not found:**
```bash
# Generate if missing
python scripts/generate_cert.py

# Check certificates exist
ls -la data/ssl/
```

---

## Authentication Issues

### "Invalid credentials" on login

**Solutions:**

1. **Reset authentication:**
   ```bash
   # Remove auth database
   rm data/auth.db

   # Restart server
   python server.py

   # Create new account at /auth/setup
   ```

2. **Check password requirements:**
   - Minimum 8 characters
   - Case-sensitive

### "Session expired"

**Cause:** FLASK_SECRET_KEY not set (random key regenerates on restart)

**Solution:**
```bash
# Generate and set permanent secret key
echo "FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
```

### "CSRF token invalid"

**Cause:** Token expired or missing

**Solutions:**
1. Refresh the page and try again
2. Clear browser cookies
3. Check if JavaScript is enabled

---

## Home Assistant Connection Issues

### "Connection refused" to Home Assistant

**Check 1: URL is correct**
```bash
# Test connection
curl http://homeassistant.local:8123/api/

# Common URLs to try:
# http://homeassistant.local:8123
# http://192.168.1.X:8123
# http://localhost:8123 (if same machine)
```

**Check 2: Home Assistant is running**
```bash
# Check HA status
curl http://homeassistant.local:8123/api/
```

**Check 3: Firewall/network**
```bash
# Test network connectivity
ping homeassistant.local
```

### "Unauthorized" (401) from Home Assistant

**Cause:** Invalid or expired token

**Solution:**
1. Generate new long-lived access token:
   - HA web UI > Profile > Long-Lived Access Tokens
   - Create new token
   - Copy immediately (shown only once)

2. Update .env:
   ```bash
   HA_TOKEN=your_new_token_here
   ```

3. Restart server

### "Entity not found"

**Cause:** Entity ID doesn't match Home Assistant

**Solution:**
1. Find correct entity ID:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states | jq '.[] | .entity_id'
   ```

2. Update configuration in `src/config.py`

---

## Device-Specific Issues

### Lights

#### "Room not found"

**Cause:** Room name doesn't match configuration

**Solution:**
```python
# Check configured rooms in src/config.py
ROOM_ENTITY_MAP = {
    "living_room": {...},
    # Room names must match these keys
}
```

Add aliases for common variations:
```python
"living_room": {
    "lights": [...],
    "aliases": ["lounge", "front room", "main room"],
}
```

#### Lights don't respond

1. **Check entity in HA:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states/light.living_room
   ```

2. **Test HA service directly:**
   ```bash
   curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"entity_id": "light.living_room"}' \
     http://homeassistant.local:8123/api/services/light/turn_on
   ```

### Spotify

#### "No active device"

**Solution:**
1. Open Spotify on any device first
2. Play something briefly to "wake" the device
3. Try command again

#### "Premium required"

Spotify Premium is required for playback control. Free accounts can only:
- Search
- View devices
- See currently playing

#### OAuth authorization failed

```bash
# Remove cached token
rm data/spotify_cache/.spotify_token_cache

# Re-authorize
python agent.py "list spotify devices"
# Follow browser prompts
```

### Vacuum

#### "Entity not found"

1. **Check HACS integration installed:**
   - HA > HACS > Integrations
   - Search for "Dreame Vacuum"

2. **Verify entity ID:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://homeassistant.local:8123/api/states | grep vacuum
   ```

3. **Update .env:**
   ```bash
   VACUUM_ENTITY_ID=vacuum.your_actual_entity_id
   ```

### Blinds

#### Blinds move wrong direction

**Cause:** Position values may be inverted

**Solution:** Add to `src/config.py`:
```python
BLINDS_INVERTED = ["cover.bedroom_blinds"]
```

#### "Cover not available"

1. **Check Tuya integration:**
   - HA > Settings > Devices & Services > Tuya
   - Re-authenticate if needed

2. **Check bridge:**
   - Hapadif hub LED should be solid
   - Try control via Smart Life app

---

## API Issues

### Rate Limiting

**Error:** "Too many requests"

**Cause:** Exceeded rate limits

**Default limits:**
- `/api/command`: 10 requests/minute
- `/api/status`: 30 requests/minute
- Global: 200 requests/day, 50 requests/hour

**Solution:** Wait before retrying. Rate limits reset automatically.

### "Command too long"

**Error:** "Command must be between 1 and 1000 characters"

**Solution:** Shorten your command. Complex requests can be broken into multiple commands.

### API returns empty response

**Check logs:**
```bash
tail -50 data/logs/smarthome.log | grep ERROR
```

**Common causes:**
1. LLM API error - check ANTHROPIC_API_KEY
2. Agent timeout - try simpler command
3. Tool execution error - check device connectivity

---

## LLM/Agent Issues

### "API key invalid"

```bash
# Verify key is set
grep ANTHROPIC_API_KEY .env

# Test key directly
curl -H "x-api-key: YOUR_KEY" \
  -H "content-type: application/json" \
  https://api.anthropic.com/v1/messages \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

### Commands not understood

**Cause:** LLM interpretation issues

**Solutions:**
1. Be more specific:
   - Instead of: "lights"
   - Try: "turn on the living room lights"

2. Use exact device names:
   - Instead of: "my speaker"
   - Try: "living room echo"

### Agent timeout

**Cause:** Complex command or slow network

**Solutions:**
1. Try simpler command
2. Check internet connectivity
3. Increase timeout in config (advanced)

---

## Performance Issues

### Slow response times

**Check 1: Cache status**
```bash
curl -k https://localhost:5050/api/health
# Look at cache stats
```

**Check 2: Network latency**
```bash
ping homeassistant.local
```

**Check 3: LLM latency**
- Anthropic API status: https://status.anthropic.com/

### High memory usage

```bash
# Check process memory
ps aux | grep python

# Restart to clear memory
sudo systemctl restart smarthome
```

### Database growth

```bash
# Check database size
ls -la data/*.db

# Vacuum old data
sqlite3 data/smarthome.db "VACUUM;"
```

---

## Voice Control Issues

### Wake word not triggering

1. **Check microphone:**
   - Test with other apps
   - Check volume/mute status

2. **Reduce background noise:**
   - TVs, music, fans can interfere

3. **Speak clearly:**
   - Face the device
   - Use normal volume

### Commands not recognized

1. **Check STT is working:**
   - HA > Developer Tools > Services
   - Test `stt.whisper` service

2. **Adjust Whisper model:**
   - Try `base` instead of `tiny`
   - Larger models are more accurate

### No voice response

1. **Check TTS:**
   - Test Piper service in HA
   - Verify speaker connection

2. **Check volume:**
   - Device speaker volume
   - TTS output level

---

## Getting Help

### Collect Diagnostic Information

Before requesting help, gather:

```bash
# System info
python --version
pip freeze

# Health status
curl -k https://localhost:5050/api/health

# Recent errors
tail -100 data/logs/errors.log

# Configuration (sanitized)
cat .env | grep -v SECRET | grep -v TOKEN | grep -v KEY
```

### Where to Get Help

1. **Check FAQ:** [docs/faq.md](faq.md)
2. **GitHub Issues:** Report bugs with diagnostic info
3. **Documentation:** Review relevant integration guides

### Reporting Issues

When reporting issues, include:
- Exact error message
- Steps to reproduce
- Relevant log excerpts
- System information (Python version, OS)
- Configuration (without secrets)
