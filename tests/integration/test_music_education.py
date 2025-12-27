"""
Integration Tests for Music Education & Context (WP-5.4)

Tests the end-to-end flow of music context retrieval and the new
agent tools for answering questions about currently playing music.

Test Strategy:
- Test get_now_playing_context tool integration
- Test get_artist_info tool with various inputs
- Test get_album_info tool with various inputs
- Test tool execution through execute_spotify_tool
- Test natural language command scenarios
- Test error handling and edge cases
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestNowPlayingContextTool:
    """Test the get_now_playing_context tool."""

    def test_get_now_playing_context_returns_full_context(self):
        """Test that get_now_playing_context returns comprehensive music context."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": True,
                "track": {
                    "name": "Bohemian Rhapsody",
                    "artist": "Queen",
                    "album": "A Night at the Opera"
                },
                "artist": {
                    "name": "Queen",
                    "genres": ["rock", "glam rock"],
                    "popularity": 85
                },
                "audio_features": {
                    "tempo": 143.0,
                    "key": "F",
                    "mode": "Major"
                }
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            assert result["success"] is True
            assert result["is_playing"] is True
            assert result["track"]["name"] == "Bohemian Rhapsody"
            assert result["artist"]["genres"] == ["rock", "glam rock"]
            assert result["audio_features"]["tempo"] == 143.0

    def test_get_now_playing_context_when_nothing_playing(self):
        """Test get_now_playing_context handles no active playback."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": False
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            assert result["success"] is True
            assert result["is_playing"] is False

    def test_get_now_playing_context_handles_spotify_unavailable(self):
        """Test graceful handling when Spotify is not configured."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": False,
                "error": "Music context service not available (Spotify not configured)"
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            assert result["success"] is False
            assert "not available" in result["error"]


class TestGetArtistInfoTool:
    """Test the get_artist_info tool."""

    def test_get_artist_info_by_name(self):
        """Test getting artist info by name."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_artist_context.return_value = {
                "success": True,
                "artist": {
                    "name": "Queen",
                    "genres": ["rock", "glam rock", "hard rock"],
                    "popularity": 85,
                    "followers": 50000000
                },
                "top_tracks": [
                    {"name": "Bohemian Rhapsody", "popularity": 90},
                    {"name": "We Will Rock You", "popularity": 88}
                ],
                "albums": [
                    {"name": "A Night at the Opera", "release_date": "1975"}
                ]
            }

            from tools.spotify import get_artist_info
            result = get_artist_info(artist_name="Queen")

            assert result["success"] is True
            assert result["artist"]["name"] == "Queen"
            assert "rock" in result["artist"]["genres"]
            assert len(result["top_tracks"]) == 2
            mock_context.get_artist_context.assert_called_with(
                artist_id=None,
                artist_name="Queen"
            )

    def test_get_artist_info_by_id(self):
        """Test getting artist info by Spotify ID."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_artist_context.return_value = {
                "success": True,
                "artist": {"name": "Radiohead", "genres": ["art rock"]}
            }

            from tools.spotify import get_artist_info
            result = get_artist_info(artist_id="radio123")

            assert result["success"] is True
            mock_context.get_artist_context.assert_called_with(
                artist_id="radio123",
                artist_name=None
            )

    def test_get_artist_info_requires_name_or_id(self):
        """Test error when neither name nor ID provided."""
        from tools.spotify import get_artist_info
        result = get_artist_info()

        assert result["success"] is False
        assert "required" in result["error"]

    def test_get_artist_info_handles_not_found(self):
        """Test handling of artist not found."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_artist_context.return_value = {
                "success": False,
                "error": "Artist 'NotARealArtist' not found"
            }

            from tools.spotify import get_artist_info
            result = get_artist_info(artist_name="NotARealArtist")

            assert result["success"] is False
            assert "not found" in result["error"]


class TestGetAlbumInfoTool:
    """Test the get_album_info tool."""

    def test_get_album_info_by_name(self):
        """Test getting album info by name."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_album_context.return_value = {
                "success": True,
                "album": {
                    "name": "Abbey Road",
                    "artist": "The Beatles",
                    "release_date": "1969-09-26",
                    "total_tracks": 17
                },
                "tracks": [
                    {"name": "Come Together", "track_number": 1},
                    {"name": "Something", "track_number": 2}
                ]
            }

            from tools.spotify import get_album_info
            result = get_album_info(album_name="Abbey Road")

            assert result["success"] is True
            assert result["album"]["name"] == "Abbey Road"
            assert result["album"]["artist"] == "The Beatles"
            assert len(result["tracks"]) == 2

    def test_get_album_info_by_id(self):
        """Test getting album info by Spotify ID."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_album_context.return_value = {
                "success": True,
                "album": {"name": "Thriller", "artist": "Michael Jackson"}
            }

            from tools.spotify import get_album_info
            result = get_album_info(album_id="album123")

            assert result["success"] is True
            mock_context.get_album_context.assert_called_with(
                album_id="album123",
                album_name=None
            )

    def test_get_album_info_requires_name_or_id(self):
        """Test error when neither name nor ID provided."""
        from tools.spotify import get_album_info
        result = get_album_info()

        assert result["success"] is False
        assert "required" in result["error"]


class TestExecuteSpotifyToolIntegration:
    """Test music context tools via execute_spotify_tool."""

    def test_execute_get_now_playing_context(self):
        """Test executing get_now_playing_context through tool router."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": True,
                "track": {"name": "Test Song"}
            }

            from tools.spotify import execute_spotify_tool
            result = execute_spotify_tool("get_now_playing_context", {})

            assert result["success"] is True
            assert result["track"]["name"] == "Test Song"

    def test_execute_get_artist_info(self):
        """Test executing get_artist_info through tool router."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_artist_context.return_value = {
                "success": True,
                "artist": {"name": "Test Artist"}
            }

            from tools.spotify import execute_spotify_tool
            result = execute_spotify_tool("get_artist_info", {
                "artist_name": "Test Artist"
            })

            assert result["success"] is True
            assert result["artist"]["name"] == "Test Artist"

    def test_execute_get_album_info(self):
        """Test executing get_album_info through tool router."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_album_context.return_value = {
                "success": True,
                "album": {"name": "Test Album"}
            }

            from tools.spotify import execute_spotify_tool
            result = execute_spotify_tool("get_album_info", {
                "album_name": "Test Album"
            })

            assert result["success"] is True
            assert result["album"]["name"] == "Test Album"


