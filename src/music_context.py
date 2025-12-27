"""
Music Context Manager

Tracks currently playing music and provides rich context about artists,
albums, and tracks for the LLM to use when answering music-related questions.

The key insight is that this module provides DATA context to the LLM,
which already has extensive knowledge about music, artists, history, and theory.
No specialized prompts are needed - we just need to tell the LLM what's
currently playing and it can answer questions naturally.

Example usage:
    context = MusicContext()
    now_playing = context.get_now_playing()
    # LLM can now answer "Tell me about this artist" using its knowledge
    # combined with the context of what's playing
"""

import time
from typing import Any

from spotipy.exceptions import SpotifyException

from src.utils import setup_logging
from tools.spotify import get_spotify_client


logger = setup_logging("music_context")

# Musical key mapping (pitch class notation)
KEY_NAMES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]

# Musical mode mapping
MODE_NAMES = {0: "Minor", 1: "Major"}

# Cache TTL in seconds (5 minutes for artist/album info)
CACHE_TTL = 300


class MusicContext:
    """
    Manager for music context tracking and retrieval.

    Provides methods to get information about currently playing music,
    artist details, album details, and track audio features.
    Uses caching to reduce API calls for repeated queries.
    """

    def __init__(self):
        """
        Initialize MusicContext.

        Attempts to create a Spotify client connection.
        If credentials are missing, marks itself as unavailable.
        """
        self._spotify = None
        self._available = False
        self._cache = {}
        self._cache_timestamps = {}

        try:
            client = get_spotify_client()
            self._spotify = client.spotify
            self._available = True
            logger.info("MusicContext initialized with Spotify client")
        except ValueError as error:
            logger.warning(f"MusicContext unavailable: {error}")
            self._available = False
        except Exception as error:
            logger.error(f"Unexpected error initializing MusicContext: {error}")
            self._available = False

    def is_available(self) -> bool:
        """Check if music context service is available."""
        return self._available

    @staticmethod
    def key_to_note(key: int) -> str:
        """
        Convert Spotify key number to note name.

        Args:
            key: Key number (0-11, pitch class notation)

        Returns:
            Note name (e.g., 'C', 'F#/Gb') or 'Unknown' for invalid keys
        """
        if 0 <= key < 12:
            return KEY_NAMES[key]
        return "Unknown"

    @staticmethod
    def mode_to_name(mode: int) -> str:
        """
        Convert Spotify mode number to mode name.

        Args:
            mode: Mode number (0=minor, 1=major)

        Returns:
            Mode name ('Major', 'Minor') or 'Unknown' for invalid modes
        """
        return MODE_NAMES.get(mode, "Unknown")

    def _get_cached(self, cache_key: str) -> dict | None:
        """Get item from cache if not expired."""
        if cache_key in self._cache:
            timestamp = self._cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < CACHE_TTL:
                return self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, value: dict) -> None:
        """Set item in cache with timestamp."""
        self._cache[cache_key] = value
        self._cache_timestamps[cache_key] = time.time()

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.debug("Cache cleared")

    def get_now_playing(self) -> dict[str, Any]:
        """
        Get information about the currently playing track.

        Returns:
            Dictionary with:
                - success: bool
                - is_playing: bool
                - track: dict with name, artist, album, duration_ms, etc. (if playing)
                - progress_ms: int (if playing)
                - device: str device name (if playing)
                - error: str (if failed)
        """
        if not self._available:
            return {
                "success": False,
                "error": "Music context service not available (Spotify not configured)",
            }

        try:
            playback = self._spotify.current_playback()

            if playback is None:
                return {"success": True, "is_playing": False}

            item = playback.get("item")
            if item is None:
                return {"success": True, "is_playing": False}

            # Extract artist info
            artists = item.get("artists", [])
            artist_name = artists[0]["name"] if artists else "Unknown"
            artist_id = artists[0].get("id") if artists else None

            # Extract album info
            album = item.get("album", {})
            album_name = album.get("name", "Unknown")
            album_id = album.get("id")
            album_image = None
            if album.get("images"):
                album_image = album["images"][0].get("url")

            # Build track info
            track_info = {
                "name": item.get("name"),
                "id": item.get("id"),
                "uri": item.get("uri"),
                "artist": artist_name,
                "artist_id": artist_id,
                "album": album_name,
                "album_id": album_id,
                "duration_ms": item.get("duration_ms", 0),
                "explicit": item.get("explicit", False),
                "popularity": item.get("popularity", 0),
            }

            if album_image:
                track_info["album_image"] = album_image

            if album.get("release_date"):
                track_info["album_release_date"] = album["release_date"]

            result = {
                "success": True,
                "is_playing": playback.get("is_playing", False),
                "track": track_info,
                "progress_ms": playback.get("progress_ms", 0),
            }

            # Add device info if available
            device = playback.get("device")
            if device:
                result["device"] = device.get("name")

            return result

        except SpotifyException as error:
            logger.error(f"Spotify API error in get_now_playing: {error}")
            return {
                "success": False,
                "error": f"Spotify API error: {getattr(error, 'msg', str(error))}",
            }
        except Exception as error:
            logger.error(f"Error in get_now_playing: {error}")
            return {"success": False, "error": str(error)}

    def get_artist_context(
        self, artist_id: str | None = None, artist_name: str | None = None
    ) -> dict[str, Any]:
        """
        Get detailed information about an artist.

        Provides rich context including genres, popularity, top tracks,
        and albums. This information is cached to reduce API calls.

        Args:
            artist_id: Spotify artist ID (preferred)
            artist_name: Artist name to search for (used if ID not provided)

        Returns:
            Dictionary with:
                - success: bool
                - artist: dict with name, genres, popularity, followers, etc.
                - top_tracks: list of top track names
                - albums: list of album info (optional)
                - error: str (if failed)
        """
        if not self._available:
            return {
                "success": False,
                "error": "Music context service not available (Spotify not configured)",
            }

        try:
            # If only name provided, search for artist
            if artist_id is None:
                if artist_name is None:
                    return {
                        "success": False,
                        "error": "Either artist_id or artist_name is required",
                    }

                # Search for artist by name
                search_results = self._spotify.search(q=artist_name, type="artist", limit=1)
                artists = search_results.get("artists", {}).get("items", [])

                if not artists:
                    return {"success": False, "error": f"Artist '{artist_name}' not found"}

                artist_id = artists[0]["id"]

            # Check cache
            cache_key = f"artist:{artist_id}"
            cached = self._get_cached(cache_key)
            if cached:
                logger.debug(f"Using cached artist context for {artist_id}")
                return cached

            # Fetch artist info
            artist_data = self._spotify.artist(artist_id)

            artist_info = {
                "name": artist_data.get("name"),
                "id": artist_data.get("id"),
                "uri": artist_data.get("uri"),
                "genres": artist_data.get("genres", []),
                "popularity": artist_data.get("popularity", 0),
                "followers": artist_data.get("followers", {}).get("total", 0),
            }

            # Get artist image
            images = artist_data.get("images", [])
            if images:
                artist_info["image"] = images[0].get("url")

            # Fetch top tracks
            top_tracks_data = self._spotify.artist_top_tracks(artist_id)
            top_tracks = []
            for track in top_tracks_data.get("tracks", [])[:5]:  # Top 5
                top_tracks.append(
                    {"name": track.get("name"), "popularity": track.get("popularity", 0)}
                )

            # Fetch recent albums
            albums_data = self._spotify.artist_albums(artist_id, limit=5)
            albums = []
            for album in albums_data.get("items", []):
                albums.append(
                    {"name": album.get("name"), "release_date": album.get("release_date")}
                )

            result = {
                "success": True,
                "artist": artist_info,
                "top_tracks": top_tracks,
                "albums": albums,
            }

            # Cache the result
            self._set_cached(cache_key, result)

            return result

        except SpotifyException as error:
            logger.error(f"Spotify API error in get_artist_context: {error}")
            return {
                "success": False,
                "error": f"Spotify API error: {getattr(error, 'msg', str(error))}",
            }
        except Exception as error:
            logger.error(f"Error in get_artist_context: {error}")
            return {"success": False, "error": str(error)}

    def get_album_context(
        self, album_id: str | None = None, album_name: str | None = None
    ) -> dict[str, Any]:
        """
        Get detailed information about an album.

        Args:
            album_id: Spotify album ID (preferred)
            album_name: Album name to search for (used if ID not provided)

        Returns:
            Dictionary with:
                - success: bool
                - album: dict with name, artist, release_date, total_tracks, etc.
                - tracks: list of track info
                - error: str (if failed)
        """
        if not self._available:
            return {
                "success": False,
                "error": "Music context service not available (Spotify not configured)",
            }

        try:
            # If only name provided, search for album
            if album_id is None:
                if album_name is None:
                    return {"success": False, "error": "Either album_id or album_name is required"}

                search_results = self._spotify.search(q=album_name, type="album", limit=1)
                albums = search_results.get("albums", {}).get("items", [])

                if not albums:
                    return {"success": False, "error": f"Album '{album_name}' not found"}

                album_id = albums[0]["id"]

            # Check cache
            cache_key = f"album:{album_id}"
            cached = self._get_cached(cache_key)
            if cached:
                logger.debug(f"Using cached album context for {album_id}")
                return cached

            # Fetch album info
            album_data = self._spotify.album(album_id)

            # Extract artist
            artists = album_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown") if artists else "Unknown"

            album_info = {
                "name": album_data.get("name"),
                "id": album_data.get("id"),
                "uri": album_data.get("uri"),
                "artist": artist_name,
                "release_date": album_data.get("release_date"),
                "total_tracks": album_data.get("total_tracks", 0),
                "popularity": album_data.get("popularity", 0),
                "label": album_data.get("label"),
            }

            # Get album art
            images = album_data.get("images", [])
            if images:
                album_info["image"] = images[0].get("url")

            # Get copyright info
            copyrights = album_data.get("copyrights", [])
            if copyrights:
                album_info["copyright"] = copyrights[0].get("text")

            # Fetch tracks
            tracks_data = self._spotify.album_tracks(album_id)
            tracks = []
            for track in tracks_data.get("items", []):
                tracks.append(
                    {
                        "name": track.get("name"),
                        "track_number": track.get("track_number"),
                        "duration_ms": track.get("duration_ms", 0),
                    }
                )

            result = {"success": True, "album": album_info, "tracks": tracks}

            # Cache the result
            self._set_cached(cache_key, result)

            return result

        except SpotifyException as error:
            logger.error(f"Spotify API error in get_album_context: {error}")
            return {
                "success": False,
                "error": f"Spotify API error: {getattr(error, 'msg', str(error))}",
            }
        except Exception as error:
            logger.error(f"Error in get_album_context: {error}")
            return {"success": False, "error": str(error)}

    def get_track_context(self, track_id: str) -> dict[str, Any]:
        """
        Get detailed information about a track including audio features.

        Audio features provide music theory context:
        - tempo (BPM)
        - key (musical key like C, F#)
        - mode (major/minor)
        - energy, danceability, valence (mood indicators)
        - acousticness, instrumentalness (sound characteristics)

        Args:
            track_id: Spotify track ID

        Returns:
            Dictionary with:
                - success: bool
                - track: dict with name, artist, album, duration, popularity
                - audio_features: dict with tempo, key, mode, energy, etc.
                - error: str (if failed)
        """
        if not self._available:
            return {
                "success": False,
                "error": "Music context service not available (Spotify not configured)",
            }

        try:
            # Fetch track info
            track_data = self._spotify.track(track_id)

            # Extract artist
            artists = track_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown") if artists else "Unknown"
            artist_id = artists[0].get("id") if artists else None

            # Extract album
            album = track_data.get("album", {})
            album_name = album.get("name", "Unknown")

            track_info = {
                "name": track_data.get("name"),
                "id": track_data.get("id"),
                "uri": track_data.get("uri"),
                "artist": artist_name,
                "artist_id": artist_id,
                "album": album_name,
                "album_id": album.get("id"),
                "duration_ms": track_data.get("duration_ms", 0),
                "popularity": track_data.get("popularity", 0),
                "explicit": track_data.get("explicit", False),
                "track_number": track_data.get("track_number"),
            }

            if album.get("release_date"):
                track_info["release_date"] = album["release_date"]

            result = {"success": True, "track": track_info}

            # Fetch audio features (music theory context)
            audio_features = self._spotify.audio_features([track_id])
            if audio_features and audio_features[0]:
                features = audio_features[0]
                result["audio_features"] = {
                    "tempo": features.get("tempo"),
                    "key": self.key_to_note(features.get("key", -1)),
                    "mode": self.mode_to_name(features.get("mode", -1)),
                    "time_signature": features.get("time_signature"),
                    "danceability": features.get("danceability"),
                    "energy": features.get("energy"),
                    "valence": features.get("valence"),  # Musical positiveness
                    "acousticness": features.get("acousticness"),
                    "instrumentalness": features.get("instrumentalness"),
                    "speechiness": features.get("speechiness"),
                    "liveness": features.get("liveness"),
                    "loudness": features.get("loudness"),
                }

            return result

        except SpotifyException as error:
            logger.error(f"Spotify API error in get_track_context: {error}")
            return {
                "success": False,
                "error": f"Spotify API error: {getattr(error, 'msg', str(error))}",
            }
        except Exception as error:
            logger.error(f"Error in get_track_context: {error}")
            return {"success": False, "error": str(error)}

    def get_current_track_context(self) -> dict[str, Any]:
        """
        Get comprehensive context about the currently playing track.

        Combines:
        - Now playing info (track, progress, device)
        - Artist context (genres, popularity, top tracks)
        - Audio features (tempo, key, mood indicators)

        This provides the LLM with everything it needs to answer questions
        about the currently playing music.

        Returns:
            Dictionary with:
                - success: bool
                - is_playing: bool
                - track: dict with full track info (if playing)
                - artist: dict with artist context (if playing)
                - audio_features: dict with music theory info (if playing)
                - error: str (if failed)
        """
        if not self._available:
            return {
                "success": False,
                "error": "Music context service not available (Spotify not configured)",
            }

        try:
            # Get currently playing
            now_playing = self.get_now_playing()

            if not now_playing.get("success"):
                return now_playing

            if not now_playing.get("is_playing", False) and not now_playing.get("track"):
                return {"success": True, "is_playing": False}

            result = {
                "success": True,
                "is_playing": now_playing.get("is_playing", False),
                "track": now_playing.get("track"),
                "progress_ms": now_playing.get("progress_ms"),
            }

            if now_playing.get("device"):
                result["device"] = now_playing["device"]

            track_info = now_playing.get("track", {})

            # Get artist context
            artist_id = track_info.get("artist_id")
            if artist_id:
                artist_context = self.get_artist_context(artist_id=artist_id)
                if artist_context.get("success"):
                    result["artist"] = artist_context.get("artist")
                    result["artist_top_tracks"] = artist_context.get("top_tracks", [])

            # Get audio features
            track_id = track_info.get("id")
            if track_id:
                track_context = self.get_track_context(track_id)
                if track_context.get("success") and track_context.get("audio_features"):
                    result["audio_features"] = track_context["audio_features"]

            return result

        except Exception as error:
            logger.error(f"Error in get_current_track_context: {error}")
            return {"success": False, "error": str(error)}


# Singleton instance
_music_context: MusicContext | None = None


def get_music_context() -> MusicContext:
    """
    Get or create the singleton MusicContext instance.

    Returns:
        MusicContext instance
    """
    global _music_context

    if _music_context is None:
        _music_context = MusicContext()

    return _music_context
