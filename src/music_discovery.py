"""
Music Discovery Agent

Provides intelligent music discovery based on user preferences and context.
This module implements REQ-026: Music Discovery Agent.

Key Features:
- TasteProfile: Stores user music preferences (genres, artists, energy, moods)
- DiscoverySession: Manages conversation flow for refining taste
- RecommendationEngine: Generates playlists based on profile
- FeedbackTracker: Learns from user responses to improve recommendations

The discovery agent asks questions to understand user preferences, then
generates personalized recommendations using Spotify's recommendation API.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR
from src.utils import setup_logging
from tools.spotify import get_spotify_client


logger = setup_logging("music_discovery")

# Database path for discovery data
DISCOVERY_DB_PATH = DATA_DIR / "discovery.db"

# Active sessions (in-memory for quick access)
_active_sessions: dict[str, "DiscoverySession"] = {}

# Genre mapping for natural language parsing
GENRE_KEYWORDS = {
    "rock": ["rock", "rock and roll", "classic rock", "hard rock", "punk", "grunge", "alternative"],
    "pop": ["pop", "popular", "top 40", "mainstream"],
    "jazz": ["jazz", "smooth jazz", "bebop", "swing"],
    "blues": ["blues", "rhythm and blues", "r&b"],
    "electronic": ["electronic", "edm", "techno", "house", "trance", "dubstep"],
    "hip-hop": ["hip hop", "hip-hop", "rap", "trap"],
    "country": ["country", "bluegrass", "americana"],
    "classical": ["classical", "orchestra", "symphony", "baroque"],
    "metal": ["metal", "heavy metal", "death metal", "thrash"],
    "folk": ["folk", "acoustic", "singer-songwriter"],
    "reggae": ["reggae", "ska", "dancehall"],
    "soul": ["soul", "motown", "funk"],
    "indie": ["indie", "independent", "alternative"],
    "latin": ["latin", "salsa", "reggaeton", "bachata"],
}

# Mood keywords for parsing
MOOD_KEYWORDS = {
    "relaxing": ["relaxing", "chill", "calm", "peaceful", "mellow", "easy"],
    "upbeat": ["upbeat", "happy", "cheerful", "positive", "fun"],
    "energetic": ["energetic", "high energy", "pumped", "intense", "powerful"],
    "melancholy": ["sad", "melancholy", "emotional", "moody", "dark"],
    "romantic": ["romantic", "love", "sensual", "intimate"],
    "focused": ["focus", "study", "concentration", "ambient", "background"],
    "party": ["party", "dance", "club", "celebration"],
}

# Questions for discovery session
DISCOVERY_QUESTIONS = [
    {
        "type": "genre",
        "text": "What genres of music do you enjoy? (e.g., rock, jazz, electronic, hip-hop)",
        "priority": 1,
    },
    {
        "type": "artist",
        "text": "Who are some of your favorite artists or bands?",
        "priority": 2,
    },
    {
        "type": "mood",
        "text": "What kind of mood do you usually want from music? (e.g., upbeat, relaxing, energetic)",
        "priority": 3,
    },
    {
        "type": "energy",
        "text": "Do you prefer high-energy music or more mellow tracks?",
        "priority": 4,
    },
    {
        "type": "discovery_style",
        "text": "Do you like discovering new artists, or do you prefer sticking to what you know?",
        "priority": 5,
    },
]


class TasteProfile:
    """
    Stores user music preferences including genres, artists, energy level, and moods.

    Preferences are weighted to allow for nuanced recommendations.
    """

    def __init__(self, user_id: str):
        """
        Initialize a new taste profile.

        Args:
            user_id: Unique identifier for the user
        """
        self.user_id = user_id
        self._genres: dict[str, float] = {}  # genre -> weight (0.0-1.0)
        self._artists: list[dict[str, Any]] = []  # [{"name": str, "id": str, "weight": float}]
        self.energy_preference: float | None = None  # 0.0 (low) to 1.0 (high)
        self._mood_preferences: set[str] = set()
        self.discovery_preference: float = 0.5  # 0=familiar, 1=adventurous
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

    @property
    def genres(self) -> list[str]:
        """Get list of genre names."""
        return list(self._genres.keys())

    @property
    def artists(self) -> list[dict[str, Any]]:
        """Get list of artist preferences."""
        return self._artists.copy()

    @property
    def mood_preferences(self) -> list[str]:
        """Get list of mood preferences."""
        return list(self._mood_preferences)

    def add_genre(self, genre: str, weight: float = 0.7) -> None:
        """
        Add or update a genre preference.

        Args:
            genre: Genre name (normalized to lowercase)
            weight: Preference weight (0.0-1.0)
        """
        genre = genre.lower().strip()
        self._genres[genre] = max(0.0, min(1.0, weight))
        self.updated_at = datetime.now()

    def get_genre_weight(self, genre: str) -> float:
        """Get weight for a genre, returns 0.0 if not found."""
        return self._genres.get(genre.lower().strip(), 0.0)

    def add_artist(self, name: str, artist_id: str | None = None, weight: float = 0.8) -> None:
        """
        Add or update an artist preference.

        Args:
            name: Artist name
            artist_id: Spotify artist ID (optional)
            weight: Preference weight (0.0-1.0)
        """
        name = name.strip()
        weight = max(0.0, min(1.0, weight))

        # Check if artist already exists
        for artist in self._artists:
            if artist["name"].lower() == name.lower():
                artist["weight"] = weight
                if artist_id:
                    artist["id"] = artist_id
                self.updated_at = datetime.now()
                return

        # Add new artist
        self._artists.append({
            "name": name,
            "id": artist_id,
            "weight": weight
        })
        self.updated_at = datetime.now()

    def set_energy_preference(self, energy: float) -> None:
        """
        Set energy preference.

        Args:
            energy: Energy level (0.0 low to 1.0 high)
        """
        self.energy_preference = max(0.0, min(1.0, energy))
        self.updated_at = datetime.now()

    def add_mood(self, mood: str) -> None:
        """Add a mood preference."""
        self._mood_preferences.add(mood.lower().strip())
        self.updated_at = datetime.now()

    def get_top_genres(self, n: int = 5) -> list[dict[str, Any]]:
        """Get top N genres by weight."""
        sorted_genres = sorted(
            self._genres.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [{"name": g, "weight": w} for g, w in sorted_genres[:n]]

    def get_top_artists(self, n: int = 5) -> list[dict[str, Any]]:
        """Get top N artists by weight."""
        sorted_artists = sorted(
            self._artists,
            key=lambda x: x.get("weight", 0),
            reverse=True
        )
        return sorted_artists[:n]

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to dictionary."""
        return {
            "user_id": self.user_id,
            "genres": [{"name": g, "weight": w} for g, w in self._genres.items()],
            "artists": self._artists,
            "energy_preference": self.energy_preference,
            "mood_preferences": list(self._mood_preferences),
            "discovery_preference": self.discovery_preference,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TasteProfile":
        """Create profile from dictionary."""
        profile = cls(user_id=data["user_id"])

        for genre_data in data.get("genres", []):
            if isinstance(genre_data, dict):
                profile.add_genre(genre_data["name"], genre_data["weight"])
            else:
                profile.add_genre(genre_data)

        for artist in data.get("artists", []):
            profile.add_artist(
                name=artist["name"],
                artist_id=artist.get("id"),
                weight=artist.get("weight", 0.8)
            )

        if data.get("energy_preference") is not None:
            profile.energy_preference = data["energy_preference"]

        for mood in data.get("mood_preferences", []):
            profile.add_mood(mood)

        profile.discovery_preference = data.get("discovery_preference", 0.5)

        if data.get("created_at"):
            profile.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            profile.updated_at = datetime.fromisoformat(data["updated_at"])

        return profile


class DiscoverySession:
    """
    Manages a conversation flow for music discovery.

    Asks questions to refine user taste and tracks progress through the discovery process.
    """

    def __init__(self, profile: TasteProfile):
        """
        Initialize a discovery session.

        Args:
            profile: User's taste profile (new or existing)
        """
        self.profile = profile
        self.session_id = str(uuid.uuid4())
        self.questions_asked = 0
        self._answered_types: set[str] = set()
        self._is_complete = False
        self.created_at = datetime.now()

    @property
    def is_complete(self) -> bool:
        """Check if session has completed."""
        return self._is_complete

    @property
    def can_recommend(self) -> bool:
        """Check if we have enough info to make recommendations."""
        # Need at least genre OR artist preference
        has_genres = len(self.profile.genres) > 0
        has_artists = len(self.profile.artists) > 0
        answered_enough = self.questions_asked >= 2

        return (has_genres or has_artists) and answered_enough

    def get_next_question(self) -> dict[str, Any] | None:
        """
        Get the next question to ask the user.

        Returns:
            Question dict or None if session is complete
        """
        if self._is_complete:
            return None

        # Sort questions by priority and filter out answered ones
        remaining = [
            q for q in DISCOVERY_QUESTIONS
            if q["type"] not in self._answered_types
        ]

        if not remaining:
            self._is_complete = True
            return None

        return remaining[0]

    def process_answer(self, question_type: str, answer: str) -> None:
        """
        Process user's answer to a question.

        Args:
            question_type: Type of question being answered
            answer: User's answer text
        """
        answer_lower = answer.lower()

        if question_type == "genre":
            self._process_genre_answer(answer_lower)
        elif question_type == "artist":
            self._process_artist_answer(answer)
        elif question_type == "mood":
            self._process_mood_answer(answer_lower)
        elif question_type == "energy":
            self._process_energy_answer(answer_lower)
        elif question_type == "discovery_style":
            self._process_discovery_style_answer(answer_lower)

        self._answered_types.add(question_type)
        self.questions_asked += 1

    def _process_genre_answer(self, answer: str) -> None:
        """Extract and add genres from answer."""
        for genre, keywords in GENRE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in answer:
                    self.profile.add_genre(genre, weight=0.8)
                    break

    def _process_artist_answer(self, answer: str) -> None:
        """Extract and add artists from answer."""
        # Try to find and resolve artist names
        # For now, just add as names - IDs resolved later
        words = answer.replace(",", "").replace("and", ",").split(",")
        for word in words:
            word = word.strip()
            if len(word) > 2:  # Skip short words
                artist_info = search_artist_by_name(word)
                if artist_info:
                    self.profile.add_artist(
                        name=artist_info.get("name", word),
                        artist_id=artist_info.get("id"),
                        weight=0.85
                    )
                else:
                    # Add without ID, will resolve later
                    self.profile.add_artist(name=word, weight=0.7)

    def _process_mood_answer(self, answer: str) -> None:
        """Extract and add moods from answer."""
        for mood, keywords in MOOD_KEYWORDS.items():
            for keyword in keywords:
                if keyword in answer:
                    self.profile.add_mood(mood)
                    break

    def _process_energy_answer(self, answer: str) -> None:
        """Extract energy preference from answer."""
        high_energy_words = ["high", "intense", "loud", "powerful", "pumped", "energetic"]
        low_energy_words = ["low", "mellow", "calm", "quiet", "chill", "relaxed"]

        high_score = sum(1 for word in high_energy_words if word in answer)
        low_score = sum(1 for word in low_energy_words if word in answer)

        if high_score > low_score:
            self.profile.set_energy_preference(0.8)
        elif low_score > high_score:
            self.profile.set_energy_preference(0.3)
        else:
            self.profile.set_energy_preference(0.5)

    def _process_discovery_style_answer(self, answer: str) -> None:
        """Extract discovery preference from answer."""
        adventure_words = ["new", "discover", "adventure", "explore", "different"]
        familiar_words = ["familiar", "know", "same", "favorite", "stick"]

        adventure_score = sum(1 for word in adventure_words if word in answer)
        familiar_score = sum(1 for word in familiar_words if word in answer)

        if adventure_score > familiar_score:
            self.profile.discovery_preference = 0.8
        elif familiar_score > adventure_score:
            self.profile.discovery_preference = 0.2
        else:
            self.profile.discovery_preference = 0.5

    def skip_question(self) -> None:
        """Skip current question."""
        current = self.get_next_question()
        if current:
            self._answered_types.add(current["type"])
            self.questions_asked += 1


class RecommendationEngine:
    """
    Generates music recommendations based on user's taste profile.

    Uses Spotify's recommendation API with seeds from the user's preferences.
    """

    def __init__(self, profile: TasteProfile):
        """
        Initialize recommendation engine.

        Args:
            profile: User's taste profile
        """
        self.profile = profile
        self._spotify = None

    def _get_spotify(self):
        """Get Spotify client."""
        if self._spotify is None:
            client = get_spotify_client()
            self._spotify = client.spotify
        return self._spotify

    def get_recommendations(self, limit: int = 20) -> dict[str, Any]:
        """
        Get personalized track recommendations.

        Args:
            limit: Maximum number of tracks to return

        Returns:
            Dictionary with success status and list of recommended tracks
        """
        try:
            spotify = self._get_spotify()

            # Build seed parameters
            seed_genres = []
            seed_artists = []

            # Get top genres (max 5 seeds total)
            top_genres = self.profile.get_top_genres(3)
            for genre in top_genres:
                seed_genres.append(genre["name"])

            # Get top artists
            top_artists = self.profile.get_top_artists(2)
            for artist in top_artists:
                if artist.get("id"):
                    seed_artists.append(artist["id"])

            # Need at least one seed
            if not seed_genres and not seed_artists:
                # Use default genres if profile is empty
                seed_genres = ["pop"]

            # Build recommendation parameters
            rec_params = {
                "limit": limit,
                "seed_genres": seed_genres[:5],  # Spotify max is 5 seeds total
            }

            if seed_artists:
                # Reduce genres to make room for artists
                rec_params["seed_genres"] = seed_genres[:max(1, 5 - len(seed_artists))]
                rec_params["seed_artists"] = seed_artists[:5 - len(rec_params["seed_genres"])]

            # Add tuning parameters
            if self.profile.energy_preference is not None:
                rec_params["target_energy"] = self.profile.energy_preference
                rec_params["min_energy"] = max(0, self.profile.energy_preference - 0.2)
                rec_params["max_energy"] = min(1, self.profile.energy_preference + 0.2)

            # Map moods to audio features
            if "upbeat" in self.profile.mood_preferences:
                rec_params["min_valence"] = 0.6
            if "melancholy" in self.profile.mood_preferences:
                rec_params["max_valence"] = 0.4
            if "party" in self.profile.mood_preferences:
                rec_params["min_danceability"] = 0.7

            logger.info(f"Getting recommendations with params: {rec_params}")

            # Get recommendations
            results = spotify.recommendations(**rec_params)

            tracks = []
            for track in results.get("tracks", []):
                tracks.append({
                    "name": track.get("name"),
                    "id": track.get("id"),
                    "uri": track.get("uri"),
                    "artist": track["artists"][0]["name"] if track.get("artists") else "Unknown",
                    "artist_id": track["artists"][0].get("id") if track.get("artists") else None,
                    "album": track["album"]["name"] if track.get("album") else "Unknown",
                    "preview_url": track.get("preview_url"),
                })

            return {
                "success": True,
                "tracks": tracks,
                "count": len(tracks),
                "message": f"Found {len(tracks)} recommended tracks",
            }

        except Exception as error:
            logger.error(f"Error getting recommendations: {error}")
            return {"success": False, "error": str(error)}

    def create_playlist(
        self, name: str, track_uris: list[str], description: str | None = None
    ) -> dict[str, Any]:
        """
        Create a Spotify playlist with the given tracks.

        Args:
            name: Playlist name
            track_uris: List of Spotify track URIs
            description: Optional playlist description

        Returns:
            Dictionary with success status and playlist info
        """
        try:
            spotify = self._get_spotify()

            # Get current user
            user = spotify.me()
            user_id = user["id"]

            # Create playlist
            playlist = spotify.user_playlist_create(
                user=user_id,
                name=name,
                public=False,
                description=description or "Discovered by Smart Home Music Agent"
            )

            playlist_id = playlist["id"]

            # Add tracks
            if track_uris:
                spotify.playlist_add_items(playlist_id, track_uris)

            return {
                "success": True,
                "playlist_id": playlist_id,
                "playlist_uri": playlist["uri"],
                "message": f"Created playlist '{name}' with {len(track_uris)} tracks",
            }

        except Exception as error:
            logger.error(f"Error creating playlist: {error}")
            return {"success": False, "error": str(error)}


class FeedbackTracker:
    """
    Tracks user feedback on recommendations and updates taste profile accordingly.
    """

    def __init__(self, profile: TasteProfile):
        """
        Initialize feedback tracker.

        Args:
            profile: User's taste profile to update
        """
        self.profile = profile
        self._feedback_counts = {"like": 0, "dislike": 0, "love": 0, "skip": 0}
        self._track_feedback: list[dict] = []

    def get_feedback_count(self, feedback_type: str) -> int:
        """Get count of feedback of a specific type."""
        return self._feedback_counts.get(feedback_type, 0)

    def record_feedback(
        self,
        track_id: str,
        track_name: str,
        artist_id: str | None,
        artist_name: str,
        genres: list[str],
        feedback: str,
    ) -> None:
        """
        Record feedback on a track and update taste profile.

        Args:
            track_id: Spotify track ID
            track_name: Track name
            artist_id: Spotify artist ID
            artist_name: Artist name
            genres: List of genres for the track
            feedback: Feedback type ("like", "dislike", "love", "skip")
        """
        # Record feedback
        self._feedback_counts[feedback] = self._feedback_counts.get(feedback, 0) + 1
        self._track_feedback.append({
            "track_id": track_id,
            "track_name": track_name,
            "artist_id": artist_id,
            "artist_name": artist_name,
            "genres": genres,
            "feedback": feedback,
            "timestamp": datetime.now().isoformat(),
        })

        # Update profile based on feedback
        weight_delta = self._get_weight_delta(feedback)

        # Update genre weights
        for genre in genres:
            current_weight = self.profile.get_genre_weight(genre)
            if current_weight > 0:
                new_weight = max(0.0, min(1.0, current_weight + weight_delta))
                self.profile.add_genre(genre, new_weight)
            elif weight_delta > 0:
                # Add new genre if liked
                self.profile.add_genre(genre, 0.5 + weight_delta)

        # Update artist weight for strong feedback
        if feedback in ("love", "like") and artist_name:
            self.profile.add_artist(
                name=artist_name,
                artist_id=artist_id,
                weight=0.9 if feedback == "love" else 0.7
            )

    def _get_weight_delta(self, feedback: str) -> float:
        """Get weight adjustment based on feedback type."""
        deltas = {
            "love": 0.2,
            "like": 0.1,
            "skip": -0.05,
            "dislike": -0.15,
        }
        return deltas.get(feedback, 0.0)


# ==================== DATABASE FUNCTIONS ====================

def _get_db_path() -> Path:
    """Get the database path as a Path object."""
    return Path(DISCOVERY_DB_PATH) if isinstance(DISCOVERY_DB_PATH, str) else DISCOVERY_DB_PATH


def init_discovery_db() -> None:
    """Initialize the discovery database with required tables."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Taste profiles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS taste_profiles (
                user_id TEXT PRIMARY KEY,
                profile_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Feedback history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                track_id TEXT NOT NULL,
                feedback TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES taste_profiles(user_id)
            )
        """)

        conn.commit()
        logger.info("Discovery database initialized")


