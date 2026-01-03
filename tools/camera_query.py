"""
Smart Home Assistant - Camera Voice Query Tools

WP-11.5: Voice Query Support ("what did cat do today")

Enables voice queries to ask about camera events and activities:
- "what has the cat been up to today"
- "did I get any packages delivered"
- "who was at the front door this morning"
- "when did Sophie go outside"

Features:
- Natural language time range parsing (today, yesterday, this morning, etc.)
- Object type normalization (cat/kitty, dog/puppy, package/delivery)
- Query execution against camera observation store
- Summary generation from LLM descriptions
- Voice response formatting

Dependencies:
- WP-11.2: Camera Storage System (camera_store.py)
- WP-11.4: LLaVA Integration (vision_llm_client.py)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from src.camera_store import get_camera_store, CameraObservationStore
from src.utils import setup_logging


logger = setup_logging("tools.camera_query")


# =============================================================================
# Constants
# =============================================================================

# Object type synonyms for normalization
OBJECT_SYNONYMS = {
    # Cat-related terms
    "cat": ["cat", "kitty", "kitten", "feline", "cats"],
    # Dog-related terms
    "dog": ["dog", "puppy", "doggy", "pup", "dogs", "sophie"],  # Sophie is the user's dog
    # Person-related terms
    "person": ["person", "someone", "anyone", "somebody", "people", "human", "visitor", "visitors"],
    # Package-related terms
    "package": ["package", "delivery", "parcel", "packages", "deliveries", "box", "boxes", "amazon"],
    # Vehicle-related terms
    "vehicle": ["car", "truck", "vehicle", "van", "cars", "trucks", "vehicles"],
}

# Camera location keywords for filtering
CAMERA_LOCATIONS = {
    "front_door": ["front door", "front", "entrance", "doorbell", "porch"],
    "living_room": ["living room", "living"],
    "backyard": ["backyard", "back yard", "outside", "yard", "garden", "patio"],
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom"],
    "garage": ["garage", "driveway"],
}

# Time period keywords
TIME_PERIODS = {
    "morning": (0, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "night": (21, 24),
}

# Maximum voice response length for TTS
MAX_VOICE_RESPONSE_LENGTH = 200


# =============================================================================
# Tool Definitions for LLM
# =============================================================================

CAMERA_QUERY_TOOLS = [
    {
        "name": "query_camera_activity",
        "description": """Query camera observations to answer questions about activity.

Use this tool when the user asks about:
- What a pet (cat, dog) has been doing
- Package deliveries
- Who was at a door/location
- Activity in a specific room/area
- Recent motion events

The tool parses natural language queries and returns a spoken summary.

Examples:
- "what has the cat been up to today" -> query about cat activity
- "did I get any packages delivered" -> query about package sightings
- "who was at the front door this morning" -> query about front door visitors
- "when did Sophie go outside" -> query about dog going to backyard""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural language query about camera activity",
                },
            },
            "required": ["query"],
        },
    },
]


# =============================================================================
# Time Range Parsing
# =============================================================================


