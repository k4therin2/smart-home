# Spotify Integration - WP-2.7

**Date:** 2025-12-18
**Work Package:** WP-2.7 Spotify Integration
**Status:** Complete (code implementation and tests)
**Author:** Agent-Spotify-Integration

## Summary

Implemented complete Spotify integration enabling voice-controlled music playback to Amazon Echo devices via Spotify Connect. Built using TDD methodology with 32 comprehensive integration tests, all passing.

## Implementation Details

### Architecture

**Core Components:**
1. **SpotifyClient** - OAuth 2.0 authentication with automatic token refresh
2. **Playback Control** - Play/pause/skip/volume functions
3. **Search** - Find tracks, albums, playlists, artists
4. **Device Management** - Spotify Connect device targeting
5. **Tool Definitions** - 5 agent tools with natural language support

### Files Created

**Primary Implementation:**
- `tools/spotify.py` (600+ lines) - Complete Spotify integration
- `tests/integration/test_spotify.py` (650+ lines) - 32 integration tests

**Configuration Changes:**
- `src/config.py` - Added SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
- `.env.example` - Added Spotify configuration documentation
- `requirements.txt` - Added spotipy>=2.23.0
- `agent.py` - Integrated SPOTIFY_TOOLS, added execute_spotify_tool handler

### OAuth Authentication Flow

**Implementation:**
- Uses Authorization Code Flow with refresh tokens
- Tokens cached in `data/spotify_cache/.spotify_token_cache`
- Automatic token refresh when expired
- Required scopes:
  - `user-modify-playback-state` - Control playback
  - `user-read-playback-state` - Read device/playback state
  - `user-read-currently-playing` - Read current track

**First-time Setup:**
User must:
1. Create Spotify app at https://developer.spotify.com/dashboard
2. Add redirect URI: `http://localhost:8888/callback`
3. Set environment variables in `.env`
4. Run initial OAuth flow (handled by spotipy library)

### Tool Definitions

**1. play_spotify**
- Play tracks, albums, playlists, or artists
- Target specific Spotify Connect devices
- Fuzzy device name matching ("living room" matches "Living Room Echo Dot")
- Examples:
  - "play Hey Jude on living room speaker"
  - "play Abbey Road album"
  - "play Chill Vibes playlist on bedroom"

**2. control_playback**
- Actions: pause, resume, next, previous, volume
- Volume validation (0-100)
- Examples:
  - "pause spotify"
  - "skip this song"
  - "set volume to 50"

**3. search_spotify**
- Search for tracks, albums, playlists, artists
- Returns up to 50 results with metadata
- Examples:
  - "find Beatles songs"
  - "search for jazz playlists"

**4. get_spotify_devices**
- List all available Spotify Connect devices
- Shows active device, volume, type
- Use to discover device names for playback targeting

**5. transfer_playback**
- Move playback between devices
- Optional auto-resume
- Examples:
  - "switch to bedroom speaker"
  - "move music to kitchen and resume"

### Test Coverage

**32 Integration Tests (100% passing):**

**OAuth Flow (4 tests):**
- Client initialization with credentials
- Missing credentials error handling
- Token refresh on expiration
- Cached token reuse

**Playback Control (8 tests):**
- Play track by name
- Play playlist
- Play album
- Pause, resume, next, previous
- Set volume

**Device Management (4 tests):**
- Get all devices
- Transfer playback
- Transfer with auto-resume
- Device not found error

**Search (5 tests):**
- Search tracks, artists, playlists, albums
- No results handling

**Error Handling (4 tests):**
- Spotify API errors
- No active devices
- Playback errors
- Invalid volume range

**Tool Integration (5 tests):**
- Tool definitions present
- Schemas valid
- Execute play tool
- Execute control tool
- Unknown tool handling

**Natural Language (2 tests):**
- Play song with natural language
- Fuzzy device matching

### Technical Decisions

**1. Used spotipy library**
- Mature, well-maintained Python SDK for Spotify Web API
- Handles OAuth complexity automatically
- Built-in token refresh
- Comprehensive API coverage

**2. Singleton client pattern**
- `get_spotify_client()` returns singleton instance
- Credentials loaded from environment variables
- Prevents redundant OAuth flows

**3. Fuzzy device matching**
- Users can say "living room" instead of exact "Living Room Echo Dot"
- Tries exact match first, then partial match
- Improves natural language usability

**4. Real integration tests**
- Mock only external Spotify API (spotipy.Spotify)
- Test real tool functions, not isolated units
- Fixture-based approach for consistent mocking
- Tests exercise actual code paths users will use

**5. Comprehensive error handling**
- SpotifyException catching for API errors
- User-friendly error messages
- Validation for parameters (volume, device names)
- Graceful degradation when devices unavailable

### Natural Language Examples

**Supported Commands:**
- "play Hey Jude by The Beatles on living room"
- "play my Chill Vibes playlist"
- "play Radiohead" (plays artist top tracks)
- "pause spotify"
- "skip this song"
- "volume to 75"
- "switch to bedroom speaker"
- "find jazz playlists"
- "what devices are available?"

### Integration with Agent

