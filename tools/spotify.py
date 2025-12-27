"""
Smart Home Assistant - Spotify Integration

Tools for controlling Spotify playback via Spotify Web API and Spotify Connect.
Enables voice-controlled music playback to Amazon Echo devices.

Key Features:
- OAuth 2.0 authentication with automatic token refresh
- Playback control (play/pause/skip/volume)
- Search for tracks, albums, playlists, artists
- Spotify Connect device targeting
- Natural language command support

Requirements:
- Spotify Premium account (required for playback control)
- spotipy library: pip install spotipy

Environment Variables:
- SPOTIFY_CLIENT_ID: Spotify app client ID
- SPOTIFY_CLIENT_SECRET: Spotify app client secret
- SPOTIFY_REDIRECT_URI: OAuth redirect URI (default: http://localhost:8888/callback)

References:
- https://developer.spotify.com/documentation/web-api
- https://spotipy.readthedocs.io/
"""

from typing import Any, Optional
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

from src.config import DATA_DIR
from src.utils import setup_logging, send_health_alert

logger = setup_logging("tools.spotify")

# Track consecutive errors to avoid alert spam
_consecutive_spotify_errors = 0
_SPOTIFY_ERROR_ALERT_THRESHOLD = 3  # Alert after N consecutive errors


def _handle_spotify_error(error: Exception, operation: str) -> None:
    """
    Handle Spotify API errors with rate-limited alerting.

    Args:
        error: The exception that occurred
        operation: Description of what operation failed
    """
    global _consecutive_spotify_errors
    _consecutive_spotify_errors += 1

    error_msg = getattr(error, 'msg', str(error)) if hasattr(error, 'msg') else str(error)
    logger.error(f"Spotify API error during {operation}: {error_msg}")

    # Alert on threshold hit to avoid spam
    if _consecutive_spotify_errors == _SPOTIFY_ERROR_ALERT_THRESHOLD:
        send_health_alert(
            title="Spotify API Errors Detected",
            message=f"*{_consecutive_spotify_errors}* consecutive Spotify API errors. Last error during `{operation}`",
            severity="warning",
            component="spotify",
            details={
                "operation": operation,
                "error": error_msg[:200],  # Truncate long error messages
                "consecutive_errors": _consecutive_spotify_errors,
            },
        )


def _reset_spotify_error_count() -> None:
    """Reset error count on successful operation."""
    global _consecutive_spotify_errors
    if _consecutive_spotify_errors > 0:
        # If we were in an error state, send recovery alert
        if _consecutive_spotify_errors >= _SPOTIFY_ERROR_ALERT_THRESHOLD:
            send_health_alert(
                title="Spotify API Recovered",
                message="Spotify API is responding normally again",
                severity="info",
                component="spotify",
            )
        _consecutive_spotify_errors = 0

# Required OAuth scopes for playback control and device management
SPOTIFY_SCOPES = [
    "user-modify-playback-state",  # Control playback
    "user-read-playback-state",    # Read device and playback state
    "user-read-currently-playing", # Read current track
]

