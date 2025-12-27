"""
Smart Home Assistant - Utilities Module

Provides logging, prompt loading, setup validation, and helper functions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime
from typing import Any

from src.config import (
    DAILY_COST_ALERT,
    DAILY_COST_TARGET,
    DATA_DIR,
    LOG_LEVEL,
    LOGS_DIR,
    OPENAI_INPUT_COST_PER_MILLION,
    OPENAI_OUTPUT_COST_PER_MILLION,
    PROMPTS_DIR,
    validate_config,
)
from src.security.config import SLACK_COST_WEBHOOK_URL, SLACK_HEALTH_WEBHOOK_URL
from src.security.slack_client import SlackNotifier


# Database path for usage tracking
USAGE_DB_PATH = DATA_DIR / "usage.db"

# Lazy-initialized notifiers (avoid circular imports at module load)
_cost_notifier = None
_health_notifier = None


def _get_cost_notifier() -> SlackNotifier:
    """Get or create the cost alert Slack notifier."""
    global _cost_notifier
    if _cost_notifier is None:
        _cost_notifier = SlackNotifier(webhook_url=SLACK_COST_WEBHOOK_URL)
    return _cost_notifier


def _get_health_notifier() -> SlackNotifier:
    """Get or create the health alert Slack notifier."""
    global _health_notifier
    if _health_notifier is None:
        _health_notifier = SlackNotifier(webhook_url=SLACK_HEALTH_WEBHOOK_URL)
    return _health_notifier


def send_health_alert(
    title: str,
    message: str,
    severity: str = "warning",
    component: str | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    """
    Send a health alert to the #smarthome-health Slack channel.

    Use this function to report device errors, service failures, and
    operational issues that require user attention.

    Args:
        title: Short alert title (e.g., "Vacuum Error", "Spotify API Failed")
        message: Detailed description of the issue
        severity: One of "critical", "warning", "info"
                  - critical: System down, service unavailable
                  - warning: Degraded performance, errors occurring
                  - info: Recovery, successful self-healing
        component: Optional component name (e.g., "vacuum", "spotify", "auth")
        details: Optional dict of additional context fields

    Returns:
        True if alert was sent successfully, False otherwise

    Example:
        send_health_alert(
            title="Vacuum Connection Lost",
            message="Unable to communicate with Dreame L10s vacuum",
            severity="warning",
            component="vacuum",
            details={"entity_id": "vacuum.dreame_r2228o", "error": "Connection timeout"}
        )
    """
    # Build fields list
    fields = []
    if component:
        fields.append({"title": "Component", "value": component})
    if details:
        for key, value in details.items():
            fields.append({"title": key.replace("_", " ").title(), "value": str(value)})

    # Log the alert
    log_level = (
        logging.CRITICAL
        if severity == "critical"
        else (logging.WARNING if severity == "warning" else logging.INFO)
    )
    logger.log(log_level, f"Health Alert [{severity}] {title}: {message}")

    # Send to Slack
    return _get_health_notifier().send_alert(
        title=title,
        message=message,
        severity=severity,
        fields=fields if fields else None,
    )


def setup_logging(name: str = "smarthome") -> logging.Logger:
    """
    Set up centralized, robust logging.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler for all logs
    log_file = LOGS_DIR / f"smarthome_{date.today().isoformat()}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Error file handler
    error_log = LOGS_DIR / f"errors_{date.today().isoformat()}.log"
    error_handler = logging.FileHandler(error_log)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)

    return logger


# Initialize module logger
logger = setup_logging()


def load_prompts() -> dict[str, Any]:
    """
    Load system prompts from prompts/config.json.

    Returns:
        Dictionary of prompt configurations
    """
    config_path = PROMPTS_DIR / "config.json"

    if not config_path.exists():
        logger.warning(f"Prompts config not found at {config_path}, using defaults")
        return get_default_prompts()

    try:
        with open(config_path) as file:
            prompts = json.load(file)
            logger.debug(f"Loaded prompts from {config_path}")
            return prompts
    except json.JSONDecodeError as error:
        logger.error(f"Failed to parse prompts config: {error}")
        return get_default_prompts()


def get_default_prompts() -> dict[str, Any]:
    """Return default system prompts."""
    return {
        "main_agent": {
            "system": """You are a smart home assistant. You control devices in the user's home through Home Assistant.

Your personality is minimal and concise. Respond briefly to confirm actions or provide information.

Available capabilities:
- Control lights (on/off, brightness, color temperature)
- Query device states
- Execute automations

When controlling devices:
1. Parse the user's intent
2. Select the appropriate tool
3. Execute the action
4. Confirm briefly

Do not be chatty. Be helpful and efficient."""
        },
        "hue_specialist": {
            "system": """You are a lighting specialist agent. You translate abstract vibe requests into specific Philips Hue settings.

Given a vibe description (e.g., "cozy evening", "focus mode", "romantic dinner"):
1. Determine appropriate brightness (0-100%)
2. Determine color temperature (2200K-6500K)
3. Consider time of day if mentioned
4. Return specific settings

Use color theory and lighting design principles."""
        },
    }