**Agent Flow:**
1. User: "play some Beatles on living room speaker"
2. Claude identifies intent, calls `play_spotify` tool
3. Tool searches Spotify for "Beatles"
4. Tool finds "living room" device (fuzzy match)
5. Tool starts playback via Spotify Connect API
6. Returns success with track/device info
7. Claude responds: "Now playing Hey Jude by The Beatles on Living Room Echo"

### Known Limitations

**1. Spotify Premium Required**
- Playback control requires Spotify Premium account
- Free accounts can only search/browse

**2. Device Must Be Active**
- Spotify Connect device must have Spotify app open
- Device appears in available devices list
- User may need to wake device before playback

**3. OAuth Initial Setup**
- First-time users must complete OAuth flow manually
- Requires browser access for authorization
- Subsequent uses work automatically via refresh tokens

**4. Single User Account**
- Current implementation supports one Spotify account
- Multi-user support requires per-user token storage (future enhancement)

### User Setup Steps

**1. Create Spotify App:**
```
Visit: https://developer.spotify.com/dashboard
Click: Create App
Set Redirect URI: http://localhost:8888/callback
Copy: Client ID and Client Secret
```

**2. Configure Environment:**
```bash
# Add to .env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

**3. Install spotipy:**
```bash
source venv/bin/activate
pip install spotipy>=2.23.0
```

**4. First OAuth Flow:**
```python
# Run once to authorize (spotipy handles browser flow)
python agent.py "what spotify devices are available?"
# Browser opens, user logs in and authorizes
# Token cached for future use
```

### Testing

**Run Tests:**
```bash
source venv/bin/activate
python -m pytest tests/integration/test_spotify.py -v
```

**Test Results:**
- 32 tests, 32 passed, 0 failed
- Execution time: ~0.5 seconds
- Coverage: All tools, OAuth flow, error handling

### Future Enhancements

**Phase 5 (Advanced Intelligence):**
- Music education context (REQ-027)
- Recently played tracking
- Playlist recommendations
- Music discovery agent integration

**Potential Improvements:**
- Multi-user token storage
- Playlist creation/modification
- Queue management
- Podcast support
- Lyrics integration
- Recently played history
- User library management (save/unsave tracks)
- Collaborative playlist support

### Dependencies

**New Dependencies:**
- spotipy>=2.23.0 (Spotify Web API client)

**Spotify Web API:**
- Authentication: OAuth 2.0 Authorization Code Flow
- Base URL: https://api.spotify.com/v1
- Rate Limits: Handled by spotipy library

### References

**Documentation:**
- Spotify Web API: https://developer.spotify.com/documentation/web-api
- spotipy Library: https://spotipy.readthedocs.io/
- OAuth 2.0 Flow: https://developer.spotify.com/documentation/web-api/tutorials/code-flow
- Spotify Connect: https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback

**Work Package:**
- Roadmap: WP-2.7 Spotify Integration
- Requirement: REQ-025
- Priority: HIGH (daily use case - living room Echo)

## Challenges and Solutions

**Challenge 1: Test Mocking Strategy**
- Initial tests tried to mock spotipy.Spotify directly
- Problem: Tools instantiate client internally via get_spotify_client()
- Solution: Mock get_spotify_client() instead, return mock with spotify attribute
- Result: Clean, fixture-based testing

**Challenge 2: OAuth Without Browser**
- spotipy expects interactive browser flow
- Problem: Server environments may not have browser
- Solution: Document manual OAuth process, cache tokens for reuse
- Result: User runs OAuth once, subsequent calls automatic

**Challenge 3: Device Name Matching**
- Users say "living room", device is "Living Room Echo Dot - Katherine's"
- Problem: Exact string match fails
- Solution: Fuzzy matching (exact first, then partial case-insensitive)
- Result: Natural language commands work seamlessly

**Challenge 4: Error Message Clarity**
- Spotify API errors can be cryptic
- Problem: User doesn't know why playback failed
- Solution: Wrap errors with context-aware messages
- Result: Clear feedback ("No devices available", "Premium required", etc.)

## Completion Status

**Completed:**
- SpotifyClient class with OAuth token management
- 5 tool functions (play, control, search, devices, transfer)
- 5 agent tool definitions
- 32 integration tests (100% passing)
- Agent integration
- Configuration setup
- Documentation

**User Testing Required:**
- Hardware validation with real Amazon Echo devices
- OAuth flow with real Spotify account
- Natural language command testing
- Device targeting accuracy
- Playback control responsiveness

**Ready for:**
- Natural language testing with Claude agent
- Real-world playback scenarios
- User acceptance testing

## Next Steps

1. User completes Spotify Developer app setup
2. User adds credentials to `.env`
3. User runs first OAuth flow to authorize
4. User tests natural language commands with Echo devices
5. User validates device targeting works correctly
6. Optional: Slack alerts for Spotify API errors (future work)

---

**Implementation Time:** ~3 hours (TDD approach)
**Lines of Code:** ~1,300 (tools + tests)
**Test Coverage:** 32 integration tests, 100% passing
**TDD Methodology:** Red-Green-Refactor cycle followed throughout