def parse_time_range(time_text: str) -> tuple[datetime, datetime]:
    """
    Parse natural language time range into start and end datetime.

    Args:
        time_text: Time reference like "today", "yesterday", "this morning", "last 3 hours"

    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    now = datetime.now()
    time_lower = time_text.lower().strip()

    # Default to today if empty
    if not time_lower:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    # Today
    if "today" in time_lower:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    # Yesterday
    if "yesterday" in time_lower:
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    # This morning
    if "morning" in time_lower:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now.hour < 12:
            end = now
        return start, end

    # This afternoon
    if "afternoon" in time_lower:
        start = now.replace(hour=12, minute=0, second=0, microsecond=0)
        end = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now.hour >= 12 and now.hour < 17:
            end = now
        elif now.hour < 12:
            # It's still morning, use yesterday afternoon
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=17, minute=0, second=0, microsecond=0)
        return start, end

    # This evening
    if "evening" in time_lower:
        start = now.replace(hour=17, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        if now.hour >= 17:
            end = now
        elif now.hour < 17:
            # It's still before evening, use yesterday evening
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=17, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    # Last hour
    if "last hour" in time_lower:
        start = now - timedelta(hours=1)
        return start, now

    # Last N hours
    hours_match = re.search(r"last\s+(\d+)\s+hours?", time_lower)
    if hours_match:
        hours = int(hours_match.group(1))
        start = now - timedelta(hours=hours)
        return start, now

    # This week
    if "this week" in time_lower or "week" in time_lower:
        # Start of week (Monday)
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start, now

    # Last month (limit to retention period)
    if "last month" in time_lower or "month" in time_lower:
        start = now - timedelta(days=30)
        return start, now

    # Tomorrow (future - default to today)
    if "tomorrow" in time_lower:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now

    # Specific date patterns (December 25th, etc.)
    date_patterns = [
        r"(?:on\s+)?(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?",  # December 25th
        r"(\d{1,2})/(\d{1,2})",  # 12/25
    ]

    for pattern in date_patterns:
        match = re.search(pattern, time_lower)
        if match:
            try:
                month_names = {
                    "january": 1, "february": 2, "march": 3, "april": 4,
                    "may": 5, "june": 6, "july": 7, "august": 8,
                    "september": 9, "october": 10, "november": 11, "december": 12,
                }
                if match.group(1).lower() in month_names:
                    month = month_names[match.group(1).lower()]
                    day = int(match.group(2))
                    year = now.year
                    target_date = datetime(year, month, day)
                    if target_date > now:
                        target_date = target_date.replace(year=year - 1)
                    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                    return start, end
            except (ValueError, KeyError):
                pass

    # Default to today
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


# =============================================================================
# Object Type Normalization
# =============================================================================


def normalize_object_type(object_text: str) -> str:
    """
    Normalize an object type to a standard term.

    Args:
        object_text: Object reference like "kitty", "puppy", "Sophie", "parcel"

    Returns:
        Normalized object type (cat, dog, person, package, vehicle)
    """
    text_lower = object_text.lower().strip()

    # Remove articles
    text_lower = re.sub(r"^(the|a|an)\s+", "", text_lower)

    for canonical, synonyms in OBJECT_SYNONYMS.items():
        if text_lower in synonyms:
            return canonical

    # Check partial matches
    for canonical, synonyms in OBJECT_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in text_lower:
                return canonical

    # Return original if no match
    return text_lower


# =============================================================================
# Query Parsing
# =============================================================================


def parse_camera_query(query: str) -> dict[str, Any]:
    """
    Parse a natural language camera query.

    Args:
        query: Natural language query like "what has the cat been up to today"

    Returns:
        Dictionary with parsed components:
        - object_type: Detected object (cat, dog, person, package)
        - time_range: Parsed time reference (today, yesterday, etc.)
        - time_context: Original time text
        - camera_filter: Detected camera location filter
        - camera_hint: Original camera location text
    """
    query_lower = query.lower().strip()

    result = {
        "original_query": query,
        "object_type": None,
        "time_range": None,
        "time_context": "",
        "camera_filter": None,
        "camera_hint": "",
    }

    # Handle empty query
    if not query_lower:
        result["object_type"] = None
        return result

    # Check for "who" questions implying person
    if query_lower.startswith("who ") or " who " in query_lower:
        result["object_type"] = "person"

    # Extract object type from synonyms (override if explicit object mentioned)
    for canonical, synonyms in OBJECT_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in query_lower:
                result["object_type"] = canonical
                break
        if result["object_type"] and result["object_type"] != "person":
            break
        if canonical != "person" and result["object_type"] == canonical:
            break

    # Extract time reference
    time_patterns = [
        r"(today)",
        r"(yesterday)",
        r"(this morning)",
        r"(this afternoon)",
        r"(this evening)",
        r"(tonight)",
        r"(last hour)",
        r"(last \d+ hours?)",
        r"(this week)",
        r"(last week)",
        r"(on \w+ \d+(?:st|nd|rd|th)?)",
    ]

    for pattern in time_patterns:
        match = re.search(pattern, query_lower)
        if match:
            result["time_context"] = match.group(1)
            result["time_range"] = match.group(1)
            break

    # If no time found, check for implicit "today"
    if not result["time_range"]:
        result["time_range"] = "today"
        result["time_context"] = "today"

    # Extract camera/location filter
    for camera_id, keywords in CAMERA_LOCATIONS.items():
        for keyword in keywords:
            if keyword in query_lower:
                result["camera_filter"] = camera_id
                result["camera_hint"] = keyword
                break
        if result["camera_filter"]:
            break

    # Handle ambiguous queries
    if not result["object_type"]:
        # Check for "activity" queries
        if "activity" in query_lower or "motion" in query_lower:
            result["object_type"] = None  # Will query all objects
        elif "happen" in query_lower or "going on" in query_lower:
            result["object_type"] = None

    return result


# =============================================================================
# Query Execution
# =============================================================================


def execute_camera_query(
    store: CameraObservationStore | None = None,
    object_type: str | None = None,
    time_range: str = "today",
    camera_filter: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Execute a camera query against the observation store.

    Args:
        store: Camera observation store (uses global if not provided)
        object_type: Object type to filter (cat, dog, person, package)
        time_range: Time range text (today, yesterday, etc.)
        camera_filter: Camera ID fragment to filter (front_door, living_room)
        limit: Maximum results to return

    Returns:
        Dictionary with query results:
        - success: Whether query succeeded
        - observations: List of matching observations
        - count: Number of results
    """
    if store is None:
        store = get_camera_store()

    try:
        # Parse time range
        start_time, end_time = parse_time_range(time_range)

        # Build camera filter
        camera_id = None
        if camera_filter:
            camera_id = f"camera.{camera_filter}"

        # Query observations
        if object_type:
            observations = store.query_by_object(
                object_type=object_type,
                start_time=start_time,
                end_time=end_time,
                camera_id=camera_id,
                limit=limit,
            )
        else:
            # General activity query
            observations = store.get_observations(
                camera_id=camera_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )

        return {
            "success": True,
            "observations": observations,
            "count": len(observations),
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
        }

    except Exception as error:
        logger.error(f"Query execution error: {error}")
        return {
            "success": False,
            "error": str(error),
            "observations": [],
            "count": 0,
        }


