"""
Utils Module Tests (Suite 10)

Test Strategy:
- Test logging setup and handler creation
- Test prompt loading from JSON files (valid, invalid, missing)
- Test API usage tracking and cost calculations
- Test daily usage aggregation and statistics
- Test cost alert thresholds
- Test setup validation

Mocking Strategy:
- Mock file system for prompt loading (use tmp_path)
- Use in-memory database for usage tracking (via test_db fixture)
- Mock Slack notifier to avoid external calls
- Integration test actual cost calculations
"""

import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_setup_logging_creates_handlers():
    """Test that setup_logging creates console, file, and error handlers."""
    from src.utils import setup_logging

    logger = setup_logging(name="test_logger")

    # Should have 3 handlers: console, file, error
    assert len(logger.handlers) == 3

    # Check handler types
    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "StreamHandler" in handler_types
    assert handler_types.count("FileHandler") == 2  # file + error

    # Verify formatters are set
    for handler in logger.handlers:
        assert handler.formatter is not None

    # Verify log level is set
    assert logger.level == logging.WARNING  # From mock_env_vars fixture

    # Test that calling again doesn't duplicate handlers
    logger2 = setup_logging(name="test_logger")
    assert len(logger2.handlers) == 3
    assert logger is logger2  # Should return same logger


def test_load_prompts_valid_json(tmp_path, monkeypatch):
    """Test loading prompts from a valid JSON file."""
    from src.utils import load_prompts

    # Create prompts directory and config
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    config_data = {
        "main_agent": {
            "system": "Test system prompt"
        },
        "hue_specialist": {
            "system": "Test specialist prompt"
        }
    }

    config_file = prompts_dir / "config.json"
    with open(config_file, "w") as file:
        json.dump(config_data, file)

    # Patch PROMPTS_DIR
    monkeypatch.setattr("src.utils.PROMPTS_DIR", prompts_dir)

    # Load prompts
    prompts = load_prompts()

    # Verify loaded data
    assert "main_agent" in prompts
    assert "hue_specialist" in prompts
    assert prompts["main_agent"]["system"] == "Test system prompt"
    assert prompts["hue_specialist"]["system"] == "Test specialist prompt"


def test_load_prompts_invalid_json(tmp_path, monkeypatch):
    """Test that invalid JSON falls back to defaults."""
    from src.utils import load_prompts, get_default_prompts

    # Create prompts directory with invalid JSON
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    config_file = prompts_dir / "config.json"
    with open(config_file, "w") as file:
        file.write("{ invalid json content }")

    # Patch PROMPTS_DIR
    monkeypatch.setattr("src.utils.PROMPTS_DIR", prompts_dir)

    # Load prompts - should return defaults
    prompts = load_prompts()
    defaults = get_default_prompts()

    # Should match default prompts
    assert prompts == defaults


def test_load_prompts_missing_file(tmp_path, monkeypatch):
    """Test that missing config file falls back to defaults."""
    from src.utils import load_prompts, get_default_prompts

    # Create empty prompts directory (no config.json)
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Patch PROMPTS_DIR
    monkeypatch.setattr("src.utils.PROMPTS_DIR", prompts_dir)

    # Load prompts - should return defaults
    prompts = load_prompts()
    defaults = get_default_prompts()

    # Should match default prompts
    assert prompts == defaults


def test_get_default_prompts():
    """Test that default prompts contain required keys."""
    from src.utils import get_default_prompts

    defaults = get_default_prompts()

    # Should have main_agent and hue_specialist
    assert "main_agent" in defaults
    assert "hue_specialist" in defaults

    # Each should have a system prompt
    assert "system" in defaults["main_agent"]
    assert "system" in defaults["hue_specialist"]

    # System prompts should be non-empty strings
    assert isinstance(defaults["main_agent"]["system"], str)
    assert len(defaults["main_agent"]["system"]) > 0
    assert isinstance(defaults["hue_specialist"]["system"], str)
    assert len(defaults["hue_specialist"]["system"]) > 0