def save_taste_profile(profile: TasteProfile) -> bool:
    """
    Save taste profile to database.

    Args:
        profile: TasteProfile to save

    Returns:
        True if saved successfully
    """
    try:
        db_path = _get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            profile_data = json.dumps(profile.to_dict())

            cursor.execute("""
                INSERT OR REPLACE INTO taste_profiles (user_id, profile_data, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                profile.user_id,
                profile_data,
                profile.created_at.isoformat(),
                profile.updated_at.isoformat(),
            ))

            conn.commit()
            logger.info(f"Saved taste profile for user {profile.user_id}")
            return True

    except Exception as error:
        logger.error(f"Error saving taste profile: {error}")
        return False


def load_taste_profile(user_id: str) -> TasteProfile | None:
    """
    Load taste profile from database.

    Args:
        user_id: User ID to load profile for

    Returns:
        TasteProfile if found, None otherwise
    """
    try:
        db_path = _get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT profile_data FROM taste_profiles WHERE user_id = ?",
                (user_id,)
            )

            row = cursor.fetchone()
            if row:
                profile_data = json.loads(row[0])
                return TasteProfile.from_dict(profile_data)

            return None

    except Exception as error:
        logger.error(f"Error loading taste profile: {error}")
        return None


def save_feedback(user_id: str, track_id: str, feedback: str) -> bool:
    """
    Save feedback to history.

    Args:
        user_id: User ID
        track_id: Track ID
        feedback: Feedback type

    Returns:
        True if saved successfully
    """
    try:
        db_path = _get_db_path()
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO feedback_history (user_id, track_id, feedback, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, track_id, feedback, datetime.now().isoformat()))

            conn.commit()
            return True

    except Exception as error:
        logger.error(f"Error saving feedback: {error}")
        return False


# ==================== HELPER FUNCTIONS ====================

def search_artist_by_name(name: str) -> dict[str, Any] | None:
    """
    Search for an artist by name and return their info.

    Args:
        name: Artist name to search

    Returns:
        Dict with artist id and name, or None if not found
    """
    try:
        client = get_spotify_client()
        spotify = client.spotify

        results = spotify.search(q=name, type="artist", limit=1)
        artists = results.get("artists", {}).get("items", [])

        if artists:
            return {
                "id": artists[0]["id"],
                "name": artists[0]["name"],
            }
        return None

    except Exception as error:
        logger.warning(f"Error searching for artist '{name}': {error}")
        return None


def get_session(session_id: str) -> DiscoverySession | None:
    """Get an active discovery session by ID."""
    return _active_sessions.get(session_id)


# ==================== VOICE TOOL FUNCTIONS ====================

def start_discovery(user_id: str = "default") -> dict[str, Any]:
    """
    Start a music discovery session.

    Args:
        user_id: User ID (optional, defaults to "default")

    Returns:
        Session info with first question
    """
    try:
        # Load existing profile or create new
        profile = load_taste_profile(user_id)
        if profile is None:
            profile = TasteProfile(user_id=user_id)

        # Create session
        session = DiscoverySession(profile)
        _active_sessions[session.session_id] = session

        # Get first question
        question = session.get_next_question()

        return {
            "success": True,
            "session_id": session.session_id,
            "question": question,
            "message": "Let's discover some music you'll love! " + (question["text"] if question else ""),
        }

    except Exception as error:
        logger.error(f"Error starting discovery: {error}")
        return {"success": False, "error": str(error)}


def answer_discovery_question(
    session_id: str,
    answer: str,
) -> dict[str, Any]:
    """
    Answer a discovery question.

    Args:
        session_id: Discovery session ID
        answer: User's answer text

    Returns:
        Next question or recommendations if ready
    """
    try:
        session = get_session(session_id)
        if session is None:
            return {"success": False, "error": "Session not found"}

        # Get current question type
        current_question = session.get_next_question()
        if current_question is None:
            return {
                "success": True,
                "complete": True,
                "message": "Session already complete",
            }

        # Process answer
        session.process_answer(current_question["type"], answer)

        # Save profile
        save_taste_profile(session.profile)

        # Check if ready for recommendations
        if session.can_recommend:
            return {
                "success": True,
                "can_recommend": True,
                "message": "I've got a good sense of your taste! Want me to find some music for you?",
            }

        # Get next question
        next_question = session.get_next_question()
        if next_question:
            return {
                "success": True,
                "question": next_question,
                "questions_asked": session.questions_asked,
            }

        return {
            "success": True,
            "complete": True,
            "can_recommend": session.can_recommend,
        }

    except Exception as error:
        logger.error(f"Error processing answer: {error}")
        return {"success": False, "error": str(error)}


def get_music_recommendations(
    user_id: str = "default",
    limit: int = 20,
    create_playlist: bool = False,
    playlist_name: str | None = None,
) -> dict[str, Any]:
    """
    Get music recommendations based on user's taste profile.

    Args:
        user_id: User ID
        limit: Maximum number of tracks
        create_playlist: Whether to create a Spotify playlist
        playlist_name: Name for the playlist (if creating)

    Returns:
        Recommended tracks and optional playlist info
    """
    try:
        profile = load_taste_profile(user_id)
        if profile is None:
            return {
                "success": False,
                "error": "No taste profile found. Start a discovery session first.",
            }

        engine = RecommendationEngine(profile)
        recommendations = engine.get_recommendations(limit=limit)

        if not recommendations.get("success"):
            return recommendations

        if create_playlist and recommendations.get("tracks"):
            track_uris = [t["uri"] for t in recommendations["tracks"] if t.get("uri")]
            playlist_result = engine.create_playlist(
                name=playlist_name or "Discovered Music",
                track_uris=track_uris,
            )
            recommendations["playlist"] = playlist_result

        return recommendations

    except Exception as error:
        logger.error(f"Error getting recommendations: {error}")
        return {"success": False, "error": str(error)}


def provide_music_feedback(
    user_id: str,
    track_id: str,
    feedback: str,
    track_name: str | None = None,
    artist_name: str | None = None,
    genres: list[str] | None = None,
) -> dict[str, Any]:
    """
    Provide feedback on a recommended track.

    Args:
        user_id: User ID
        track_id: Spotify track ID
        feedback: Feedback type ("like", "dislike", "love", "skip")
        track_name: Track name (optional)
        artist_name: Artist name (optional)
        genres: Track genres (optional)

    Returns:
        Success status
    """
    try:
        profile = load_taste_profile(user_id)
        if profile is None:
            profile = TasteProfile(user_id=user_id)

        tracker = FeedbackTracker(profile)
        tracker.record_feedback(
            track_id=track_id,
            track_name=track_name or "Unknown",
            artist_id=None,
            artist_name=artist_name or "Unknown",
            genres=genres or [],
            feedback=feedback,
        )

        # Save updated profile
        save_taste_profile(profile)

        # Save feedback history
        save_feedback(user_id, track_id, feedback)

        return {
            "success": True,
            "message": f"Thanks for the feedback! I'll remember you {feedback}d this.",
        }

    except Exception as error:
        logger.error(f"Error recording feedback: {error}")
        return {"success": False, "error": str(error)}


# ==================== TOOL DEFINITIONS ====================

MUSIC_DISCOVERY_TOOLS = [
    {
        "name": "start_discovery",
        "description": """Start a music discovery session to learn about user's taste.

Use this when the user wants to:
- Discover new music
- Get personalized recommendations
- "Help me find new music"
- "What should I listen to?"

The session will ask questions to understand their preferences, then generate recommendations.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID (defaults to 'default')",
                },
            },
            "required": [],
        },
    },
    {
        "name": "answer_discovery_question",
        "description": """Answer a question during a music discovery session.

Use this to process the user's response to a discovery question.
The session tracks answers and updates the user's taste profile.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Discovery session ID from start_discovery",
                },
                "answer": {
                    "type": "string",
                    "description": "User's answer to the current question",
                },
            },
            "required": ["session_id", "answer"],
        },
    },
    {
        "name": "get_music_recommendations",
        "description": """Get personalized music recommendations based on user's taste profile.

Use this when the user:
- Wants recommendations after discovery session
- Asks for "something to listen to"
- Wants a playlist based on their taste

Can optionally create a Spotify playlist with the recommendations.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID (defaults to 'default')",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of tracks (default: 20)",
                },
                "create_playlist": {
                    "type": "boolean",
                    "description": "Whether to create a Spotify playlist",
                },
                "playlist_name": {
                    "type": "string",
                    "description": "Name for the playlist (if creating)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "provide_music_feedback",
        "description": """Provide feedback on a recommended track to improve future recommendations.

Use this when the user:
- Likes or dislikes a recommendation
- Loves a track
- Skips a track

Feedback types: "like", "dislike", "love", "skip".""",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID",
                },
                "track_id": {
                    "type": "string",
                    "description": "Spotify track ID",
                },
                "feedback": {
                    "type": "string",
                    "enum": ["like", "dislike", "love", "skip"],
                    "description": "Feedback type",
                },
                "track_name": {
                    "type": "string",
                    "description": "Track name (optional)",
                },
                "artist_name": {
                    "type": "string",
                    "description": "Artist name (optional)",
                },
                "genres": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Track genres (optional)",
                },
            },
            "required": ["track_id", "feedback"],
        },
    },
]


def execute_discovery_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a music discovery tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing discovery tool: {tool_name}")

    if tool_name == "start_discovery":
        return start_discovery(
            user_id=tool_input.get("user_id", "default"),
        )

    elif tool_name == "answer_discovery_question":
        return answer_discovery_question(
            session_id=tool_input.get("session_id", ""),
            answer=tool_input.get("answer", ""),
        )

    elif tool_name == "get_music_recommendations":
        return get_music_recommendations(
            user_id=tool_input.get("user_id", "default"),
            limit=tool_input.get("limit", 20),
            create_playlist=tool_input.get("create_playlist", False),
            playlist_name=tool_input.get("playlist_name"),
        )

    elif tool_name == "provide_music_feedback":
        return provide_music_feedback(
            user_id=tool_input.get("user_id", "default"),
            track_id=tool_input.get("track_id", ""),
            feedback=tool_input.get("feedback", ""),
            track_name=tool_input.get("track_name"),
            artist_name=tool_input.get("artist_name"),
            genres=tool_input.get("genres"),
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
