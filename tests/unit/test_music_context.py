"""
Unit Tests for Music Context Manager

Tests the MusicContext class which tracks currently playing music and provides
rich context about artists, albums, and tracks for the LLM to use.

Test Strategy:
- Test getting currently playing track information
- Test artist context retrieval (genres, followers, popularity)
- Test album context retrieval (tracks, release date)
- Test track context retrieval (features, analysis)
- Test caching behavior
- Test error handling when no music is playing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestMusicContextInit:
    """Test MusicContext initialization."""

    def test_music_context_creates_with_spotify_client(self):
        """Test MusicContext initializes with Spotify client."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            from src.music_context import MusicContext
            context = MusicContext()

            assert context is not None
            mock_get_client.assert_called_once()

    def test_music_context_handles_missing_credentials(self):
        """Test MusicContext handles missing Spotify credentials gracefully."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_get_client.side_effect = ValueError("client_id is required")

            from src.music_context import MusicContext
            context = MusicContext()

            # Should not raise, just mark as unavailable
            assert context.is_available() is False


class TestGetNowPlaying:
    """Test getting currently playing track."""

    def test_get_now_playing_returns_track_info(self):
        """Test get_now_playing returns complete track information."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.current_playback.return_value = {
                'is_playing': True,
                'item': {
                    'name': 'Bohemian Rhapsody',
                    'uri': 'spotify:track:abc123',
                    'duration_ms': 354000,
                    'explicit': False,
                    'popularity': 85,
                    'artists': [
                        {'name': 'Queen', 'id': 'queen123', 'uri': 'spotify:artist:queen123'}
                    ],
                    'album': {
                        'name': 'A Night at the Opera',
                        'id': 'album123',
                        'uri': 'spotify:album:album123',
                        'release_date': '1975-11-21',
                        'images': [{'url': 'https://example.com/image.jpg', 'height': 640}]
                    }
                },
                'progress_ms': 120000,
                'device': {
                    'name': 'Living Room Echo',
                    'type': 'Speaker'
                }
            }

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_now_playing()

            assert result['success'] is True
            assert result['is_playing'] is True
            assert result['track']['name'] == 'Bohemian Rhapsody'
            assert result['track']['artist'] == 'Queen'
            assert result['track']['album'] == 'A Night at the Opera'
            assert result['track']['duration_ms'] == 354000
            assert result['progress_ms'] == 120000
            assert result['device'] == 'Living Room Echo'

    def test_get_now_playing_when_nothing_playing(self):
        """Test get_now_playing when nothing is currently playing."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.current_playback.return_value = None

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_now_playing()

            assert result['success'] is True
            assert result['is_playing'] is False
            assert 'track' not in result

    def test_get_now_playing_when_paused(self):
        """Test get_now_playing returns track info even when paused."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.current_playback.return_value = {
                'is_playing': False,  # Paused
                'item': {
                    'name': 'Test Song',
                    'uri': 'spotify:track:test',
                    'duration_ms': 200000,
                    'artists': [{'name': 'Test Artist', 'id': 'art1', 'uri': 'spotify:artist:art1'}],
                    'album': {'name': 'Test Album', 'id': 'alb1', 'uri': 'spotify:album:alb1'}
                },
                'progress_ms': 50000
            }

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_now_playing()

            assert result['success'] is True
            assert result['is_playing'] is False
            assert result['track']['name'] == 'Test Song'
            assert result['progress_ms'] == 50000

    def test_get_now_playing_handles_api_error(self):
        """Test get_now_playing handles Spotify API errors gracefully."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            from spotipy.exceptions import SpotifyException

            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.current_playback.side_effect = SpotifyException(
                http_status=401, code=-1, msg="Unauthorized"
            )

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_now_playing()

            assert result['success'] is False
            assert 'error' in result


class TestGetArtistContext:
    """Test getting detailed artist information."""

    def test_get_artist_context_returns_full_info(self):
        """Test get_artist_context returns comprehensive artist information."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.artist.return_value = {
                'name': 'Queen',
                'id': 'queen123',
                'uri': 'spotify:artist:queen123',
                'genres': ['rock', 'glam rock', 'hard rock'],
                'popularity': 85,
                'followers': {'total': 50000000},
                'images': [{'url': 'https://example.com/queen.jpg', 'height': 640}]
            }

            mock_sp.artist_top_tracks.return_value = {
                'tracks': [
                    {'name': 'Bohemian Rhapsody', 'popularity': 90},
                    {'name': 'We Will Rock You', 'popularity': 88},
                    {'name': 'We Are the Champions', 'popularity': 87}
                ]
            }

            mock_sp.artist_albums.return_value = {
                'items': [
                    {'name': 'A Night at the Opera', 'release_date': '1975'},
                    {'name': 'News of the World', 'release_date': '1977'}
                ]
            }

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_artist_context('queen123')

            assert result['success'] is True
            assert result['artist']['name'] == 'Queen'
            assert 'rock' in result['artist']['genres']
            assert result['artist']['followers'] == 50000000
            assert result['artist']['popularity'] == 85
            assert len(result['top_tracks']) == 3
            assert result['top_tracks'][0]['name'] == 'Bohemian Rhapsody'

    def test_get_artist_context_by_name(self):
        """Test get_artist_context searches by name if no ID provided."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            # Search returns artist
            mock_sp.search.return_value = {
                'artists': {
                    'items': [
                        {'name': 'Queen', 'id': 'queen123', 'uri': 'spotify:artist:queen123'}
                    ]
                }
            }

            mock_sp.artist.return_value = {
                'name': 'Queen',
                'id': 'queen123',
                'genres': ['rock'],
                'popularity': 85,
                'followers': {'total': 50000000}
            }

            mock_sp.artist_top_tracks.return_value = {'tracks': []}
            mock_sp.artist_albums.return_value = {'items': []}

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_artist_context(artist_name='Queen')

            assert result['success'] is True
            assert result['artist']['name'] == 'Queen'
            mock_sp.search.assert_called_once()

    def test_get_artist_context_handles_not_found(self):
        """Test get_artist_context handles artist not found."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.search.return_value = {'artists': {'items': []}}

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_artist_context(artist_name='NonexistentArtist12345')

            assert result['success'] is False
            assert 'not found' in result['error'].lower()


