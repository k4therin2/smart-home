"""
Tests for src/logging_config.py - Centralized Logging Module

These tests cover the logging configuration including log level conversion,
logger setup, API logging, and the LogContext context manager.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest

from src.logging_config import (
    get_log_level,
    setup_logging,
    get_logger,
    get_api_logger,
    log_api_call,
    LogContext,
    DETAILED_FORMAT,
    SIMPLE_FORMAT,
    CONSOLE_FORMAT,
)


# =============================================================================
# Log Level Tests
# =============================================================================


class TestGetLogLevel:
    """Tests for the get_log_level function."""

    def test_debug_level(self):
        """Test DEBUG level conversion."""
        assert get_log_level("DEBUG") == logging.DEBUG

    def test_info_level(self):
        """Test INFO level conversion."""
        assert get_log_level("INFO") == logging.INFO

    def test_warning_level(self):
        """Test WARNING level conversion."""
        assert get_log_level("WARNING") == logging.WARNING

    def test_error_level(self):
        """Test ERROR level conversion."""
        assert get_log_level("ERROR") == logging.ERROR

    def test_critical_level(self):
        """Test CRITICAL level conversion."""
        assert get_log_level("CRITICAL") == logging.CRITICAL

    def test_case_insensitive(self):
        """Test that level names are case insensitive."""
        assert get_log_level("debug") == logging.DEBUG
        assert get_log_level("Debug") == logging.DEBUG
        assert get_log_level("DeBuG") == logging.DEBUG

    def test_unknown_level_defaults_to_info(self):
        """Test that unknown levels default to INFO."""
        assert get_log_level("UNKNOWN") == logging.INFO
        assert get_log_level("TRACE") == logging.INFO
        assert get_log_level("") == logging.INFO


# =============================================================================
# Setup Logging Tests
# =============================================================================


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_setup_returns_logger(self):
        """Test that setup_logging returns a logger instance."""
        # Use a unique name to avoid handler reuse
        unique_name = f"test_logger_{datetime.now().timestamp()}"
        logger = setup_logging(name=unique_name, log_to_file=False, log_to_console=False)

        assert isinstance(logger, logging.Logger)
        assert logger.name == unique_name

    def test_setup_with_console_only(self):
        """Test setup with console logging only."""
        unique_name = f"test_console_{datetime.now().timestamp()}"
        logger = setup_logging(name=unique_name, log_to_file=False, log_to_console=True)

        # Should have at least one handler (console)
        assert len(logger.handlers) >= 1
        # Check that one handler is StreamHandler
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_setup_respects_log_level(self):
        """Test that setup respects the provided log level."""
        unique_name = f"test_level_{datetime.now().timestamp()}"
        logger = setup_logging(
            name=unique_name,
            level="DEBUG",
            log_to_file=False,
            log_to_console=False
        )

        assert logger.level == logging.DEBUG

    def test_setup_avoids_duplicate_handlers(self):
        """Test that calling setup twice doesn't duplicate handlers."""
        unique_name = f"test_dup_{datetime.now().timestamp()}"

        logger1 = setup_logging(name=unique_name, log_to_file=False, log_to_console=True)
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logging(name=unique_name, log_to_file=False, log_to_console=True)
        handler_count2 = len(logger2.handlers)

        assert logger1 is logger2
        assert handler_count1 == handler_count2


