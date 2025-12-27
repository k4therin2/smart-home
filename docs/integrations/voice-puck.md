# Voice Puck Setup

This guide covers setting up voice control hardware with the Smart Home Assistant.

## Overview

Voice pucks enable hands-free control of your smart home:
- Wake word activation ("Hey Jarvis", "OK Home", etc.)
- Natural language commands
- Spoken responses via TTS
- Multi-room support

## Hardware Options

### Option 1: Home Assistant Voice PE ($59)

The official Home Assistant voice device.

**Pros:**
- Official support
- Plug-and-play setup
- Built-in speaker and microphone
- Local wake word processing

**Setup:**
1. Connect to power
2. Add via Home Assistant > Settings > Devices
3. Configure wake word in HA
4. Route commands to Smart Home Assistant (see below)

### Option 2: ATOM Echo ($30)

M5Stack ATOM Echo - compact and affordable.

**Pros:**
- Small form factor
- Good value
- ESPHome compatible

**Setup:**
1. Flash ESPHome firmware
2. Configure voice pipeline
3. Add to Home Assistant
4. Route commands to Smart Home Assistant

### Option 3: ESP32-S3-BOX (DIY)

Build your own with full customization.

**Pros:**
- Full control
- Local processing
- Customizable

**Components needed:**
- ESP32-S3-BOX or ESP32-S3-BOX-3
- ESPHome configuration
- Optional: external speaker

### Option 4: Existing Smart Speaker (Limited)

Use existing Alexa/Google devices with limited integration.

**Limitation:** Cannot fully bypass commercial assistants, but can trigger HA automations.

## Software Prerequisites

Before hardware setup:

1. **Smart Home Assistant running:**
   ```bash
   curl -k https://localhost:5050/api/health
   ```

2. **Voice webhook token configured:**
   ```bash
   # In .env
   VOICE_WEBHOOK_TOKEN=your_secure_token_here
   ```

3. **HTTPS enabled:**
   - Voice webhooks should use HTTPS
   - Certificate warnings are OK for local network

## Home Assistant Configuration

### Step 1: Voice Pipeline Setup

Configure Home Assistant's voice pipeline:

1. Go to Settings > Voice assistants
2. Add a new assistant or edit default
3. Configure components:
   - **STT (Speech-to-Text):** Whisper (local) or cloud provider
   - **TTS (Text-to-Speech):** Piper (local) or cloud provider
   - **Conversation Agent:** Custom webhook (next step)

### Step 2: Configure Webhook Routing

Choose one of these methods to route voice commands to Smart Home Assistant:

#### Method A: REST Command (Recommended)

Add to Home Assistant `configuration.yaml`:

```yaml
rest_command:
  smart_home_voice:
    url: "https://YOUR_SERVER:5050/api/voice_command"
    method: POST
    verify_ssl: false  # For self-signed certificates
    headers:
      Authorization: "Bearer {{ states('input_text.voice_webhook_token') }}"
      Content-Type: "application/json"
    payload: >
      {
        "text": "{{ text }}",
        "language": "{{ language }}",
        "device_id": "{{ device_id }}"
      }

input_text:
  voice_webhook_token:
    name: Voice Webhook Token
    initial: ""  # Set via UI with your VOICE_WEBHOOK_TOKEN value
```

#### Method B: Custom Conversation Agent

For direct integration with HA Voice Pipeline:

```yaml
conversation:
  - platform: rest
    name: "Smart Home Agent"
    url: "https://YOUR_SERVER:5050/api/voice_command"
    headers:
      Authorization: "Bearer YOUR_TOKEN_HERE"
```

#### Method C: Automation Routing

Route all voice commands through an automation:

```yaml
automation:
  - alias: "Route Voice to Smart Home Agent"
    trigger:
      - platform: conversation
        command: "*"  # Match all commands
    action:
      - service: rest_command.smart_home_voice
        data:
          text: "{{ trigger.sentence }}"
          language: "{{ trigger.language }}"
          device_id: "{{ trigger.device_id }}"
```

### Step 3: Configure STT (Speech-to-Text)

#### Option A: Whisper (Local - Recommended)

1. Install Whisper add-on:
   - Settings > Add-ons > Add-on Store
   - Search "Whisper"
   - Install and start

2. Configure pipeline:
   - Settings > Voice assistants
   - Select Whisper for STT

**Whisper models:**
| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | 75MB | Fast | Good |
| base | 142MB | Medium | Better |
| small | 466MB | Slow | Best |

Use `base` for good balance of speed and accuracy.

#### Option B: Cloud STT

Use Google Cloud, Azure, or AWS speech recognition:
- Faster initial response
- Better accuracy for some accents
- Requires internet and API keys
- Privacy considerations

### Step 4: Configure TTS (Text-to-Speech)

#### Option A: Piper (Local - Recommended)

1. Install Piper add-on
2. Select voice (e.g., `en_US-lessac-medium`)
3. Configure in voice pipeline

#### Option B: Cloud TTS

- Google Cloud TTS
- Amazon Polly
- Microsoft Azure TTS

### Step 5: Set Up Voice Puck

Follow hardware-specific setup for your device:

#### Home Assistant Voice PE