class TestMusicEducationToolDefinitions:
    """Test that new tool definitions are properly configured."""

    def test_music_education_tools_in_spotify_tools(self):
        """Test that music education tools are in SPOTIFY_TOOLS list."""
        from tools.spotify import SPOTIFY_TOOLS

        tool_names = [tool["name"] for tool in SPOTIFY_TOOLS]

        assert "get_now_playing_context" in tool_names
        assert "get_artist_info" in tool_names
        assert "get_album_info" in tool_names

    def test_get_now_playing_context_tool_schema(self):
        """Test get_now_playing_context has valid schema."""
        from tools.spotify import SPOTIFY_TOOLS

        tool = next(t for t in SPOTIFY_TOOLS if t["name"] == "get_now_playing_context")

        assert "description" in tool
        assert "input_schema" in tool
        assert "What's playing" in tool["description"]
        assert tool["input_schema"]["required"] == []

    def test_get_artist_info_tool_schema(self):
        """Test get_artist_info has valid schema."""
        from tools.spotify import SPOTIFY_TOOLS

        tool = next(t for t in SPOTIFY_TOOLS if t["name"] == "get_artist_info")

        assert "description" in tool
        assert "input_schema" in tool
        assert "artist_name" in tool["input_schema"]["properties"]
        assert "artist_id" in tool["input_schema"]["properties"]
        assert "Tell me about" in tool["description"]

    def test_get_album_info_tool_schema(self):
        """Test get_album_info has valid schema."""
        from tools.spotify import SPOTIFY_TOOLS

        tool = next(t for t in SPOTIFY_TOOLS if t["name"] == "get_album_info")

        assert "description" in tool
        assert "input_schema" in tool
        assert "album_name" in tool["input_schema"]["properties"]
        assert "album_id" in tool["input_schema"]["properties"]


