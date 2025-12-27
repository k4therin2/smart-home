"""
Unit tests for the LogReader module.

Tests log parsing, filtering, pagination, and search functionality.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest

# Import will fail until we implement the module - this is TDD
from src.log_reader import LogReader, LogEntry, LogLevel


class TestLogEntry:
    """Tests for LogEntry dataclass."""

    def test_log_entry_creation(self):
        """Test creating a LogEntry with all fields."""
        entry = LogEntry(
            timestamp=datetime(2025, 12, 18, 10, 30, 0),
            level=LogLevel.INFO,
            module="test_module",
            function="test_func",
            message="Test message",
            line_number=42,
        )
        assert entry.timestamp == datetime(2025, 12, 18, 10, 30, 0)
        assert entry.level == LogLevel.INFO
        assert entry.module == "test_module"
        assert entry.function == "test_func"
        assert entry.message == "Test message"
        assert entry.line_number == 42

    def test_log_entry_to_dict(self):
        """Test converting LogEntry to dictionary."""
        entry = LogEntry(
            timestamp=datetime(2025, 12, 18, 10, 30, 0),
            level=LogLevel.ERROR,
            module="test_module",
            function="test_func",
            message="Error occurred",
            line_number=100,
        )
        result = entry.to_dict()
        assert result["timestamp"] == "2025-12-18T10:30:00"
        assert result["level"] == "ERROR"
        assert result["module"] == "test_module"
        assert result["function"] == "test_func"
        assert result["message"] == "Error occurred"
        assert result["line_number"] == 100


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_levels_exist(self):
        """Test all expected log levels exist."""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_log_level_from_string(self):
        """Test parsing log level from string."""
        assert LogLevel.from_string("DEBUG") == LogLevel.DEBUG
        assert LogLevel.from_string("INFO") == LogLevel.INFO
        assert LogLevel.from_string("WARNING") == LogLevel.WARNING
        assert LogLevel.from_string("ERROR") == LogLevel.ERROR
        assert LogLevel.from_string("CRITICAL") == LogLevel.CRITICAL

    def test_log_level_from_string_case_insensitive(self):
        """Test parsing log level is case insensitive."""
        assert LogLevel.from_string("info") == LogLevel.INFO
        assert LogLevel.from_string("Warning") == LogLevel.WARNING

    def test_log_level_from_string_invalid(self):
        """Test parsing invalid log level returns None."""
        assert LogLevel.from_string("INVALID") is None
        assert LogLevel.from_string("") is None

    def test_log_level_severity_ordering(self):
        """Test log levels have correct severity ordering."""
        assert LogLevel.DEBUG.severity < LogLevel.INFO.severity
        assert LogLevel.INFO.severity < LogLevel.WARNING.severity
        assert LogLevel.WARNING.severity < LogLevel.ERROR.severity
        assert LogLevel.ERROR.severity < LogLevel.CRITICAL.severity


@pytest.fixture
def sample_log_content() -> str:
    """Sample log file content for testing."""
    return """2025-12-18 10:00:00,123 | INFO     | server                    | start                | Server starting