# =============================================================================
# Get Logger Tests
# =============================================================================


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_returns_named_logger(self):
        """Test that get_logger returns a logger with the correct name."""
        logger = get_logger("test.module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_get_logger_same_name_returns_same_instance(self):
        """Test that same name returns same logger instance."""
        logger1 = get_logger("same.module")
        logger2 = get_logger("same.module")

        assert logger1 is logger2


# =============================================================================
# API Logger Tests
# =============================================================================


class TestGetApiLogger:
    """Tests for the get_api_logger function."""

    def test_get_api_logger_returns_logger(self):
        """Test that get_api_logger returns a logger."""
        logger = get_api_logger()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "api_calls"

    def test_get_api_logger_level_is_debug(self):
        """Test that API logger is set to DEBUG level."""
        logger = get_api_logger()

        assert logger.level == logging.DEBUG

    def test_get_api_logger_same_instance(self):
        """Test that get_api_logger returns same instance."""
        logger1 = get_api_logger()
        logger2 = get_api_logger()

        assert logger1 is logger2


# =============================================================================
# Log API Call Tests
# =============================================================================


class TestLogApiCall:
    """Tests for the log_api_call function."""

    def test_log_basic_call(self):
        """Test logging a basic API call."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="openai",
                endpoint="/v1/chat/completions",
                method="POST"
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "provider=openai" in call_args
            assert "endpoint=/v1/chat/completions" in call_args
            assert "method=POST" in call_args

    def test_log_call_with_status_code(self):
        """Test logging API call with status code."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="home_assistant",
                endpoint="/api/states",
                method="GET",
                status_code=200
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "status=200" in call_args

    def test_log_call_with_latency(self):
        """Test logging API call with latency."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="anthropic",
                endpoint="/v1/messages",
                method="POST",
                latency_ms=150
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "latency_ms=150" in call_args

    def test_log_call_with_tokens(self):
        """Test logging API call with token counts."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="openai",
                endpoint="/v1/chat/completions",
                method="POST",
                input_tokens=100,
                output_tokens=50
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "input_tokens=100" in call_args
            assert "output_tokens=50" in call_args

    def test_log_call_with_error(self):
        """Test logging API call with error."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="openai",
                endpoint="/v1/chat/completions",
                method="POST",
                error="Rate limit exceeded"
            )

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "error=Rate limit exceeded" in call_args

    def test_log_call_full_params(self):
        """Test logging API call with all parameters."""
        with patch('src.logging_config.get_api_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            log_api_call(
                provider="anthropic",
                endpoint="/v1/messages",
                method="POST",
                status_code=200,
                latency_ms=250,
                input_tokens=500,
                output_tokens=200
            )

            call_args = mock_logger.info.call_args[0][0]
            assert "provider=anthropic" in call_args
            assert "status=200" in call_args
            assert "latency_ms=250" in call_args
            assert "input_tokens=500" in call_args
            assert "output_tokens=200" in call_args


# =============================================================================
# LogContext Tests
# =============================================================================


class TestLogContext:
    """Tests for the LogContext context manager."""

    def test_context_logs_start_message(self):
        """Test that context logs start message on entry."""
        mock_logger = MagicMock()

        with LogContext(mock_logger, "Test operation"):
            pass

        # Check that log was called at least once for start
        log_calls = mock_logger.log.call_args_list
        start_call = log_calls[0]
        assert "Starting: Test operation" in start_call[0][1]

    def test_context_logs_completion_message(self):
        """Test that context logs completion message on successful exit."""
        mock_logger = MagicMock()

        with LogContext(mock_logger, "Test operation"):
            pass

        # Check the completion log
        log_calls = mock_logger.log.call_args_list
        completion_call = log_calls[-1]
        assert "Completed: Test operation" in completion_call[0][1]
        assert "elapsed_ms=" in completion_call[0][1]

    def test_context_logs_error_on_exception(self):
        """Test that context logs error when exception occurs."""
        mock_logger = MagicMock()

        with pytest.raises(ValueError):
            with LogContext(mock_logger, "Failing operation"):
                raise ValueError("Test error")

        # Check that error was logged
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "Failed: Failing operation" in error_message
        assert "ValueError: Test error" in error_message

    def test_context_includes_additional_context(self):
        """Test that context includes additional key-value pairs."""
        mock_logger = MagicMock()

        with LogContext(mock_logger, "Test operation", command="lights on", room="living room"):
            pass

        start_call = mock_logger.log.call_args_list[0][0][1]
        assert "command=lights on" in start_call
        assert "room=living room" in start_call

    def test_context_uses_custom_log_level(self):
        """Test that context respects custom log level."""
        mock_logger = MagicMock()

        with LogContext(mock_logger, "Debug operation", level=logging.DEBUG):
            pass

        # Check that log was called with DEBUG level
        start_call = mock_logger.log.call_args_list[0]
        assert start_call[0][0] == logging.DEBUG

    def test_context_tracks_elapsed_time(self):
        """Test that context tracks elapsed time correctly."""
        import time
        mock_logger = MagicMock()

        with LogContext(mock_logger, "Timed operation"):
            time.sleep(0.1)  # Sleep 100ms

        completion_call = mock_logger.log.call_args_list[-1][0][1]
        # Extract elapsed_ms from the log message
        import re
        match = re.search(r'elapsed_ms=(\d+)', completion_call)
        assert match is not None
        elapsed = int(match.group(1))
        # Should be approximately 100ms (with some tolerance)
        assert elapsed >= 90  # At least 90ms

    def test_context_does_not_suppress_exceptions(self):
        """Test that context doesn't suppress exceptions."""
        mock_logger = MagicMock()

        with pytest.raises(RuntimeError):
            with LogContext(mock_logger, "Test operation"):
                raise RuntimeError("Unhandled error")

    def test_context_returns_self(self):
        """Test that context manager returns self on entry."""
        mock_logger = MagicMock()
        context = LogContext(mock_logger, "Test operation")

        with context as ctx:
            assert ctx is context


# =============================================================================
# Log Format Tests
# =============================================================================


class TestLogFormats:
    """Tests for log format strings."""

    def test_detailed_format_includes_required_fields(self):
        """Test that detailed format includes required fields."""
        assert "%(asctime)s" in DETAILED_FORMAT
        assert "%(levelname)" in DETAILED_FORMAT
        assert "%(name)" in DETAILED_FORMAT
        assert "%(funcName)" in DETAILED_FORMAT
        assert "%(message)s" in DETAILED_FORMAT

    def test_simple_format_includes_required_fields(self):
        """Test that simple format includes required fields."""
        assert "%(asctime)s" in SIMPLE_FORMAT
        assert "%(levelname)" in SIMPLE_FORMAT
        assert "%(message)s" in SIMPLE_FORMAT

    def test_console_format_includes_required_fields(self):
        """Test that console format includes required fields."""
        assert "%(levelname)" in CONSOLE_FORMAT
        assert "%(name)" in CONSOLE_FORMAT
        assert "%(message)s" in CONSOLE_FORMAT
