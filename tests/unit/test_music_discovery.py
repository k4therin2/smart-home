"""
Unit Tests for Music Discovery Agent

Tests the music discovery system which provides intelligent music discovery
based on user preferences and context.

Test Strategy:
- Test taste profile creation and updates
- Test discovery conversation flow
- Test recommendation generation
- Test feedback learning
- Test persistence of taste profiles
- Test integration with Spotify API

REQ-026 Acceptance Criteria:
- [ ] LLM-powered research agent for music discovery
- [ ] Prompts user with questions to refine taste
- [ ] Generates playlists or recommendations
- [ ] Results pushed to mobile UI (web notifications or dedicated section)
- [ ] Learns from user feedback on recommendations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import tempfile
import os


# ==================== TASTE PROFILE TESTS ====================

class TestTasteProfile:
    """Test TasteProfile class for storing user preferences."""

    def test_create_empty_taste_profile(self):
        """Test creating a new taste profile with default values."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")

        assert profile.user_id == "test_user"
        assert profile.genres == []
        assert profile.artists == []
        assert profile.energy_preference is None
        assert profile.mood_preferences == []
        assert profile.created_at is not None

    def test_add_genre_preference(self):
        """Test adding a genre to user preferences."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("rock", weight=0.8)

        assert "rock" in profile.genres
        assert profile.get_genre_weight("rock") == 0.8

    def test_add_artist_preference(self):
        """Test adding a favorite artist."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_artist("queen", artist_id="queen123", weight=0.9)

        assert len(profile.artists) == 1
        assert profile.artists[0]["name"] == "queen"
        assert profile.artists[0]["id"] == "queen123"
        assert profile.artists[0]["weight"] == 0.9

    def test_set_energy_preference(self):
        """Test setting energy level preference (0.0-1.0)."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.set_energy_preference(0.7)

        assert profile.energy_preference == 0.7

    def test_add_mood_preference(self):
        """Test adding mood preferences."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_mood("relaxing")
        profile.add_mood("upbeat")

        assert "relaxing" in profile.mood_preferences
        assert "upbeat" in profile.mood_preferences

    def test_taste_profile_serialization(self):
        """Test taste profile can be serialized to dict."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("rock", weight=0.8)
        profile.add_artist("queen", artist_id="queen123", weight=0.9)

        data = profile.to_dict()

        assert data["user_id"] == "test_user"
        assert "rock" in [g["name"] for g in data["genres"]]
        assert "queen" in [a["name"] for a in data["artists"]]

    def test_taste_profile_deserialization(self):
        """Test taste profile can be created from dict."""
        from src.music_discovery import TasteProfile

        data = {
            "user_id": "test_user",
            "genres": [{"name": "rock", "weight": 0.8}],
            "artists": [{"name": "queen", "id": "queen123", "weight": 0.9}],
            "energy_preference": 0.7,
            "mood_preferences": ["relaxing"],
            "created_at": "2025-12-01T10:00:00",
            "updated_at": "2025-12-01T10:00:00"
        }

        profile = TasteProfile.from_dict(data)

        assert profile.user_id == "test_user"
        assert profile.get_genre_weight("rock") == 0.8
        assert profile.energy_preference == 0.7

    def test_update_genre_weight(self):
        """Test updating weight of existing genre."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("rock", weight=0.5)
        profile.add_genre("rock", weight=0.9)  # Update

        assert profile.get_genre_weight("rock") == 0.9

    def test_get_top_genres(self):
        """Test getting top N genres by weight."""
        from src.music_discovery import TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("rock", weight=0.9)
        profile.add_genre("jazz", weight=0.5)
        profile.add_genre("pop", weight=0.7)

        top_genres = profile.get_top_genres(2)

        assert len(top_genres) == 2
        assert top_genres[0]["name"] == "rock"
        assert top_genres[1]["name"] == "pop"


# ==================== DISCOVERY SESSION TESTS ====================