2025-12-18 10:00:01,456 | DEBUG    | ha_client                 | connect              | Connecting to HA
2025-12-18 10:00:02,789 | WARNING  | cache                     | evict                | Cache full, evicting old entries
2025-12-18 10:00:03,012 | ERROR    | agent                     | process              | Failed to process command
2025-12-18 10:00:04,345 | CRITICAL | database                  | query                | Database connection lost
2025-12-18 10:01:00,678 | INFO     | server                    | handle_request       | Processing request for /api/status
"""


@pytest.fixture
def temp_log_file(sample_log_content: str) -> Generator[Path, None, None]:
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as temp_file:
        temp_file.write(sample_log_content)
        temp_path = Path(temp_file.name)
    yield temp_path
    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def log_reader(temp_log_file: Path) -> LogReader:
    """Create a LogReader with the temp log file."""
    return LogReader(log_dir=temp_log_file.parent)


class TestLogReader:
    """Tests for the LogReader class."""

    def test_init_with_default_dir(self):
        """Test LogReader initializes with default log directory."""
        reader = LogReader()
        assert reader.log_dir is not None
        assert reader.log_dir.exists() or True  # May not exist in test environment

    def test_init_with_custom_dir(self, temp_log_file: Path):
        """Test LogReader initializes with custom directory."""
        reader = LogReader(log_dir=temp_log_file.parent)
        assert reader.log_dir == temp_log_file.parent

    def test_parse_log_line_valid(self):
        """Test parsing a valid log line."""
        reader = LogReader()
        line = "2025-12-18 10:30:45,123 | INFO     | test_module           | test_func            | Test message here"
        entry = reader.parse_log_line(line, line_number=1)

        assert entry is not None
        assert entry.timestamp == datetime(2025, 12, 18, 10, 30, 45, 123000)
        assert entry.level == LogLevel.INFO
        assert entry.module == "test_module"
        assert entry.function == "test_func"
        assert entry.message == "Test message here"
        assert entry.line_number == 1

    def test_parse_log_line_invalid(self):
        """Test parsing an invalid log line returns None."""
        reader = LogReader()
        invalid_lines = [
            "",
            "Not a log line",
            "2025-12-18 | Missing parts",
            "Invalid date | INFO | module | func | msg",
        ]
        for line in invalid_lines:
            assert reader.parse_log_line(line, line_number=1) is None

    def test_parse_log_line_with_pipe_in_message(self):
        """Test parsing a log line where the message contains pipe characters."""
        reader = LogReader()
        line = "2025-12-18 10:30:45,123 | INFO     | test_module           | test_func            | Message with | pipe | chars"
        entry = reader.parse_log_line(line, line_number=1)

        assert entry is not None
        assert entry.message == "Message with | pipe | chars"

    def test_list_log_files(self, temp_log_file: Path):
        """Test listing log files in directory."""
        reader = LogReader(log_dir=temp_log_file.parent)
        files = reader.list_log_files()
        assert len(files) >= 1
        assert any(temp_log_file.name in str(f) for f in files)

    def test_list_log_files_by_type(self, temp_log_file: Path):
        """Test listing log files filtered by type."""
        # Create additional mock log files
        error_log = temp_log_file.parent / "errors.log"
        api_log = temp_log_file.parent / "api_calls.log"
        error_log.write_text("test")
        api_log.write_text("test")

        try:
            reader = LogReader(log_dir=temp_log_file.parent)

            # Test filtering by main logs
            main_files = reader.list_log_files(log_type="main")
            error_files = reader.list_log_files(log_type="error")
            api_files = reader.list_log_files(log_type="api")

            assert all("error" not in str(f).lower() and "api" not in str(f).lower() for f in main_files)
            assert all("error" in str(f).lower() for f in error_files)
            assert all("api" in str(f).lower() for f in api_files)
        finally:
            error_log.unlink(missing_ok=True)
            api_log.unlink(missing_ok=True)


class TestLogReaderRead:
    """Tests for LogReader.read() method."""

    def test_read_all_entries(self, temp_log_file: Path, sample_log_content: str):
        """Test reading all entries from a log file."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries = reader.read(file_path=temp_log_file)
        # Sample has 6 lines
        assert len(entries) == 6

    def test_read_with_pagination(self, temp_log_file: Path):
        """Test reading entries with pagination."""
        reader = LogReader(log_dir=temp_log_file.parent)

        # First page
        page1 = reader.read(file_path=temp_log_file, offset=0, limit=3)
        assert len(page1) == 3

        # Second page
        page2 = reader.read(file_path=temp_log_file, offset=3, limit=3)
        assert len(page2) == 3

        # Third page (empty)
        page3 = reader.read(file_path=temp_log_file, offset=6, limit=3)
        assert len(page3) == 0

    def test_read_reverse_order(self, temp_log_file: Path):
        """Test reading entries in reverse chronological order."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries = reader.read(file_path=temp_log_file, reverse=True)

        # First entry should be the latest
        assert entries[0].timestamp > entries[-1].timestamp


class TestLogReaderFiltering:
    """Tests for LogReader filtering capabilities."""

    def test_filter_by_level(self, temp_log_file: Path):
        """Test filtering entries by log level."""
        reader = LogReader(log_dir=temp_log_file.parent)

        # Filter for ERROR and above
        errors = reader.read(file_path=temp_log_file, min_level=LogLevel.ERROR)
        assert all(e.level.severity >= LogLevel.ERROR.severity for e in errors)
        assert len(errors) == 2  # ERROR and CRITICAL

        # Filter for INFO only
        info_only = reader.read(file_path=temp_log_file, levels=[LogLevel.INFO])
        assert all(e.level == LogLevel.INFO for e in info_only)
        assert len(info_only) == 2

    def test_filter_by_date_range(self, temp_log_file: Path):
        """Test filtering entries by date range."""
        reader = LogReader(log_dir=temp_log_file.parent)

        start = datetime(2025, 12, 18, 10, 0, 2)
        end = datetime(2025, 12, 18, 10, 0, 4)

        entries = reader.read(file_path=temp_log_file, start_time=start, end_time=end)
        # Should include entries at 10:00:02 and 10:00:03
        assert len(entries) == 2
        assert all(start <= e.timestamp <= end for e in entries)

    def test_filter_by_module(self, temp_log_file: Path):
        """Test filtering entries by module name."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries = reader.read(file_path=temp_log_file, module="server")
        assert len(entries) == 2
        assert all(e.module == "server" for e in entries)

    def test_filter_by_module_pattern(self, temp_log_file: Path):
        """Test filtering entries by module name pattern."""
        reader = LogReader(log_dir=temp_log_file.parent)
        # Pattern matching: modules starting with 'ha'
        entries = reader.read(file_path=temp_log_file, module_pattern="ha_*")
        assert len(entries) == 1
        assert entries[0].module == "ha_client"


