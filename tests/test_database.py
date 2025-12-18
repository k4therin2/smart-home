"""
Tests for src/database.py - Database Operations

Tests SQLite database operations including device registry,
command history, API usage tracking, and settings.
"""

import json
from datetime import datetime, timedelta

import pytest


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""

    def test_database_file_created(self, test_db):
        """Database file should be created on initialization."""
        assert test_db.exists()

    def test_devices_table_exists(self, test_db):
        """Devices table should exist after initialization."""
        from src.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='devices'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_command_history_table_exists(self, test_db):
        """Command history table should exist."""
        from src.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_api_usage_table_exists(self, test_db):
        """API usage table should exist."""
        from src.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_settings_table_exists(self, test_db):
        """Settings table should exist."""
        from src.database import get_cursor

        with get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
            )
            result = cursor.fetchone()
            assert result is not None


class TestDeviceRegistry:
    """Test device registry CRUD operations."""

    def test_register_new_device(self, test_db):
        """Should successfully register a new device."""
        from src.database import register_device, get_device

        result = register_device(
            entity_id="light.test_room",
            device_type="light",
            friendly_name="Test Room Light",
            room="test_room",
            capabilities=["brightness", "color_temp"],
        )

        assert result is True

        device = get_device("light.test_room")
        assert device is not None
        assert device["entity_id"] == "light.test_room"
        assert device["device_type"] == "light"
        assert device["friendly_name"] == "Test Room Light"
        assert device["room"] == "test_room"
        assert "brightness" in device["capabilities"]

    def test_update_existing_device(self, test_db):
        """Should update device on conflict (upsert)."""
        from src.database import register_device, get_device

        # Register initial device
        register_device(
            entity_id="light.update_test",
            device_type="light",
            friendly_name="Original Name",
            room="room1",
        )

        # Update with same entity_id
        register_device(
            entity_id="light.update_test",
            device_type="light",
            friendly_name="Updated Name",
            room="room2",
        )

        device = get_device("light.update_test")
        assert device["friendly_name"] == "Updated Name"
        assert device["room"] == "room2"

    def test_get_nonexistent_device(self, test_db):
        """Should return None for nonexistent device."""
        from src.database import get_device

        device = get_device("light.does_not_exist")
        assert device is None

    def test_get_all_devices(self, test_db, sample_devices):
        """Should return all registered devices."""
        from src.database import register_device, get_all_devices

        # Register sample devices
        for device_data in sample_devices:
            register_device(**device_data)

        devices = get_all_devices()
        assert len(devices) == len(sample_devices)

    def test_get_devices_by_room(self, test_db, sample_devices):
        """Should filter devices by room."""
        from src.database import register_device, get_devices_by_room

        for device_data in sample_devices:
            register_device(**device_data)

        living_room_devices = get_devices_by_room("living_room")
        assert len(living_room_devices) == 1
        assert living_room_devices[0]["entity_id"] == "light.living_room"

    def test_get_devices_by_type(self, test_db, sample_devices):
        """Should filter devices by type."""
        from src.database import register_device, get_devices_by_type

        for device_data in sample_devices:
            register_device(**device_data)

        lights = get_devices_by_type("light")
        assert len(lights) == 2

        switches = get_devices_by_type("switch")
        assert len(switches) == 1

    def test_delete_device(self, test_db):
        """Should delete a device from registry."""
        from src.database import register_device, get_device, delete_device

        register_device(
            entity_id="light.to_delete",
            device_type="light",
        )

        assert get_device("light.to_delete") is not None

        result = delete_device("light.to_delete")
        assert result is True

        assert get_device("light.to_delete") is None

    def test_delete_nonexistent_device(self, test_db):
        """Should return False when deleting nonexistent device."""
        from src.database import delete_device

        result = delete_device("light.does_not_exist")
        assert result is False

    def test_device_metadata_json_stored(self, test_db):
        """Should store and retrieve device metadata as JSON."""
        from src.database import register_device, get_device

        metadata = {
            "sw_version": "1.2.3",
            "hw_version": "A1",
            "custom_field": {"nested": "value"},
        }

        register_device(
            entity_id="light.with_metadata",
            device_type="light",
            metadata=metadata,
        )

        device = get_device("light.with_metadata")
        assert device["metadata"] == metadata
        assert device["metadata"]["custom_field"]["nested"] == "value"