class TestNaturalLanguageScenarios:
    """Test natural language command scenarios for music education."""

    def test_whats_playing_scenario(self):
        """Test 'What's playing?' scenario returns useful context."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": True,
                "track": {
                    "name": "Stairway to Heaven",
                    "artist": "Led Zeppelin",
                    "album": "Led Zeppelin IV",
                    "duration_ms": 482000
                },
                "artist": {
                    "name": "Led Zeppelin",
                    "genres": ["hard rock", "blues rock", "classic rock"],
                    "popularity": 82
                },
                "audio_features": {
                    "tempo": 82.0,
                    "key": "A",
                    "mode": "Minor"
                }
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            # Verify context has all info needed to answer follow-up questions
            assert result["success"] is True
            assert result["track"]["name"] == "Stairway to Heaven"
            assert result["track"]["artist"] == "Led Zeppelin"
            assert "hard rock" in result["artist"]["genres"]
            assert result["audio_features"]["key"] == "A"
            assert result["audio_features"]["mode"] == "Minor"

    def test_tell_me_about_artist_scenario(self):
        """Test 'Tell me about this artist' scenario."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_artist_context.return_value = {
                "success": True,
                "artist": {
                    "name": "Pink Floyd",
                    "genres": ["progressive rock", "psychedelic rock", "art rock"],
                    "popularity": 81,
                    "followers": 25000000
                },
                "top_tracks": [
                    {"name": "Comfortably Numb", "popularity": 83},
                    {"name": "Wish You Were Here", "popularity": 82},
                    {"name": "Another Brick in the Wall", "popularity": 80}
                ],
                "albums": [
                    {"name": "The Dark Side of the Moon", "release_date": "1973"},
                    {"name": "The Wall", "release_date": "1979"}
                ]
            }

            from tools.spotify import get_artist_info
            result = get_artist_info(artist_name="Pink Floyd")

            # LLM can use this context + its knowledge to provide rich answer
            assert result["success"] is True
            assert result["artist"]["name"] == "Pink Floyd"
            assert "progressive rock" in result["artist"]["genres"]
            assert result["artist"]["followers"] == 25000000
            assert len(result["top_tracks"]) >= 3

    def test_what_genre_is_this_scenario(self):
        """Test 'What genre is this?' scenario uses now playing context."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": True,
                "track": {"name": "Superstition", "artist": "Stevie Wonder"},
                "artist": {
                    "name": "Stevie Wonder",
                    "genres": ["soul", "motown", "funk", "r&b"]
                }
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            # Genres are available in the context
            assert result["success"] is True
            assert "soul" in result["artist"]["genres"]
            assert "funk" in result["artist"]["genres"]

    def test_music_theory_info_scenario(self):
        """Test that audio features provide music theory context."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_get_context.return_value = mock_context

            mock_context.get_current_track_context.return_value = {
                "success": True,
                "is_playing": True,
                "track": {"name": "Take Five", "artist": "Dave Brubeck"},
                "artist": {"name": "Dave Brubeck", "genres": ["jazz", "cool jazz"]},
                "audio_features": {
                    "tempo": 176.0,
                    "key": "E",
                    "mode": "Minor",
                    "time_signature": 5,  # 5/4 time signature
                    "danceability": 0.55,
                    "energy": 0.32
                }
            }

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            # LLM can explain the unusual time signature
            assert result["audio_features"]["time_signature"] == 5
            assert result["audio_features"]["key"] == "E"
            assert result["audio_features"]["mode"] == "Minor"


class TestErrorHandling:
    """Test error handling in music education tools."""

    def test_handles_api_exception(self):
        """Test graceful handling of Spotify API errors."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_get_context.side_effect = Exception("API connection failed")

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            assert result["success"] is False
            assert "error" in result

    def test_handles_music_context_unavailable(self):
        """Test handling when MusicContext initialization fails."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_context.get_current_track_context.return_value = {
                "success": False,
                "error": "Music context service not available"
            }
            mock_get_context.return_value = mock_context

            from tools.spotify import get_now_playing_context
            result = get_now_playing_context()

            assert result["success"] is False

    def test_artist_search_returns_error_message(self):
        """Test that artist search errors provide clear feedback."""
        with patch('src.music_context.get_music_context') as mock_get_context:
            mock_context = Mock()
            mock_context.get_artist_context.return_value = {
                "success": False,
                "error": "Artist 'asdfghjkl' not found"
            }
            mock_get_context.return_value = mock_context

            from tools.spotify import get_artist_info
            result = get_artist_info(artist_name="asdfghjkl")

            assert result["success"] is False
            assert "not found" in result["error"]