def test_track_api_usage_cost_calculation(tmp_path, monkeypatch):
    """Test that API usage tracking calculates costs correctly."""
    from src.utils import track_api_usage, init_usage_db

    # Set up test database
    db_path = tmp_path / "test_usage.db"
    monkeypatch.setattr("src.utils.USAGE_DB_PATH", db_path)

    # Mock the cost notifier to avoid Slack calls
    with patch("src.utils._get_cost_notifier") as mock_notifier:
        mock_notifier.return_value = MagicMock()

        # Track API usage
        cost = track_api_usage(
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            command="test command"
        )

        # Cost should be $3 (input) + $15 (output) = $18
        assert cost == 18.0

        # Verify stored in database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_usage")
            rows = cursor.fetchall()

            assert len(rows) == 1
            row = rows[0]
            assert row[3] == "claude-sonnet-4-20250514"  # model
            assert row[4] == 1_000_000  # input_tokens
            assert row[5] == 1_000_000  # output_tokens
            assert row[6] == 18.0  # cost_usd
            assert row[7] == "test command"  # command


def test_track_api_usage_daily_aggregation(tmp_path, monkeypatch):
    """Test that multiple API calls aggregate correctly for daily totals."""
    from src.utils import track_api_usage, get_daily_usage

    # Set up test database
    db_path = tmp_path / "test_usage.db"
    monkeypatch.setattr("src.utils.USAGE_DB_PATH", db_path)

    # Mock the cost notifier
    with patch("src.utils._get_cost_notifier") as mock_notifier:
        mock_notifier.return_value = MagicMock()

        # Track multiple API calls
        cost1 = track_api_usage("claude-sonnet-4-20250514", 100_000, 50_000)
        cost2 = track_api_usage("claude-sonnet-4-20250514", 200_000, 100_000)
        cost3 = track_api_usage("claude-sonnet-4-20250514", 150_000, 75_000)

        # Calculate expected total
        # cost1: 0.3 + 0.75 = 1.05
        # cost2: 0.6 + 1.5 = 2.1
        # cost3: 0.45 + 1.125 = 1.575
        # total: 4.725
        expected_total = cost1 + cost2 + cost3

        # Get daily usage
        daily_total = get_daily_usage()

        # Should match sum of individual costs
        assert abs(daily_total - expected_total) < 0.001  # Float comparison tolerance


def test_get_daily_usage(tmp_path, monkeypatch):
    """Test retrieving daily usage for specific dates."""
    from src.utils import init_usage_db, get_daily_usage

    # Set up test database
    db_path = tmp_path / "test_usage.db"
    monkeypatch.setattr("src.utils.USAGE_DB_PATH", db_path)
    init_usage_db()

    # Insert test data for different dates
    today = date.today()
    yesterday = today - timedelta(days=1)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Today's data
        cursor.execute("""
            INSERT INTO api_usage (timestamp, date, model, input_tokens, output_tokens, cost_usd, command)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            today.isoformat(),
            "claude-sonnet-4-20250514",
            100_000,
            50_000,
            1.05,
            "test1"
        ))

        cursor.execute("""
            INSERT INTO api_usage (timestamp, date, model, input_tokens, output_tokens, cost_usd, command)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            today.isoformat(),
            "claude-sonnet-4-20250514",
            200_000,
            100_000,
            2.1,
            "test2"
        ))

        # Yesterday's data
        cursor.execute("""
            INSERT INTO api_usage (timestamp, date, model, input_tokens, output_tokens, cost_usd, command)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            (datetime.now() - timedelta(days=1)).isoformat(),
            yesterday.isoformat(),
            "claude-sonnet-4-20250514",
            300_000,
            150_000,
            3.15,
            "test3"
        ))

        conn.commit()

    # Get today's usage
    today_usage = get_daily_usage(today)
    assert abs(today_usage - 3.15) < 0.001  # 1.05 + 2.1 = 3.15

    # Get yesterday's usage
    yesterday_usage = get_daily_usage(yesterday)
    assert abs(yesterday_usage - 3.15) < 0.001

    # Get usage for a date with no data
    future_date = today + timedelta(days=10)
    future_usage = get_daily_usage(future_date)
    assert future_usage == 0.0


def test_get_usage_stats(tmp_path, monkeypatch):
    """Test retrieving usage statistics over multiple days."""
    from src.utils import init_usage_db, get_usage_stats

    # Set up test database
    db_path = tmp_path / "test_usage.db"
    monkeypatch.setattr("src.utils.USAGE_DB_PATH", db_path)
    init_usage_db()

    # Insert test data for past 3 days
    today = date.today()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        for days_ago in range(3):
            target_date = today - timedelta(days=days_ago)
            timestamp = datetime.now() - timedelta(days=days_ago)

            # Add 2 requests per day
            for request_num in range(2):
                cursor.execute("""
                    INSERT INTO api_usage (timestamp, date, model, input_tokens, output_tokens, cost_usd, command)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp.isoformat(),
                    target_date.isoformat(),
                    "claude-sonnet-4-20250514",
                    100_000,
                    50_000,
                    1.05,
                    f"test_day_{days_ago}_req_{request_num}"
                ))

        conn.commit()

    # Get stats for 7 days
    stats = get_usage_stats(days=7)

    # Should have 6 total requests (2 per day × 3 days)
    assert stats["total_requests"] == 6

    # Total cost should be 6.3 (6 × 1.05)
    assert abs(stats["total_cost"] - 6.3) < 0.001

    # Should have 3 days in breakdown
    assert len(stats["daily_breakdown"]) == 3

    # Each day should have 2 requests and 2.1 cost
    for day_stat in stats["daily_breakdown"]:
        assert day_stat["requests"] == 2
        assert abs(day_stat["cost"] - 2.1) < 0.001

    # Average daily cost should be 6.3 / 7 ≈ 0.9
    assert abs(stats["average_daily_cost"] - (6.3 / 7)) < 0.001