class TestCommandHistory:
    """Test command history recording and retrieval."""

    def test_record_command(self, test_db):
        """Should record a command to history."""
        from src.database import record_command, get_command_history

        command_id = record_command(
            command_text="turn on living room lights",
            command_type="voice",
            result="success",
            response_text="Turned on the living room lights",
            input_tokens=150,
            output_tokens=50,
            cost_usd=0.001,
            latency_ms=500,
        )

        assert command_id > 0

        history = get_command_history(limit=1)
        assert len(history) == 1
        assert history[0]["command_text"] == "turn on living room lights"
        assert history[0]["command_type"] == "voice"
        assert history[0]["result"] == "success"

    def test_record_command_with_interpreted_action(self, test_db):
        """Should store interpreted action as JSON."""
        from src.database import record_command, get_command_history

        action = {
            "tool": "set_room_ambiance",
            "params": {"room": "living_room", "action": "on"},
        }

        record_command(
            command_text="lights on",
            interpreted_action=action,
        )

        history = get_command_history(limit=1)
        assert history[0]["interpreted_action"] == action

    def test_record_failed_command(self, test_db):
        """Should record failed commands with error messages."""
        from src.database import record_command, get_command_history

        record_command(
            command_text="invalid command",
            result="failure",
            error_message="Unknown room: basement",
        )

        history = get_command_history(limit=1)
        assert history[0]["result"] == "failure"
        assert "Unknown room" in history[0]["error_message"]

    def test_get_command_history_ordering(self, test_db):
        """Should return commands in reverse chronological order."""
        from src.database import record_command, get_command_history

        record_command(command_text="first command")
        record_command(command_text="second command")
        record_command(command_text="third command")

        history = get_command_history(limit=3)
        assert history[0]["command_text"] == "third command"
        assert history[2]["command_text"] == "first command"

    def test_get_command_history_limit(self, test_db):
        """Should respect limit parameter."""
        from src.database import record_command, get_command_history

        for i in range(10):
            record_command(command_text=f"command {i}")

        history = get_command_history(limit=5)
        assert len(history) == 5

    def test_get_command_history_offset(self, test_db):
        """Should respect offset parameter."""
        from src.database import record_command, get_command_history

        for i in range(10):
            record_command(command_text=f"command {i}")

        history = get_command_history(limit=5, offset=5)
        assert len(history) == 5
        # Due to DESC ordering, offset=5 skips newest 5
        assert history[0]["command_text"] == "command 4"


