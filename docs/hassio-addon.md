# Home Assistant Add-on Installation

SmartHome can be installed as a Home Assistant add-on for easy deployment on Home Assistant OS or Home Assistant Supervised installations.

## Prerequisites

- Home Assistant OS or Home Assistant Supervised
- Home Assistant version 2024.1 or later
- OpenAI API key (for LLM functionality)

## Installation

### Step 1: Add the Repository

1. Open your Home Assistant instance
2. Go to **Settings** > **Add-ons** > **Add-on Store**
3. Click the three-dot menu (top-right corner)
4. Select **Repositories**
5. Add: `https://github.com/k4therin2/smarthome`
6. Click **Add** then **Close**

### Step 2: Install the Add-on

1. In the Add-on Store, find "SmartHome Assistant" in the "SmartHome Add-ons" section
2. Click on it to view details
3. Click **Install**
4. Wait for the installation to complete

### Step 3: Configure

1. Go to the **Configuration** tab
2. Enter your **OpenAI API Key** (required)
3. Adjust other settings as needed (see Configuration Options below)
4. Click **Save**

### Step 4: Start

1. Go to the **Info** tab
2. Click **Start**
3. Enable **Watchdog** to auto-restart on failures
4. Optionally enable **Start on boot**

## Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `openai_api_key` | Yes | | Your OpenAI API key |
| `openai_model` | No | `gpt-4o-mini` | OpenAI model to use |
| `daily_cost_target` | No | `2.0` | Daily API cost target (USD) |
| `daily_cost_alert` | No | `5.0` | Cost threshold for alerts (USD) |
| `log_level` | No | `INFO` | Logging level |
| `slack_webhook_url` | No | | Slack webhook for alerts |
| `spotify_client_id` | No | | Spotify app client ID |
| `spotify_client_secret` | No | | Spotify app secret |

## Accessing the UI

Once started, SmartHome is accessible via:

- **Home Assistant Sidebar** - Click the SmartHome icon (if ingress is enabled)
- **Direct URL** - `http://[your-ha-ip]:5050`

## Voice Control Integration

To use SmartHome with voice commands:

1. Go to **Settings** > **Voice assistants**
2. Create or edit an Assist pipeline
3. Under **Conversation agent**, select "SmartHome Agent"
4. Save the pipeline

Now you can use voice commands like:
- "Hey Jarvis, turn on the living room lights"
- "Set bedroom to cozy evening"
- "Play some relaxing music"

## Data Storage

The add-on stores data in Home Assistant's `/data` directory:
- **Database**: `/data/smarthome.db` (SQLite)
- **Logs**: Accessible via add-on log viewer

Data is automatically backed up with Home Assistant backups.

## Troubleshooting

### Add-on fails to start

1. Check the **Log** tab for error messages
2. Verify your OpenAI API key is valid
3. Ensure no other service is using ports 5049/5050

### Can't access the UI

1. Check the add-on is running (green status)
2. Try accessing directly at `http://[ha-ip]:5050`
3. Check browser console for errors

### Voice commands not working

1. Verify the Assist pipeline is configured correctly
2. Check SmartHome logs for transcription errors
3. Test the API directly: `curl http://[ha-ip]:5050/api/health`

### High API costs

1. Monitor costs at `/api/costs`
2. Set up Slack alerts for cost thresholds
3. Consider using a cheaper model

## Updating

To update the add-on:

1. Go to **Settings** > **Add-ons**
2. Click on "SmartHome Assistant"
3. If an update is available, click **Update**
4. The add-on will restart automatically

## Uninstalling

1. Go to **Settings** > **Add-ons**
2. Click on "SmartHome Assistant"
3. Click **Uninstall**
4. Optionally, remove the repository from the Add-on Store

**Note:** Uninstalling removes the add-on but not your data in `/data/smarthome.db`. To remove data, delete the file via SSH or the File Editor add-on.

## Comparison with Docker Installation

| Feature | Add-on | Docker |
|---------|--------|--------|
| Installation | One-click | Manual |
| Updates | Automatic | Manual |
| Backup | Included with HA | Separate |
| Home Assistant integration | Native (supervisor) | Manual (API) |
| Resource management | HA managed | Manual |
| Best for | HA OS users | Advanced users |

The add-on is recommended for most users running Home Assistant OS. Docker installation is better for advanced users who want more control or are running Home Assistant Core/Container.