# Tool definitions for Claude
SPOTIFY_TOOLS = [
    {
        "name": "play_spotify",
        "description": """Play music on Spotify via Spotify Connect. Use this for requests to play songs, albums, playlists, or artists.

Supports:
- Playing specific tracks by name
- Playing albums
- Playing playlists
- Playing artist radio/top tracks
- Targeting specific devices (Amazon Echo, etc.)

Examples:
- "play Hey Jude on living room speaker" -> query='Hey Jude', device_name='living room'
- "play Abbey Road album" -> query='Abbey Road', content_type='album'
- "play my Chill Vibes playlist on bedroom" -> query='Chill Vibes', content_type='playlist', device_name='bedroom'
- "play Radiohead" -> query='Radiohead', content_type='artist'

NOTE: Requires Spotify Premium account and active Spotify Connect device.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song name, album, playlist, or artist to play"
                },
                "content_type": {
                    "type": "string",
                    "enum": ["track", "album", "playlist", "artist"],
                    "description": "Type of content to play (default: track)"
                },
                "device_name": {
                    "type": "string",
                    "description": "Device name to play on (e.g., 'living room', 'bedroom echo'). If not specified, plays on currently active device."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "control_playback",
        "description": """Control Spotify playback (pause, resume, skip, volume).

Actions:
- pause: Pause current playback
- resume: Resume paused playback
- next: Skip to next track
- previous: Skip to previous track
- volume: Set volume level (0-100)

Examples:
- "pause spotify" -> action='pause'
- "skip this song" -> action='next'
- "previous track" -> action='previous'
- "set volume to 50" -> action='volume', volume=50""",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["pause", "resume", "next", "previous", "volume"],
                    "description": "Playback control action"
                },
                "volume": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Volume level (0-100), required when action='volume'"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "search_spotify",
        "description": """Search Spotify for tracks, albums, playlists, or artists.

Returns a list of matching results with metadata (name, artist, URI, etc.).

Examples:
- "find Beatles songs" -> query='Beatles', search_type='track'
- "search for jazz playlists" -> query='jazz', search_type='playlist'
- "look up Radiohead albums" -> query='Radiohead', search_type='album'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["track", "album", "playlist", "artist"],
                    "description": "Type of content to search for"
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of results (default: 10)"
                }
            },
            "required": ["query", "search_type"]
        }
    },
    {
        "name": "get_spotify_devices",
        "description": """Get all available Spotify Connect devices.

Returns a list of devices with their ID, name, type, and active status.
Use this to see what devices can be targeted for playback.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "transfer_playback",
        "description": """Transfer Spotify playback to a different device.

Use this to move currently playing music to another speaker.

Examples:
- "switch to bedroom speaker" -> device_name='bedroom'
- "move music to kitchen and resume" -> device_name='kitchen', force_play=True""",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Target device name"
                },
                "force_play": {
                    "type": "boolean",
                    "description": "Automatically resume playback on new device (default: False)"
                }
            },
            "required": ["device_name"]
        }
    },
    {
        "name": "get_now_playing_context",
        "description": """Get detailed context about the currently playing music.

Returns comprehensive information about what's playing including:
- Track name, artist, album
- Artist genres, popularity, and top tracks
- Audio features (tempo, key, energy, mood)
- Playback progress and device

Use this when the user asks about:
- "What's playing?" / "What song is this?"
- "Tell me about this artist/band"
- "What genre is this?"
- "Who sings this song?"

The returned context enables answering follow-up questions about the music.""",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_artist_info",
        "description": """Get detailed information about a music artist.

Returns:
- Artist name, genres, popularity score
- Follower count
- Top tracks
- Recent albums

Use this when the user asks about:
- "Tell me about [artist]"
- "What genre is [artist]?"
- "What are [artist]'s best songs?"
- Historical/background questions about artists

Examples:
- "Tell me about Queen" -> artist_name='Queen'
- "What genre is Radiohead?" -> artist_name='Radiohead'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "artist_name": {
                    "type": "string",
                    "description": "Name of the artist to look up"
                },
                "artist_id": {
                    "type": "string",
                    "description": "Spotify artist ID (optional, more precise than name)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_album_info",
        "description": """Get detailed information about a music album.

Returns:
- Album name, artist, release date
- Total tracks, track listing
- Record label, copyright info

Use this when the user asks about:
- "Tell me about [album]"
- "What songs are on [album]?"
- "When was [album] released?"

Examples:
- "Tell me about Abbey Road" -> album_name='Abbey Road'
- "What tracks are on Thriller?" -> album_name='Thriller'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "album_name": {
                    "type": "string",
                    "description": "Name of the album to look up"
                },
                "album_id": {
                    "type": "string",
                    "description": "Spotify album ID (optional, more precise than name)"
                }
            },
            "required": []
        }
    }
]


class SpotifyClient:
    """
    Spotify API client with OAuth authentication and automatic token refresh.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        """
        Initialize Spotify client.

        Args:
            client_id: Spotify app client ID (or SPOTIFY_CLIENT_ID env var)
            client_secret: Spotify app client secret (or SPOTIFY_CLIENT_SECRET env var)
            redirect_uri: OAuth redirect URI (default: http://localhost:8888/callback)

        Raises:
            ValueError: If required credentials are missing
        """
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv(
            "SPOTIFY_REDIRECT_URI",
            "http://localhost:8888/callback"
        )

        if not self.client_id:
            raise ValueError("client_id is required (SPOTIFY_CLIENT_ID)")
        if not self.client_secret:
            raise ValueError("client_secret is required (SPOTIFY_CLIENT_SECRET)")

        # Create cache directory for tokens
        cache_dir = DATA_DIR / "spotify_cache"
        cache_dir.mkdir(exist_ok=True)
        cache_path = cache_dir / ".spotify_token_cache"

        # Initialize OAuth manager
        self.auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=" ".join(SPOTIFY_SCOPES),
            cache_path=str(cache_path),
            open_browser=False  # Don't auto-open browser in server environment
        )

        # Initialize Spotify client
        self.spotify = spotipy.Spotify(auth_manager=self.auth_manager)

        logger.info("Spotify client initialized")

    def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token string
        """
        token_info = self.auth_manager.get_cached_token()

        if not token_info:
            logger.warning("No cached token found. User must authenticate.")
            raise ValueError("No cached token. Run OAuth flow first.")

        # Check if token is expired and refresh if needed
        if self.auth_manager.is_token_expired(token_info):
            logger.info("Token expired, refreshing...")
            token_info = self.auth_manager.refresh_access_token(
                token_info['refresh_token']
            )

        return token_info['access_token']


# Singleton client instance
_spotify_client: Optional[SpotifyClient] = None


def get_spotify_client() -> SpotifyClient:
    """
    Get or create the singleton Spotify client instance.

    Returns:
        SpotifyClient instance

    Raises:
        ValueError: If credentials are not configured
    """
    global _spotify_client

    if _spotify_client is None:
        _spotify_client = SpotifyClient()

    return _spotify_client


def find_device_by_name(devices: list[dict], device_name: str) -> Optional[dict]:
    """
    Find a Spotify device by name (case-insensitive, partial match).

    Args:
        devices: List of device dictionaries from Spotify API
        device_name: Device name to search for

    Returns:
        Matching device dict or None
    """
    device_name_lower = device_name.lower()

    # Try exact match first
    for device in devices:
        if device['name'].lower() == device_name_lower:
            return device

    # Try partial match (e.g., "living room" matches "Living Room Echo Dot")
    for device in devices:
        if device_name_lower in device['name'].lower():
            return device

    return None


def play_spotify(
    query: str,
    content_type: str = "track",
    device_name: Optional[str] = None
) -> dict[str, Any]:
    """
    Play music on Spotify via Spotify Connect.

    Args:
        query: Song name, album, playlist, or artist
        content_type: Type of content ('track', 'album', 'playlist', 'artist')
        device_name: Target device name (optional)

    Returns:
        Result dictionary with success status and details
    """
    try:
        client = get_spotify_client()
        spotify = client.spotify

        # Search for content
        logger.info(f"Searching Spotify: query='{query}', type='{content_type}'")
        search_results = spotify.search(q=query, type=content_type, limit=1)

        # Extract results based on content type
        items_key = f"{content_type}s"
        items = search_results.get(items_key, {}).get('items', [])

        if not items:
            return {
                "success": False,
                "error": f"No {content_type} found matching '{query}'"
            }

        item = items[0]
        content_uri = item['uri']
        content_name = item['name']

        # Get artist name for tracks/albums
        artist_name = None
        if content_type in ('track', 'album'):
            artists = item.get('artists', [])
            if artists:
                artist_name = artists[0]['name']

        # Get available devices
        devices_result = spotify.devices()
        devices = devices_result.get('devices', [])

        if not devices:
            return {
                "success": False,
                "error": "No Spotify devices available. Make sure a device is active."
            }

        # Find target device
        target_device = None
        if device_name:
            target_device = find_device_by_name(devices, device_name)
            if not target_device:
                available = [d['name'] for d in devices]
                return {
                    "success": False,
                    "error": f"Device '{device_name}' not found",
                    "available_devices": available
                }
        else:
            # Use currently active device or first available
            for device in devices:
                if device.get('is_active'):
                    target_device = device
                    break
            if not target_device:
                target_device = devices[0]

        device_id = target_device['id']
        device_display_name = target_device['name']

        # Start playback
        logger.info(f"Starting playback: {content_name} on {device_display_name}")

        if content_type == 'track':
            # Play specific track
            spotify.start_playback(device_id=device_id, uris=[content_uri])
        else:
            # Play album/playlist/artist (context URI)
            spotify.start_playback(device_id=device_id, context_uri=content_uri)

        result = {
            "success": True,
            "content_type": content_type,
            "device": device_display_name,
            "message": f"Now playing {content_name}"
        }

        if content_type == 'track':
            result['track_name'] = content_name
            if artist_name:
                result['artist'] = artist_name
        elif content_type == 'album':
            result['album_name'] = content_name
            if artist_name:
                result['artist'] = artist_name
        elif content_type == 'playlist':
            result['playlist_name'] = content_name
            owner = item.get('owner', {}).get('display_name')
            if owner:
                result['owner'] = owner
        elif content_type == 'artist':
            result['artist_name'] = content_name

        _reset_spotify_error_count()
        return result

    except SpotifyException as error:
        _handle_spotify_error(error, f"play_spotify({content_type}: {query})")
        return {
            "success": False,
            "error": f"Spotify API error: {error.msg if hasattr(error, 'msg') else str(error)}"
        }
    except Exception as error:
        logger.error(f"Error playing Spotify: {error}")
        return {"success": False, "error": str(error)}


def control_playback(
    action: str,
    volume: Optional[int] = None
) -> dict[str, Any]:
    """
    Control Spotify playback.

    Args:
        action: Control action ('pause', 'resume', 'next', 'previous', 'volume')
        volume: Volume level 0-100 (required for action='volume')

    Returns:
        Result dictionary with success status
    """
    try:
        # Validate volume parameter
        if action == "volume":
            if volume is None:
                return {
                    "success": False,
                    "error": "volume parameter required for volume action"
                }
            if not 0 <= volume <= 100:
                return {
                    "success": False,
                    "error": f"volume must be 0-100, got {volume}"
                }

        client = get_spotify_client()
        spotify = client.spotify

        logger.info(f"Spotify playback control: action={action}, volume={volume}")

        if action == "pause":
            spotify.pause_playback()
        elif action == "resume":
            spotify.start_playback()
        elif action == "next":
            spotify.next_track()
        elif action == "previous":
            spotify.previous_track()
        elif action == "volume":
            spotify.volume(volume_percent=volume)
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }

        result = {
            "success": True,
            "action": action,
            "message": f"Playback {action} executed"
        }

        if action == "volume":
            result["volume"] = volume

        _reset_spotify_error_count()
        return result

    except SpotifyException as error:
        _handle_spotify_error(error, f"control_playback({action})")
        return {
            "success": False,
            "error": f"Spotify API error: {error.msg if hasattr(error, 'msg') else str(error)}"
        }
    except Exception as error:
        logger.error(f"Error controlling playback: {error}")
        return {"success": False, "error": str(error)}


def search_spotify(
    query: str,
    search_type: str,
    limit: int = 10
) -> dict[str, Any]:
    """
    Search Spotify for content.

    Args:
        query: Search query
        search_type: Type to search for ('track', 'album', 'playlist', 'artist')
        limit: Maximum number of results (1-50)

    Returns:
        Result dictionary with search results
    """
    try:
        client = get_spotify_client()
        spotify = client.spotify

        logger.info(f"Searching Spotify: query='{query}', type='{search_type}', limit={limit}")

        search_results = spotify.search(q=query, type=search_type, limit=limit)

        # Extract results based on search type
        items_key = f"{search_type}s"
        items = search_results.get(items_key, {}).get('items', [])

        results = []

        if search_type == 'track':
            for track in items:
                results.append({
                    'name': track['name'],
                    'artist': track['artists'][0]['name'] if track.get('artists') else 'Unknown',
                    'album': track['album']['name'] if track.get('album') else 'Unknown',
                    'uri': track['uri'],
                    'duration_ms': track.get('duration_ms', 0)
                })

        elif search_type == 'album':
            for album in items:
                results.append({
                    'name': album['name'],
                    'artist': album['artists'][0]['name'] if album.get('artists') else 'Unknown',
                    'uri': album['uri'],
                    'release_date': album.get('release_date'),
                    'total_tracks': album.get('total_tracks', 0)
                })

        elif search_type == 'playlist':
            for playlist in items:
                results.append({
                    'name': playlist['name'],
                    'uri': playlist['uri'],
                    'owner': playlist.get('owner', {}).get('display_name', 'Unknown'),
                    'track_count': playlist.get('tracks', {}).get('total', 0)
                })

        elif search_type == 'artist':
            for artist in items:
                results.append({
                    'name': artist['name'],
                    'uri': artist['uri'],
                    'genres': artist.get('genres', []),
                    'followers': artist.get('followers', {}).get('total', 0)
                })

        message = f"Found {len(results)} {search_type}(s)"
        if len(results) == 0:
            message = f"No results found for '{query}'"

        _reset_spotify_error_count()
        return {
            "success": True,
            "search_type": search_type,
            "query": query,
            "results": results,
            "count": len(results),
            "message": message
        }

    except SpotifyException as error:
        _handle_spotify_error(error, f"search_spotify({search_type}: {query})")
        return {
            "success": False,
            "error": f"Spotify API error: {error.msg if hasattr(error, 'msg') else str(error)}"
        }
    except Exception as error:
        logger.error(f"Error searching Spotify: {error}")
        return {"success": False, "error": str(error)}


def get_spotify_devices() -> dict[str, Any]:
    """
    Get all available Spotify Connect devices.

    Returns:
        Result dictionary with list of devices
    """
    try:
        client = get_spotify_client()
        spotify = client.spotify

        logger.info("Getting Spotify devices")

        devices_result = spotify.devices()
        devices = devices_result.get('devices', [])

        device_list = []
        for device in devices:
            device_list.append({
                'id': device['id'],
                'name': device['name'],
                'type': device['type'],
                'is_active': device.get('is_active', False),
                'volume_percent': device.get('volume_percent', 0)
            })

        _reset_spotify_error_count()
        return {
            "success": True,
            "devices": device_list,
            "count": len(device_list),
            "message": f"Found {len(device_list)} device(s)"
        }

    except SpotifyException as error:
        _handle_spotify_error(error, "get_spotify_devices")
        return {
            "success": False,
            "error": f"Spotify API error: {error.msg if hasattr(error, 'msg') else str(error)}"
        }
    except Exception as error:
        logger.error(f"Error getting devices: {error}")
        return {"success": False, "error": str(error)}


def transfer_playback(
    device_name: str,
    force_play: bool = False
) -> dict[str, Any]:
    """
    Transfer Spotify playback to a different device.

    Args:
        device_name: Target device name
        force_play: Automatically resume playback on new device

    Returns:
        Result dictionary with success status
    """
    try:
        client = get_spotify_client()
        spotify = client.spotify

        logger.info(f"Transferring playback to: {device_name}, force_play={force_play}")

        # Get available devices
        devices_result = spotify.devices()
        devices = devices_result.get('devices', [])

        if not devices:
            return {
                "success": False,
                "error": "No Spotify devices available"
            }

        # Find target device
        target_device = find_device_by_name(devices, device_name)

        if not target_device:
            available = [d['name'] for d in devices]
            return {
                "success": False,
                "error": f"Device '{device_name}' not found",
                "available_devices": available
            }

        device_id = target_device['id']
        device_display_name = target_device['name']

        # Transfer playback
        spotify.transfer_playback(device_id=device_id, force_play=force_play)

        _reset_spotify_error_count()
        return {
            "success": True,
            "device": device_display_name,
            "force_play": force_play,
            "message": f"Playback transferred to {device_display_name}"
        }

    except SpotifyException as error:
        _handle_spotify_error(error, f"transfer_playback({device_name})")
        return {
            "success": False,
            "error": f"Spotify API error: {error.msg if hasattr(error, 'msg') else str(error)}"
        }
    except Exception as error:
        logger.error(f"Error transferring playback: {error}")
        return {"success": False, "error": str(error)}


def get_now_playing_context() -> dict[str, Any]:
    """
    Get comprehensive context about the currently playing music.

    Returns detailed information for answering questions about what's playing,
    including artist genres, audio features (tempo, key, mood), etc.

    Returns:
        Result dictionary with full music context
    """
    try:
        from src.music_context import get_music_context

        context = get_music_context()
        result = context.get_current_track_context()

        logger.info(f"Got now playing context: success={result.get('success')}")
        return result

    except Exception as error:
        logger.error(f"Error getting now playing context: {error}")
        return {"success": False, "error": str(error)}


def get_artist_info(
    artist_name: Optional[str] = None,
    artist_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Get detailed information about a music artist.

    Args:
        artist_name: Artist name to search for
        artist_id: Spotify artist ID (more precise)

    Returns:
        Result dictionary with artist details
    """
    try:
        if not artist_name and not artist_id:
            return {
                "success": False,
                "error": "Either artist_name or artist_id is required"
            }

        from src.music_context import get_music_context

        context = get_music_context()
        result = context.get_artist_context(
            artist_id=artist_id,
            artist_name=artist_name
        )

        logger.info(f"Got artist info: success={result.get('success')}")
        return result

    except Exception as error:
        logger.error(f"Error getting artist info: {error}")
        return {"success": False, "error": str(error)}


def get_album_info(
    album_name: Optional[str] = None,
    album_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Get detailed information about a music album.

    Args:
        album_name: Album name to search for
        album_id: Spotify album ID (more precise)

    Returns:
        Result dictionary with album details
    """
    try:
        if not album_name and not album_id:
            return {
                "success": False,
                "error": "Either album_name or album_id is required"
            }

        from src.music_context import get_music_context

        context = get_music_context()
        result = context.get_album_context(
            album_id=album_id,
            album_name=album_name
        )

        logger.info(f"Got album info: success={result.get('success')}")
        return result

    except Exception as error:
        logger.error(f"Error getting album info: {error}")
        return {"success": False, "error": str(error)}


def execute_spotify_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a Spotify tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing Spotify tool: {tool_name}")

    if tool_name == "play_spotify":
        return play_spotify(
            query=tool_input.get("query", ""),
            content_type=tool_input.get("content_type", "track"),
            device_name=tool_input.get("device_name")
        )

    elif tool_name == "control_playback":
        return control_playback(
            action=tool_input.get("action", ""),
            volume=tool_input.get("volume")
        )

    elif tool_name == "search_spotify":
        return search_spotify(
            query=tool_input.get("query", ""),
            search_type=tool_input.get("search_type", "track"),
            limit=tool_input.get("limit", 10)
        )

    elif tool_name == "get_spotify_devices":
        return get_spotify_devices()

    elif tool_name == "transfer_playback":
        return transfer_playback(
            device_name=tool_input.get("device_name", ""),
            force_play=tool_input.get("force_play", False)
        )

    elif tool_name == "get_now_playing_context":
        return get_now_playing_context()

    elif tool_name == "get_artist_info":
        return get_artist_info(
            artist_name=tool_input.get("artist_name"),
            artist_id=tool_input.get("artist_id")
        )

    elif tool_name == "get_album_info":
        return get_album_info(
            album_name=tool_input.get("album_name"),
            album_id=tool_input.get("album_id")
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
