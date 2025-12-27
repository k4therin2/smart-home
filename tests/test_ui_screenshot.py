"""
Test script to capture screenshot of Web UI using Playwright.

This is not a standard pytest test - it's a standalone utility script.
Run directly with: python tests/test_ui_screenshot.py
"""

import pytest

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None

# Skip all tests in this module if playwright is not installed
pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT,
    reason="playwright not installed - run 'pip install playwright && playwright install'"
)


def capture_screenshot():
    """Capture screenshot of the web UI."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Load the page
        page.goto("http://localhost:5050")

        # Wait for the page to load
        page.wait_for_load_state("networkidle")

        # Take initial screenshot
        page.screenshot(path="/Users/katherine/Documents/Smarthome/tests/screenshot_initial.png")
        print("Captured initial screenshot")

        # Type a command and submit
        page.fill("#command-input", "turn on living room lights")
        page.click("#submit-btn")

        # Wait for response
        page.wait_for_selector(".response-message", timeout=5000)

        # Take screenshot after command
        page.screenshot(path="/Users/katherine/Documents/Smarthome/tests/screenshot_with_response.png")
        print("Captured screenshot with response")

        browser.close()
        print("Done!")


if __name__ == "__main__":
    capture_screenshot()
