# Alexa Integration Guide

Complete guide for integrating voice control via Amazon Alexa.

## Current Status

✅ **Completed:**
- Local agent server running ([server.py](../server.py))
- Cloudflare Tunnel providing public HTTPS access
- Lambda function code ready ([lambda/alexa_forwarder.py](../lambda/alexa_forwarder.py))

⏳ **To Complete:**
- Deploy Lambda function to AWS
- Create Alexa Custom Skill
- Configure skill to use Lambda
- Test end-to-end voice control

## Architecture

```
"Alexa, ask home brain to turn living room to fire"
    ↓
Alexa Service (cloud)
    ↓ (JSON intent)
AWS Lambda Function
    ↓ (HTTP POST)
Cloudflare Tunnel
    ↓
Local Server (localhost:5001)
    ↓
Agent → Home Assistant → Hue Lights
```

## Part 1: Cloudflare Tunnel (DONE ✅)

### Current Tunnel

**URL:** https://pan-metal-fourth-sand.trycloudflare.com

**Running:** Background process on your Mac
**Command:**
```bash
cloudflared tunnel --url http://localhost:5001
```

### Test Tunnel

```bash
# Health check
curl https://pan-metal-fourth-sand.trycloudflare.com/health

# Test command
curl -X POST https://pan-metal-fourth-sand.trycloudflare.com/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "turn living room to fire"}'
```

### Important Notes

⚠️ **Free tunnel URLs change every restart!**
- Each time you run `cloudflared tunnel`, you get a new random URL
- You'll need to update the Lambda environment variable when URL changes

## Part 2: AWS Lambda Function

### Lambda Code

Located at: [lambda/alexa_forwarder.py](../lambda/alexa_forwarder.py)

This function:
- Receives Alexa's complex JSON requests
- Extracts the natural language command
- Forwards to your local agent via tunnel
- Formats response back to Alexa

### Deploy Lambda (TODO)

1. **Go to AWS Console** → Lambda
2. **Create function:**
   - Name: `alexa-home-automation-forwarder`
   - Runtime: Python 3.12
   - Architecture: arm64 (cheaper) or x86_64
3. **Copy code:**
   - Open [lambda/alexa_forwarder.py](../lambda/alexa_forwarder.py)
   - Copy entire contents
   - Paste into Lambda function code editor
4. **Set environment variable:**
   - Key: `AGENT_URL`
   - Value: `https://pan-metal-fourth-sand.trycloudflare.com` (your current tunnel URL)
5. **Configure:**
   - Timeout: 30 seconds (default 3s is too short)
   - Memory: 128 MB is fine
6. **Save** and note the Lambda ARN

### Lambda ARN Format

```
arn:aws:lambda:us-east-1:123456789012:function:alexa-home-automation-forwarder
```

You'll need this for the Alexa Skill.

## Part 3: Alexa Custom Skill (TODO)

### Create Skill

1. **Go to [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)**
2. **Create Skill:**
   - Name: "Home Brain" (or whatever you want)
   - Primary locale: English (US)
   - Model: Custom
   - Hosting: Alexa-hosted (Node.js) - but we'll use Lambda instead
3. **Choose template:** Start from scratch

### Configure Invocation

**Invocation name:** `home brain`

This is what users say: "Alexa, ask **home brain** to..."

### Create Intent

**Intent name:** `LightingIntent`

**Sample utterances:**
```
turn {command}
make {command}
set {command}
{command}
```

**Slot:**
- Name: `command`
- Type: `AMAZON.SearchQuery` (captures everything user says)

### Connect to Lambda

1. **Endpoint** section
2. **Select:** AWS Lambda ARN
3. **Paste your Lambda ARN:**
   ```
   arn:aws:lambda:us-east-1:YOUR_ACCOUNT:function:alexa-home-automation-forwarder
   ```
4. **Save Endpoints**

### Build Model

Click **"Build Model"** - takes ~30 seconds

### Testing

1. **Test tab** in Alexa console
2. **Type or speak:** "ask home brain to turn living room to fire"
3. **Check response:**
   - Should see agent's response
   - Check CloudWatch logs in Lambda for debugging

## Part 4: Testing End-to-End

### Test with Actual Alexa Device

Once skill is enabled in test mode:

```
"Alexa, ask home brain to turn living room to fire"
"Alexa, tell home brain to make me feel like I'm under the sea"
"Alexa, ask home brain for cozy bedroom lighting"
```

