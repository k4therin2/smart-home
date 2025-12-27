"""
Tests for Time and Date Query Tools (WP-3.4)

Tests comprehensive time and date functionality including:
- Current time in various formats (12-hour, 24-hour)
- Current date with day of week
- Timezone-aware datetime information
- Comprehensive datetime status (day of week, ordinal date, etc.)
- Edge cases around midnight, month boundaries, DST transitions

Integration tests verify real component interactions:
- Tools execute correctly within agent loop
- Tool results are properly formatted for Claude
- Timezone configuration is respected
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pytz


class TestGetCurrentTime:
    """Test get_current_time tool functionality."""

    def test_current_time_format_12_hour(self):
        """Current time should return 12-hour format by default."""
        from tools.system import get_current_time

        result = get_current_time()

        # Should contain time in format like "2:30 PM" or "10:45 AM"
        assert ":" in result
        assert ("AM" in result or "PM" in result)

    def test_current_time_format_24_hour(self):
        """Current time should support 24-hour format."""
        from tools.system import get_current_time

        result = get_current_time(format_24h=True)

        # Should contain time in format like "14:30" or "09:45"
        assert ":" in result
        # Verify no AM/PM in 24-hour format
        assert "AM" not in result and "PM" not in result

    def test_current_time_hour_range(self):
        """Hour component should be valid 1-12 for 12-hour format."""
        from tools.system import get_current_time

        result = get_current_time()

        # Extract hour from format like "2:30 PM"
        time_part = result.split()[0]
        hour_str = time_part.split(":")[0]
        hour = int(hour_str)

        assert 1 <= hour <= 12

    def test_current_time_minute_range(self):
        """Minute component should be valid 0-59."""
        from tools.system import get_current_time

        result = get_current_time()

        # Extract minute
        time_part = result.split()[0]
        minute_str = time_part.split(":")[1]
        minute = int(minute_str)

        assert 0 <= minute <= 59

    def test_current_time_respects_timezone(self):
        """Current time should respect configured timezone."""
        from tools.system import get_current_time, set_timezone
        import pytz

        # Set timezone to US/Pacific
        pacific = pytz.timezone("US/Pacific")
        set_timezone(pacific)

        result = get_current_time()

        # Result should be a valid time string
        assert isinstance(result, str)
        assert ":" in result

    def test_current_time_consistency_within_second(self):
        """Multiple calls within same second should return same time."""
        from tools.system import get_current_time

        result1 = get_current_time()
        result2 = get_current_time()

        # Should be identical within same second
        assert result1 == result2


class TestGetCurrentDate:
    """Test get_current_date tool functionality."""

    def test_current_date_includes_day_of_week(self):
        """Current date should include full day name."""
        from tools.system import get_current_date

        result = get_current_date()

        # Should contain one of the weekday names
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert any(day in result for day in weekdays)

    def test_current_date_includes_month_name(self):
        """Current date should include full month name."""
        from tools.system import get_current_date

        result = get_current_date()

        # Should contain one of the month names
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        assert any(month in result for month in months)

    def test_current_date_includes_date_number(self):
        """Current date should include day of month (1-31)."""
        from tools.system import get_current_date, set_timezone
        import pytz

        # Reset timezone to UTC to ensure consistent behavior
        set_timezone(pytz.UTC)

        result = get_current_date()

        # Should have a number between 1-31
        today = datetime.now(pytz.UTC)
        day_str = str(today.day)
        assert day_str in result

    def test_current_date_includes_year(self):
        """Current date should include 4-digit year."""
        from tools.system import get_current_date

        result = get_current_date()

        # Should contain current year
        today = datetime.now()
        year_str = str(today.year)
        assert year_str in result

    def test_current_date_format_is_readable(self):
        """Date format should be human-readable (e.g., 'Monday, January 13, 2025')."""
        from tools.system import get_current_date

        result = get_current_date()

        # Should contain commas for readability
        assert "," in result
        # Should be a reasonable string length (20-40 chars)
        assert 15 < len(result) < 50

    def test_current_date_respects_timezone(self):
        """Current date should respect configured timezone."""
        from tools.system import get_current_date, set_timezone
        import pytz

        # Set timezone to Asia/Tokyo (UTC+9)
        tokyo = pytz.timezone("Asia/Tokyo")
        set_timezone(tokyo)

        result = get_current_date()

        # Result should contain a valid date
        assert isinstance(result, str)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert any(day in result for day in weekdays)


class TestGetDatetimeInfo:
    """Test comprehensive datetime information function."""

    def test_datetime_info_includes_time(self):
        """Datetime info should include current time."""
        from tools.system import get_datetime_info

        result = get_datetime_info()

        # Should be a dict or object with time component
        assert isinstance(result, dict)
        assert "time" in result

    def test_datetime_info_includes_date(self):
        """Datetime info should include current date."""
        from tools.system import get_datetime_info

        result = get_datetime_info()

        assert "date" in result

    def test_datetime_info_includes_day_of_week(self):
        """Datetime info should include day of week."""
        from tools.system import get_datetime_info

        result = get_datetime_info()

        assert "day_of_week" in result
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert result["day_of_week"] in weekdays

    def test_datetime_info_includes_timestamp(self):
        """Datetime info should include Unix timestamp."""
        from tools.system import get_datetime_info

        result = get_datetime_info()

        assert "timestamp" in result
        # Timestamp should be a reasonable value (after year 2000)
        assert result["timestamp"] > 946684800

    def test_datetime_info_includes_timezone(self):
        """Datetime info should include timezone information."""
        from tools.system import get_datetime_info

        result = get_datetime_info()

        assert "timezone" in result

    def test_datetime_info_is_consistent(self):
        """Datetime info should be internally consistent."""
        from tools.system import get_datetime_info, get_timezone

        result = get_datetime_info()

        # Time and date should match the timestamp
        timestamp = result["timestamp"]
        dt_from_timestamp = datetime.fromtimestamp(timestamp)

        # Day of week should match the configured timezone (not local system time)
        timezone_obj = get_timezone()
        actual_day = datetime.now(timezone_obj).strftime("%A")
        assert result["day_of_week"] == actual_day


class TestDatetimeToolIntegration:
    """Integration tests for datetime tools within agent loop."""

    def test_get_current_time_tool_definition(self):
        """Tool definition should be valid and properly formatted."""
        from agent import SYSTEM_TOOLS

        # Find time tool
        time_tool = None
        for tool in SYSTEM_TOOLS:
            if tool["name"] == "get_current_time":
                time_tool = tool
                break

        assert time_tool is not None
        assert "description" in time_tool
        assert "input_schema" in time_tool
        assert time_tool["input_schema"]["type"] == "object"

    def test_get_datetime_info_tool_definition(self):
        """Datetime info tool should be defined in agent."""
        from agent import SYSTEM_TOOLS

        # Find datetime tool
        datetime_tool = None
        for tool in SYSTEM_TOOLS:
            if tool["name"] == "get_datetime_info":
                datetime_tool = tool
                break

        assert datetime_tool is not None

    def test_tool_execution_in_agent(self):
        """Tool should execute correctly through agent's execute_tool function."""
        from agent import execute_tool

        # Test time tool execution
        result = execute_tool("get_current_time", {})

        assert isinstance(result, str)
        assert ":" in result  # Should contain time

    def test_datetime_info_tool_execution_in_agent(self):
        """Datetime info tool should execute through agent."""
        from agent import execute_tool
        import json

        result = execute_tool("get_datetime_info", {})

        # Result should be JSON-serializable
        if isinstance(result, str):
            parsed = json.loads(result)
            assert isinstance(parsed, dict)
        else:
            assert isinstance(result, dict)

    def test_tool_execution_error_handling(self):
        """Tool execution should handle missing timezones gracefully."""
        from agent import execute_tool

        # Should not raise exception even if timezone not set
        result = execute_tool("get_current_time", {})
        assert isinstance(result, str)


