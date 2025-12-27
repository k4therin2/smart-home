"""
Smart Home Assistant - Log Reader Module

Provides utilities for reading, parsing, filtering, and exporting log files.
Supports pagination, search, real-time tailing, and statistics.
"""

import fnmatch
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from src.config import LOGS_DIR


class LogLevel(Enum):
    """Log severity levels with associated severity values."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def severity(self) -> int:
        """Return numeric severity for comparison."""
        severity_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        return severity_map[self.value]

    @classmethod
    def from_string(cls, level_str: str) -> Optional["LogLevel"]:
        """
        Parse a log level from a string.

        Args:
            level_str: Level name (case insensitive)

        Returns:
            LogLevel enum or None if invalid
        """
        if not level_str:
            return None
        try:
            return cls[level_str.upper().strip()]
        except KeyError:
            return None


@dataclass
class LogEntry:
    """Represents a single log entry."""

    timestamp: datetime
    level: LogLevel
    module: str
    function: str
    message: str
    line_number: int = 0
    raw_line: str = ""

    def to_dict(self) -> dict:
        """Convert log entry to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "module": self.module,
            "function": self.function,
            "message": self.message,
            "line_number": self.line_number,
        }


class LogReader:
    """
    Utility class for reading and parsing log files.

    Supports filtering by level, date range, module, and text search.
    Provides pagination, export, and real-time tailing capabilities.
    """

    # Log line format: YYYY-MM-DD HH:MM:SS,mmm | LEVEL | module | function | message
    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s*\|\s*"
        r"(\w+)\s*\|\s*"
        r"([\w.]+)\s*\|\s*"
        r"([\w_]+)\s*\|\s*"
        r"(.*)$"
    )

    def __init__(self, log_dir: Path | None = None):
        """
        Initialize LogReader.

        Args:
            log_dir: Directory containing log files. Defaults to LOGS_DIR.
        """
        self.log_dir = Path(log_dir) if log_dir else LOGS_DIR

    def parse_log_line(self, line: str, line_number: int = 0) -> LogEntry | None:
        """
        Parse a single log line into a LogEntry.

        Args:
            line: Raw log line string
            line_number: Line number in the file

        Returns:
            LogEntry if parsing succeeds, None otherwise
        """
        if not line or not line.strip():
            return None

        match = self.LOG_PATTERN.match(line.strip())
        if not match:
            return None

        timestamp_str, level_str, module, function, message = match.groups()

        # Parse timestamp
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
        except ValueError:
            return None

        # Parse level
        level = LogLevel.from_string(level_str)
        if level is None:
            return None

        return LogEntry(
            timestamp=timestamp,
            level=level,
            module=module.strip(),
            function=function.strip(),
            message=message.strip(),
            line_number=line_number,
            raw_line=line,
        )

    def list_log_files(self, log_type: str | None = None) -> list[Path]:
        """
        List log files in the log directory.

        Args:
            log_type: Filter by type ('main', 'error', 'api') or None for all

        Returns:
            List of Path objects for matching log files
        """
        if not self.log_dir.exists():
            return []

        all_files = sorted(
            self.log_dir.glob("*.log"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        if log_type is None:
            return all_files

        type_patterns = {
            "main": lambda f: "error" not in f.name.lower() and "api" not in f.name.lower(),
            "error": lambda f: "error" in f.name.lower(),
            "api": lambda f: "api" in f.name.lower(),
        }

        filter_func = type_patterns.get(log_type, lambda _: True)
        return [f for f in all_files if filter_func(f)]

    def read(
        self,
        file_path: Path | None = None,
        offset: int = 0,
        limit: int | None = None,
        reverse: bool = False,
        min_level: LogLevel | None = None,
        levels: list[LogLevel] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        module: str | None = None,
        module_pattern: str | None = None,
        search: str | None = None,
        search_regex: str | None = None,
    ) -> list[LogEntry]:
        """
        Read and filter log entries from a file.

        Args:
            file_path: Path to log file. Defaults to main log.
            offset: Number of entries to skip (for pagination)
            limit: Maximum entries to return
            reverse: Return entries in reverse chronological order
            min_level: Minimum log level to include
            levels: Specific log levels to include
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            module: Exact module name to filter
            module_pattern: Module name pattern (fnmatch style)
            search: Text to search for in messages (case insensitive)
            search_regex: Regex pattern to search for in messages

        Returns:
            List of matching LogEntry objects
        """
        if file_path is None:
            main_files = self.list_log_files(log_type="main")
            if not main_files:
                return []
            file_path = main_files[0]

        if not file_path.exists():
            return []

        entries: list[LogEntry] = []
        compiled_regex = None
        if search_regex:
            compiled_regex = re.compile(search_regex, re.IGNORECASE)

        with open(file_path, encoding="utf-8", errors="replace") as file:
            for line_num, line in enumerate(file, start=1):
                entry = self.parse_log_line(line, line_number=line_num)
                if entry is None:
                    continue

                # Apply filters
                if min_level and entry.level.severity < min_level.severity:
                    continue

                if levels and entry.level not in levels:
                    continue

                if start_time and entry.timestamp < start_time:
                    continue

                if end_time and entry.timestamp > end_time:
                    continue

                if module and entry.module != module:
                    continue

                if module_pattern and not fnmatch.fnmatch(entry.module, module_pattern):
                    continue

                if search and search.lower() not in entry.message.lower():
                    continue

                if compiled_regex and not compiled_regex.search(entry.message):
                    continue

                entries.append(entry)

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp, reverse=reverse)

        # Apply pagination
        if offset:
            entries = entries[offset:]
        if limit:
            entries = entries[:limit]

        return entries

    def get_stats(self, file_path: Path | None = None) -> dict:
        """
        Get statistics for a log file.

        Args:
            file_path: Path to log file. Defaults to main log.

        Returns:
            Dictionary with statistics
        """
        entries = self.read(file_path=file_path)

        level_counts = {level.value: 0 for level in LogLevel}
        for entry in entries:
            level_counts[entry.level.value] += 1

        first_entry = min((e.timestamp for e in entries), default=None)
        last_entry = max((e.timestamp for e in entries), default=None)

        return {
            "total_entries": len(entries),
            "level_counts": level_counts,
            "first_entry": first_entry,
            "last_entry": last_entry,
        }

    def export(
        self,
        file_path: Path | None = None,
        format: str = "json",
        **filter_kwargs,
    ) -> str:
        """
        Export log entries to a string format.

        Args:
            file_path: Path to log file
            format: Output format ('json' or 'text')
            **filter_kwargs: Additional filter arguments for read()

        Returns:
            Formatted string of log entries
        """
        entries = self.read(file_path=file_path, **filter_kwargs)

        if format == "json":
            stats = self.get_stats(file_path=file_path)
            # Convert datetime objects to ISO format strings for JSON
            if stats["first_entry"]:
                stats["first_entry"] = stats["first_entry"].isoformat()
            if stats["last_entry"]:
                stats["last_entry"] = stats["last_entry"].isoformat()

            return json.dumps(
                {
                    "entries": [e.to_dict() for e in entries],
                    "stats": stats,
                },
                indent=2,
            )
        else:  # text format
            lines = []
            for entry in entries:
                lines.append(
                    f"{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} | "
                    f"{entry.level.value:8} | {entry.module:25} | "
                    f"{entry.function:20} | {entry.message}"
                )
            return "\n".join(lines)

    def tail(
        self,
        file_path: Path | None = None,
        lines: int = 10,
    ) -> list[LogEntry]:
        """
        Get the last n entries from a log file.

        Args:
            file_path: Path to log file
            lines: Number of lines to return

        Returns:
            List of the last n LogEntry objects
        """
        entries = self.read(file_path=file_path)
        return entries[-lines:] if len(entries) > lines else entries

    def tail_with_position(
        self,
        file_path: Path | None = None,
        lines: int = 10,
    ) -> tuple[list[LogEntry], int]:
        """
        Get the last n entries and the current file position.

        Useful for implementing follow mode.

        Args:
            file_path: Path to log file
            lines: Number of lines to return

        Returns:
            Tuple of (entries, file_position)
        """
        if file_path is None:
            main_files = self.list_log_files(log_type="main")
            if not main_files:
                return [], 0
            file_path = main_files[0]

        if not file_path.exists():
            return [], 0

        entries = self.tail(file_path=file_path, lines=lines)
        position = file_path.stat().st_size

        return entries, position

    def read_from_position(
        self,
        file_path: Path,
        position: int,
    ) -> list[LogEntry]:
        """
        Read new entries from a given file position.

        Args:
            file_path: Path to log file
            position: File position to read from

        Returns:
            List of new LogEntry objects
        """
        if not file_path.exists():
            return []

        entries: list[LogEntry] = []

        with open(file_path, encoding="utf-8", errors="replace") as file:
            file.seek(position)
            for line in file:
                entry = self.parse_log_line(line)
                if entry:
                    entries.append(entry)

        return entries
