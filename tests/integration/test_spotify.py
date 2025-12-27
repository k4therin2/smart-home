"""
Integration Tests for Spotify Integration

Tests real interactions between Spotify tools and Home Assistant,
mocking only the external Spotify API calls.

Test Strategy:
- Test OAuth flow and token management
- Test playback control with real tool functions
- Test device targeting and Spotify Connect
- Test search functionality
- Test error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import os

from tools.spotify import (
    play_spotify,
    control_playback,
    search_spotify,
    get_spotify_devices,
    transfer_playback,
    execute_spotify_tool,
    SPOTIFY_TOOLS
)


@pytest.fixture
def mock_spotify_client():
    """Fixture that mocks the Spotify client."""
    with patch('tools.spotify.get_spotify_client') as mock_get_client:
        mock_client = Mock()
        mock_sp = Mock()
        mock_client.spotify = mock_sp
        mock_get_client.return_value = mock_client
        yield mock_sp


class TestSpotifyOAuthFlow:
    """Test OAuth authentication and token management."""

    def test_spotify_client_initialization_with_valid_credentials(self):
        """Test SpotifyClient initializes with valid credentials."""
        with patch('tools.spotify.SpotifyOAuth') as mock_oauth:
            mock_oauth.return_value = Mock()
            from tools.spotify import SpotifyClient

            client = SpotifyClient(
                client_id="test_id",
                client_secret="test_secret",
                redirect_uri="http://localhost:8888/callback"
            )

            assert client is not None
            mock_oauth.assert_called_once()

    @patch.dict('os.environ', {}, clear=True)
    def test_spotify_client_handles_missing_credentials(self):
        """Test SpotifyClient raises error with missing credentials."""
        from tools.spotify import SpotifyClient

        with pytest.raises(ValueError, match="client_id.*required"):
            SpotifyClient(client_id=None, client_secret="secret", redirect_uri="uri")

    def test_token_refresh_on_expiration(self):
        """Test automatic token refresh when expired."""
        with patch('tools.spotify.SpotifyOAuth') as mock_oauth:
            mock_auth_manager = Mock()
            # Simulate expired token
            mock_auth_manager.get_cached_token.return_value = {
                'access_token': 'old_token',
                'refresh_token': 'refresh_token',
                'expires_at': (datetime.now() - timedelta(hours=1)).timestamp()
            }
            mock_auth_manager.refresh_access_token.return_value = {
                'access_token': 'new_token',
                'refresh_token': 'refresh_token',
                'expires_at': (datetime.now() + timedelta(hours=1)).timestamp()
            }
            mock_oauth.return_value = mock_auth_manager

            from tools.spotify import SpotifyClient
            client = SpotifyClient("id", "secret", "uri")
            token = client.get_valid_token()

            assert token == 'new_token'
            mock_auth_manager.refresh_access_token.assert_called_once()

    def test_cached_token_used_when_valid(self):
        """Test cached token is used when not expired."""
        with patch('tools.spotify.SpotifyOAuth') as mock_oauth:
            mock_auth_manager = Mock()
            # Simulate valid token (is_token_expired returns False)
            mock_auth_manager.get_cached_token.return_value = {
                'access_token': 'valid_token',
                'refresh_token': 'refresh',
                'expires_at': (datetime.now() + timedelta(hours=1)).timestamp()
            }
            mock_auth_manager.is_token_expired.return_value = False
            mock_oauth.return_value = mock_auth_manager

            from tools.spotify import SpotifyClient
            client = SpotifyClient("id", "secret", "uri")
            token = client.get_valid_token()

            assert token == 'valid_token'
            mock_auth_manager.refresh_access_token.assert_not_called()


class TestSpotifyPlaybackControl:
    """Test playback control functionality."""

    def test_play_track_by_name(self, mock_spotify_client):
        """Test playing a track by name on a specific device."""
        # Mock search results
        mock_spotify_client.search.return_value = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:123',
                    'name': 'Hey Jude',
                    'artists': [{'name': 'The Beatles'}]
                }]
            }
        }

        # Mock devices
        mock_spotify_client.devices.return_value = {
            'devices': [{
                'id': 'device_123',
                'name': 'Living Room Echo',
                'type': 'Speaker'
            }]
        }

        mock_spotify_client.start_playback.return_value = None

        result = play_spotify(
            query="Hey Jude by The Beatles",
            device_name="Living Room Echo"
        )

        assert result['success'] is True
        assert 'Hey Jude' in result['track_name']
        assert result['device'] == 'Living Room Echo'
        mock_spotify_client.start_playback.assert_called_once()

    def test_play_playlist(self, mock_spotify_client):
        """Test playing a playlist."""
        mock_spotify_client.search.return_value = {
            'playlists': {
                'items': [{
                    'uri': 'spotify:playlist:abc123',
                    'name': 'Chill Vibes',
                    'owner': {'display_name': 'Spotify'}
                }]
            }
        }

        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'Echo', 'type': 'Speaker'}]
        }

        mock_spotify_client.start_playback.return_value = None

        result = play_spotify(
            query="Chill Vibes",
            content_type="playlist",
            device_name="Echo"
        )

        assert result['success'] is True
        assert 'playlist' in result['content_type']
        mock_spotify_client.start_playback.assert_called_with(
            device_id='dev1',
            context_uri='spotify:playlist:abc123'
        )

    def test_play_album(self, mock_spotify_client):
        """Test playing an album."""

        mock_spotify_client.search.return_value = {
            'albums': {
                'items': [{
                    'uri': 'spotify:album:xyz789',
                    'name': 'Abbey Road',
                    'artists': [{'name': 'The Beatles'}]
                }]
            }
        }

        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'Bedroom', 'type': 'Speaker'}]
        }

        result = play_spotify(
            query="Abbey Road",
            content_type="album",
            device_name="Bedroom"
        )

        assert result['success'] is True
        assert 'album' in result['content_type']

    def test_pause_playback(self, mock_spotify_client):
        """Test pausing playback."""
        mock_spotify_client.pause_playback.return_value = None

        result = control_playback(action="pause")

        assert result['success'] is True
        assert result['action'] == 'pause'
        mock_spotify_client.pause_playback.assert_called_once()

    def test_resume_playback(self, mock_spotify_client):
        """Test resuming playback."""
        mock_spotify_client.start_playback.return_value = None

        result = control_playback(action="resume")

        assert result['success'] is True
        assert result['action'] == 'resume'
        mock_spotify_client.start_playback.assert_called_once()

    def test_skip_to_next_track(self, mock_spotify_client):
        """Test skipping to next track."""
        mock_spotify_client.next_track.return_value = None

        result = control_playback(action="next")

        assert result['success'] is True
        assert result['action'] == 'next'
        mock_spotify_client.next_track.assert_called_once()

    def test_skip_to_previous_track(self, mock_spotify_client):
        """Test skipping to previous track."""
        mock_spotify_client.previous_track.return_value = None

        result = control_playback(action="previous")

        assert result['success'] is True
        assert result['action'] == 'previous'
        mock_spotify_client.previous_track.assert_called_once()

    def test_set_volume(self, mock_spotify_client):
        """Test setting volume level."""
        mock_spotify_client.volume.return_value = None

        result = control_playback(action="volume", volume=75)

        assert result['success'] is True
        assert result['volume'] == 75
        mock_spotify_client.volume.assert_called_with(volume_percent=75)


class TestSpotifyDeviceManagement:
    """Test device discovery and targeting."""

    def test_get_all_devices(self, mock_spotify_client):
        """Test retrieving all available Spotify devices."""

        mock_spotify_client.devices.return_value = {
            'devices': [
                {
                    'id': 'dev1',
                    'name': 'Living Room Echo',
                    'type': 'Speaker',
                    'is_active': True,
                    'volume_percent': 50
                },
                {
                    'id': 'dev2',
                    'name': 'Bedroom Echo',
                    'type': 'Speaker',
                    'is_active': False,
                    'volume_percent': 30
                }
            ]
        }

        result = get_spotify_devices()

        assert result['success'] is True
        assert len(result['devices']) == 2
        assert result['devices'][0]['name'] == 'Living Room Echo'
        assert result['devices'][0]['is_active'] is True

    def test_transfer_playback_to_device(self, mock_spotify_client):
        """Test transferring playback to a specific device."""

        mock_spotify_client.devices.return_value = {
            'devices': [
                {'id': 'dev1', 'name': 'Kitchen Echo', 'type': 'Speaker'},
                {'id': 'dev2', 'name': 'Office Echo', 'type': 'Speaker'}
            ]
        }

        mock_spotify_client.transfer_playback.return_value = None

        result = transfer_playback(device_name="Office Echo")

        assert result['success'] is True
        assert result['device'] == 'Office Echo'
        mock_spotify_client.transfer_playback.assert_called_with(
            device_id='dev2',
            force_play=False
        )

    def test_transfer_playback_with_resume(self, mock_spotify_client):
        """Test transferring playback and resuming automatically."""

        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'Echo', 'type': 'Speaker'}]
        }

        result = transfer_playback(device_name="Echo", force_play=True)

        assert result['success'] is True
        mock_spotify_client.transfer_playback.assert_called_with(
            device_id='dev1',
            force_play=True
        )

    def test_device_not_found_error(self, mock_spotify_client):
        """Test error handling when device is not found."""

        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'Echo', 'type': 'Speaker'}]
        }

        result = transfer_playback(device_name="NonExistent Device")

        assert result['success'] is False
        assert 'not found' in result['error'].lower()


class TestSpotifySearch:
    """Test search functionality."""

    def test_search_tracks(self, mock_spotify_client):
        """Test searching for tracks."""

        mock_spotify_client.search.return_value = {
            'tracks': {
                'items': [
                    {
                        'name': 'Yesterday',
                        'artists': [{'name': 'The Beatles'}],
                        'album': {'name': 'Help!'},
                        'uri': 'spotify:track:123',
                        'duration_ms': 125000
                    },
                    {
                        'name': 'Here Comes The Sun',
                        'artists': [{'name': 'The Beatles'}],
                        'album': {'name': 'Abbey Road'},
                        'uri': 'spotify:track:456',
                        'duration_ms': 185000
                    }
                ]
            }
        }

        result = search_spotify(query="The Beatles", search_type="track", limit=2)

        assert result['success'] is True
        assert result['search_type'] == 'track'
        assert len(result['results']) == 2
        assert result['results'][0]['name'] == 'Yesterday'
        assert 'The Beatles' in result['results'][0]['artist']

    def test_search_artists(self, mock_spotify_client):
        """Test searching for artists."""

        mock_spotify_client.search.return_value = {
            'artists': {
                'items': [
                    {
                        'name': 'Radiohead',
                        'uri': 'spotify:artist:abc',
                        'genres': ['alternative rock', 'art rock'],
                        'followers': {'total': 8000000}
                    }
                ]
            }
        }

        result = search_spotify(query="Radiohead", search_type="artist")

        assert result['success'] is True
        assert result['results'][0]['name'] == 'Radiohead'
        assert 'alternative rock' in result['results'][0]['genres']

    def test_search_playlists(self, mock_spotify_client):
        """Test searching for playlists."""

        mock_spotify_client.search.return_value = {
            'playlists': {
                'items': [
                    {
                        'name': 'Peaceful Piano',
                        'uri': 'spotify:playlist:xyz',
                        'owner': {'display_name': 'Spotify'},
                        'tracks': {'total': 200}
                    }
                ]
            }
        }

        result = search_spotify(query="Peaceful Piano", search_type="playlist")

        assert result['success'] is True
        assert result['results'][0]['name'] == 'Peaceful Piano'
        assert result['results'][0]['track_count'] == 200

    def test_search_albums(self, mock_spotify_client):
        """Test searching for albums."""

        mock_spotify_client.search.return_value = {
            'albums': {
                'items': [
                    {
                        'name': 'Dark Side of the Moon',
                        'artists': [{'name': 'Pink Floyd'}],
                        'uri': 'spotify:album:def',
                        'release_date': '1973-03-01',
                        'total_tracks': 10
                    }
                ]
            }
        }

        result = search_spotify(query="Dark Side of the Moon", search_type="album")

        assert result['success'] is True
        assert result['results'][0]['name'] == 'Dark Side of the Moon'
        assert 'Pink Floyd' in result['results'][0]['artist']

    def test_search_no_results(self, mock_spotify_client):
        """Test search with no results found."""

        mock_spotify_client.search.return_value = {
            'tracks': {'items': []}
        }

        result = search_spotify(query="NonExistentSong12345", search_type="track")

        assert result['success'] is True
        assert len(result['results']) == 0
        assert 'no results' in result['message'].lower()


class TestSpotifyErrorHandling:
    """Test error handling and edge cases."""

    def test_api_error_handling(self, mock_spotify_client):
        """Test handling of Spotify API errors."""
        from spotipy.exceptions import SpotifyException

        mock_spotify_client.search.side_effect = SpotifyException(
            http_status=401,
            code=-1,
            msg="Invalid access token"
        )

        result = search_spotify(query="test", search_type="track")

        assert result['success'] is False
        assert 'error' in result

    def test_no_active_device_error(self, mock_spotify_client):
        """Test error when no devices are available."""

        mock_spotify_client.search.return_value = {
            'tracks': {'items': [{'uri': 'spotify:track:123', 'name': 'Test'}]}
        }
        mock_spotify_client.devices.return_value = {'devices': []}

        result = play_spotify(query="test song", device_name="Echo")

        assert result['success'] is False
        assert 'no' in result['error'].lower() and 'device' in result['error'].lower()

    def test_playback_error_handling(self, mock_spotify_client):
        """Test error handling during playback start."""
        from spotipy.exceptions import SpotifyException


        mock_spotify_client.search.return_value = {
            'tracks': {'items': [{'uri': 'spotify:track:123', 'name': 'Test'}]}
        }
        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'Echo', 'type': 'Speaker'}]
        }
        mock_spotify_client.start_playback.side_effect = SpotifyException(
            http_status=403,
            code=-1,
            msg="Player command failed: Premium required"
        )

        result = play_spotify(query="test", device_name="Echo")

        assert result['success'] is False
        assert 'error' in result

    def test_invalid_volume_range(self):
        """Test validation of volume parameter."""
        result = control_playback(action="volume", volume=150)

        assert result['success'] is False
        assert 'volume' in result['error'].lower()


class TestSpotifyToolIntegration:
    """Test integration with agent tool execution system."""

    def test_tool_definitions_present(self):
        """Test that all required tool definitions exist."""
        tool_names = [tool['name'] for tool in SPOTIFY_TOOLS]

        assert 'play_spotify' in tool_names
        assert 'control_playback' in tool_names
        assert 'search_spotify' in tool_names
        assert 'get_spotify_devices' in tool_names
        assert 'transfer_playback' in tool_names

    def test_tool_schemas_valid(self):
        """Test that tool schemas are properly structured."""
        for tool in SPOTIFY_TOOLS:
            assert 'name' in tool
            assert 'description' in tool
            assert 'input_schema' in tool
            assert 'type' in tool['input_schema']
            assert 'properties' in tool['input_schema']
            assert 'required' in tool['input_schema']

    @patch('tools.spotify.play_spotify')
    def test_execute_spotify_tool_play(self, mock_play):
        """Test execute_spotify_tool delegates to play_spotify."""
        mock_play.return_value = {'success': True}

        result = execute_spotify_tool('play_spotify', {
            'query': 'test song',
            'device_name': 'Echo'
        })

        assert result['success'] is True
        mock_play.assert_called_once()

    @patch('tools.spotify.control_playback')
    def test_execute_spotify_tool_control(self, mock_control):
        """Test execute_spotify_tool delegates to control_playback."""
        mock_control.return_value = {'success': True, 'action': 'pause'}

        result = execute_spotify_tool('control_playback', {'action': 'pause'})

        assert result['success'] is True
        mock_control.assert_called_once()

    def test_execute_spotify_tool_unknown(self):
        """Test execute_spotify_tool handles unknown tools."""
        result = execute_spotify_tool('unknown_tool', {})

        assert result['success'] is False
        assert 'unknown' in result['error'].lower()


class TestSpotifyNaturalLanguageCommands:
    """Test natural language command processing."""

    def test_play_song_with_natural_language(self, mock_spotify_client):
        """Test playing song from natural language query."""

        mock_spotify_client.search.return_value = {
            'tracks': {
                'items': [{
                    'uri': 'spotify:track:123',
                    'name': 'Imagine',
                    'artists': [{'name': 'John Lennon'}]
                }]
            }
        }
        mock_spotify_client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'living room', 'type': 'Speaker'}]
        }

        # Natural language: "play Imagine on living room"
        result = play_spotify(
            query="Imagine",
            device_name="living room"
        )

        assert result['success'] is True
        assert 'Imagine' in result['track_name']

    def test_play_playlist_with_fuzzy_device_match(self, mock_spotify_client):
        """Test device matching with fuzzy/partial names."""

        mock_spotify_client.search.return_value = {
            'playlists': {
                'items': [{
                    'uri': 'spotify:playlist:abc',
                    'name': 'My Playlist',
                    'owner': {'display_name': 'User'}
                }]
            }
        }

        mock_spotify_client.devices.return_value = {
            'devices': [
                {'id': 'dev1', 'name': 'Living Room Echo Dot', 'type': 'Speaker'}
            ]
        }

        # User says "living room" but device is "Living Room Echo Dot"
        result = play_spotify(
            query="My Playlist",
            content_type="playlist",
            device_name="living room"
        )

        assert result['success'] is True