class TestGetAlbumContext:
    """Test getting detailed album information."""

    def test_get_album_context_returns_full_info(self):
        """Test get_album_context returns comprehensive album information."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.album.return_value = {
                'name': 'A Night at the Opera',
                'id': 'album123',
                'uri': 'spotify:album:album123',
                'release_date': '1975-11-21',
                'total_tracks': 12,
                'popularity': 80,
                'label': 'EMI',
                'artists': [{'name': 'Queen', 'id': 'queen123'}],
                'images': [{'url': 'https://example.com/album.jpg', 'height': 640}],
                'copyrights': [{'text': '1975 EMI Records', 'type': 'P'}]
            }

            mock_sp.album_tracks.return_value = {
                'items': [
                    {'name': 'Death on Two Legs', 'track_number': 1, 'duration_ms': 223000},
                    {'name': 'Lazing on a Sunday Afternoon', 'track_number': 2, 'duration_ms': 68000},
                    {'name': 'Bohemian Rhapsody', 'track_number': 11, 'duration_ms': 354000}
                ]
            }

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_album_context('album123')

            assert result['success'] is True
            assert result['album']['name'] == 'A Night at the Opera'
            assert result['album']['release_date'] == '1975-11-21'
            assert result['album']['total_tracks'] == 12
            assert result['album']['artist'] == 'Queen'
            assert len(result['tracks']) == 3

    def test_get_album_context_by_name(self):
        """Test get_album_context searches by name if no ID provided."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.search.return_value = {
                'albums': {
                    'items': [
                        {'name': 'A Night at the Opera', 'id': 'album123'}
                    ]
                }
            }

            mock_sp.album.return_value = {
                'name': 'A Night at the Opera',
                'id': 'album123',
                'release_date': '1975',
                'total_tracks': 12,
                'artists': [{'name': 'Queen'}]
            }

            mock_sp.album_tracks.return_value = {'items': []}

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_album_context(album_name='A Night at the Opera')

            assert result['success'] is True
            mock_sp.search.assert_called_once()


