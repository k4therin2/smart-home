# Music Discovery Agent

The Music Discovery Agent provides intelligent music discovery based on user preferences and context. It learns your taste through interactive questions and generates personalized recommendations using Spotify's recommendation engine.

## Features

- **Taste Profiling**: Learn your music preferences through questions about genres, artists, moods, and energy levels
- **Personalized Recommendations**: Generate track lists tailored to your taste profile
- **Feedback Learning**: Improve recommendations over time based on your likes/dislikes
- **Playlist Creation**: Create Spotify playlists from recommendations
- **Persistence**: Profiles and feedback history saved to database

## Voice Commands

### Start Discovery Session

```
"Help me discover new music"
"Find me some music I'll like"
"What should I listen to?"
```

This starts a discovery session that will ask questions to understand your preferences.

### Answer Discovery Questions

When the agent asks questions like "What genres do you enjoy?", just answer naturally:

```
"I love classic rock and blues"
"Queen, Led Zeppelin, and Pink Floyd are my favorites"
"I like upbeat music for working out"
```

### Get Recommendations

```
"Give me some music recommendations"
"Make me a playlist based on my taste"
"Find 10 songs I might like"
```

### Provide Feedback

```
"I like this song"
"Skip this one"
"I love this track!"
"Not a fan of this"
```

## How It Works

### 1. Taste Profile

The system builds a taste profile based on:
- **Genres**: Rock, jazz, electronic, hip-hop, etc. (with weighted preferences)
- **Artists**: Your favorite artists and bands
- **Moods**: Relaxing, upbeat, energetic, melancholy, etc.
- **Energy Level**: Preference for high-energy or mellow tracks
- **Discovery Style**: Whether you prefer familiar music or exploring new artists

### 2. Discovery Session

A discovery session asks 3-5 questions to understand your preferences:

1. **Genres**: "What genres of music do you enjoy?"
2. **Artists**: "Who are some of your favorite artists?"
3. **Mood**: "What kind of mood do you want from music?"
4. **Energy**: "Do you prefer high-energy or mellow tracks?"
5. **Discovery**: "Do you like discovering new artists?"

### 3. Recommendations

Once enough information is gathered, the system uses Spotify's recommendation API with:
- **Seed genres** from your top preferences
- **Seed artists** from your favorites
- **Audio feature targets** based on energy and mood preferences

### 4. Feedback Loop

When you like or dislike a recommendation:
- **Like/Love**: Increases weight of that track's genres and adds artist to favorites
- **Dislike**: Decreases weight of those genres
- **Skip**: Slight decrease in genre weights

## API Reference

### Tool: `start_discovery`

Start a music discovery session.

**Parameters:**
- `user_id` (optional): User identifier (defaults to "default")

**Returns:**
- `session_id`: Session ID for answering questions
- `question`: First question to ask user

### Tool: `answer_discovery_question`

Answer a question in the discovery session.

**Parameters:**
- `session_id` (required): Session ID from start_discovery
- `answer` (required): User's answer text

**Returns:**
- `question`: Next question (if more needed)
- `can_recommend`: True if ready for recommendations

### Tool: `get_music_recommendations`

Get personalized music recommendations.

**Parameters:**
- `user_id` (optional): User identifier
- `limit` (optional): Maximum tracks (1-50, default: 20)
- `create_playlist` (optional): Create Spotify playlist
- `playlist_name` (optional): Name for playlist

**Returns:**
- `tracks`: List of recommended tracks with name, artist, album
- `playlist`: Playlist info if created

### Tool: `provide_music_feedback`

Provide feedback on a recommendation.

**Parameters:**
- `track_id` (required): Spotify track ID
- `feedback` (required): "like", "dislike", "love", or "skip"
- `user_id` (optional): User identifier
- `track_name`, `artist_name`, `genres` (optional): Track metadata

**Returns:**
- `success`: Whether feedback was recorded
- `message`: Confirmation message

## Database Schema

Taste profiles and feedback are stored in `data/discovery.db`:

### taste_profiles
| Column | Type | Description |
|--------|------|-------------|
| user_id | TEXT | Primary key |
| profile_data | TEXT | JSON serialized profile |
| created_at | TEXT | Creation timestamp |
| updated_at | TEXT | Last update timestamp |

### feedback_history
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | TEXT | User identifier |
| track_id | TEXT | Spotify track ID |
| feedback | TEXT | Feedback type |
| timestamp | TEXT | When feedback was given |

## Configuration

The music discovery agent uses the same Spotify credentials as the main music system:

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
```

## Example Session

```
User: "Help me discover new music"

Agent: "Let's discover some music you'll love! What genres of music do you enjoy?"

User: "I love classic rock and blues"

Agent: "Great taste! Who are some of your favorite artists or bands?"

User: "Queen, Led Zeppelin, and Stevie Ray Vaughan"

Agent: "Excellent! What kind of mood do you usually want from music?"

User: "Something energetic for working out, but also mellow stuff for relaxing"

Agent: "I've got a good sense of your taste! Want me to find some music for you?"

User: "Yes please"

Agent: "Here are 10 tracks I think you'll enjoy:
1. 'Black Dog' by Led Zeppelin
2. 'Pride and Joy' by Stevie Ray Vaughan
3. 'Stone Free' by Jimi Hendrix
4. 'Crossfire' by Stevie Ray Vaughan
5. 'Good Times Bad Times' by Led Zeppelin
..."

User: "I love track 3, skip track 4"

Agent: "Thanks for the feedback! I'll remember you love Jimi Hendrix's style."
```