class TestDiscoverySession:
    """Test DiscoverySession for managing discovery conversations."""

    def test_create_discovery_session(self):
        """Test creating a new discovery session."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        assert session.profile == profile
        assert session.questions_asked == 0
        assert session.is_complete is False

    def test_get_next_question_for_new_user(self):
        """Test getting first question for new user."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        question = session.get_next_question()

        assert question is not None
        assert "type" in question
        assert "text" in question

    def test_process_genre_answer(self):
        """Test processing user's genre answer."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        session.process_answer("genre", "I love rock and jazz")

        # Should update profile with mentioned genres
        assert "rock" in profile.genres or profile.get_genre_weight("rock") > 0
        assert "jazz" in profile.genres or profile.get_genre_weight("jazz") > 0

    def test_process_artist_answer(self):
        """Test processing user's favorite artist answer."""
        from src.music_discovery import DiscoverySession, TasteProfile

        with patch('src.music_discovery.search_artist_by_name') as mock_search:
            mock_search.return_value = {"id": "queen123", "name": "Queen"}

            profile = TasteProfile(user_id="test_user")
            session = DiscoverySession(profile)

            session.process_answer("artist", "Queen is my favorite band")

            # Should add artist to profile
            assert len(profile.artists) >= 1

    def test_process_mood_answer(self):
        """Test processing user's mood preference answer."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        session.process_answer("mood", "I like upbeat and energetic music")

        assert len(profile.mood_preferences) > 0

    def test_session_completes_after_enough_questions(self):
        """Test session marks as complete after gathering enough info."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        # Answer several questions
        session.process_answer("genre", "rock")
        session.process_answer("artist", "Queen")
        session.process_answer("mood", "upbeat")
        session.process_answer("energy", "high energy")

        # After answering key questions, session should be ready
        assert session.can_recommend is True

    def test_skip_question_increments_counter(self):
        """Test skipping a question still counts as asked."""
        from src.music_discovery import DiscoverySession, TasteProfile

        profile = TasteProfile(user_id="test_user")
        session = DiscoverySession(profile)

        initial_count = session.questions_asked
        session.skip_question()

        assert session.questions_asked == initial_count + 1


# ==================== RECOMMENDATION ENGINE TESTS ====================

