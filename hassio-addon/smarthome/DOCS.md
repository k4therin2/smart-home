# SmartHome Assistant Add-on

Privacy-focused, agentic smart home assistant with LLM-powered natural language control.

## About

SmartHome is a self-hosted smart home assistant designed to replace commercial voice assistants (Alexa, Google Home) with an open-source, privacy-focused alternative.

**Key Features:**
- Natural language control of lights, blinds, music, and more
- Voice control integration via Home Assistant Assist pipeline
- Automatic cost tracking and alerts for API usage
- Self-monitoring and self-healing capabilities
- Privacy-first design - all data stored locally

## Installation

1. Add this repository to your Home Assistant add-on store:
   - Go to **Settings** > **Add-ons** > **Add-on Store**
   - Click the three-dot menu (top-right) > **Repositories**
   - Add: `https://github.com/k4therin2/smarthome`

2. Find "SmartHome Assistant" in the add-on store and click **Install**

3. Configure the add-on (see Configuration section below)

4. Click **Start**

## Configuration

### Required Settings

| Option | Description |
|--------|-------------|
| `openai_api_key` | Your OpenAI API key. Get one at https://platform.openai.com/api-keys |

### Optional Settings

| Option | Default | Description |
|--------|---------|-------------|
| `openai_model` | `gpt-4o-mini` | OpenAI model to use |
| `daily_cost_target` | `2.0` | Daily API cost target (USD) |
| `daily_cost_alert` | `5.0` | Cost threshold for Slack alerts (USD) |
| `log_level` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `slack_webhook_url` | | Slack webhook for alerts (optional) |
| `spotify_client_id` | | Spotify app client ID (optional) |
| `spotify_client_secret` | | Spotify app secret (optional) |

### Example Configuration

```yaml
openai_api_key: "sk-..."
openai_model: "gpt-4o-mini"
daily_cost_target: 2.0
daily_cost_alert: 5.0
log_level: "INFO"
```

## Usage

### Web UI

Access the SmartHome web interface from the Home Assistant sidebar or at:
- **HTTP:** `http://homeassistant.local:5049`
- **HTTPS:** `https://homeassistant.local:5050`

### Voice Control

SmartHome integrates with Home Assistant's Assist pipeline for voice control:

1. Go to **Settings** > **Voice assistants**
2. Create or edit an Assist pipeline
3. Set the **Conversation agent** to "SmartHome Agent"

### Example Commands

- "Turn on the living room lights"
- "Set bedroom to cozy evening"
- "Play some jazz music"
- "What's the temperature in the kitchen?"
- "Turn off all lights downstairs"

## Integrations

SmartHome works with devices already configured in Home Assistant:

- **Philips Hue** - Lights and color control
- **Smart Blinds** - Tuya/Hapadif blinds
- **Spotify** - Music playback control
- **Ring Cameras** - Camera integration
- **Vacuum** - Dreame L10s Ultra

## Troubleshooting

### Add-on won't start

1. Check that your OpenAI API key is valid
2. Review the add-on logs for error messages
3. Ensure port 5050 isn't in use by another service

### Voice commands not working

1. Verify the Assist pipeline is configured correctly
2. Check SmartHome logs for transcription errors
3. Test direct API calls to `/api/voice_command`

### High API costs

1. Check the cost tracker at `/api/costs`
2. Consider using a cheaper model (gpt-4o-mini)
3. Set up Slack alerts for cost thresholds

## Support

- **GitHub Issues:** https://github.com/k4therin2/smarthome/issues
- **Documentation:** https://github.com/k4therin2/smarthome/docs

## Privacy

SmartHome is designed with privacy in mind:

- All data stored locally in Home Assistant
- No telemetry or analytics sent to developers
- Third-party services (OpenAI, Spotify) only used when explicitly enabled
- Full privacy policy available at PRIVACY_POLICY.md

## License

MIT License - See LICENSE file for details.