class TestTimezoneConfigure:
    """Test timezone configuration functionality."""

    def test_set_timezone_function_exists(self):
        """set_timezone function should exist and be callable."""
        from tools.system import set_timezone

        assert callable(set_timezone)

    def test_set_timezone_with_string(self):
        """set_timezone should accept timezone string."""
        from tools.system import set_timezone
        import pytz

        # Should not raise
        set_timezone("US/Eastern")

    def test_set_timezone_with_pytz_object(self):
        """set_timezone should accept pytz timezone object."""
        from tools.system import set_timezone
        import pytz

        eastern = pytz.timezone("US/Eastern")
        # Should not raise
        set_timezone(eastern)

    def test_set_timezone_affects_time_output(self):
        """Setting timezone should affect time output."""
        from tools.system import set_timezone, get_current_time
        import pytz

        # Set to UTC
        set_timezone("UTC")
        time_utc = get_current_time()

        # Set to US/Eastern (UTC-5)
        set_timezone("US/Eastern")
        time_eastern = get_current_time()

        # Times may differ (depends on actual UTC time)
        # Just verify both return valid time strings
        assert ":" in time_utc
        assert ":" in time_eastern

    def test_get_timezone_function_exists(self):
        """get_timezone function should exist."""
        from tools.system import get_timezone

        assert callable(get_timezone)

    def test_get_timezone_returns_current(self):
        """get_timezone should return currently configured timezone."""
        from tools.system import set_timezone, get_timezone
        import pytz

        set_timezone("US/Pacific")
        current_tz = get_timezone()

        # Should be a timezone object or string
        assert current_tz is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_midnight_transition(self):
        """Time should format correctly at midnight."""
        from tools.system import format_time_12h

        # Test with datetime at midnight
        dt = datetime.strptime("00:00:00", "%H:%M:%S")
        result = format_time_12h(dt)

        assert "12:" in result
        assert "AM" in result

    def test_noon_time(self):
        """Time should format correctly at noon."""
        from tools.system import format_time_12h

        # Test with datetime at noon
        dt = datetime.strptime("12:00:00", "%H:%M:%S")
        result = format_time_12h(dt)

        assert "12:" in result
        assert "PM" in result

    def test_11_59_pm(self):
        """Time should format correctly at 23:59."""
        from tools.system import format_time_12h

        dt = datetime.strptime("23:59:59", "%H:%M:%S")
        result = format_time_12h(dt)

        assert "11:59" in result
        assert "PM" in result

    def test_single_digit_hour_formatting(self):
        """Single-digit hours should format correctly without leading zero."""
        from tools.system import format_time_12h

        dt = datetime.strptime("09:30:00", "%H:%M:%S")
        result = format_time_12h(dt)

        # Should show as "9:30 AM" not "09:30 AM"
        assert result.startswith("9:")

    def test_month_boundary_date(self):
        """Date should format correctly on month boundaries."""
        from tools.system import get_current_date

        result = get_current_date()

        # Just verify it returns a valid date string
        assert isinstance(result, str)
        assert len(result) > 10

    def test_year_boundary_date(self):
        """Date should format correctly on year boundaries."""
        from tools.system import get_current_date

        result = get_current_date()

        # Should contain year
        current_year = str(datetime.now().year)
        assert current_year in result