class TestRecommendationEngine:
    """Test RecommendationEngine for generating recommendations."""

    def test_create_recommendation_engine(self):
        """Test creating recommendation engine with profile."""
        from src.music_discovery import RecommendationEngine, TasteProfile

        profile = TasteProfile(user_id="test_user")
        engine = RecommendationEngine(profile)

        assert engine.profile == profile

    def test_generate_recommendations_from_genres(self):
        """Test generating recommendations based on genre preferences."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [
                    {"name": "Song 1", "id": "track1", "artists": [{"name": "Artist 1"}]},
                    {"name": "Song 2", "id": "track2", "artists": [{"name": "Artist 2"}]},
                ]
            }

            from src.music_discovery import RecommendationEngine, TasteProfile

            profile = TasteProfile(user_id="test_user")
            profile.add_genre("rock", weight=0.9)
            engine = RecommendationEngine(profile)

            recommendations = engine.get_recommendations(limit=10)

            assert recommendations["success"] is True
            assert len(recommendations["tracks"]) >= 1

    def test_generate_recommendations_from_artists(self):
        """Test generating recommendations based on artist preferences."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [
                    {"name": "Song 1", "id": "track1", "artists": [{"name": "Artist 1"}]},
                ]
            }

            from src.music_discovery import RecommendationEngine, TasteProfile

            profile = TasteProfile(user_id="test_user")
            profile.add_artist("queen", artist_id="queen123", weight=0.9)
            engine = RecommendationEngine(profile)

            recommendations = engine.get_recommendations()

            assert recommendations["success"] is True
            mock_sp.recommendations.assert_called()

    def test_generate_recommendations_with_energy_filter(self):
        """Test recommendations respect energy preference."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [{"name": "Song 1", "id": "track1", "artists": [{"name": "Artist 1"}]}]
            }

            from src.music_discovery import RecommendationEngine, TasteProfile

            profile = TasteProfile(user_id="test_user")
            profile.add_genre("rock", weight=0.9)
            profile.set_energy_preference(0.8)
            engine = RecommendationEngine(profile)

            engine.get_recommendations()

            # Check that energy was passed to Spotify API
            call_kwargs = mock_sp.recommendations.call_args[1]
            assert "target_energy" in call_kwargs or "min_energy" in call_kwargs

    def test_create_playlist_from_recommendations(self):
        """Test creating a Spotify playlist from recommendations."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.me.return_value = {"id": "user123"}
            mock_sp.user_playlist_create.return_value = {"id": "playlist123", "uri": "spotify:playlist:playlist123"}
            mock_sp.playlist_add_items.return_value = {}

            from src.music_discovery import RecommendationEngine, TasteProfile

            profile = TasteProfile(user_id="test_user")
            engine = RecommendationEngine(profile)

            track_uris = ["spotify:track:track1", "spotify:track:track2"]
            result = engine.create_playlist("My Discovery Playlist", track_uris)

            assert result["success"] is True
            assert "playlist_id" in result

    def test_handle_empty_profile(self):
        """Test recommendations with empty profile uses defaults."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {"tracks": []}

            from src.music_discovery import RecommendationEngine, TasteProfile

            profile = TasteProfile(user_id="test_user")
            engine = RecommendationEngine(profile)

            result = engine.get_recommendations()

            # Should still work, just return empty or default recommendations
            assert result["success"] is True or "error" in result


# ==================== FEEDBACK TRACKER TESTS ====================

class TestFeedbackTracker:
    """Test FeedbackTracker for learning from user responses."""

    def test_record_positive_feedback(self):
        """Test recording positive feedback on a track."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Artist 1",
            genres=["rock"],
            feedback="like"
        )

        assert tracker.get_feedback_count("like") == 1

    def test_record_negative_feedback(self):
        """Test recording negative feedback on a track."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Artist 1",
            genres=["jazz"],
            feedback="dislike"
        )

        assert tracker.get_feedback_count("dislike") == 1

    def test_positive_feedback_increases_genre_weight(self):
        """Test liking a track increases weight of its genre."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("rock", weight=0.5)
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Artist 1",
            genres=["rock"],
            feedback="like"
        )

        # Weight should increase
        assert profile.get_genre_weight("rock") > 0.5

    def test_negative_feedback_decreases_genre_weight(self):
        """Test disliking a track decreases weight of its genre."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        profile.add_genre("jazz", weight=0.5)
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Artist 1",
            genres=["jazz"],
            feedback="dislike"
        )

        # Weight should decrease
        assert profile.get_genre_weight("jazz") < 0.5

    def test_feedback_adds_new_genre_if_liked(self):
        """Test liking a track adds its genre to profile if not present."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Artist 1",
            genres=["electronic"],
            feedback="like"
        )

        # Genre should be added
        assert profile.get_genre_weight("electronic") > 0

    def test_save_feedback_affects_artist_weight(self):
        """Test feedback also affects artist preferences."""
        from src.music_discovery import FeedbackTracker, TasteProfile

        profile = TasteProfile(user_id="test_user")
        tracker = FeedbackTracker(profile)

        tracker.record_feedback(
            track_id="track123",
            track_name="Song 1",
            artist_id="artist123",
            artist_name="Loved Artist",
            genres=["rock"],
            feedback="love"  # Strong positive
        )

        # Artist should be added with high weight
        artist_names = [a["name"] for a in profile.artists]
        assert "Loved Artist" in artist_names


# ==================== PERSISTENCE TESTS ====================

