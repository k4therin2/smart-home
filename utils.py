#!/usr/bin/env python3
"""
Utility scripts for managing the home automation agent.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, Any
from functools import wraps
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


# ============================================================================
# Prompt Management and API Tracking
# ============================================================================

# Pricing for Claude Sonnet 4 (per million tokens)
SONNET_4_INPUT_PRICE = 3.00   # $3.00 per 1M input tokens
SONNET_4_OUTPUT_PRICE = 15.00  # $15.00 per 1M output tokens


def load_prompts() -> Dict[str, Any]:
    """
    Load prompt configuration from prompts/config.json.

    Returns:
        Dictionary with all prompt configurations
    """
    config_path = os.path.join("prompts", "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Prompt config not found at {config_path}")
        return {
            "main_agent": {"system": "You are a helpful home lighting assistant.", "description": ""},
            "hue_specialist": {"system": "", "fire_flicker": "", "effect_mapping": "", "description": ""}
        }


def save_prompts(prompts: Dict[str, Any]) -> bool:
    """
    Save prompt configuration to prompts/config.json.

    Args:
        prompts: Dictionary with prompt configurations

    Returns:
        True if successful, False otherwise
    """
    config_path = os.path.join("prompts", "config.json")
    try:
        with open(config_path, "w") as f:
            json.dump(prompts, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving prompts: {e}")
        return False


def extract_json_from_markdown(response_text: str) -> str:
    """
    Robustly extract JSON from Claude response that may contain markdown code blocks.

    Handles various formats:
    - ```json\\n{...}\\n```
    - ```\\n{...}\\n```
    - {...} (plain JSON)

    Args:
        response_text: Raw response text from Claude

    Returns:
        Clean JSON string ready for parsing
    """
    # Remove markdown code fences
    response_text = re.sub(r'```[a-z]*\n', '', response_text)
    response_text = re.sub(r'\n?```', '', response_text)

    return response_text.strip()


def track_api_usage(input_tokens: int, output_tokens: int):
    """
    Track API usage for the current day.

    Args:
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
    """
    usage_file = os.path.join("data", "api_usage.json")

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # Load existing usage
    try:
        with open(usage_file, "r") as f:
            usage_data = json.load(f)
    except FileNotFoundError:
        usage_data = {}

    # Get today's date
    today = datetime.now().strftime("%Y-%m-%d")

    # Initialize today's data if not exists
    if today not in usage_data:
        usage_data[today] = {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0
        }

    # Update usage
    usage_data[today]["requests"] += 1
    usage_data[today]["input_tokens"] += input_tokens
    usage_data[today]["output_tokens"] += output_tokens

    # Calculate cost
    input_cost = (input_tokens / 1_000_000) * SONNET_4_INPUT_PRICE
    output_cost = (output_tokens / 1_000_000) * SONNET_4_OUTPUT_PRICE
    usage_data[today]["cost_usd"] += input_cost + output_cost

    # Round to 4 decimal places
    usage_data[today]["cost_usd"] = round(usage_data[today]["cost_usd"], 4)

    # Save updated usage
    with open(usage_file, "w") as f:
        json.dump(usage_data, f, indent=2)


def get_daily_usage(date: str = None) -> Dict[str, Any]:
    """
    Get API usage for a specific date.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.

    Returns:
        Dictionary with usage stats for the date
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    usage_file = os.path.join("data", "api_usage.json")

    try:
        with open(usage_file, "r") as f:
            usage_data = json.load(f)

        if date in usage_data:
            return {
                "date": date,
                **usage_data[date]
            }
        else:
            return {
                "date": date,
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0
            }
    except FileNotFoundError:
        return {
            "date": date,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0
        }


def anthropic_with_tracking(client_method):
    """
    Decorator to track Anthropic API calls.

    Wraps client.messages.create() to automatically track usage.
    """
    @wraps(client_method)
    def wrapper(*args, **kwargs):
        response = client_method(*args, **kwargs)

        # Track usage
        if hasattr(response, 'usage'):
            track_api_usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )

        return response

    return wrapper


def commit_prompt_changes(review_result: Dict[str, Any], user: str = "UI") -> Dict[str, Any]:
    """
    Git commit prompt configuration changes with review metadata.

    Args:
        review_result: Review results from the review agent
        user: Who made the change (e.g., "UI", "API", username)

    Returns:
        Dictionary with commit result
    """
    import subprocess

    try:
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--quiet", "prompts/config.json"],
            cwd=os.getcwd(),
            capture_output=True
        )

        # Exit code 1 means there are changes
        if result.returncode != 1:
            return {
                "success": True,
                "message": "No changes to commit",
                "committed": False
            }

        # Stage the config file
        subprocess.run(
            ["git", "add", "prompts/config.json"],
            cwd=os.getcwd(),
            check=True,
            capture_output=True
        )

        # Build commit message with review summary
        summary = review_result.get("summary", "Prompt configuration updated")
        total_issues = review_result.get("total_issues", 0)
        approved = review_result.get("approved", True)

        commit_msg = f"""Update prompt configuration via {user}

{summary}

Review: {"✓ Approved" if approved else "⚠ Has critical issues"} ({total_issues} issues found)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

        # Commit the changes
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=os.getcwd(),
            check=True,
            capture_output=True,
            text=True
        )

        # Get the commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = hash_result.stdout.strip()

        return {
            "success": True,
            "message": f"Changes committed: {commit_hash}",
            "committed": True,
            "commit_hash": commit_hash
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Git commit failed: {e.stderr.decode() if e.stderr else str(e)}",
            "committed": False
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Commit error: {str(e)}",
            "committed": False
        }


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