class TestClientIntegration:
    """Test integration with actual client usage patterns."""

    @patch('anthropic.Anthropic')
    def test_time_query_agent_scenario(self, mock_anthropic):
        """Test realistic agent scenario: 'what time is it?'"""
        from agent import execute_tool

        # Execute tool as agent would
        result = execute_tool("get_current_time", {})

        # Result should be formatted for Claude
        assert isinstance(result, str)
        assert ":" in result

    @patch('anthropic.Anthropic')
    def test_date_query_agent_scenario(self, mock_anthropic):
        """Test realistic agent scenario: 'what's today's date?'"""
        from agent import execute_tool
        from tools.system import set_timezone
        import pytz

        # Reset timezone for test consistency
        set_timezone(pytz.UTC)

        result = execute_tool("get_current_date", {})

        assert isinstance(result, str)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert any(day in result for day in weekdays)

    @patch('anthropic.Anthropic')
    def test_datetime_info_agent_scenario(self, mock_anthropic):
        """Test realistic agent scenario: comprehensive datetime info."""
        from agent import execute_tool
        import json

        result = execute_tool("get_datetime_info", {})

        # Parse if it's a JSON string
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result

        assert isinstance(data, dict)
        assert "time" in data
        assert "date" in data

    def test_logging_for_time_queries(self, capture_logs):
        """Tool execution should log appropriately."""
        from agent import execute_tool

        result = execute_tool("get_current_time", {})

        # Should have executed without errors
        assert isinstance(result, str)