### Debugging

**If not working:**

1. **Check tunnel is running:**
   ```bash
   curl https://pan-metal-fourth-sand.trycloudflare.com/health
   ```

2. **Check Lambda logs:**
   - AWS Console → CloudWatch → Log groups
   - Look for `/aws/lambda/alexa-home-automation-forwarder`

3. **Test Lambda directly:**
   - Lambda console → Test tab
   - Use test event (see below)

4. **Check agent logs:**
   - Look at terminal running `server.py`

### Lambda Test Event

Use this to test Lambda without Alexa:

```json
{
  "request": {
    "type": "IntentRequest",
    "intent": {
      "name": "LightingIntent",
      "slots": {
        "command": {
          "value": "turn living room to fire"
        }
      }
    }
  }
}
```

## Production Migration (FUTURE)

### Current (Development)
- **Tunnel:** Cloudflare free tier (URL changes)
- **Location:** Running on your Mac
- **Stability:** Manual restart needed

### Production (When Moving to Old Laptop)

#### Option 1: Cloudflare Named Tunnel (FREE - RECOMMENDED)

**Pros:**
- Free forever
- Static URL (doesn't change)
- Automatic reconnection
- Better reliability

**Setup:**
1. Create Cloudflare account (free)
2. Install cloudflared on old laptop
3. Create named tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create home-automation
   cloudflared tunnel route dns home-automation home.yourdomain.com
   ```
4. Run as service:
   ```bash
   cloudflared tunnel run home-automation
   ```

**Cost:** $0/month

#### Option 2: Tailscale VPN (FREE)

**Pros:**
- Most secure (private VPN)
- No exposed ports
- Works anywhere

**Cons:**
- Slightly more complex Lambda setup (need Tailscale Lambda Layer)

**Setup:**
1. Install Tailscale on old laptop
2. Install Tailscale Lambda Layer
3. Lambda connects via private Tailscale network

**Cost:** $0/month (up to 100 devices)

#### Option 3: Router Port Forwarding + Dynamic DNS (FREE)

**Pros:**
- No third-party dependency
- Direct connection

**Cons:**
- Need router access
- Security concerns (port exposed to internet)
- Need SSL certificate

**Setup:**
1. Port forward 5001 on router → old laptop
2. Set up Dynamic DNS (DuckDNS, No-IP)
3. Get Let's Encrypt SSL certificate

**Cost:** $0/month

### Recommended: Cloudflare Named Tunnel

For production, use Cloudflare Named Tunnel because:
- Free
- Static URL (update Lambda once)
- Reliable
- No router configuration needed
- No security concerns

## Common Issues

### Tunnel URL Changed

**Symptom:** Lambda returns "timeout" or "connection refused"

**Fix:**
1. Check current tunnel URL (look at cloudflared output)
2. Update Lambda environment variable `AGENT_URL`
3. Test again

### Lambda Timeout

**Symptom:** Alexa says "there was a problem" after long pause

**Fix:**
1. Increase Lambda timeout to 30 seconds
2. Check agent is responding quickly

### Alexa Doesn't Understand

**Symptom:** Alexa triggers wrong intent or says "I don't know that"

**Fix:**
1. Add more sample utterances to LightingIntent
2. Rebuild Alexa model
3. Test in Alexa console first

### Agent Returns Error

**Symptom:** Alexa repeats agent's error message

**Fix:**
1. Check agent logs
2. Test command directly: `python agent.py "your command"`
3. Check Home Assistant is running

## Next Steps

1. ✅ Tunnel running and tested
2. ⏳ Deploy Lambda function to AWS
3. ⏳ Create Alexa Custom Skill
4. ⏳ Test end-to-end with voice
5. ⏳ Document production migration in [session-log.md](session-log.md)

## Quick Reference

**Current Tunnel URL:**
```
https://pan-metal-fourth-sand.trycloudflare.com
```

**Restart Tunnel:**
```bash
cloudflared tunnel --url http://localhost:5001
```

**Test Command:**
```bash
curl -X POST https://pan-metal-fourth-sand.trycloudflare.com/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "turn living room to fire"}'
```

**Lambda File:**
```
lambda/alexa_forwarder.py
```

**Environment Variable:**
```
AGENT_URL=https://pan-metal-fourth-sand.trycloudflare.com
```
