"""
E2E Test Configuration and Fixtures

Provides shared fixtures for end-to-end tests using Playwright.
Tests interact with the running application via browser automation.

WP-10.27: E2E Testing Suite
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from playwright.sync_api import sync_playwright, expect
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None
    expect = None


# =============================================================================
# Test Configuration
# =============================================================================

# URLs
BASE_URL = os.getenv("TEST_URL", "http://localhost:5049")
SECURE_URL = os.getenv("TEST_SECURE_URL", "https://localhost:5050")

# Test User
TEST_USERNAME = os.getenv("TEST_USERNAME", "e2etest")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "e2etest123")

# Directories
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots" / "e2e"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Timeouts (ms)
DEFAULT_TIMEOUT = 10000
COMMAND_TIMEOUT = 30000
NAVIGATION_TIMEOUT = 15000


# =============================================================================
# Skip markers
# =============================================================================

pytest_plugins = []

# Skip all tests if Playwright not installed
pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT,
    reason="playwright not installed - run 'pip install playwright && playwright install'"
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def browser():
    """
    Session-scoped browser instance.

    Launches a single browser for all tests in the session.
    """
    if not HAS_PLAYWRIGHT:
        pytest.skip("Playwright not installed")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            slow_mo=int(os.getenv("SLOW_MO", "0"))
        )
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    """
    Fresh page for each test function.

    Provides isolated context for each test.
    """
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,  # Allow self-signed certs
    )
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    yield page
    page.close()
    context.close()


@pytest.fixture(scope="function")
def logged_in_page(page):
    """
    Page that's already logged in with test credentials.
    """
    ensure_test_user_exists()
    login_to_app(page)
    yield page


@pytest.fixture
def screenshot_path():
    """
    Factory fixture for generating screenshot paths.
    """
    def _get_path(name: str) -> str:
        return str(SCREENSHOT_DIR / f"{name}.png")
    return _get_path


# =============================================================================
# Helper Functions
# =============================================================================


def ensure_test_user_exists():
    """Create E2E test user if it doesn't exist."""
    try:
        from src.security.auth import create_user, verify_user

        if verify_user(TEST_USERNAME, TEST_PASSWORD) is None:
            create_user(TEST_USERNAME, TEST_PASSWORD)
    except Exception as e:
        print(f"Warning: Could not ensure test user: {e}")


def login_to_app(page, username: str = None, password: str = None):
    """
    Log in to the application.

    Args:
        page: Playwright page object
        username: Username to use (default: TEST_USERNAME)
        password: Password to use (default: TEST_PASSWORD)
    """
    username = username or TEST_USERNAME
    password = password or TEST_PASSWORD

    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)

    try:
        # Check if login form is visible
        username_input = page.locator("input[name='username']")
        if username_input.is_visible(timeout=2000):
            page.fill("input[name='username']", username)
            page.fill("input[name='password']", password)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
    except Exception:
        pass  # May already be logged in

    # Wait for main app to load
    page.wait_for_selector("#command-input", timeout=DEFAULT_TIMEOUT)


def wait_for_response(page, timeout: int = COMMAND_TIMEOUT):
    """Wait for command response to appear."""
    page.wait_for_selector(".response-text", timeout=timeout)


def take_screenshot(page, name: str):
    """Take a screenshot and save to the screenshots directory."""
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path))
    return path


def submit_command(page, command: str, wait_for_response: bool = True):
    """
    Submit a command and optionally wait for response.

    Args:
        page: Playwright page object
        command: Command text to submit
        wait_for_response: Whether to wait for response

    Returns:
        Response text if wait_for_response is True
    """
    command_input = page.locator("#command-input")
    command_input.fill(command)
    page.locator("#submit-btn").click()

    if wait_for_response:
        page.wait_for_selector(".response-text", timeout=COMMAND_TIMEOUT)
        return page.locator(".response-text").first.text_content()

    return None


def get_all_responses(page) -> list[str]:
    """Get all response texts from the conversation."""
    responses = page.locator(".response-text").all()
    return [r.text_content() for r in responses]


def clear_conversation(page):
    """Clear the conversation history if a clear button exists."""
    try:
        clear_btn = page.locator("#clear-btn, .clear-conversation")
        if clear_btn.is_visible(timeout=1000):
            clear_btn.click()
            time.sleep(0.5)
    except Exception:
        pass


# =============================================================================
# Mock Helpers
# =============================================================================


def mock_api_response(page, endpoint: str, response_data: dict, status: int = 200):
    """
    Set up route interception to mock API responses.

    Args:
        page: Playwright page object
        endpoint: API endpoint pattern (e.g., "**/api/command")
        response_data: Data to return
        status: HTTP status code
    """
    def handle_route(route):
        route.fulfill(
            status=status,
            body=json.dumps(response_data),
            headers={"Content-Type": "application/json"}
        )

    page.route(endpoint, handle_route)


def mock_command_api(page, response: str = "Done!"):
    """Mock the command API with a standard response."""
    mock_api_response(page, "**/api/command", {
        "success": True,
        "response": response
    })


def mock_voice_api(page, transcription: str = "test command"):
    """Mock the voice transcription API."""
    mock_api_response(page, "**/api/voice", {
        "success": True,
        "transcription": transcription
    })
