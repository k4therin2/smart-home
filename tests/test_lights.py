"""
Test suite for lighting ambiance scenarios.

This script tests various natural language descriptions to ensure
the agent interprets them correctly.
"""

import sys
import os

# Add parent directory to path to import agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import run_agent


# Test scenarios from the README
TEST_SCENARIOS = [
    {
        "command": "turn living room to fire",
        "expected": {
            "temp_range": (2000, 2500),
            "brightness_range": (40, 60),
            "description": "warm, fire-like glow"
        }
    },
    {
        "command": "make living room ocean",
        "expected": {
            "temp_range": (5000, 6500),
            "brightness_range": (50, 70),
            "description": "cool blue tones"
        }
    },
    {
        "command": "set living room to cozy",
        "expected": {
            "temp_range": (2200, 2700),
            "brightness_range": (30, 50),
            "description": "warm, dim"
        }
    },
    {
        "command": "make living room energizing",
        "expected": {
            "temp_range": (4000, 5000),
            "brightness_range": (80, 100),
            "description": "cool white, bright"
        }
    },
    {
        "command": "turn bedroom romantic",
        "expected": {
            "temp_range": (2000, 2200),
            "brightness_range": (10, 30),
            "description": "very warm, very dim"
        }
    },
    {
        "command": "set office for reading",
        "expected": {
            "temp_range": (3000, 3500),
            "brightness_range": (70, 90),
            "description": "neutral-warm, bright"
        }
    }
]


def run_manual_tests():
    """
    Run manual tests where you observe the actual lights.

    This is for Phase 1 development - you run commands and see
    if the lights match what you expected.
    """
    print("=" * 70)
    print("MANUAL LIGHTING TEST SUITE")
    print("=" * 70)
    print("\nThis will test various ambiance descriptions.")
    print("Observe your actual lights and verify they match expectations.\n")

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}/{len(TEST_SCENARIOS)}: {scenario['command']}")
        print(f"{'='*70}")
        print(f"\nExpected:")
        print(f"  - Color temp: {scenario['expected']['temp_range'][0]}-{scenario['expected']['temp_range'][1]}K")
        print(f"  - Brightness: {scenario['expected']['brightness_range'][0]}-{scenario['expected']['brightness_range'][1]}%")
        print(f"  - Feel: {scenario['expected']['description']}")

        input("\nPress Enter to run this test (or Ctrl+C to exit)...")

        # Run the agent
        response = run_agent(scenario["command"], verbose=True)

        print(f"\n{'='*70}")
        print(f"Agent Response: {response}")
        print(f"{'='*70}")

        # Get user feedback
        feedback = input("\nDoes the lighting match expectations? (y/n/skip): ").strip().lower()

        if feedback == 'y':
            print("✓ Test passed!")
        elif feedback == 'n':
            notes = input("What was wrong? (optional): ").strip()
            print(f"✗ Test failed. Notes: {notes}")
        else:
            print("⊘ Test skipped")

        print("\n")


def run_quick_test():
    """
    Run a quick single test to verify the agent is working.
    """
    print("Running quick test: 'turn living room to fire'\n")
    response = run_agent("turn living room to fire", verbose=True)
    print(f"\nAgent response: {response}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        run_quick_test()
    else:
        run_manual_tests()
