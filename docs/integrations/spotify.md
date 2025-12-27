# Spotify Integration

This guide covers setting up Spotify music playback with the Smart Home Assistant.

## Overview

The Spotify integration enables:
- Voice-controlled music playback
- Targeting specific Spotify Connect devices (Echo, speakers)
- Search for tracks, albums, playlists, and artists
- Playback controls (play, pause, skip, volume)
- Device transfer (move music between speakers)

## Prerequisites

- Spotify Premium account (required for playback control)
- Spotify Connect devices (Echo, Sonos, etc.)
- Python 3.12+ with Smart Home Assistant installed

## Step 1: Create Spotify Developer App

1. Visit [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create App"
4. Fill in the form:
   - **App name:** Smart Home Assistant
   - **App description:** Home automation music control
   - **Redirect URI:** `http://localhost:8888/callback`
   - **Which API/SDKs are you planning to use?** Web API
5. Check the Terms of Service agreement
6. Click "Save"

### Get Your Credentials

After creating the app:
1. Click on your new app
2. Click "Settings" (top right)
3. Note your **Client ID**
4. Click "View client secret" to see your **Client Secret**

## Step 2: Configure Environment

Add to your `.env` file:

```bash
# Spotify Configuration
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

Replace `your_client_id_here` and `your_client_secret_here` with your actual credentials.

## Step 3: Complete OAuth Authorization

The first time you use Spotify commands, you'll need to authorize the app:

1. Run a Spotify command:
   ```bash
   source venv/bin/activate
   python agent.py "what spotify devices are available?"
   ```

2. A browser window opens automatically
3. Log in to Spotify if prompted
4. Click "Agree" to authorize the app
5. The browser redirects to `localhost:8888/callback`
6. Copy the full URL from the browser address bar
7. Paste it in the terminal when prompted

The token is cached in `data/spotify_cache/.spotify_token_cache` and refreshes automatically.

## Available Commands

### Playing Music

```
"Play Hey Jude on living room speaker"
"Play Abbey Road album"
"Play some jazz"
"Play my Chill Vibes playlist"
"Play The Beatles"
"Play something relaxing on bedroom speaker"
```

### Playback Control

```
"Pause Spotify"
"Resume music"
"Skip this song"
"Previous track"
"Set volume to 50"
"Volume up"
"Volume down"
```

### Device Management

```
"What Spotify devices are available?"
"Switch music to kitchen speaker"
"Move playback to bedroom"
"Transfer to living room echo"
```

### Search

```
"Find jazz playlists"
"Search for Beatles songs"
"Find workout music"
```

## Device Targeting

### Fuzzy Matching

You don't need to use exact device names. The system uses fuzzy matching:

| You say | Matches |
|---------|---------|
| "living room" | "Living Room Echo Dot" |
| "bedroom speaker" | "Bedroom Echo" |
| "kitchen" | "Kitchen Sonos" |

### Finding Device Names

To see exact device names:
```
"What Spotify devices are available?"
```

Response:
```
Available Spotify devices:
- Living Room Echo Dot (active)
- Bedroom Echo (inactive)
- Kitchen Sonos One (inactive)
```

### Common Issues with Devices

**"No active device found":**
- Spotify must be open on at least one device
- Play something via Spotify app first to "wake" a device
- Then use voice commands

**Device not appearing:**
- Ensure device is connected to WiFi
- Open Spotify app on device or use Spotify Connect
- Some devices need Spotify running in background

## Configuration

### Multiple Accounts

Currently supports a single Spotify account. For multi-user support:
1. Each user would need separate token storage
2. This is planned for future development

### Token Refresh

Tokens refresh automatically. If you encounter auth errors:

1. Delete the cached token:
   ```bash
   rm data/spotify_cache/.spotify_token_cache
   ```

2. Run any Spotify command to re-authorize

### Scopes

The integration requests these Spotify scopes:
- `user-modify-playback-state` - Control playback
- `user-read-playback-state` - Read device/playback state
- `user-read-currently-playing` - Read current track

## Troubleshooting

### "Spotify Premium Required"

Playback control requires Spotify Premium. Free accounts can only:
- Search for music
- Get device list
- See currently playing

### "No Device Found"

1. **Check Spotify is active:**
   - Open Spotify app on your Echo/speaker
   - Play something briefly via Spotify app
   - Devices stay active for ~30 minutes after last use

2. **Check device connectivity:**
   - Ensure device is on same network
   - Restart the device if needed

### "Authorization Failed"

1. **Verify credentials:**
   - Check SPOTIFY_CLIENT_ID in .env matches dashboard
   - Check SPOTIFY_CLIENT_SECRET in .env

2. **Check redirect URI:**
   - Dashboard redirect URI must exactly match .env
   - Default: `http://localhost:8888/callback`

3. **Re-authorize:**
   ```bash
   rm data/spotify_cache/.spotify_token_cache
   python agent.py "list spotify devices"
   ```

### "Rate Limited"

Spotify has API rate limits. If you hit them:
- Wait a few minutes
- The system includes automatic retry logic
- Reduce command frequency if persistent

### Echo/Alexa Not Working

1. **Link Spotify to Alexa:**
   - Open Alexa app
   - Settings > Music & Podcasts
   - Link Spotify account

2. **Set default music service:**
   - Alexa app > Settings > Music
   - Default Services > Spotify

3. **Enable Spotify Connect:**
   - Play via Spotify app first
   - Echo appears as Spotify Connect device

## Testing the Integration

### Run Integration Tests

```bash
source venv/bin/activate
pytest tests/integration/test_spotify.py -v
```

### Manual Testing

```bash
# Test device discovery
python agent.py "list spotify devices"

# Test playback (with active device)
python agent.py "play some jazz music"

# Test search
python agent.py "find Beatles albums"

# Test control
python agent.py "pause spotify"
```

## API Usage and Costs

The Spotify integration uses Spotify's Web API, which is free to use. The integration:
- Caches results to reduce API calls
- Uses efficient batch operations
- Handles rate limiting automatically

This does NOT count against your Anthropic API usage - only the LLM processing does.

## References

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api)
- [Spotipy Library Documentation](https://spotipy.readthedocs.io/)
- [Spotify Connect Guide](https://support.spotify.com/us/article/spotify-connect/)
- [OAuth 2.0 Authorization Code Flow](https://developer.spotify.com/documentation/web-api/tutorials/code-flow)
