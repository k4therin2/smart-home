"""
Smart Home Assistant - Local Data Storage Module

SQLite-based local storage for device registry, command history,
usage tracking, and other persistent data.
"""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from src.config import DATA_DIR


logger = logging.getLogger(__name__)

# Database file path
DATABASE_PATH = DATA_DIR / "smarthome.db"


def get_connection() -> sqlite3.Connection:
    """
    Create a database connection with row factory.

    Returns:
        SQLite connection with dict-like row access
    """
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database operations.

    Yields:
        SQLite cursor

    Example:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM devices")
            rows = cursor.fetchall()
    """
    connection = get_connection()
    try:
        cursor = connection.cursor()
        yield cursor
        connection.commit()
    except Exception as error:
        connection.rollback()
        logger.error(f"Database error: {error}")
        raise
    finally:
        connection.close()


def initialize_database():
    """
    Initialize the database with required tables.

    Creates tables if they don't exist:
    - devices: Device registry
    - command_history: Record of commands processed
    - api_usage: Token and cost tracking
    - settings: Key-value settings store
    """
    with get_cursor() as cursor:
        # Device Registry
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                entity_id TEXT PRIMARY KEY,
                friendly_name TEXT,
                device_type TEXT NOT NULL,
                room TEXT,
                manufacturer TEXT,
                model TEXT,
                capabilities TEXT,  -- JSON array of capabilities
                metadata TEXT,      -- JSON object for additional data
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Command History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_text TEXT NOT NULL,
                command_type TEXT,           -- 'voice', 'text', 'api'
                interpreted_action TEXT,     -- JSON of parsed action
                result TEXT,                 -- 'success', 'failure', 'partial'
                error_message TEXT,
                response_text TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd REAL,
                latency_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # API Usage Tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,          -- YYYY-MM-DD format
                provider TEXT NOT NULL,      -- 'anthropic', 'openai', etc.
                model TEXT NOT NULL,
                total_input_tokens INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                total_requests INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, provider, model)
            )
        """)

        # Settings Store
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,         -- JSON encoded value
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Device State Snapshots (for history/trends)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_state_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                attributes TEXT,             -- JSON object
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entity_id) REFERENCES devices(entity_id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_history_created
            ON command_history(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_usage_date
            ON api_usage(date)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_device_state_history_entity
            ON device_state_history(entity_id, recorded_at)
        """)

    logger.info(f"Database initialized at {DATABASE_PATH}")


# =============================================================================
# Device Registry Functions
# =============================================================================


def register_device(
    entity_id: str,
    device_type: str,
    friendly_name: str | None = None,
    room: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    capabilities: list[str] | None = None,
    metadata: dict | None = None,
) -> bool:
    """
    Register or update a device in the registry.

    Args:
        entity_id: Home Assistant entity ID
        device_type: Type of device (light, switch, sensor, etc.)
        friendly_name: Human-readable name
        room: Room location
        manufacturer: Device manufacturer
        model: Device model
        capabilities: List of device capabilities
        metadata: Additional metadata dict

    Returns:
        True if successful
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO devices (
                entity_id, device_type, friendly_name, room,
                manufacturer, model, capabilities, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                device_type = excluded.device_type,
                friendly_name = excluded.friendly_name,
                room = excluded.room,
                manufacturer = excluded.manufacturer,
                model = excluded.model,
                capabilities = excluded.capabilities,
                metadata = excluded.metadata,
                updated_at = CURRENT_TIMESTAMP
        """,
            (
                entity_id,
                device_type,
                friendly_name,
                room,
                manufacturer,
                model,
                json.dumps(capabilities) if capabilities else None,
                json.dumps(metadata) if metadata else None,
            ),
        )

    logger.debug(f"Registered device: {entity_id}")
    return True


def get_device(entity_id: str) -> dict | None:
    """
    Get a device from the registry.

    Args:
        entity_id: Device entity ID

    Returns:
        Device dict or None if not found
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM devices WHERE entity_id = ?", (entity_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        device = dict(row)
        # Parse JSON fields
        if device.get("capabilities"):
            device["capabilities"] = json.loads(device["capabilities"])
        if device.get("metadata"):
            device["metadata"] = json.loads(device["metadata"])

        return device


def get_all_devices() -> list[dict]:
    """
    Get all devices from the registry.

    Returns:
        List of device dicts
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM devices ORDER BY room, device_type, entity_id")
        rows = cursor.fetchall()

        devices = []
        for row in rows:
            device = dict(row)
            if device.get("capabilities"):
                device["capabilities"] = json.loads(device["capabilities"])
            if device.get("metadata"):
                device["metadata"] = json.loads(device["metadata"])
            devices.append(device)

        return devices


def get_devices_by_room(room: str) -> list[dict]:
    """
    Get all devices in a specific room.

    Args:
        room: Room name

    Returns:
        List of device dicts
    """
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM devices WHERE room = ? ORDER BY device_type, entity_id", (room,)
        )
        rows = cursor.fetchall()

        devices = []
        for row in rows:
            device = dict(row)
            if device.get("capabilities"):
                device["capabilities"] = json.loads(device["capabilities"])
            if device.get("metadata"):
                device["metadata"] = json.loads(device["metadata"])
            devices.append(device)

        return devices


def get_devices_by_type(device_type: str) -> list[dict]:
    """
    Get all devices of a specific type.

    Args:
        device_type: Device type (light, switch, etc.)

    Returns:
        List of device dicts
    """
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM devices WHERE device_type = ? ORDER BY room, entity_id", (device_type,)
        )
        rows = cursor.fetchall()

        devices = []
        for row in rows:
            device = dict(row)
            if device.get("capabilities"):
                device["capabilities"] = json.loads(device["capabilities"])
            if device.get("metadata"):
                device["metadata"] = json.loads(device["metadata"])
            devices.append(device)

        return devices


def delete_device(entity_id: str) -> bool:
    """
    Remove a device from the registry.

    Args:
        entity_id: Device entity ID

    Returns:
        True if device was deleted
    """
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM devices WHERE entity_id = ?", (entity_id,))
        return cursor.rowcount > 0


# =============================================================================
# Command History Functions
# =============================================================================


def record_command(
    command_text: str,
    command_type: str = "text",
    interpreted_action: dict | None = None,
    result: str = "success",
    error_message: str | None = None,
    response_text: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
) -> int:
    """
    Record a command in history.

    Args:
        command_text: Original command text
        command_type: Type of command (voice, text, api)
        interpreted_action: Parsed action dict
        result: Command result (success, failure, partial)
        error_message: Error message if failed
        response_text: Response given to user
        input_tokens: LLM input tokens used
        output_tokens: LLM output tokens used
        cost_usd: Cost in USD
        latency_ms: Response latency in milliseconds

    Returns:
        ID of the recorded command
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO command_history (
                command_text, command_type, interpreted_action, result,
                error_message, response_text, input_tokens, output_tokens,
                cost_usd, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                command_text,
                command_type,
                json.dumps(interpreted_action) if interpreted_action else None,
                result,
                error_message,
                response_text,
                input_tokens,
                output_tokens,
                cost_usd,
                latency_ms,
            ),
        )
        return cursor.lastrowid


def get_command_history(limit: int = 100, offset: int = 0) -> list[dict]:
    """
    Get recent command history.

    Args:
        limit: Maximum number of records
        offset: Number of records to skip

    Returns:
        List of command history dicts
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM command_history
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )
        rows = cursor.fetchall()

        history = []
        for row in rows:
            record = dict(row)
            if record.get("interpreted_action"):
                record["interpreted_action"] = json.loads(record["interpreted_action"])
            history.append(record)

        return history


# =============================================================================
# API Usage Tracking Functions
# =============================================================================


def track_api_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
):
    """
    Track API usage for cost monitoring.

    Args:
        provider: API provider (anthropic, openai)
        model: Model name
        input_tokens: Input tokens used
        output_tokens: Output tokens used
        cost_usd: Cost in USD
    """
    today = datetime.now().strftime("%Y-%m-%d")

    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO api_usage (
                date, provider, model, total_input_tokens,
                total_output_tokens, total_requests, total_cost_usd
            ) VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(date, provider, model) DO UPDATE SET
                total_input_tokens = total_input_tokens + excluded.total_input_tokens,
                total_output_tokens = total_output_tokens + excluded.total_output_tokens,
                total_requests = total_requests + 1,
                total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                updated_at = CURRENT_TIMESTAMP
        """,
            (today, provider, model, input_tokens, output_tokens, cost_usd),
        )


def get_daily_usage(date: str | None = None) -> dict:
    """
    Get API usage for a specific date.

    Args:
        date: Date in YYYY-MM-DD format (defaults to today)

    Returns:
        Dict with usage totals
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_requests) as requests,
                SUM(total_cost_usd) as cost_usd
            FROM api_usage
            WHERE date = ?
        """,
            (date,),
        )
        row = cursor.fetchone()

        return {
            "date": date,
            "input_tokens": row["input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
            "requests": row["requests"] or 0,
            "cost_usd": row["cost_usd"] or 0.0,
        }


def get_usage_for_period(start_date: str, end_date: str) -> list[dict]:
    """
    Get daily API usage for a date range.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of daily usage dicts
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                date,
                SUM(total_input_tokens) as input_tokens,
                SUM(total_output_tokens) as output_tokens,
                SUM(total_requests) as requests,
                SUM(total_cost_usd) as cost_usd
            FROM api_usage
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
        """,
            (start_date, end_date),
        )

        return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# Settings Functions