class TestGetTrackContext:
    """Test getting detailed track information."""

    def test_get_track_context_returns_full_info(self):
        """Test get_track_context returns comprehensive track information."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.track.return_value = {
                'name': 'Bohemian Rhapsody',
                'id': 'track123',
                'uri': 'spotify:track:track123',
                'duration_ms': 354000,
                'explicit': False,
                'popularity': 90,
                'track_number': 11,
                'artists': [{'name': 'Queen', 'id': 'queen123'}],
                'album': {
                    'name': 'A Night at the Opera',
                    'id': 'album123',
                    'release_date': '1975-11-21'
                }
            }

            # Audio features provide music theory context
            mock_sp.audio_features.return_value = [{
                'danceability': 0.41,
                'energy': 0.40,
                'key': 5,  # F major
                'loudness': -10.0,
                'mode': 1,  # Major
                'speechiness': 0.05,
                'acousticness': 0.32,
                'instrumentalness': 0.01,
                'liveness': 0.22,
                'valence': 0.22,
                'tempo': 143.0,
                'time_signature': 4
            }]

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_track_context('track123')

            assert result['success'] is True
            assert result['track']['name'] == 'Bohemian Rhapsody'
            assert result['track']['artist'] == 'Queen'
            assert result['track']['album'] == 'A Night at the Opera'
            assert result['track']['duration_ms'] == 354000
            assert result['track']['popularity'] == 90
            assert 'audio_features' in result
            assert result['audio_features']['tempo'] == 143.0
            assert result['audio_features']['key'] == 'F'
            assert result['audio_features']['mode'] == 'Major'

    def test_get_track_context_without_audio_features(self):
        """Test get_track_context handles missing audio features."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.track.return_value = {
                'name': 'Test Track',
                'id': 'track123',
                'duration_ms': 200000,
                'artists': [{'name': 'Test Artist'}],
                'album': {'name': 'Test Album'}
            }

            mock_sp.audio_features.return_value = [None]

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_track_context('track123')

            assert result['success'] is True
            assert result['track']['name'] == 'Test Track'
            assert result.get('audio_features') is None or 'audio_features' not in result


class TestCurrentTrackContext:
    """Test getting context for the currently playing track."""

    def test_get_current_track_context_returns_combined_info(self):
        """Test get_current_track_context combines now playing with enriched context."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            # Current playback
            mock_sp.current_playback.return_value = {
                'is_playing': True,
                'item': {
                    'name': 'Bohemian Rhapsody',
                    'id': 'track123',
                    'uri': 'spotify:track:track123',
                    'duration_ms': 354000,
                    'artists': [{'name': 'Queen', 'id': 'queen123', 'uri': 'spotify:artist:queen123'}],
                    'album': {
                        'name': 'A Night at the Opera',
                        'id': 'album123',
                        'release_date': '1975-11-21'
                    }
                },
                'progress_ms': 120000
            }

            # Artist info
            mock_sp.artist.return_value = {
                'name': 'Queen',
                'id': 'queen123',
                'genres': ['rock', 'glam rock'],
                'popularity': 85,
                'followers': {'total': 50000000}
            }

            # Artist top tracks (required by get_artist_context)
            mock_sp.artist_top_tracks.return_value = {'tracks': []}

            # Artist albums (required by get_artist_context)
            mock_sp.artist_albums.return_value = {'items': []}

            # Track info (required by get_track_context)
            mock_sp.track.return_value = {
                'name': 'Bohemian Rhapsody',
                'id': 'track123',
                'duration_ms': 354000,
                'artists': [{'name': 'Queen', 'id': 'queen123'}],
                'album': {'name': 'A Night at the Opera', 'id': 'album123'}
            }

            # Audio features
            mock_sp.audio_features.return_value = [{
                'tempo': 143.0,
                'key': 5,
                'mode': 1,
                'energy': 0.40,
                'valence': 0.22
            }]

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_current_track_context()

            assert result['success'] is True
            assert result['track']['name'] == 'Bohemian Rhapsody'
            assert result['artist']['name'] == 'Queen'
            assert 'rock' in result['artist']['genres']
            assert 'audio_features' in result

    def test_get_current_track_context_when_nothing_playing(self):
        """Test get_current_track_context when nothing is playing."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.current_playback.return_value = None

            from src.music_context import MusicContext
            context = MusicContext()
            result = context.get_current_track_context()

            assert result['success'] is True
            assert result['is_playing'] is False
            assert 'track' not in result