1. Connect to power
2. HA auto-discovers the device
3. Add to your voice pipeline
4. Configure wake word

#### ATOM Echo with ESPHome

Example ESPHome configuration:

```yaml
esphome:
  name: voice-puck-living-room

esp32:
  board: m5stack-atom

i2s_audio:
  i2s_lrclk_pin: GPIO33
  i2s_bclk_pin: GPIO19

microphone:
  - platform: i2s_audio
    id: atom_mic
    i2s_din_pin: GPIO23
    adc_type: external

speaker:
  - platform: i2s_audio
    id: atom_speaker
    dac_type: external
    i2s_dout_pin: GPIO22
    mode: mono

voice_assistant:
  microphone: atom_mic
  speaker: atom_speaker
  noise_suppression_level: 2
  auto_gain: 31dBFS
  volume_multiplier: 2.0
```

## Testing Voice Control

### Test 1: Verify Webhook

```bash
curl -k -X POST https://localhost:5050/api/voice_command \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"text": "what time is it?"}'
```

Expected response:
```json
{
  "response": "It's 3:45 PM.",
  "success": true
}
```

### Test 2: End-to-End Voice

1. Activate wake word
2. Say a command: "Turn on the living room lights"
3. Verify:
   - STT converts speech to text
   - Webhook receives command
   - Agent processes command
   - TTS speaks response
   - Action completes

### Test 3: Response Quality

Test these command types:
- Simple: "What time is it?"
- Device control: "Turn on the lights"
- Query: "What's the temperature?"
- Complex: "Set a timer for 10 minutes"

## Voice Response Formatting

The Smart Home Assistant formats responses for TTS:

**Before (raw agent output):**
```
Sure! I'd be happy to help! The living room lights have been turned on. 💡
```

**After (TTS-friendly):**
```
The living room lights have been turned on.
```

The ResponseFormatter:
- Removes chatty phrases ("Sure!", "Of course!")
- Strips emojis and special characters
- Truncates long responses (100 words default)
- Normalizes whitespace

## Multi-Room Setup

### Registering Voice Pucks

Each voice puck has a location identity for context-aware commands:

```bash
# Register a puck via command
python agent.py "register voice puck living_room_puck in living room"
```

Or via the location tools API.

### Context-Aware Commands

When location is known:
- "Turn on the lights" → Uses puck's room
- "Turn on bedroom lights" → Explicit override
- "Turn on all lights" → All rooms

### Room Inference

The system infers room from:
1. Voice puck device ID (if registered)
2. User's tracked location
3. Default location setting
4. Asks for clarification if unknown

## Troubleshooting

### Voice Not Recognized

1. **Check STT is working:**
   - HA > Developer Tools > Services
   - Call `stt.whisper` service manually
   - Verify transcription appears

2. **Microphone issues:**
   - Check puck microphone isn't muted
   - Verify audio levels in ESPHome logs
   - Test with `arecord` on Linux

### No Response Spoken

1. **Check TTS is working:**
   - HA > Developer Tools > Services
   - Call `tts.piper` or your TTS service
   - Verify audio plays

2. **Speaker issues:**
   - Check volume levels
   - Verify speaker connection
   - Test with known working audio

### Commands Not Executing

1. **Check webhook token:**
   - Must match between HA config and .env
   - Token is case-sensitive

2. **Verify HTTPS:**
   - Self-signed certs need `verify_ssl: false` in HA
   - Or use HTTP for local network (less secure)

3. **Check server logs:**
   ```bash
   tail -f data/logs/smarthome.log
   ```

### High Latency

Typical response times:
- Wake word: <500ms (local)
- STT: 1-3 seconds (varies by model)
- Agent processing: 1-2 seconds
- TTS: <1 second (local)
- **Total: 3-6 seconds**

To reduce latency:
1. Use smaller Whisper model
2. Enable response caching
3. Use local STT/TTS (no cloud round-trip)
4. Ensure good WiFi signal

### Wake Word Issues

1. **Too sensitive:**
   - Adjust sensitivity in device config
   - Choose less common wake word

2. **Not triggering:**
   - Speak clearly toward device
   - Reduce background noise
   - Check wake word model

## Security Considerations

1. **Use HTTPS:** Voice commands should be encrypted
2. **Token authentication:** Never expose webhook without auth
3. **Local processing:** Prefer Whisper/Piper for privacy
4. **Network isolation:** Consider VLAN for IoT devices

## Example Voice Commands

After setup, try these commands:

```
"Turn on the living room lights"
"Set bedroom to 50% brightness"
"Make it cozy"
"What's the temperature?"
"Play some jazz on the living room speaker"
"Set a timer for 15 minutes"
"Add milk to my shopping list"
"What's on my todo list?"
"Start the vacuum"
"Close the blinds"
```

## References

- [Home Assistant Voice PE](https://www.home-assistant.io/voice_control/)
- [ESPHome Voice Assistant](https://esphome.io/components/voice_assistant.html)
- [Whisper Add-on](https://github.com/home-assistant/addons/tree/master/whisper)
- [Piper Add-on](https://github.com/home-assistant/addons/tree/master/piper)
- [M5Stack ATOM Echo](https://shop.m5stack.com/products/atom-echo-smart-speaker-dev-kit)
