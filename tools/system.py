"""
Smart Home Assistant - System Tools

Provides system-level functionality:
- Current time queries (12-hour and 24-hour formats)
- Current date with day of week
- Comprehensive datetime information
- Timezone configuration and awareness

All time operations respect the configured timezone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
import pytz
import logging

logger = logging.getLogger(__name__)

# Global timezone configuration
_timezone: Optional[pytz.timezone] = None


def set_timezone(timezone_input: str | pytz.timezone) -> None:
    """
    Set the timezone for all time/date operations.

    Args:
        timezone_input: Either a timezone string (e.g., 'US/Eastern') or a pytz timezone object
    """
    global _timezone

    try:
        if isinstance(timezone_input, str):
            _timezone = pytz.timezone(timezone_input)
        else:
            _timezone = timezone_input
        logger.info(f"Timezone set to: {_timezone}")
    except Exception as error:
        logger.error(f"Failed to set timezone: {error}")
        _timezone = pytz.UTC


def get_timezone() -> pytz.timezone:
    """
    Get the currently configured timezone.

    Returns:
        pytz timezone object. Defaults to UTC if not configured.
    """
    global _timezone

    if _timezone is None:
        _timezone = pytz.UTC
    return _timezone


def _get_local_now() -> datetime:
    """
    Get current datetime in the configured timezone.

    Returns:
        timezone-aware datetime object in configured timezone
    """
    timezone_obj = get_timezone()

    if timezone_obj == pytz.UTC:
        return datetime.now(pytz.UTC)
    else:
        return datetime.now(timezone_obj)


def format_time_12h(dt: Optional[datetime] = None) -> str:
    """
    Format time in 12-hour format with AM/PM.

    Args:
        dt: datetime object (uses current time if not provided)

    Returns:
        Formatted time string (e.g., "2:30 PM" or "10:45 AM")
    """
    if dt is None:
        dt = _get_local_now()

    return dt.strftime("%-I:%M %p") if hasattr(dt, 'strftime') else f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def format_time_24h(dt: Optional[datetime] = None) -> str:
    """
    Format time in 24-hour format.

    Args:
        dt: datetime object (uses current time if not provided)

    Returns:
        Formatted time string (e.g., "14:30" or "09:45")
    """
    if dt is None:
        dt = _get_local_now()

    return dt.strftime("%H:%M")


def get_current_time(format_24h: bool = False) -> str:
    """
    Get the current time in the configured timezone.

    Args:
        format_24h: If True, return 24-hour format; otherwise 12-hour format

    Returns:
        Current time as a formatted string
    """
    now = _get_local_now()

    if format_24h:
        return format_time_24h(now)
    else:
        return format_time_12h(now)


def get_current_date() -> str:
    """
    Get the current date in human-readable format.

    Returns:
        Date string like "Monday, January 13, 2025"
    """
    now = _get_local_now()
    return now.strftime("%A, %B %d, %Y")


def get_datetime_info() -> Dict[str, Any]:
    """
    Get comprehensive datetime information in the configured timezone.

    Returns:
        Dictionary with:
        - time: Current time (12-hour format)
        - time_24h: Current time (24-hour format)
        - date: Current date with day of week
        - day_of_week: Day name only
        - timestamp: Unix timestamp
        - timezone: Timezone name
        - iso_format: ISO 8601 format
    """
    now = _get_local_now()
    timezone_obj = get_timezone()

    return {
        "time": format_time_12h(now),
        "time_24h": format_time_24h(now),
        "date": now.strftime("%A, %B %d, %Y"),
        "day_of_week": now.strftime("%A"),
        "timestamp": int(now.timestamp()),
        "timezone": str(timezone_obj),
        "iso_format": now.isoformat(),
    }


def get_time_until_event(event_hour: int, event_minute: int = 0) -> str:
    """
    Calculate time remaining until a specific time today.

    Args:
        event_hour: Hour of the event (0-23)
        event_minute: Minute of the event (0-59)

    Returns:
        Human-readable string describing time until event
    """
    now = _get_local_now()

    # Create event datetime for today
    event_time = now.replace(hour=event_hour, minute=event_minute, second=0, microsecond=0)

    # If event is in the past, calculate for tomorrow
    if event_time <= now:
        event_time = event_time.replace(day=event_time.day + 1)

    # Calculate time difference
    time_diff = event_time - now
    hours = int(time_diff.total_seconds() // 3600)
    minutes = int((time_diff.total_seconds() % 3600) // 60)

    if hours == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