# =============================================================================
# Summary Generation
# =============================================================================


def generate_activity_summary(
    observations: list[dict],
    object_type: str | None = None,
    time_range: str = "today",
) -> str:
    """
    Generate a voice-friendly summary from observations.

    Args:
        observations: List of observation dictionaries
        object_type: Object type being queried
        time_range: Time range text for context

    Returns:
        Natural language summary suitable for voice response
    """
    if not observations:
        # No results
        if object_type:
            return f"I didn't see any {object_type} activity {time_range}."
        else:
            return f"I didn't detect any activity {time_range}."

    count = len(observations)

    # Build summary parts
    parts = []

    if object_type:
        if count == 1:
            parts.append(f"The {object_type} was seen once {time_range}.")
        else:
            parts.append(f"The {object_type} was seen {count} times {time_range}.")
    else:
        if count == 1:
            parts.append(f"There was 1 activity event {time_range}.")
        else:
            parts.append(f"There were {count} activity events {time_range}.")

    # Add recent descriptions (limit to most recent 3)
    recent = observations[:3]
    now = datetime.now()

    for obs in recent:
        timestamp_str = obs.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
                time_diff = now - timestamp

                if time_diff.total_seconds() < 3600:
                    minutes = int(time_diff.total_seconds() / 60)
                    time_desc = f"{minutes} minutes ago"
                elif time_diff.total_seconds() < 86400:
                    hours = int(time_diff.total_seconds() / 3600)
                    time_desc = f"{hours} hours ago" if hours > 1 else "1 hour ago"
                else:
                    time_desc = timestamp.strftime("%I:%M %p")
            except (ValueError, TypeError):
                time_desc = ""
        else:
            time_desc = ""

        camera_id = obs.get("camera_id", "")
        location = camera_id.replace("camera.", "").replace("_", " ") if camera_id else "unknown"

        description = obs.get("llm_description", "")
        if description:
            # Truncate description if too long
            if len(description) > 80:
                description = description[:77] + "..."

            if time_desc:
                parts.append(f"At {time_desc} in the {location}: {description}")
            else:
                parts.append(f"In the {location}: {description}")

    # Join parts
    summary = " ".join(parts)

    return summary


# =============================================================================
# Voice Response Formatting
# =============================================================================


def format_for_voice(text: str, max_length: int = MAX_VOICE_RESPONSE_LENGTH) -> str:
    """
    Format text for voice output (TTS).

    Args:
        text: Summary text
        max_length: Maximum character length

    Returns:
        Formatted text suitable for TTS
    """
    if not text:
        return ""

    # Ensure ends with punctuation
    text = text.strip()
    if not text.endswith((".", "!", "?")):
        text += "."

    # Truncate if too long
    if len(text) > max_length:
        # Find last sentence that fits
        sentences = re.split(r"(?<=[.!?])\s+", text)
        result = ""

        for sentence in sentences:
            if len(result) + len(sentence) + 1 <= max_length:
                result += sentence + " "
            else:
                break

        if not result:
            # Single sentence too long, truncate
            result = text[: max_length - 3] + "..."

        text = result.strip()

    return text


# =============================================================================
# Voice Query Handler
# =============================================================================


def handle_voice_query(query: str) -> dict[str, Any]:
    """
    Handle a voice query about camera activity.

    This is the main entry point for voice queries.

    Args:
        query: Natural language query

    Returns:
        Dictionary with:
        - success: Whether query succeeded
        - response: Voice response text
        - observations: Raw observation data (if successful)
    """
    try:
        # Parse the query
        parsed = parse_camera_query(query)

        # Execute the query
        result = execute_camera_query(
            object_type=parsed.get("object_type"),
            time_range=parsed.get("time_range", "today"),
            camera_filter=parsed.get("camera_filter"),
        )

        if not result["success"]:
            return {
                "success": False,
                "error": result.get("error", "Query failed"),
                "response": "I'm sorry, I couldn't check the camera activity right now.",
            }

        # Generate summary
        summary = generate_activity_summary(
            observations=result["observations"],
            object_type=parsed.get("object_type"),
            time_range=parsed.get("time_range", "today"),
        )

        # Format for voice
        response = format_for_voice(summary)

        return {
            "success": True,
            "response": response,
            "observations": result["observations"],
            "count": result["count"],
            "parsed_query": parsed,
        }

    except Exception as error:
        logger.error(f"Voice query error: {error}")
        return {
            "success": False,
            "error": str(error),
            "response": "I'm sorry, I couldn't process your camera query.",
        }


# =============================================================================
# Tool Execution Entry Point
# =============================================================================


def execute_camera_query_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a camera query tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing camera query tool: {tool_name}")

    if tool_name == "query_camera_activity":
        query = tool_input.get("query", "")
        return handle_voice_query(query)

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