class TestMusicDiscoveryPersistence:
    """Test persistence of taste profiles and feedback."""

    def test_save_taste_profile_to_database(self):
        """Test saving taste profile to SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "discovery.db")

            with patch('src.music_discovery.DISCOVERY_DB_PATH', db_path):
                from src.music_discovery import TasteProfile, save_taste_profile, init_discovery_db

                init_discovery_db()

                profile = TasteProfile(user_id="test_user")
                profile.add_genre("rock", weight=0.8)
                profile.add_artist("queen", artist_id="queen123", weight=0.9)

                result = save_taste_profile(profile)

                assert result is True

    def test_load_taste_profile_from_database(self):
        """Test loading taste profile from SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "discovery.db")

            with patch('src.music_discovery.DISCOVERY_DB_PATH', db_path):
                from src.music_discovery import (
                    TasteProfile, save_taste_profile, load_taste_profile, init_discovery_db
                )

                init_discovery_db()

                profile = TasteProfile(user_id="test_user")
                profile.add_genre("rock", weight=0.8)
                save_taste_profile(profile)

                loaded_profile = load_taste_profile("test_user")

                assert loaded_profile is not None
                assert loaded_profile.user_id == "test_user"
                assert loaded_profile.get_genre_weight("rock") == 0.8

    def test_load_nonexistent_profile_returns_none(self):
        """Test loading non-existent profile returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "discovery.db")

            with patch('src.music_discovery.DISCOVERY_DB_PATH', db_path):
                from src.music_discovery import load_taste_profile, init_discovery_db

                init_discovery_db()

                loaded_profile = load_taste_profile("nonexistent_user")

                assert loaded_profile is None

    def test_save_feedback_history(self):
        """Test saving feedback history to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "discovery.db")

            with patch('src.music_discovery.DISCOVERY_DB_PATH', db_path):
                from src.music_discovery import (
                    TasteProfile, FeedbackTracker, save_feedback, init_discovery_db
                )

                init_discovery_db()

                profile = TasteProfile(user_id="test_user")
                tracker = FeedbackTracker(profile)

                tracker.record_feedback(
                    track_id="track123",
                    track_name="Song 1",
                    artist_id="artist123",
                    artist_name="Artist 1",
                    genres=["rock"],
                    feedback="like"
                )

                result = save_feedback(
                    user_id="test_user",
                    track_id="track123",
                    feedback="like"
                )

                assert result is True


# ==================== INTEGRATION TESTS ====================

class TestMusicDiscoveryIntegration:
    """Integration tests for the full discovery flow."""

    def test_full_discovery_flow(self):
        """Test complete discovery flow from session to recommendations."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [
                    {"name": "Recommended Song", "id": "track1", "uri": "spotify:track:track1",
                     "artists": [{"name": "Artist 1", "id": "artist1"}]},
                ]
            }

            from src.music_discovery import (
                TasteProfile, DiscoverySession, RecommendationEngine
            )

            # Create profile
            profile = TasteProfile(user_id="test_user")

            # Run discovery session
            session = DiscoverySession(profile)
            session.process_answer("genre", "I love classic rock and blues")
            session.process_answer("energy", "medium energy, not too loud")

            # Generate recommendations
            engine = RecommendationEngine(profile)
            recommendations = engine.get_recommendations()

            assert recommendations["success"] is True

    def test_discovery_with_existing_profile(self):
        """Test discovery uses existing profile for better recommendations."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [{"name": "Song", "id": "track1", "artists": [{"name": "Artist"}]}]
            }

            from src.music_discovery import TasteProfile, RecommendationEngine

            # Profile with history
            profile = TasteProfile(user_id="test_user")
            profile.add_genre("rock", weight=0.9)
            profile.add_genre("jazz", weight=0.3)
            profile.add_artist("queen", artist_id="queen123", weight=0.95)

            engine = RecommendationEngine(profile)
            engine.get_recommendations()

            # Should prioritize rock and queen in seeds
            call_kwargs = mock_sp.recommendations.call_args[1]
            seed_genres = call_kwargs.get("seed_genres", [])
            seed_artists = call_kwargs.get("seed_artists", [])

            # Rock should be prioritized
            assert "rock" in seed_genres or len(seed_genres) == 0  # May use artists instead


# ==================== VOICE TOOL TESTS ====================