# =============================================================================


def set_setting(key: str, value: Any, description: str | None = None):
    """
    Set a configuration setting.

    Args:
        key: Setting key
        value: Setting value (will be JSON encoded)
        description: Optional description
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO settings (key, value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                description = COALESCE(excluded.description, settings.description),
                updated_at = CURRENT_TIMESTAMP
        """,
            (key, json.dumps(value), description),
        )


def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a configuration setting.

    Args:
        key: Setting key
        default: Default value if not found

    Returns:
        Setting value or default
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row is None:
            return default

        return json.loads(row["value"])


def get_all_settings() -> dict[str, Any]:
    """
    Get all settings.

    Returns:
        Dict of key-value pairs
    """
    with get_cursor() as cursor:
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()

        return {row["key"]: json.loads(row["value"]) for row in rows}


# =============================================================================
# Device State History Functions
# =============================================================================


def record_device_state(
    entity_id: str,
    state: str,
    attributes: dict | None = None,
):
    """
    Record a device state snapshot.

    Args:
        entity_id: Device entity ID
        state: Current state value
        attributes: State attributes
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO device_state_history (entity_id, state, attributes)
            VALUES (?, ?, ?)
        """,
            (
                entity_id,
                state,
                json.dumps(attributes) if attributes else None,
            ),
        )


def get_device_state_history(
    entity_id: str,
    limit: int = 100,
) -> list[dict]:
    """
    Get state history for a device.

    Args:
        entity_id: Device entity ID
        limit: Maximum number of records

    Returns:
        List of state history dicts
    """
    with get_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM device_state_history
            WHERE entity_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        """,
            (entity_id, limit),
        )
        rows = cursor.fetchall()

        history = []
        for row in rows:
            record = dict(row)
            if record.get("attributes"):
                record["attributes"] = json.loads(record["attributes"])
            history.append(record)

        return history


# Initialize database on module import
initialize_database()
