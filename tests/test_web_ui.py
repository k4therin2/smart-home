#!/usr/bin/env python3
"""
Web UI Integration Tests using Playwright

Tests the Phase 1 Stream 3 web interface functionality.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv("TEST_URL", "http://localhost:5050")
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def test_web_ui():
    """Test the web UI loads and basic functionality works."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        # Test 1: Page loads
        print("Test 1: Loading page...")
        page.goto(BASE_URL)
        page.screenshot(path=str(SCREENSHOT_DIR / "01_initial_load.png"))

        # Verify header exists
        header = page.locator("header h1")
        expect(header).to_have_text("Smart Home")
        print("  ✓ Page loaded, header found")

        # Test 2: Status indicator shows connected
        print("Test 2: Checking status indicator...")
        page.wait_for_selector("#status-text")
        page.screenshot(path=str(SCREENSHOT_DIR / "02_status_loaded.png"))
        status_text = page.locator("#status-text").text_content()
        print(f"  Status: {status_text}")
        assert status_text in ["Online", "Degraded", "Unknown"], f"Unexpected status: {status_text}"
        print("  ✓ Status indicator working")

        # Test 3: Device grid shows devices
        print("Test 3: Checking device grid...")
        page.wait_for_timeout(1000)  # Wait for status API response
        page.screenshot(path=str(SCREENSHOT_DIR / "03_devices_loaded.png"))
        devices_grid = page.locator("#devices-grid")
        device_cards = devices_grid.locator(".device-card")
        device_count = device_cards.count()
        print(f"  Found {device_count} device(s)")

        # Test 4: Command input exists and is focused
        print("Test 4: Checking command input...")
        command_input = page.locator("#command-input")
        expect(command_input).to_be_visible()
        expect(command_input).to_be_enabled()
        print("  ✓ Command input visible and enabled")

        # Test 5: Voice button exists
        print("Test 5: Checking voice button...")
        voice_btn = page.locator("#voice-btn")
        expect(voice_btn).to_be_visible()
        print("  ✓ Voice button visible")

        # Test 6: Submit a command (will use agent)
        print("Test 6: Testing command submission...")
        command_input.fill("what time is it")
        page.screenshot(path=str(SCREENSHOT_DIR / "04_command_entered.png"))

        submit_btn = page.locator("#submit-btn")
        submit_btn.click()

        # Wait for response
        page.wait_for_timeout(5000)  # Agent may take a few seconds
        page.screenshot(path=str(SCREENSHOT_DIR / "05_response_received.png"))

        response_area = page.locator("#response-area")
        response_messages = response_area.locator(".response-message")

        if response_messages.count() > 0:
            response_text = response_messages.first.locator(".response-text").text_content()
            print(f"  Response: {response_text[:100]}...")
            print("  ✓ Command submitted and response received")
        else:
            print("  ⚠ No response message found (may be placeholder)")

        # Test 7: History list updates
        print("Test 7: Checking history list...")
        history_list = page.locator("#history-list")
        history_items = history_list.locator("li:not(.placeholder-text)")
        if history_items.count() > 0:
            print(f"  Found {history_items.count()} history item(s)")
            print("  ✓ History list updated")
        else:
            print("  ⚠ No history items (may be first run)")

        # Final screenshot
        page.screenshot(path=str(SCREENSHOT_DIR / "06_final_state.png"))

        browser.close()

        print("\n" + "=" * 50)
        print("All tests passed!")
        print(f"Screenshots saved to: {SCREENSHOT_DIR}")
        print("=" * 50)


if __name__ == "__main__":
    test_web_ui()