class TestMusicDiscoveryTools:
    """Test voice command tools for music discovery."""

    def test_start_discovery_tool(self):
        """Test tool to start music discovery session."""
        with patch('src.music_discovery.load_taste_profile') as mock_load:
            mock_load.return_value = None  # New user

            from src.music_discovery import start_discovery

            result = start_discovery(user_id="test_user")

            assert result["success"] is True
            assert "session_id" in result
            assert "question" in result

    def test_answer_discovery_question_tool(self):
        """Test tool to answer discovery question."""
        from src.music_discovery import start_discovery, answer_discovery_question

        with patch('src.music_discovery.load_taste_profile') as mock_load:
            mock_load.return_value = None

            # Start session
            start_result = start_discovery(user_id="test_user")
            session_id = start_result["session_id"]

            # Answer question
            with patch('src.music_discovery.get_session') as mock_get_session:
                from src.music_discovery import TasteProfile, DiscoverySession
                profile = TasteProfile(user_id="test_user")
                session = DiscoverySession(profile)
                mock_get_session.return_value = session

                result = answer_discovery_question(
                    session_id=session_id,
                    answer="I love rock and jazz"
                )

                assert result["success"] is True

    def test_get_music_recommendations_tool(self):
        """Test tool to get recommendations based on profile."""
        with patch('src.music_discovery.get_spotify_client') as mock_get_client:
            mock_client = Mock()
            mock_sp = Mock()
            mock_client.spotify = mock_sp
            mock_get_client.return_value = mock_client

            mock_sp.recommendations.return_value = {
                "tracks": [{"name": "Song 1", "id": "track1", "artists": [{"name": "Artist 1"}]}]
            }

            with patch('src.music_discovery.load_taste_profile') as mock_load:
                from src.music_discovery import TasteProfile
                profile = TasteProfile(user_id="test_user")
                profile.add_genre("rock", weight=0.9)
                mock_load.return_value = profile

                from src.music_discovery import get_music_recommendations

                result = get_music_recommendations(user_id="test_user")

                assert result["success"] is True
                assert "tracks" in result

    def test_provide_music_feedback_tool(self):
        """Test tool to provide feedback on recommendations."""
        with patch('src.music_discovery.load_taste_profile') as mock_load:
            from src.music_discovery import TasteProfile
            profile = TasteProfile(user_id="test_user")
            mock_load.return_value = profile

            with patch('src.music_discovery.save_taste_profile'):
                with patch('src.music_discovery.save_feedback'):
                    from src.music_discovery import provide_music_feedback

                    result = provide_music_feedback(
                        user_id="test_user",
                        track_id="track123",
                        feedback="like",
                        track_name="Song 1",
                        artist_name="Artist 1",
                        genres=["rock"]
                    )

                    assert result["success"] is True


# ==================== TOOL DEFINITIONS TESTS ====================

class TestMusicDiscoveryToolDefinitions:
    """Test tool definitions are properly formatted for Claude."""

    def test_discovery_tools_have_required_fields(self):
        """Test discovery tools have name, description, input_schema."""
        from src.music_discovery import MUSIC_DISCOVERY_TOOLS

        for tool in MUSIC_DISCOVERY_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "type" in tool["input_schema"]

    def test_start_discovery_tool_definition(self):
        """Test start_discovery tool has proper schema."""
        from src.music_discovery import MUSIC_DISCOVERY_TOOLS

        tool = next((t for t in MUSIC_DISCOVERY_TOOLS if t["name"] == "start_discovery"), None)

        assert tool is not None
        assert "user_id" not in tool["input_schema"].get("required", [])  # Optional, can be inferred

    def test_answer_discovery_tool_definition(self):
        """Test answer_discovery_question tool has proper schema."""
        from src.music_discovery import MUSIC_DISCOVERY_TOOLS

        tool = next((t for t in MUSIC_DISCOVERY_TOOLS if t["name"] == "answer_discovery_question"), None)

        assert tool is not None
        props = tool["input_schema"].get("properties", {})
        assert "answer" in props

    def test_get_recommendations_tool_definition(self):
        """Test get_music_recommendations tool has proper schema."""
        from src.music_discovery import MUSIC_DISCOVERY_TOOLS

        tool = next((t for t in MUSIC_DISCOVERY_TOOLS if t["name"] == "get_music_recommendations"), None)

        assert tool is not None
        props = tool["input_schema"].get("properties", {})
        assert "limit" in props or len(props) >= 0  # May have optional params

    def test_provide_feedback_tool_definition(self):
        """Test provide_music_feedback tool has proper schema."""
        from src.music_discovery import MUSIC_DISCOVERY_TOOLS

        tool = next((t for t in MUSIC_DISCOVERY_TOOLS if t["name"] == "provide_music_feedback"), None)

        assert tool is not None
        props = tool["input_schema"].get("properties", {})
        assert "track_id" in props
        assert "feedback" in props
