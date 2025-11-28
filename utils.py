#!/usr/bin/env python3
"""
Utility scripts for managing the home automation agent.
"""

import os
import json
from dotenv import load_dotenv
from tools.lights import get_available_rooms

load_dotenv()


def list_lights():
    """List all available lights in Home Assistant."""
    print("Fetching lights from Home Assistant...\n")

    result = get_available_rooms()

    if not result["success"]:
        print(f"Error: {result['error']}")
        return

    lights = result["lights"]
    print(f"Found {result['count']} lights:\n")

    for light in lights:
        state_icon = "💡" if light["state"] == "on" else "⚫"
        print(f"{state_icon} {light['name']}")
        print(f"   Entity ID: {light['entity_id']}")
        print(f"   State: {light['state']}")
        print()

    print("\nTo use these in your agent:")
    print("1. Edit tools/lights.py")
    print("2. Update the room_entity_map dictionary")
    print("3. Map room names to entity IDs")


def test_ha_connection():
    """Test connection to Home Assistant."""
    ha_url = os.getenv("HA_URL")
    ha_token = os.getenv("HA_TOKEN")

    print("Testing Home Assistant connection...\n")

    if not ha_url:
        print("❌ HA_URL not set in .env file")
        return

    if not ha_token:
        print("❌ HA_TOKEN not set in .env file")
        return

    print(f"✓ HA_URL configured: {ha_url}")
    print(f"✓ HA_TOKEN configured: {ha_token[:20]}...")

    import requests
    try:
        response = requests.get(
            f"{ha_url}/api/",
            headers={"Authorization": f"Bearer {ha_token}"},
            timeout=5
        )
        response.raise_for_status()
        print(f"\n✓ Successfully connected to Home Assistant!")
        print(f"  Message: {response.json().get('message', 'N/A')}")
    except Exception as e:
        print(f"\n❌ Failed to connect to Home Assistant:")
        print(f"   {str(e)}")


def test_anthropic_key():
    """Test Anthropic API key."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    print("Testing Anthropic API key...\n")

    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set in .env file")
        return

    if not api_key.startswith("sk-ant-"):
        print("⚠️  API key doesn't start with 'sk-ant-' - it might be invalid")
        return

    print(f"✓ API key configured: {api_key[:20]}...")

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        # Simple test call
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )

        print("✓ Successfully authenticated with Anthropic API!")
        print(f"  Model: {response.model}")

    except Exception as e:
        print(f"❌ Failed to authenticate with Anthropic API:")
        print(f"   {str(e)}")


def check_setup():
    """Run all setup checks."""
    print("=" * 70)
    print("HOME AUTOMATION AGENT - SETUP CHECK")
    print("=" * 70)
    print()

    # Check for .env file
    if not os.path.exists(".env"):
        print("❌ No .env file found!")
        print("   Run: cp .env.example .env")
        print("   Then edit .env with your credentials\n")
        return

    print("✓ .env file exists\n")

    # Test each component
    test_anthropic_key()
    print()
    test_ha_connection()
    print()

    print("=" * 70)
    print("\nNext steps:")
    print("1. Run: python utils.py --list-lights")
    print("2. Update tools/lights.py with your room mappings")
    print("3. Test: python agent.py \"turn living room to fire\"")
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "--list-lights":
            list_lights()
        elif command == "--test-ha":
            test_ha_connection()
        elif command == "--test-api":
            test_anthropic_key()
        elif command == "--check":
            check_setup()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  --check        Run all setup checks")
            print("  --list-lights  List all lights in Home Assistant")
            print("  --test-ha      Test Home Assistant connection")
            print("  --test-api     Test Anthropic API key")
    else:
        check_setup()