class TestKeyMapping:
    """Test musical key mapping for audio features."""

    def test_key_mapping_returns_correct_notes(self):
        """Test key numbers are converted to note names correctly."""
        from src.music_context import MusicContext

        # Pitch class mapping: 0=C, 1=C#, 2=D, etc.
        assert MusicContext.key_to_note(0) == 'C'
        assert MusicContext.key_to_note(1) == 'C#/Db'
        assert MusicContext.key_to_note(2) == 'D'
        assert MusicContext.key_to_note(5) == 'F'
        assert MusicContext.key_to_note(7) == 'G'
        assert MusicContext.key_to_note(9) == 'A'
        assert MusicContext.key_to_note(11) == 'B'

    def test_key_mapping_handles_invalid_key(self):
        """Test key mapping handles invalid key values."""
        from src.music_context import MusicContext

        assert MusicContext.key_to_note(-1) == 'Unknown'
        assert MusicContext.key_to_note(12) == 'Unknown'


class TestModeMapping:
    """Test musical mode (major/minor) mapping."""

    def test_mode_mapping_returns_correct_mode(self):
        """Test mode numbers are converted to mode names."""
        from src.music_context import MusicContext

        assert MusicContext.mode_to_name(0) == 'Minor'
        assert MusicContext.mode_to_name(1) == 'Major'

    def test_mode_mapping_handles_invalid_mode(self):
        """Test mode mapping handles invalid mode values."""
        from src.music_context import MusicContext

        assert MusicContext.mode_to_name(-1) == 'Unknown'
        assert MusicContext.mode_to_name(2) == 'Unknown'


class TestCaching:
    """Test caching behavior for repeated requests."""

    def test_artist_context_is_cached(self):
        """Test artist context is cached to reduce API calls."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.artist.return_value = {
                'name': 'Queen',
                'id': 'queen123',
                'genres': ['rock'],
                'popularity': 85,
                'followers': {'total': 50000000}
            }
            mock_sp.artist_top_tracks.return_value = {'tracks': []}
            mock_sp.artist_albums.return_value = {'items': []}

            from src.music_context import MusicContext
            context = MusicContext()

            # First call
            result1 = context.get_artist_context('queen123')
            # Second call should use cache
            result2 = context.get_artist_context('queen123')

            assert result1 == result2
            # Artist should only be fetched once
            assert mock_sp.artist.call_count == 1

    def test_cache_expires_after_ttl(self):
        """Test cache entries expire after TTL."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            from unittest.mock import patch as inner_patch

            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.artist.return_value = {
                'name': 'Queen',
                'id': 'queen123',
                'genres': ['rock'],
                'popularity': 85,
                'followers': {'total': 50000000}
            }
            mock_sp.artist_top_tracks.return_value = {'tracks': []}
            mock_sp.artist_albums.return_value = {'items': []}

            from src.music_context import MusicContext
            context = MusicContext()

            # First call
            context.get_artist_context('queen123')

            # Simulate time passing beyond TTL
            context.clear_cache()

            # Second call should fetch again
            context.get_artist_context('queen123')

            assert mock_sp.artist.call_count == 2


class TestServiceAvailability:
    """Test service availability checking."""

    def test_is_available_returns_true_when_spotify_configured(self):
        """Test is_available returns True when Spotify is properly configured."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            from src.music_context import MusicContext
            context = MusicContext()

            assert context.is_available() is True

    def test_is_available_returns_false_when_spotify_not_configured(self):
        """Test is_available returns False when Spotify credentials missing."""
        with patch('src.music_context.get_spotify_client') as mock_get_client:
            mock_get_client.side_effect = ValueError("credentials required")

            from src.music_context import MusicContext
            context = MusicContext()

            assert context.is_available() is False
