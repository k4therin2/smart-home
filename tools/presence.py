"""
Smart Home Assistant - Presence Detection Tools

Agent tools for managing user presence, device trackers, and vacuum automation.
Part of WP-8.1: Presence-Based Automation.
"""

from typing import Any

from src.presence_manager import PresenceManager
from src.utils import setup_logging


logger = setup_logging("tools.presence")

# Singleton instance
_presence_manager: PresenceManager | None = None


def get_presence_manager() -> PresenceManager:
    """Get or create the singleton PresenceManager instance."""
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager


# Tool definitions for Claude
PRESENCE_TOOLS = [
    {
        "name": "get_presence_status",
        "description": """Get the user's current presence status.

Returns the presence state (home, away, arriving, leaving), confidence level,
and when it was last updated.

Examples:
- "am I home?" -> Get presence status
- "where am I?" -> Get presence status (if asking about home/away)
- "is anyone home?" -> Get presence status
- "what's my presence status?" -> Get presence status

Use this to check if the user is home before automations.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_presence_mode",
        "description": """Manually set the presence mode (override automatic detection).

Use when the user explicitly says they're leaving or arriving home.
Manual overrides have highest confidence and take priority over trackers.

Parameters:
- state: 'home', 'away', 'arriving', or 'leaving'
- duration_minutes: Optional - auto-clear override after N minutes

Examples:
- "I'm leaving" -> state='leaving'
- "I'm going out" -> state='away'
- "I'm home" -> state='home'
- "I'll be gone for 2 hours" -> state='away', duration_minutes=120
- "I'm almost home" -> state='arriving'

This triggers automations like starting/stopping the vacuum.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["home", "away", "arriving", "leaving"],
                    "description": "Presence state to set",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Optional: Minutes until override expires and reverts to automatic detection",
                },
            },
            "required": ["state"],
        },
    },
    {
        "name": "get_presence_history",
        "description": """Get presence change history.

Returns a list of recent presence state changes with timestamps.
Useful for debugging or checking patterns.

Parameters:
- limit: Maximum number of entries to return (default 10)

Examples:
- "show my presence history" -> Get recent history
- "when did I last leave?" -> Check history for departure times
- "show last 5 presence changes" -> limit=5""",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of history entries to return (default 10)",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
    {
        "name": "register_presence_tracker",
        "description": """Register a Home Assistant device tracker for presence detection.

Adds a device tracker (phone GPS, router, etc.) to presence monitoring.
Multiple trackers combine for higher confidence.

Parameters:
- entity_id: HA entity ID like 'device_tracker.phone'
- source_type: Type of tracker ('gps', 'router', 'bluetooth')
- display_name: Optional friendly name
- priority: Optional priority (1-15, higher = more trusted, default varies by type)

Examples:
- "add my phone as a presence tracker" -> entity_id='device_tracker.phone', source_type='gps'
- "register the router tracker" -> entity_id='device_tracker.router', source_type='router'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Home Assistant entity ID (e.g., 'device_tracker.phone')",
                },
                "source_type": {
                    "type": "string",
                    "enum": ["gps", "router", "bluetooth", "unknown"],
                    "description": "Type of device tracker",
                },
                "display_name": {
                    "type": "string",
                    "description": "Optional friendly name for the tracker",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority level 1-15 (higher = more trusted)",
                },
            },
            "required": ["entity_id", "source_type"],
        },
    },
    {
        "name": "list_presence_trackers",
        "description": """List all registered presence trackers.

Shows all device trackers being monitored for presence detection,
their types, priorities, and last known states.

Examples:
- "what trackers do I have?" -> List all trackers
- "show presence trackers" -> List all trackers
- "list my presence devices" -> List all trackers""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "predict_departure",
        "description": """Predict typical departure time based on learned patterns.

Uses historical departure data to predict when the user typically leaves
on a given day of the week. Requires at least 3 data points.

Parameters:
- day_of_week: 0=Monday, 1=Tuesday, ..., 6=Sunday (default: today)

Examples:
- "when do I usually leave?" -> Predict for today
- "what time do I leave on Mondays?" -> day_of_week=0
- "predict my departure for Friday" -> day_of_week=4""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_of_week": {
                    "type": "integer",
                    "description": "Day of week (0=Monday to 6=Sunday). Default is today.",
                    "minimum": 0,
                    "maximum": 6,
                }
            },
            "required": [],
        },
    },
    {
        "name": "predict_arrival",
        "description": """Predict typical arrival time based on learned patterns.

Uses historical arrival data to predict when the user typically arrives
on a given day of the week. Requires at least 3 data points.

Parameters:
- day_of_week: 0=Monday, 1=Tuesday, ..., 6=Sunday (default: today)

Examples:
- "when do I usually get home?" -> Predict for today
- "what time do I arrive on weekdays?" -> Predict for Monday-Friday
- "predict my arrival for Saturday" -> day_of_week=5""",
        "input_schema": {
            "type": "object",
            "properties": {
                "day_of_week": {
                    "type": "integer",
                    "description": "Day of week (0=Monday to 6=Sunday). Default is today.",
                    "minimum": 0,
                    "maximum": 6,
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_presence_settings",
        "description": """Get current presence detection settings.

Returns settings like home zone radius, arriving distance,
and vacuum automation delay.

Examples:
- "show presence settings" -> Get all settings
- "what are my presence detection settings?" -> Get all settings""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_vacuum_delay",
        "description": """Set how long to wait before starting vacuum after departure.

The vacuum starts after this delay to confirm you've actually left,
not just stepped outside briefly.

Parameters:
- minutes: Delay in minutes before starting vacuum

Examples:
- "start vacuum 5 minutes after I leave" -> minutes=5
- "set vacuum delay to 10 minutes" -> minutes=10
- "wait 15 minutes before vacuuming" -> minutes=15""",
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "description": "Minutes to wait before starting vacuum after departure",
                    "minimum": 0,
                    "maximum": 60,
                }
            },
            "required": ["minutes"],
        },
    },
    {
        "name": "discover_ha_trackers",
        "description": """Discover available device trackers from Home Assistant.

Scans Home Assistant for all device_tracker entities that could be
used for presence detection. Returns list of available trackers.

Examples:
- "find device trackers" -> Discover from HA
- "what trackers are available?" -> Discover from HA
- "scan for presence trackers" -> Discover from HA""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sync_presence_from_ha",
        "description": """Sync presence state from Home Assistant device trackers.

Updates presence based on current state of all registered trackers.
Use this to manually refresh presence after HA state changes.

Examples:
- "sync presence" -> Update from all trackers
- "refresh presence status" -> Update from all trackers""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ========== Tool Handler Functions ==========


def get_presence_status() -> dict[str, Any]:
    """Get the user's current presence status."""
    try:
        manager = get_presence_manager()
        state = manager.get_presence_state()

        return {
            "success": True,
            "state": state.get("state", "unknown"),
            "source": state.get("source", "unknown"),
            "confidence": state.get("confidence", 0.0),
            "updated_at": state.get("updated_at"),
            "message": f"You are currently {state.get('state', 'unknown')} "
            f"(confidence: {state.get('confidence', 0.0):.0%})",
        }
    except Exception as error:
        logger.error(f"Error getting presence status: {error}")
        return {"success": False, "error": str(error)}


def set_presence_mode(state: str, duration_minutes: int | None = None) -> dict[str, Any]:
    """Manually set presence mode."""
    try:
        manager = get_presence_manager()
        result = manager.manual_set_presence(state, duration_minutes)

        message = f"Presence set to {state}"
        if duration_minutes:
            message += f" (will expire in {duration_minutes} minutes)"

        return {
            "success": result,
            "state": state,
            "duration_minutes": duration_minutes,
            "message": message,
        }
    except ValueError as error:
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Error setting presence mode: {error}")
        return {"success": False, "error": str(error)}


def get_presence_history(limit: int = 10) -> dict[str, Any]:
    """Get presence change history."""
    try:
        manager = get_presence_manager()
        history = manager.get_presence_history(limit=limit)

        return {
            "success": True,
            "count": len(history),
            "history": history,
            "message": f"Found {len(history)} presence history entries",
        }
    except Exception as error:
        logger.error(f"Error getting presence history: {error}")
        return {"success": False, "error": str(error)}


def register_presence_tracker(
    entity_id: str, source_type: str, display_name: str | None = None, priority: int | None = None
) -> dict[str, Any]:
    """Register a device tracker for presence detection."""
    try:
        manager = get_presence_manager()
        result = manager.register_device_tracker(
            entity_id=entity_id,
            source_type=source_type,
            display_name=display_name,
            priority=priority,
        )

        return {
            "success": result,
            "entity_id": entity_id,
            "source_type": source_type,
            "message": f"Registered {entity_id} as a {source_type} tracker",
        }
    except Exception as error:
        logger.error(f"Error registering tracker: {error}")
        return {"success": False, "error": str(error)}


def list_presence_trackers() -> dict[str, Any]:
    """List all registered presence trackers."""
    try:
        manager = get_presence_manager()
        trackers = manager.list_device_trackers()

        return {
            "success": True,
            "count": len(trackers),
            "trackers": trackers,
            "message": f"Found {len(trackers)} registered presence trackers",
        }
    except Exception as error:
        logger.error(f"Error listing trackers: {error}")
        return {"success": False, "error": str(error)}


def predict_departure(day_of_week: int | None = None) -> dict[str, Any]:
    """Predict typical departure time."""
    try:
        from datetime import datetime

        manager = get_presence_manager()

        if day_of_week is None:
            day_of_week = datetime.now().weekday()

        prediction = manager.predict_departure(day_of_week)

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[day_of_week]

        if prediction:
            return {
                "success": True,
                "day": day_name,
                "hour": prediction["hour"],
                "minute": prediction["minute"],
                "confidence": prediction["confidence"],
                "data_points": prediction.get("data_points", 0),
                "message": f"On {day_name}s, you typically leave around "
                f"{prediction['hour']:02d}:{prediction['minute']:02d} "
                f"(confidence: {prediction['confidence']:.0%})",
            }
        else:
            return {
                "success": True,
                "day": day_name,
                "prediction": None,
                "message": f"Not enough data to predict departure time for {day_name}s. "
                "Need at least 3 departure records.",
            }
    except Exception as error:
        logger.error(f"Error predicting departure: {error}")
        return {"success": False, "error": str(error)}


def predict_arrival(day_of_week: int | None = None) -> dict[str, Any]:
    """Predict typical arrival time."""
    try:
        from datetime import datetime

        manager = get_presence_manager()

        if day_of_week is None:
            day_of_week = datetime.now().weekday()

        prediction = manager.predict_arrival(day_of_week)

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = day_names[day_of_week]

        if prediction:
            return {
                "success": True,
                "day": day_name,
                "hour": prediction["hour"],
                "minute": prediction["minute"],
                "confidence": prediction["confidence"],
                "data_points": prediction.get("data_points", 0),
                "message": f"On {day_name}s, you typically arrive around "
                f"{prediction['hour']:02d}:{prediction['minute']:02d} "
                f"(confidence: {prediction['confidence']:.0%})",
            }
        else:
            return {
                "success": True,
                "day": day_name,
                "prediction": None,
                "message": f"Not enough data to predict arrival time for {day_name}s. "
                "Need at least 3 arrival records.",
            }
    except Exception as error:
        logger.error(f"Error predicting arrival: {error}")
        return {"success": False, "error": str(error)}


def get_presence_settings() -> dict[str, Any]:
    """Get presence detection settings."""
    try:
        manager = get_presence_manager()
        settings = manager.get_settings()

        return {
            "success": True,
            "settings": settings,
            "message": f"Home zone: {settings['home_zone_radius']}m, "
            f"Arriving distance: {settings['arriving_distance']}m, "
            f"Vacuum delay: {settings['vacuum_start_delay']} minutes",
        }
    except Exception as error:
        logger.error(f"Error getting settings: {error}")
        return {"success": False, "error": str(error)}


def set_vacuum_delay(minutes: int) -> dict[str, Any]:
    """Set vacuum start delay after departure."""
    try:
        manager = get_presence_manager()
        result = manager.set_vacuum_start_delay(minutes)

        return {
            "success": result,
            "delay_minutes": minutes,
            "message": f"Vacuum will now start {minutes} minutes after you leave",
        }
    except Exception as error:
        logger.error(f"Error setting vacuum delay: {error}")
        return {"success": False, "error": str(error)}


def discover_ha_trackers() -> dict[str, Any]:
    """Discover device trackers from Home Assistant."""
    try:
        manager = get_presence_manager()
        trackers = manager.discover_ha_trackers()

        return {
            "success": True,
            "count": len(trackers),
            "trackers": trackers,
            "message": f"Found {len(trackers)} device trackers in Home Assistant",
        }
    except Exception as error:
        logger.error(f"Error discovering trackers: {error}")
        return {"success": False, "error": str(error)}


def sync_presence_from_ha() -> dict[str, Any]:
    """Sync presence from all registered HA trackers."""
    try:
        manager = get_presence_manager()
        trackers = manager.list_device_trackers()

        synced = 0
        for tracker in trackers:
            if tracker.get("enabled"):
                if manager.sync_tracker_from_ha(tracker["entity_id"]):
                    synced += 1

        state = manager.get_presence_state()

        return {
            "success": True,
            "trackers_synced": synced,
            "current_state": state.get("state", "unknown"),
            "confidence": state.get("confidence", 0.0),
            "message": f"Synced {synced} trackers. Current status: {state.get('state', 'unknown')}",
        }
    except Exception as error:
        logger.error(f"Error syncing presence: {error}")
        return {"success": False, "error": str(error)}


def execute_presence_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a presence tool by name."""
    logger.info(f"Executing presence tool: {tool_name}")

    if tool_name == "get_presence_status":
        return get_presence_status()

    elif tool_name == "set_presence_mode":
        return set_presence_mode(
            state=tool_input.get("state", "unknown"),
            duration_minutes=tool_input.get("duration_minutes"),
        )

    elif tool_name == "get_presence_history":
        return get_presence_history(limit=tool_input.get("limit", 10))

    elif tool_name == "register_presence_tracker":
        return register_presence_tracker(
            entity_id=tool_input.get("entity_id", ""),
            source_type=tool_input.get("source_type", "unknown"),
            display_name=tool_input.get("display_name"),
            priority=tool_input.get("priority"),
        )

    elif tool_name == "list_presence_trackers":
        return list_presence_trackers()

    elif tool_name == "predict_departure":
        return predict_departure(day_of_week=tool_input.get("day_of_week"))

    elif tool_name == "predict_arrival":
        return predict_arrival(day_of_week=tool_input.get("day_of_week"))

    elif tool_name == "get_presence_settings":
        return get_presence_settings()

    elif tool_name == "set_vacuum_delay":
        return set_vacuum_delay(minutes=tool_input.get("minutes", 5))

    elif tool_name == "discover_ha_trackers":
        return discover_ha_trackers()

    elif tool_name == "sync_presence_from_ha":
        return sync_presence_from_ha()

    else:
        return {"success": False, "error": f"Unknown presence tool: {tool_name}"}