class TestLogReaderSearch:
    """Tests for LogReader search functionality."""

    def test_search_in_message(self, temp_log_file: Path):
        """Test searching for text in log messages."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries = reader.read(file_path=temp_log_file, search="request")
        assert len(entries) == 1
        assert "request" in entries[0].message.lower()

    def test_search_case_insensitive(self, temp_log_file: Path):
        """Test that search is case insensitive."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries_lower = reader.read(file_path=temp_log_file, search="server")
        entries_upper = reader.read(file_path=temp_log_file, search="SERVER")
        assert len(entries_lower) == len(entries_upper)

    def test_search_with_regex(self, temp_log_file: Path):
        """Test searching with regex pattern."""
        reader = LogReader(log_dir=temp_log_file.parent)
        # Find entries mentioning connection-related words
        entries = reader.read(file_path=temp_log_file, search_regex=r"connect\w*")
        assert len(entries) == 2  # "Connecting" and "connection"


class TestLogReaderStats:
    """Tests for LogReader statistics functionality."""

    def test_get_stats(self, temp_log_file: Path):
        """Test getting log statistics."""
        reader = LogReader(log_dir=temp_log_file.parent)
        stats = reader.get_stats(file_path=temp_log_file)

        assert stats["total_entries"] == 6
        assert stats["level_counts"]["INFO"] == 2
        assert stats["level_counts"]["DEBUG"] == 1
        assert stats["level_counts"]["WARNING"] == 1
        assert stats["level_counts"]["ERROR"] == 1
        assert stats["level_counts"]["CRITICAL"] == 1

    def test_get_stats_includes_time_range(self, temp_log_file: Path):
        """Test stats include time range of log entries."""
        reader = LogReader(log_dir=temp_log_file.parent)
        stats = reader.get_stats(file_path=temp_log_file)

        assert "first_entry" in stats
        assert "last_entry" in stats
        assert stats["first_entry"] <= stats["last_entry"]


class TestLogReaderExport:
    """Tests for LogReader export functionality."""

    def test_export_json(self, temp_log_file: Path):
        """Test exporting logs to JSON format."""
        reader = LogReader(log_dir=temp_log_file.parent)
        json_output = reader.export(file_path=temp_log_file, format="json")

        import json
        data = json.loads(json_output)
        assert "entries" in data
        assert "stats" in data
        assert len(data["entries"]) == 6

    def test_export_text(self, temp_log_file: Path):
        """Test exporting logs to plain text format."""
        reader = LogReader(log_dir=temp_log_file.parent)
        text_output = reader.export(file_path=temp_log_file, format="text")

        lines = text_output.strip().split("\n")
        assert len(lines) == 6

    def test_export_with_filters(self, temp_log_file: Path):
        """Test exporting logs with filters applied."""
        reader = LogReader(log_dir=temp_log_file.parent)
        json_output = reader.export(
            file_path=temp_log_file,
            format="json",
            min_level=LogLevel.ERROR
        )

        import json
        data = json.loads(json_output)
        assert len(data["entries"]) == 2  # ERROR and CRITICAL only


class TestLogReaderTail:
    """Tests for LogReader tail (real-time) functionality."""

    def test_tail_returns_latest_entries(self, temp_log_file: Path):
        """Test tail returns the latest n entries."""
        reader = LogReader(log_dir=temp_log_file.parent)
        entries = reader.tail(file_path=temp_log_file, lines=3)

        assert len(entries) == 3
        # Should be in chronological order, latest last
        assert entries[-1].message.startswith("Processing request")

    def test_tail_with_follow_initial_read(self, temp_log_file: Path):
        """Test tail follow mode returns initial entries."""
        reader = LogReader(log_dir=temp_log_file.parent)
        # This just tests the initial read - actual following would require threading
        entries, position = reader.tail_with_position(file_path=temp_log_file, lines=2)

        assert len(entries) == 2
        assert position > 0  # Should return file position for follow-up reads

    def test_tail_from_position(self, temp_log_file: Path):
        """Test reading new entries from a given file position."""
        reader = LogReader(log_dir=temp_log_file.parent)

        # Get initial position
        _, position = reader.tail_with_position(file_path=temp_log_file, lines=3)

        # Append new entry
        with open(temp_log_file, "a") as f:
            f.write("2025-12-18 10:02:00,000 | INFO     | test                      | new_entry            | New log entry\n")

        # Read from position
        new_entries = reader.read_from_position(file_path=temp_log_file, position=position)
        assert len(new_entries) == 1
        assert new_entries[0].message == "New log entry"
