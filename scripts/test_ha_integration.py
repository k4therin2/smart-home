#!/usr/bin/env python3
"""
Test script for Home Assistant integration.

Tests connectivity, service calls, and device sync.

Usage:
    python scripts/test_ha_integration.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import get_logger, setup_logging
from src.config import HA_URL, HA_TOKEN, validate_config
from src.homeassistant import (
    HomeAssistantClient,
    HomeAssistantConnectionError,
    HomeAssistantAuthError,
    HomeAssistantError,
)
from src.database import (
    get_all_devices,
    get_daily_usage,
    get_setting,
    set_setting,
)
from src.device_sync import sync_devices_from_ha, get_device_summary

# Set up logging
setup_logging(level="DEBUG")
logger = get_logger(__name__)


def test_config_validation():
    """Test configuration validation."""
    print("\n" + "=" * 60)
    print("Testing Configuration Validation")
    print("=" * 60)

    errors = validate_config()

    if errors:
        print(f"Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("Configuration valid!")
    print(f"  HA_URL: {HA_URL}")
    print(f"  HA_TOKEN: {'*' * 8}...{HA_TOKEN[-4:] if HA_TOKEN else 'NOT SET'}")
    return True


def test_ha_connection():
    """Test Home Assistant connectivity."""
    print("\n" + "=" * 60)
    print("Testing Home Assistant Connection")
    print("=" * 60)

    try:
        client = HomeAssistantClient()
        client.check_connection()
        print("Connection successful!")

        # Get HA config
        config = client.get_config()
        print(f"  HA Version: {config.get('version', 'unknown')}")
        print(f"  Location: {config.get('location_name', 'unknown')}")
        print(f"  Unit System: {config.get('unit_system', {}).get('temperature', 'unknown')}")

        return True, client

    except HomeAssistantAuthError as error:
        print(f"Authentication failed: {error}")
        return False, None

    except HomeAssistantConnectionError as error:
        print(f"Connection failed: {error}")
        return False, None

    except HomeAssistantError as error:
        print(f"Error: {error}")
        return False, None


def test_device_queries(client: HomeAssistantClient):
    """Test device state queries."""
    print("\n" + "=" * 60)
    print("Testing Device Queries")
    print("=" * 60)

    # Get all lights
    lights = client.get_lights()
    print(f"\nFound {len(lights)} lights:")
    for light in lights[:5]:  # Show first 5
        entity_id = light.get("entity_id")
        state = light.get("state")
        name = light.get("attributes", {}).get("friendly_name", entity_id)
        print(f"  - {name} ({entity_id}): {state}")

    if len(lights) > 5:
        print(f"  ... and {len(lights) - 5} more")

    # Get all switches
    switches = client.get_switches()
    print(f"\nFound {len(switches)} switches:")
    for switch in switches[:5]:
        entity_id = switch.get("entity_id")
        state = switch.get("state")
        name = switch.get("attributes", {}).get("friendly_name", entity_id)
        print(f"  - {name} ({entity_id}): {state}")

    if len(switches) > 5:
        print(f"  ... and {len(switches) - 5} more")

    return True


def test_device_sync(client: HomeAssistantClient):
    """Test device sync to local database."""
    print("\n" + "=" * 60)
    print("Testing Device Sync")
    print("=" * 60)

    stats = sync_devices_from_ha(client)
    print(f"\nSync Statistics:")
    print(f"  Total discovered: {stats['total_discovered']}")
    print(f"  New devices: {stats['new_devices']}")
    print(f"  Updated devices: {stats['updated_devices']}")
    print(f"\n  By domain:")
    for domain, count in sorted(stats['by_domain'].items()):
        print(f"    {domain}: {count}")

    # Get summary from local DB
    summary = get_device_summary()
    print(f"\nLocal Database Summary:")
    print(f"  Total devices: {summary['total']}")
    print(f"\n  By room:")
    for room, count in sorted(summary['by_room'].items()):
        print(f"    {room}: {count}")

    return True


def test_database_operations():
    """Test database operations."""
    print("\n" + "=" * 60)
    print("Testing Database Operations")
    print("=" * 60)

    # Test settings
    set_setting("test_key", {"foo": "bar"}, "Test setting")
    value = get_setting("test_key")
    print(f"Settings test: {value}")

    # Test daily usage
    usage = get_daily_usage()
    print(f"\nDaily API usage:")
    print(f"  Date: {usage['date']}")
    print(f"  Requests: {usage['requests']}")
    print(f"  Cost: ${usage['cost_usd']:.4f}")

    # List all devices
    devices = get_all_devices()
    print(f"\nRegistered devices: {len(devices)}")

    return True


def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# Home Assistant Integration Tests")
    print("#" * 60)

    # Test configuration
    if not test_config_validation():
        print("\nConfiguration invalid - cannot proceed with tests")
        print("Please set up your .env file with HA_URL and HA_TOKEN")
        return 1

    # Test HA connection
    success, client = test_ha_connection()
    if not success:
        print("\nCannot connect to Home Assistant")
        print("Please verify:")
        print("  1. Home Assistant is running")
        print(f"  2. URL is correct: {HA_URL}")
        print("  3. Access token is valid")
        return 1

    # Test device queries
    test_device_queries(client)

    # Test device sync
    test_device_sync(client)

    # Test database
    test_database_operations()

    print("\n" + "#" * 60)
    print("# All tests completed successfully!")
    print("#" * 60 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
