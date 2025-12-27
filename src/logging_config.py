"""
Smart Home Assistant - Centralized Logging Module

Provides consistent logging configuration across all components.
Logs to both console and rotating file handlers.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from src.config import LOG_LEVEL, LOGS_DIR


# Ensure logs directory exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Log file paths
MAIN_LOG_FILE = LOGS_DIR / "smarthome.log"
ERROR_LOG_FILE = LOGS_DIR / "errors.log"
API_LOG_FILE = LOGS_DIR / "api_calls.log"

# Log format strings
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s | %(message)s"
SIMPLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
CONSOLE_FORMAT = "%(levelname)-8s | %(name)-20s | %(message)s"


def get_log_level(level_name: str) -> int:
    """
    Convert log level name to logging constant.

    Args:
        level_name: Level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logging level constant
    """
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return levels.get(level_name.upper(), logging.INFO)


def setup_logging(
    name: str | None = None,
    level: str | None = None,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Set up logging for a component.

    Args:
        name: Logger name (None for root logger)
        level: Log level override (defaults to LOG_LEVEL from config)
        log_to_file: Enable file logging
        log_to_console: Enable console logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    log_level = get_log_level(level or LOG_LEVEL)
    logger.setLevel(log_level)

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        logger.addHandler(console_handler)

    # Main log file handler (rotating, 5MB max, keep 5 backups)
    if log_to_file:
        file_handler = RotatingFileHandler(
            MAIN_LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logger.addHandler(file_handler)

        # Error-only file handler
        error_handler = RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logger.addHandler(error_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a component.

    This is the primary function to use throughout the codebase.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        from src.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Starting process")
    """
    # Ensure root logger is configured
    setup_logging()

    # Return named logger (inherits root config)
    return logging.getLogger(name)


def get_api_logger() -> logging.Logger:
    """
    Get a specialized logger for API calls.

    Logs API requests, responses, and timing to a separate file.

    Returns:
        Logger configured for API logging
    """
    logger = logging.getLogger("api_calls")

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # API-specific file handler
    api_handler = RotatingFileHandler(
        API_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB (APIs generate more logs)
        backupCount=5,
        encoding="utf-8",
    )
    api_handler.setLevel(logging.DEBUG)
    api_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
    logger.addHandler(api_handler)

    return logger


def log_api_call(
    provider: str,
    endpoint: str,
    method: str,
    status_code: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
):
    """
    Log an API call with structured data.

    Args:
        provider: API provider (anthropic, home_assistant, etc.)
        endpoint: API endpoint called
        method: HTTP method
        status_code: Response status code
        latency_ms: Request latency in milliseconds
        error: Error message if failed
        input_tokens: Input tokens (for LLM calls)
        output_tokens: Output tokens (for LLM calls)
    """
    api_logger = get_api_logger()

    message_parts = [
        f"provider={provider}",
        f"endpoint={endpoint}",
        f"method={method}",
    ]

    if status_code is not None:
        message_parts.append(f"status={status_code}")

    if latency_ms is not None:
        message_parts.append(f"latency_ms={latency_ms}")

    if input_tokens is not None:
        message_parts.append(f"input_tokens={input_tokens}")

    if output_tokens is not None:
        message_parts.append(f"output_tokens={output_tokens}")

    message = " | ".join(message_parts)

    if error:
        api_logger.error(f"{message} | error={error}")
    else:
        api_logger.info(message)


class LogContext:
    """
    Context manager for logging operation timing.

    Example:
        with LogContext(logger, "Processing command", command=cmd):
            result = process(cmd)
    """

    def __init__(
        self, logger: logging.Logger, operation: str, level: int = logging.INFO, **context
    ):
        """
        Initialize log context.

        Args:
            logger: Logger to use
            operation: Operation description
            level: Log level
            **context: Additional context key-values
        """
        self.logger = logger
        self.operation = operation
        self.level = level
        self.context = context
        self.start_time: datetime | None = None

    def __enter__(self):
        self.start_time = datetime.now()
        context_str = " | ".join(f"{key}={value}" for key, value in self.context.items())
        message = f"Starting: {self.operation}"
        if context_str:
            message += f" | {context_str}"
        self.logger.log(self.level, message)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)

        if exc_type is not None:
            self.logger.error(
                f"Failed: {self.operation} | elapsed_ms={elapsed_ms} | "
                f"error={exc_type.__name__}: {exc_val}"
            )
        else:
            self.logger.log(self.level, f"Completed: {self.operation} | elapsed_ms={elapsed_ms}")

        # Don't suppress exceptions
        return False


# Initialize root logger on module import
setup_logging()