class TestAPIUsageTracking:
    """Test API usage tracking and aggregation."""

    def test_track_api_usage(self, test_db):
        """Should track API usage for the day."""
        from src.database import track_api_usage, get_daily_usage

        track_api_usage(
            provider="anthropic",
            model="claude-sonnet-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
        )

        usage = get_daily_usage()
        assert usage["input_tokens"] == 1000
        assert usage["output_tokens"] == 500
        assert usage["requests"] == 1
        assert usage["cost_usd"] == 0.05

    def test_track_api_usage_aggregation(self, test_db):
        """Should aggregate multiple API calls for same day/provider/model."""
        from src.database import track_api_usage, get_daily_usage

        # First call
        track_api_usage(
            provider="anthropic",
            model="claude-sonnet-4",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.05,
        )

        # Second call
        track_api_usage(
            provider="anthropic",
            model="claude-sonnet-4",
            input_tokens=2000,
            output_tokens=1000,
            cost_usd=0.10,
        )

        usage = get_daily_usage()
        assert usage["input_tokens"] == 3000
        assert usage["output_tokens"] == 1500
        assert usage["requests"] == 2
        assert abs(usage["cost_usd"] - 0.15) < 0.001  # floating point tolerance

    def test_get_daily_usage_specific_date(self, test_db):
        """Should return usage for specific date."""
        from src.database import get_daily_usage

        usage = get_daily_usage(date="2024-01-15")
        # No usage for this date
        assert usage["input_tokens"] == 0
        assert usage["requests"] == 0
        assert usage["cost_usd"] == 0.0

    def test_get_usage_for_period(self, test_db):
        """Should return usage across date range."""
        from src.database import get_cursor, get_usage_for_period

        # Insert test data for multiple dates
        with get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO api_usage (date, provider, model, total_input_tokens,
                                       total_output_tokens, total_requests, total_cost_usd)
                VALUES
                    ('2024-01-01', 'anthropic', 'claude-sonnet-4', 1000, 500, 5, 0.10),
                    ('2024-01-02', 'anthropic', 'claude-sonnet-4', 2000, 1000, 10, 0.20),
                    ('2024-01-03', 'anthropic', 'claude-sonnet-4', 1500, 750, 7, 0.15)
            """)

        usage = get_usage_for_period("2024-01-01", "2024-01-03")
        assert len(usage) == 3
        assert usage[0]["date"] == "2024-01-01"
        assert usage[2]["date"] == "2024-01-03"


class TestSettingsStore:
    """Test key-value settings store."""

    def test_set_and_get_setting(self, test_db):
        """Should set and retrieve a setting."""
        from src.database import set_setting, get_setting

        set_setting("test_key", "test_value")
        result = get_setting("test_key")
        assert result == "test_value"

    def test_set_setting_with_description(self, test_db):
        """Should store setting with description."""
        from src.database import set_setting, get_cursor

        set_setting("test_key", "test_value", description="Test description")

        with get_cursor() as cursor:
            cursor.execute("SELECT description FROM settings WHERE key = ?", ("test_key",))
            row = cursor.fetchone()
            assert row["description"] == "Test description"

    def test_get_nonexistent_setting_returns_default(self, test_db):
        """Should return default value for missing setting."""
        from src.database import get_setting

        result = get_setting("nonexistent", default="default_value")
        assert result == "default_value"

    def test_get_nonexistent_setting_returns_none(self, test_db):
        """Should return None for missing setting without default."""
        from src.database import get_setting

        result = get_setting("nonexistent")
        assert result is None

    def test_set_setting_complex_value(self, test_db):
        """Should store complex JSON values."""
        from src.database import set_setting, get_setting

        value = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "number": 42.5,
            "boolean": True,
        }

        set_setting("complex_setting", value)
        result = get_setting("complex_setting")
        assert result == value

    def test_update_existing_setting(self, test_db):
        """Should update existing setting on conflict."""
        from src.database import set_setting, get_setting

        set_setting("update_test", "original")
        set_setting("update_test", "updated")

        result = get_setting("update_test")
        assert result == "updated"

    def test_get_all_settings(self, test_db):
        """Should retrieve all settings."""
        from src.database import set_setting, get_all_settings

        set_setting("key1", "value1")
        set_setting("key2", "value2")
        set_setting("key3", {"nested": True})

        all_settings = get_all_settings()
        assert all_settings["key1"] == "value1"
        assert all_settings["key2"] == "value2"
        assert all_settings["key3"]["nested"] is True


class TestDeviceStateHistory:
    """Test device state history recording."""

    def test_record_device_state(self, test_db):
        """Should record a device state snapshot."""
        from src.database import record_device_state, get_device_state_history

        record_device_state(
            entity_id="light.test",
            state="on",
            attributes={"brightness": 255, "color_temp": 370},
        )

        history = get_device_state_history("light.test", limit=1)
        assert len(history) == 1
        assert history[0]["state"] == "on"
        assert history[0]["attributes"]["brightness"] == 255

    def test_device_state_history_ordering(self, test_db):
        """Should return state history in reverse chronological order."""
        from src.database import record_device_state, get_device_state_history

        record_device_state("light.test", "off")
        record_device_state("light.test", "on")
        record_device_state("light.test", "off")

        history = get_device_state_history("light.test", limit=3)
        assert history[0]["state"] == "off"  # Most recent
        assert history[2]["state"] == "off"  # First recorded

    def test_device_state_history_limit(self, test_db):
        """Should respect limit parameter."""
        from src.database import record_device_state, get_device_state_history

        for i in range(10):
            record_device_state("light.test", f"state_{i}")

        history = get_device_state_history("light.test", limit=5)
        assert len(history) == 5


class TestDatabaseErrorHandling:
    """Test database error handling and rollback."""

    def test_cursor_context_manager_rollback(self, test_db):
        """Should rollback on error within context manager."""
        from src.database import get_cursor, get_device

        try:
            with get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO devices (entity_id, device_type) VALUES (?, ?)",
                    ("light.rollback_test", "light")
                )
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Device should not exist due to rollback
        device = get_device("light.rollback_test")
        assert device is None