def test_cost_alert_threshold(tmp_path, monkeypatch):
    """Test that cost alerts are triggered when threshold is exceeded."""
    from src.utils import track_api_usage

    # Set up test database
    db_path = tmp_path / "test_usage.db"
    monkeypatch.setattr("src.utils.USAGE_DB_PATH", db_path)

    # Mock environment variables for thresholds
    monkeypatch.setattr("src.utils.DAILY_COST_TARGET", 2.0)
    monkeypatch.setattr("src.utils.DAILY_COST_ALERT", 5.0)

    # Mock the cost notifier
    mock_notifier = MagicMock()
    with patch("src.utils._get_cost_notifier") as mock_get_notifier:
        mock_get_notifier.return_value = mock_notifier

        # First call - below target (no alert)
        track_api_usage("claude-sonnet-4-20250514", 100_000, 50_000)  # $1.05
        assert mock_notifier.send_alert.call_count == 0

        # Second call - exceeds target but below alert (logs info but no Slack)
        track_api_usage("claude-sonnet-4-20250514", 200_000, 100_000)  # $2.1, total $3.15
        assert mock_notifier.send_alert.call_count == 0

        # Third call - exceeds alert threshold (should trigger Slack alert)
        track_api_usage("claude-sonnet-4-20250514", 400_000, 200_000)  # $4.2, total $7.35
        assert mock_notifier.send_alert.call_count == 1

        # Verify alert was called with correct parameters
        alert_call = mock_notifier.send_alert.call_args
        assert alert_call[1]["title"] == "API Cost Alert"
        assert "7.35" in alert_call[1]["message"] or "7.3" in alert_call[1]["message"]
        assert alert_call[1]["severity"] == "warning"


def test_check_setup_all_valid(tmp_path, monkeypatch):
    """Test setup check when all configuration is valid."""
    from src.utils import check_setup

    # Mock directories
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"
    data_dir.mkdir()
    logs_dir.mkdir()

    monkeypatch.setattr("src.utils.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.LOGS_DIR", logs_dir)

    # Environment variables are set by mock_env_vars fixture
    # ANTHROPIC_API_KEY, HA_TOKEN, HA_URL should all be set

    # Run setup check
    is_valid, errors = check_setup()

    # Should be valid with no errors
    assert is_valid is True
    assert errors == []


def test_check_setup_missing_directories(tmp_path, monkeypatch):
    """Test that setup check creates missing directories."""
    from src.utils import check_setup

    # Set directories that don't exist yet
    data_dir = tmp_path / "data"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr("src.utils.DATA_DIR", data_dir)
    monkeypatch.setattr("src.utils.LOGS_DIR", logs_dir)

    # Directories should not exist initially
    assert not data_dir.exists()
    assert not logs_dir.exists()

    # Run setup check
    is_valid, errors = check_setup()

    # Should create directories
    assert data_dir.exists()
    assert logs_dir.exists()

    # Should be valid with no errors
    assert is_valid is True
    assert errors == []
