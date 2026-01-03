#!/usr/bin/env python3
"""
Test the feedback endpoint to ensure it doesn't hang.

This script simulates the feedback flow without requiring authentication.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.feedback_handler import file_bug_in_vikunja, alert_developers_via_nats


def test_bug_filing():
    """Test bug filing in Vikunja."""
    print("Testing bug filing in Vikunja...")

    command = "turn off kitchen lights"
    response = "I've turned off the kitchen lights."

    bug_id = file_bug_in_vikunja(command, response)

    if bug_id:
        print(f"✓ Bug filed successfully: {bug_id}")
        return bug_id
    else:
        print("✗ Bug filing failed")
        return None


def test_nats_alert(bug_id: str):
    """Test NATS alert (should not hang even if NATS is unreachable)."""
    print("Testing NATS alert (with timeout)...")

    command = "turn off kitchen lights"
    response = "I've turned off the kitchen lights."

    try:
        # This should complete within 2 seconds even if NATS fails
        alert_developers_via_nats(bug_id, command, response)
        print("✓ NATS alert completed (may have failed, but didn't hang)")
        return True
    except Exception as e:
        print(f"✗ NATS alert raised exception: {e}")
        return False


if __name__ == "__main__":
    print("=== Feedback Handler Test ===\n")

    # Test 1: Bug filing
    bug_id = test_bug_filing()
    if not bug_id:
        print("\n❌ Bug filing failed - cannot continue")
        sys.exit(1)

    print()

    # Test 2: NATS alert (with timeout)
    nats_success = test_nats_alert(bug_id)

    print("\n=== Test Complete ===")
    if bug_id and nats_success:
        print("✓ All tests passed")
        print(f"\nBug ID: {bug_id}")
        print("Note: NATS alert may have failed due to SSL, but it didn't hang.")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)
