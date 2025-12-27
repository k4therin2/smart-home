"""
Smart Home Assistant - Timer and Alarm Tools

Agent tools for managing countdown timers and scheduled alarms.
Part of WP-4.3: Timers & Alarms feature.
"""

from datetime import datetime
from typing import Any

from src.timer_manager import get_timer_manager
from src.utils import setup_logging


logger = setup_logging("tools.timers")

# Tool definitions for Claude
TIMER_TOOLS = [
    {
        "name": "set_timer",
        "description": """Set a countdown timer.

Examples:
- "set a timer for 10 minutes" -> duration='10 minutes'
- "set a 5 minute timer for pasta" -> duration='5 minutes', name='pasta'
- "set a timer for 1 hour 30 minutes" -> duration='1 hour 30 minutes'
- "set a pizza timer for 20 min" -> name='pizza', duration='20 min'

Duration formats: '10 minutes', '2 hours', '30 seconds', '1 hour 30 min'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "duration": {
                    "type": "string",
                    "description": "Timer duration in natural language (e.g., '10 minutes', '1 hour 30 min')",
                },
                "name": {
                    "type": "string",
                    "description": "Optional name for the timer (e.g., 'pizza', 'laundry')",
                },
            },
            "required": ["duration"],
        },
    },
    {
        "name": "list_timers",
        "description": """Show all active timers with their remaining time.

Use this when the user asks:
- "how much time is left on my timer?"
- "what timers do I have?"
- "check my timers"

Returns a list of all running timers with remaining time.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_timer",
        "description": """Cancel an active timer.

Examples:
- "cancel the pizza timer" -> name='pizza'
- "stop my timer" -> (cancels most recent timer if only one active)
- "cancel all timers" -> cancel_all=true

Can cancel by name or by ID.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "timer_id": {"type": "integer", "description": "Timer ID to cancel (if known)"},
                "name": {"type": "string", "description": "Name of timer to cancel (fuzzy match)"},
                "cancel_all": {
                    "type": "boolean",
                    "description": "Cancel all active timers",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "set_alarm",
        "description": """Set an alarm for a specific time.

Examples:
- "set an alarm for 7am" -> time='7am'
- "set an alarm for 7:30pm" -> time='7:30pm'
- "wake me up at 6:30am" -> time='6:30am', name='wake up'
- "set an alarm for tomorrow at 8am" -> time='tomorrow at 8am'
- "set a weekday alarm for 7am" -> time='7am', repeat_days=['monday','tuesday','wednesday','thursday','friday']

Time formats: '7am', '7:30pm', '15:30', 'tomorrow at 7am'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "time": {
                    "type": "string",
                    "description": "Alarm time in natural language (e.g., '7am', '7:30pm', 'tomorrow at 8am')",
                },
                "name": {"type": "string", "description": "Optional name for the alarm"},
                "repeat_days": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Days to repeat (e.g., ['monday', 'friday'])",
                },
            },
            "required": ["time"],
        },
    },
    {
        "name": "list_alarms",
        "description": """Show all active alarms.

Use this when the user asks:
- "what alarms do I have?"
- "show my alarms"
- "when is my next alarm?"

Returns all pending alarms with their scheduled times.""",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cancel_alarm",
        "description": """Cancel an alarm.

Examples:
- "cancel my 7am alarm" -> name='7am' or time_match='7am'
- "delete the wake up alarm" -> name='wake up'
- "cancel all alarms" -> cancel_all=true

Can cancel by name, time match, or ID.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "alarm_id": {"type": "integer", "description": "Alarm ID to cancel (if known)"},
                "name": {"type": "string", "description": "Name of alarm to cancel"},
                "time_match": {"type": "string", "description": "Time to match (e.g., '7am')"},
                "cancel_all": {
                    "type": "boolean",
                    "description": "Cancel all active alarms",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "snooze_alarm",
        "description": """Snooze an alarm that is ringing or was recently triggered.

Examples:
- "snooze" -> snooze most recent alarm for 10 minutes
- "snooze for 5 minutes" -> minutes=5
- "snooze the wake up alarm" -> name='wake up'

Default snooze duration is 10 minutes.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "alarm_id": {"type": "integer", "description": "Alarm ID to snooze (if known)"},
                "name": {"type": "string", "description": "Name of alarm to snooze"},
                "minutes": {
                    "type": "integer",
                    "description": "Minutes to snooze (default 10)",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
]


def _format_remaining_time(seconds: int) -> str:
    """Format seconds as human-readable remaining time."""
    if seconds <= 0:
        return "done"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if minutes > 0:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    if secs > 0 and hours == 0:
        parts.append(f"{secs} second" + ("s" if secs != 1 else ""))

    return " ".join(parts) if parts else "less than a second"


def _format_timers(timers: list[dict]) -> str:
    """Format timer list for voice/text output."""
    if not timers:
        return "No active timers."

    manager = get_timer_manager()
    lines = [f"You have {len(timers)} active timer" + ("s" if len(timers) != 1 else "") + ":"]

    for timer in timers:
        remaining = manager.get_remaining_seconds(timer["id"])
        remaining_str = _format_remaining_time(remaining)
        name_str = f" ({timer['name']})" if timer.get("name") else ""
        lines.append(f"- {remaining_str} remaining{name_str}")

    return "\n".join(lines)


def _format_alarms(alarms: list[dict]) -> str:
    """Format alarm list for voice/text output."""
    if not alarms:
        return "No alarms set."

    lines = [f"You have {len(alarms)} alarm" + ("s" if len(alarms) != 1 else "") + ":"]

    for alarm in alarms:
        alarm_time = datetime.fromisoformat(alarm["alarm_time"])
        time_str = alarm_time.strftime("%I:%M %p on %A")
        name_str = f" ({alarm['name']})" if alarm.get("name") else ""

        repeat_str = ""
        if alarm.get("repeat_days"):
            days = alarm["repeat_days"]
            if len(days) == 7:
                repeat_str = " (daily)"
            elif len(days) == 5 and "saturday" not in days and "sunday" not in days:
                repeat_str = " (weekdays)"
            else:
                repeat_str = f" ({', '.join(day[:3] for day in days)})"

        lines.append(f"- {time_str}{name_str}{repeat_str}")

    return "\n".join(lines)


def set_timer(
    duration: str,
    name: str | None = None,
) -> dict[str, Any]:
    """
    Set a countdown timer.

    Args:
        duration: Duration string (e.g., '10 minutes', '1 hour 30 min')
        name: Optional timer name

    Returns:
        Result dictionary with success status
    """
    if not duration or not duration.strip():
        return {"success": False, "error": "Duration is required"}

    try:
        manager = get_timer_manager()

        # Parse duration
        seconds = manager.parse_duration(duration)
        if not seconds:
            return {
                "success": False,
                "error": f"Could not understand duration '{duration}'. Try '10 minutes' or '1 hour 30 min'.",
            }

        # Create timer
        timer_id = manager.create_timer(duration_seconds=seconds, name=name)

        duration_str = manager.format_duration(seconds)
        name_msg = f" called '{name}'" if name else ""

        logger.info(f"Set timer: {duration_str}{name_msg}")

        return {
            "success": True,
            "timer_id": timer_id,
            "duration_seconds": seconds,
            "name": name,
            "message": f"Timer set for {duration_str}{name_msg}.",
        }

    except Exception as error:
        logger.error(f"Error setting timer: {error}")
        return {"success": False, "error": str(error)}


def list_timers() -> dict[str, Any]:
    """
    Get all active timers.

    Returns:
        Result dictionary with timers
    """
    try:
        manager = get_timer_manager()
        timers = manager.get_active_timers()

        # Add remaining time to each timer
        for timer in timers:
            timer["remaining_seconds"] = manager.get_remaining_seconds(timer["id"])

        return {
            "success": True,
            "timers": timers,
            "count": len(timers),
            "message": _format_timers(timers),
        }

    except Exception as error:
        logger.error(f"Error listing timers: {error}")
        return {"success": False, "error": str(error)}


def cancel_timer(
    timer_id: int | None = None,
    name: str | None = None,
    cancel_all: bool = False,
) -> dict[str, Any]:
    """
    Cancel a timer.

    Args:
        timer_id: Timer ID to cancel
        name: Timer name to match
        cancel_all: Cancel all active timers

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_timer_manager()

        if cancel_all:
            timers = manager.get_active_timers()
            count = 0
            for timer in timers:
                if manager.cancel_timer(timer["id"]):
                    count += 1
            logger.info(f"Cancelled {count} timers")
            return {
                "success": True,
                "cancelled_count": count,
                "message": f"Cancelled {count} timer" + ("s" if count != 1 else "") + ".",
            }

        if timer_id:
            success = manager.cancel_timer(timer_id)
            if success:
                logger.info(f"Cancelled timer {timer_id}")
                return {"success": True, "message": f"Timer {timer_id} cancelled."}
            else:
                return {
                    "success": False,
                    "error": f"Timer {timer_id} not found or already cancelled.",
                }

        if name:
            timer = manager.get_timer_by_name(name)
            if timer:
                success = manager.cancel_timer(timer["id"])
                if success:
                    logger.info(f"Cancelled timer '{name}'")
                    return {
                        "success": True,
                        "message": f"Cancelled the {timer.get('name', '')} timer.",
                    }
            return {"success": False, "error": f"No active timer matching '{name}' found."}

        # No specific timer - cancel the most recent one if only one active
        timers = manager.get_active_timers()
        if len(timers) == 1:
            timer = timers[0]
            manager.cancel_timer(timer["id"])
            name_str = f" ({timer['name']})" if timer.get("name") else ""
            return {"success": True, "message": f"Timer cancelled{name_str}."}
        elif len(timers) > 1:
            return {
                "success": False,
                "error": "Multiple timers active. Please specify which one to cancel by name.",
                "active_timers": [t.get("name") or f"Timer {t['id']}" for t in timers],
            }
        else:
            return {"success": False, "error": "No active timers to cancel."}

    except Exception as error:
        logger.error(f"Error cancelling timer: {error}")
        return {"success": False, "error": str(error)}


def set_alarm(
    time: str,
    name: str | None = None,
    repeat_days: list[str] | None = None,
) -> dict[str, Any]:
    """
    Set an alarm.

    Args:
        time: Alarm time (e.g., '7am', 'tomorrow at 8am')
        name: Optional alarm name
        repeat_days: Days to repeat (e.g., ['monday', 'friday'])

    Returns:
        Result dictionary with success status
    """
    if not time or not time.strip():
        return {"success": False, "error": "Time is required"}

    try:
        manager = get_timer_manager()

        # Parse alarm time
        alarm_time = manager.parse_alarm_time(time)
        if not alarm_time:
            return {
                "success": False,
                "error": f"Could not understand time '{time}'. Try '7am', '7:30pm', or 'tomorrow at 8am'.",
            }

        # Validate repeat days
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if repeat_days:
            normalized_days = [day.lower() for day in repeat_days]
            invalid = [day for day in normalized_days if day not in valid_days]
            if invalid:
                return {
                    "success": False,
                    "error": f"Invalid day(s): {', '.join(invalid)}. Use full day names like 'monday', 'friday'.",
                }
            repeat_days = normalized_days

        # Create alarm
        alarm_id = manager.create_alarm(
            alarm_time=alarm_time,
            name=name,
            repeat_days=repeat_days,
        )

        time_str = alarm_time.strftime("%I:%M %p on %A, %B %d")
        name_msg = f" called '{name}'" if name else ""
        repeat_msg = ""
        if repeat_days:
            if len(repeat_days) == 7:
                repeat_msg = " (repeating daily)"
            elif (
                len(repeat_days) == 5
                and "saturday" not in repeat_days
                and "sunday" not in repeat_days
            ):
                repeat_msg = " (repeating weekdays)"
            else:
                repeat_msg = f" (repeating {', '.join(day[:3] for day in repeat_days)})"

        logger.info(f"Set alarm: {time_str}{name_msg}{repeat_msg}")

        return {
            "success": True,
            "alarm_id": alarm_id,
            "alarm_time": alarm_time.isoformat(),
            "name": name,
            "repeat_days": repeat_days,
            "message": f"Alarm set for {time_str}{name_msg}{repeat_msg}.",
        }

    except ValueError as error:
        return {"success": False, "error": str(error)}
    except Exception as error:
        logger.error(f"Error setting alarm: {error}")
        return {"success": False, "error": str(error)}


def list_alarms() -> dict[str, Any]:
    """
    Get all active alarms.

    Returns:
        Result dictionary with alarms
    """
    try:
        manager = get_timer_manager()
        alarms = manager.get_active_alarms()

        return {
            "success": True,
            "alarms": alarms,
            "count": len(alarms),
            "message": _format_alarms(alarms),
        }

    except Exception as error:
        logger.error(f"Error listing alarms: {error}")
        return {"success": False, "error": str(error)}


def cancel_alarm(
    alarm_id: int | None = None,
    name: str | None = None,
    time_match: str | None = None,
    cancel_all: bool = False,
) -> dict[str, Any]:
    """
    Cancel an alarm.

    Args:
        alarm_id: Alarm ID to cancel
        name: Alarm name to match
        time_match: Time string to match
        cancel_all: Cancel all active alarms

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_timer_manager()

        if cancel_all:
            alarms = manager.get_active_alarms()
            count = 0
            for alarm in alarms:
                if manager.cancel_alarm(alarm["id"]):
                    count += 1
            logger.info(f"Cancelled {count} alarms")
            return {
                "success": True,
                "cancelled_count": count,
                "message": f"Cancelled {count} alarm" + ("s" if count != 1 else "") + ".",
            }

        if alarm_id:
            success = manager.cancel_alarm(alarm_id)
            if success:
                logger.info(f"Cancelled alarm {alarm_id}")
                return {"success": True, "message": f"Alarm {alarm_id} cancelled."}
            else:
                return {
                    "success": False,
                    "error": f"Alarm {alarm_id} not found or already cancelled.",
                }

        # Search by name or time
        alarms = manager.get_active_alarms()

        if name:
            for alarm in alarms:
                if alarm.get("name") and name.lower() in alarm["name"].lower():
                    manager.cancel_alarm(alarm["id"])
                    logger.info(f"Cancelled alarm '{alarm['name']}'")
                    return {"success": True, "message": f"Cancelled the {alarm['name']} alarm."}
            return {"success": False, "error": f"No alarm matching '{name}' found."}

        if time_match:
            # Try to parse and match time
            parsed_time = manager.parse_alarm_time(time_match)
            if parsed_time:
                for alarm in alarms:
                    alarm_time = datetime.fromisoformat(alarm["alarm_time"])
                    if (
                        alarm_time.hour == parsed_time.hour
                        and alarm_time.minute == parsed_time.minute
                    ):
                        manager.cancel_alarm(alarm["id"])
                        time_str = alarm_time.strftime("%I:%M %p")
                        logger.info(f"Cancelled {time_str} alarm")
                        return {"success": True, "message": f"Cancelled the {time_str} alarm."}
            return {"success": False, "error": f"No alarm at '{time_match}' found."}

        # No specific alarm - show what's available
        if len(alarms) == 1:
            alarm = alarms[0]
            manager.cancel_alarm(alarm["id"])
            return {"success": True, "message": "Alarm cancelled."}
        elif len(alarms) > 1:
            return {
                "success": False,
                "error": "Multiple alarms set. Please specify which one to cancel.",
                "active_alarms": [
                    f"{a.get('name') or datetime.fromisoformat(a['alarm_time']).strftime('%I:%M %p')}"
                    for a in alarms
                ],
            }
        else:
            return {"success": False, "error": "No alarms to cancel."}

    except Exception as error:
        logger.error(f"Error cancelling alarm: {error}")
        return {"success": False, "error": str(error)}


def snooze_alarm(
    alarm_id: int | None = None,
    name: str | None = None,
    minutes: int = 10,
) -> dict[str, Any]:
    """
    Snooze an alarm.

    Args:
        alarm_id: Alarm ID to snooze
        name: Alarm name to match
        minutes: Minutes to snooze (default 10)

    Returns:
        Result dictionary with success status
    """
    try:
        manager = get_timer_manager()

        if alarm_id:
            success = manager.snooze_alarm(alarm_id, minutes=minutes)
            if success:
                logger.info(f"Snoozed alarm {alarm_id} for {minutes} minutes")
                return {"success": True, "message": f"Alarm snoozed for {minutes} minutes."}
            else:
                return {"success": False, "error": f"Alarm {alarm_id} not found."}

        # Find alarm by name or most recent due alarm
        alarms = manager.get_active_alarms()

        if name:
            for alarm in alarms:
                if alarm.get("name") and name.lower() in alarm["name"].lower():
                    manager.snooze_alarm(alarm["id"], minutes=minutes)
                    logger.info(f"Snoozed alarm '{alarm['name']}' for {minutes} minutes")
                    return {
                        "success": True,
                        "message": f"Snoozed the {alarm['name']} alarm for {minutes} minutes.",
                    }
            return {"success": False, "error": f"No alarm matching '{name}' found."}

        # Check for due alarms first (ones that should be ringing)
        due_alarms = manager.get_due_alarms()
        if due_alarms:
            alarm = due_alarms[0]
            manager.snooze_alarm(alarm["id"], minutes=minutes)
            name_str = f" ({alarm['name']})" if alarm.get("name") else ""
            logger.info(f"Snoozed due alarm{name_str} for {minutes} minutes")
            return {"success": True, "message": f"Alarm snoozed for {minutes} minutes."}

        # No due alarms - snooze the next upcoming one
        if alarms:
            alarm = alarms[0]  # First is soonest due to ordering
            manager.snooze_alarm(alarm["id"], minutes=minutes)
            name_str = f" ({alarm['name']})" if alarm.get("name") else ""
            logger.info(f"Snoozed alarm{name_str} for {minutes} minutes")
            return {"success": True, "message": f"Alarm snoozed for {minutes} minutes."}

        return {"success": False, "error": "No alarms to snooze."}

    except Exception as error:
        logger.error(f"Error snoozing alarm: {error}")
        return {"success": False, "error": str(error)}


def execute_timer_tool(tool_name: str, tool_input: dict) -> dict[str, Any]:
    """
    Execute a timer/alarm tool by name.

    Args:
        tool_name: Name of the tool
        tool_input: Tool input parameters

    Returns:
        Tool result dictionary
    """
    logger.info(f"Executing timer tool: {tool_name}")

    if tool_name == "set_timer":
        return set_timer(
            duration=tool_input.get("duration", ""),
            name=tool_input.get("name"),
        )

    elif tool_name == "list_timers":
        return list_timers()

    elif tool_name == "cancel_timer":
        return cancel_timer(
            timer_id=tool_input.get("timer_id"),
            name=tool_input.get("name"),
            cancel_all=tool_input.get("cancel_all", False),
        )

    elif tool_name == "set_alarm":
        return set_alarm(
            time=tool_input.get("time", ""),
            name=tool_input.get("name"),
            repeat_days=tool_input.get("repeat_days"),
        )

    elif tool_name == "list_alarms":
        return list_alarms()

    elif tool_name == "cancel_alarm":
        return cancel_alarm(
            alarm_id=tool_input.get("alarm_id"),
            name=tool_input.get("name"),
            time_match=tool_input.get("time_match"),
            cancel_all=tool_input.get("cancel_all", False),
        )

    elif tool_name == "snooze_alarm":
        return snooze_alarm(
            alarm_id=tool_input.get("alarm_id"),
            name=tool_input.get("name"),
            minutes=tool_input.get("minutes", 10),
        )

    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