def init_usage_db() -> None:
    """Initialize the usage tracking database."""
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                command TEXT
            )
        """)
        conn.commit()
        logger.debug("Usage database initialized")


def track_api_usage(
    model: str, input_tokens: int, output_tokens: int, command: str | None = None
) -> float:
    """
    Track API usage and cost.

    Args:
        model: Model name used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        command: Optional command that triggered this usage

    Returns:
        Cost in USD for this request
    """
    # Calculate cost
    input_cost = (input_tokens / 1_000_000) * OPENAI_INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OPENAI_OUTPUT_COST_PER_MILLION
    total_cost = input_cost + output_cost

    # Initialize DB if needed
    if not USAGE_DB_PATH.exists():
        init_usage_db()

    # Store in database
    now = datetime.now()
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO api_usage (timestamp, date, model, input_tokens, output_tokens, cost_usd, command)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                now.isoformat(),
                now.date().isoformat(),
                model,
                input_tokens,
                output_tokens,
                total_cost,
                command,
            ),
        )
        conn.commit()

    logger.info(f"API usage: {input_tokens} in / {output_tokens} out = ${total_cost:.4f}")

    # Check daily limit and send Slack alert if threshold exceeded
    daily_cost = get_daily_usage()
    if daily_cost >= DAILY_COST_ALERT:
        logger.warning(
            f"COST ALERT: Daily spend ${daily_cost:.2f} exceeds ${DAILY_COST_ALERT:.2f} threshold!"
        )
        _get_cost_notifier().send_alert(
            title="API Cost Alert",
            message=f"Daily API spend has reached *${daily_cost:.2f}* (threshold: ${DAILY_COST_ALERT:.2f})",
            severity="warning",
            fields=[
                {"title": "Today's Cost", "value": f"${daily_cost:.2f}"},
                {"title": "Threshold", "value": f"${DAILY_COST_ALERT:.2f}"},
                {"title": "Last Request", "value": f"${total_cost:.4f}"},
            ],
        )
    elif daily_cost >= DAILY_COST_TARGET:
        logger.info(f"Daily spend ${daily_cost:.2f} exceeds target ${DAILY_COST_TARGET:.2f}")

    return total_cost


def get_daily_usage(target_date: date | None = None) -> float:
    """
    Get total API cost for a specific date.

    Args:
        target_date: Date to check (defaults to today)

    Returns:
        Total cost in USD
    """
    if target_date is None:
        target_date = date.today()

    if not USAGE_DB_PATH.exists():
        return 0.0

    with sqlite3.connect(USAGE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM api_usage
            WHERE date = ?
        """,
            (target_date.isoformat(),),
        )
        result = cursor.fetchone()
        return result[0] if result else 0.0


def get_usage_stats(days: int = 7) -> dict[str, Any]:
    """
    Get usage statistics for the past N days.

    Args:
        days: Number of days to include

    Returns:
        Dictionary with usage statistics
    """
    if not USAGE_DB_PATH.exists():
        return {"total_cost": 0, "total_requests": 0, "daily_breakdown": []}

    with sqlite3.connect(USAGE_DB_PATH) as conn:
        cursor = conn.cursor()

        # Get daily breakdown
        cursor.execute(
            """
            SELECT date, COUNT(*) as requests, SUM(cost_usd) as cost
            FROM api_usage
            WHERE date >= date('now', ?)
            GROUP BY date
            ORDER BY date DESC
        """,
            (f"-{days} days",),
        )
        daily = [{"date": row[0], "requests": row[1], "cost": row[2]} for row in cursor.fetchall()]

        # Get totals
        cursor.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(cost_usd), 0)
            FROM api_usage
            WHERE date >= date('now', ?)
        """,
            (f"-{days} days",),
        )
        totals = cursor.fetchone()

        return {
            "total_requests": totals[0],
            "total_cost": totals[1],
            "daily_breakdown": daily,
            "average_daily_cost": totals[1] / days if days > 0 else 0,
        }


def check_setup() -> tuple[bool, list[str]]:
    """
    Verify system setup and configuration.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = validate_config()

    # Check data directory
    if not DATA_DIR.exists():
        try:
            DATA_DIR.mkdir(parents=True)
        except Exception as error:
            errors.append(f"Cannot create data directory: {error}")

    # Check logs directory
    if not LOGS_DIR.exists():
        try:
            LOGS_DIR.mkdir(parents=True)
        except Exception as error:
            errors.append(f"Cannot create logs directory: {error}")

    if errors:
        for error in errors:
            logger.error(f"Setup error: {error}")
        return False, errors

    logger.info("Setup validation passed")
    return True, []


def log_command(command: str, source: str = "cli") -> None:
    """
    Log a user command for history tracking.

    Args:
        command: The command text
        source: Source of command (cli, web, voice)
    """
    logger.info(f"Command [{source}]: {command}")


def log_tool_call(tool_name: str, parameters: dict, result: Any) -> None:
    """
    Log a tool execution.

    Args:
        tool_name: Name of the tool called
        parameters: Tool parameters
        result: Tool execution result
    """
    logger.debug(f"Tool call: {tool_name}")
    logger.debug(f"  Parameters: {parameters}")
    logger.debug(f"  Result: {result}")
