"""
UI Tests for Response Feedback Feature

Tests the feedback UI components using Playwright for browser automation.

Tests cover:
1. Feedback buttons render correctly with responses
2. Thumbs up button shows success confirmation
3. Thumbs down button triggers feedback form expansion
4. Feedback form submit/cancel behavior
5. Proper error handling for API failures

Uses Playwright for cross-browser UI testing, following project conventions
from test_web_ui.py and test_mobile_web_ui.py.
"""

import os
import re
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from playwright.sync_api import sync_playwright, expect
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None
    expect = None

# Skip all tests in this module if playwright is not installed
pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT,
    reason="playwright not installed - run 'pip install playwright && playwright install'"
)

BASE_URL = os.getenv("TEST_URL", "http://localhost:5049")
TEST_USERNAME = os.getenv("TEST_USERNAME", "uitest")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "uitest123")
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots" / "feedback"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Helper Functions
# =============================================================================

def ensure_test_user_exists():
    """Create test user for UI tests if it doesn't exist."""
    try:
        # Add project root to path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.security.auth import create_user, verify_user

        # Check if user exists by trying to verify
        if verify_user(TEST_USERNAME, TEST_PASSWORD) is None:
            # Create test user
            create_user(TEST_USERNAME, TEST_PASSWORD)
    except Exception as e:
        print(f"Warning: Could not ensure test user: {e}")


def login_to_app(page):
    """Log in to the app with test credentials."""
    # Navigate to base URL
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle", timeout=10000)

    # Check if we're on the login page (not already logged in)
    try:
        username_input = page.locator("input[name='username']")
        if username_input.is_visible(timeout=2000):
            page.fill("input[name='username']", TEST_USERNAME)
            page.fill("input[name='password']", TEST_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        # Already logged in or on main page - continue
        pass

    # Wait for main app to load (command input indicates we're logged in)
    page.wait_for_selector("#command-input", timeout=10000)


def inject_mock_response(page, command, response_text):
    """
    Inject a mock response into the page to test feedback UI.

    This bypasses the actual API call and directly calls displayResponse()
    to show feedback buttons without needing the server running.
    """
    page.evaluate(
        """
        ({command, response}) => {
            displayResponse(command, {response: response, success: true});
        }
        """,
        {"command": command, "response": response_text}
    )


def wait_for_feedback_buttons(page, timeout=2000):
    """Wait for feedback buttons to appear on the page."""
    page.wait_for_selector(".feedback-btn-up", timeout=timeout)
    page.wait_for_selector(".feedback-btn-down", timeout=timeout)


# =============================================================================
# Module Setup
# =============================================================================

# Ensure test user exists before running any tests
ensure_test_user_exists()


# =============================================================================
# Feedback Button Rendering Tests
# =============================================================================

class TestFeedbackButtonRendering:
    """Test that feedback buttons render correctly with responses."""

    def test_feedback_buttons_appear_with_response(self):
        """Test that thumbs up/down buttons appear after command response."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Inject a mock response
            inject_mock_response(page, "turn on kitchen light", "Done!")

            # Wait for feedback buttons to appear
            wait_for_feedback_buttons(page)

            # Verify both buttons are visible
            thumbs_up = page.locator(".feedback-btn-up").first
            thumbs_down = page.locator(".feedback-btn-down").first

            expect(thumbs_up).to_be_visible()
            expect(thumbs_down).to_be_visible()

            page.screenshot(path=str(SCREENSHOT_DIR / "01_buttons_rendered.png"))
            browser.close()

    def test_feedback_buttons_have_correct_attributes(self):
        """Test that feedback buttons have proper ARIA labels and data attributes."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Inject mock response
            inject_mock_response(page, "test command", "test response")
            wait_for_feedback_buttons(page)

            # Check thumbs up button
            thumbs_up = page.locator(".feedback-btn-up").first
            expect(thumbs_up).to_have_attribute("aria-label", "Mark as successful")
            expect(thumbs_up).to_have_attribute("data-command", "test command")
            expect(thumbs_up).to_have_attribute("data-response", "test response")

            # Check thumbs down button
            thumbs_down = page.locator(".feedback-btn-down").first
            expect(thumbs_down).to_have_attribute("aria-label", "Report unsuccessful response")
            expect(thumbs_down).to_have_attribute("data-command", "test command")
            expect(thumbs_down).to_have_attribute("data-response", "test response")

            browser.close()

    def test_multiple_responses_each_have_feedback_buttons(self):
        """Test that each response has its own set of feedback buttons."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Inject multiple responses
            inject_mock_response(page, "command 1", "response 1")
            inject_mock_response(page, "command 2", "response 2")
            inject_mock_response(page, "command 3", "response 3")

            # Should have 3 pairs of feedback buttons
            thumbs_up_buttons = page.locator(".feedback-btn-up")
            thumbs_down_buttons = page.locator(".feedback-btn-down")

            assert thumbs_up_buttons.count() == 3
            assert thumbs_down_buttons.count() == 3

            page.screenshot(path=str(SCREENSHOT_DIR / "02_multiple_responses.png"))
            browser.close()

    def test_feedback_buttons_use_touch_friendly_size(self):
        """Test that feedback buttons meet minimum touch target size (44px)."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Check button height meets touch target minimum
            thumbs_up = page.locator(".feedback-btn-up").first
            box = thumbs_up.bounding_box()

            # CSS defines min-height: var(--touch-target-min) which is 44px
            assert box["height"] >= 44, f"Button height {box['height']}px is below 44px minimum"

            browser.close()


# =============================================================================
# Thumbs Up Flow Tests
# =============================================================================

class TestThumbsUpFlow:
    """Test thumbs up button click and confirmation display."""

    def test_thumbs_up_shows_success_message(self):
        """Test that clicking thumbs up shows 'Thanks for the feedback!' message."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test command", "test response")
            wait_for_feedback_buttons(page)

            # Click thumbs up
            thumbs_up = page.locator(".feedback-btn-up").first
            thumbs_up.click()

            # Wait for success message
            page.wait_for_selector(".feedback-success", timeout=2000)
            success_msg = page.locator(".feedback-success").first

            expect(success_msg).to_be_visible()
            expect(success_msg).to_have_text("Thanks for the feedback!")

            page.screenshot(path=str(SCREENSHOT_DIR / "03_thumbs_up_success.png"))
            browser.close()

    def test_thumbs_up_hides_both_buttons(self):
        """Test that clicking thumbs up hides both feedback buttons."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Get button reference before clicking
            response_feedback = page.locator(".response-feedback").first
            thumbs_up = page.locator(".feedback-btn-up").first

            # Click thumbs up
            thumbs_up.click()
            page.wait_for_timeout(500)  # Wait for DOM update

            # Buttons should be replaced by success message
            # Check that feedback-btn-up and feedback-btn-down are no longer in the feedback area
            expect(response_feedback.locator(".feedback-btn-up")).not_to_be_visible()
            expect(response_feedback.locator(".feedback-btn-down")).not_to_be_visible()

            browser.close()

    def test_thumbs_up_svg_icon_renders(self):
        """Test that thumbs up button has SVG icon."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Check for SVG element inside button
            svg = page.locator(".feedback-btn-up svg").first
            expect(svg).to_be_visible()

            browser.close()


# =============================================================================
# Thumbs Down Flow Tests
# =============================================================================

class TestThumbsDownFlow:
    """Test thumbs down button triggers bug filing flow."""

    def test_thumbs_down_shows_loading_state(self):
        """Test that clicking thumbs down shows loading state before result."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock the API with a delay to see loading state
            def delayed_response(route):
                time.sleep(1)  # Delay to allow loading state to be visible
                route.fulfill(
                    status=200,
                    body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                    headers={"Content-Type": "application/json"}
                )

            page.route("**/api/feedback", delayed_response)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Click thumbs down
            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Should show loading spinner - capture it quickly
            page.wait_for_selector(".feedback-status", timeout=2000)
            status = page.locator(".feedback-status").first

            # The status should be visible during the delay
            expect(status).to_be_visible()
            page.screenshot(path=str(SCREENSHOT_DIR / "04_thumbs_down_loading.png"))

            # Wait for the result to appear
            page.wait_for_selector(".feedback-bug-filed", timeout=5000)
            browser.close()

    def test_thumbs_down_shows_bug_filed_confirmation(self):
        """Test that thumbs down shows bug ID after successful filing."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock successful bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-20260102120000"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "broken command", "wrong response")
            wait_for_feedback_buttons(page)

            # Click thumbs down
            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Wait for bug filed confirmation
            page.wait_for_selector(".feedback-bug-filed", timeout=5000)
            bug_filed = page.locator(".feedback-bug-filed").first

            expect(bug_filed).to_be_visible()
            expect(bug_filed).to_contain_text("Bug")
            expect(bug_filed).to_contain_text("BUG-20260102120000")

            page.screenshot(path=str(SCREENSHOT_DIR / "05_bug_filed_success.png"))
            browser.close()

    def test_thumbs_down_shows_more_button_after_filing(self):
        """Test that '...' button appears after bug is filed."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock successful bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Wait for more button
            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first

            expect(more_btn).to_be_visible()
            expect(more_btn).to_have_text("...")

            browser.close()

    def test_thumbs_down_hides_down_button(self):
        """Test that thumbs down button is hidden after clicking."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock API
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Get initial visibility
            thumbs_down = page.locator(".feedback-btn-down").first
            expect(thumbs_down).to_be_visible()

            # Click it
            thumbs_down.click()
            page.wait_for_timeout(1000)

            # Should now be hidden (has .hidden class)
            expect(thumbs_down).to_have_class(re.compile(r".*hidden.*"))

            browser.close()

    def test_thumbs_down_api_failure_shows_error(self):
        """Test that API failure shows error message."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock API failure
            page.route("**/api/feedback", lambda route: route.abort("failed"))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Wait for error message
            page.wait_for_selector(".feedback-error", timeout=5000)
            error_msg = page.locator(".feedback-error").first

            expect(error_msg).to_be_visible()
            expect(error_msg).to_contain_text("Error")

            page.screenshot(path=str(SCREENSHOT_DIR / "06_api_error.png"))
            browser.close()


# =============================================================================
# Feedback Form Tests
# =============================================================================

class TestFeedbackForm:
    """Test feedback form expansion, submit, and cancel behavior."""

    def test_more_button_shows_feedback_form(self):
        """Test that clicking '...' button shows the feedback form."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Click thumbs down to get to bug filed state
            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Wait for and click more button
            more_btn = page.locator(".feedback-more-btn").first
            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn.click()

            # Form should appear
            page.wait_for_selector(".feedback-form", timeout=2000)
            feedback_form = page.locator(".feedback-form").first

            expect(feedback_form).to_be_visible()
            # Form should not have 'hidden' class
            class_attr = feedback_form.get_attribute("class")
            assert "hidden" not in class_attr

            page.screenshot(path=str(SCREENSHOT_DIR / "07_form_expanded.png"))
            browser.close()

    def test_feedback_form_has_input_and_buttons(self):
        """Test that feedback form contains input field and submit/cancel buttons."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            more_btn = page.locator(".feedback-more-btn").first
            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn.click()

            page.wait_for_selector(".feedback-form", timeout=2000)

            # Check form elements
            feedback_input = page.locator(".feedback-input").first
            submit_btn = page.locator(".feedback-submit").first
            cancel_btn = page.locator(".feedback-cancel").first

            expect(feedback_input).to_be_visible()
            expect(feedback_input).to_have_attribute("placeholder", "What went wrong? (optional)")
            expect(submit_btn).to_be_visible()
            expect(submit_btn).to_have_text("Retry")
            expect(cancel_btn).to_be_visible()
            expect(cancel_btn).to_have_text("Cancel")

            browser.close()

    def test_feedback_form_input_is_focused(self):
        """Test that input field receives focus when form appears."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            # Input should be focused
            page.wait_for_selector(".feedback-input", timeout=2000)
            feedback_input = page.locator(".feedback-input").first

            expect(feedback_input).to_be_focused()

            browser.close()

    def test_feedback_form_cancel_hides_form(self):
        """Test that clicking Cancel hides the form."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            page.wait_for_selector(".feedback-form", timeout=2000)

            # Click cancel
            cancel_btn = page.locator(".feedback-cancel").first
            cancel_btn.click()
            page.wait_for_timeout(500)

            # Form should be hidden
            feedback_form = page.locator(".feedback-form").first
            expect(feedback_form).to_have_class(re.compile(r".*hidden.*"))

            # More button should be visible again
            expect(more_btn).to_be_visible()

            page.screenshot(path=str(SCREENSHOT_DIR / "08_form_cancelled.png"))
            browser.close()

    def test_feedback_form_submit_with_text_triggers_retry(self):
        """Test that submitting form with text triggers retry flow."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Track API calls
            api_calls = []

            def handle_route(route):
                request_data = route.request.post_data_json
                api_calls.append(request_data)

                # First call: bug filing
                if len(api_calls) == 1:
                    route.fulfill(
                        status=200,
                        body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                        headers={"Content-Type": "application/json"}
                    )
                # Second call: retry with feedback
                else:
                    route.fulfill(
                        status=200,
                        body='{"success": true, "action": "retry", "response": "Fixed it!"}',
                        headers={"Content-Type": "application/json"}
                    )

            page.route("**/api/feedback", handle_route)

            inject_mock_response(page, "test command", "test response")
            wait_for_feedback_buttons(page)

            # Trigger bug filing
            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            # Open form
            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            # Fill in feedback
            page.wait_for_selector(".feedback-input", timeout=2000)
            feedback_input = page.locator(".feedback-input").first
            feedback_input.fill("The light didn't turn off")

            # Submit
            submit_btn = page.locator(".feedback-submit").first
            submit_btn.click()

            # Wait for retry result
            page.wait_for_selector(".feedback-retry-result", timeout=5000)
            retry_result = page.locator(".feedback-retry-result").first

            expect(retry_result).to_be_visible()
            expect(retry_result).to_contain_text("Fixed it!")

            # Verify API was called with feedback_text
            assert len(api_calls) == 2
            assert "feedback_text" in api_calls[1]
            assert api_calls[1]["feedback_text"] == "The light didn't turn off"

            page.screenshot(path=str(SCREENSHOT_DIR / "09_retry_success.png"))
            browser.close()

    def test_feedback_form_submit_empty_just_closes_form(self):
        """Test that submitting empty form just hides the form."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            page.wait_for_selector(".feedback-form", timeout=2000)

            # Submit without entering text
            submit_btn = page.locator(".feedback-submit").first
            submit_btn.click()
            page.wait_for_timeout(500)

            # Form should be hidden
            feedback_form = page.locator(".feedback-form").first
            expect(feedback_form).to_have_class(re.compile(r".*hidden.*"))

            browser.close()

    def test_feedback_form_retry_failure_shows_error(self):
        """Test that retry failure shows error message."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            api_call_count = [0]

            def handle_route(route):
                api_call_count[0] += 1
                if api_call_count[0] == 1:
                    # Bug filing succeeds
                    route.fulfill(
                        status=200,
                        body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    # Retry fails
                    route.fulfill(
                        status=200,
                        body='{"success": false, "action": "retry", "response": "Retry failed: timeout"}',
                        headers={"Content-Type": "application/json"}
                    )

            page.route("**/api/feedback", handle_route)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            page.wait_for_selector(".feedback-input", timeout=2000)
            feedback_input = page.locator(".feedback-input").first
            feedback_input.fill("still broken")

            submit_btn = page.locator(".feedback-submit").first
            submit_btn.click()

            # Should show error or failure message
            page.wait_for_timeout(2000)
            status = page.locator(".feedback-status").first
            expect(status).to_contain_text("Retry failed")

            page.screenshot(path=str(SCREENSHOT_DIR / "10_retry_failure.png"))
            browser.close()


# =============================================================================
# Visual Regression Tests
# =============================================================================

class TestFeedbackVisuals:
    """Test visual appearance and styling of feedback components."""

    def test_feedback_buttons_have_correct_styling(self):
        """Test that feedback buttons match design specs."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_up = page.locator(".feedback-btn-up").first

            # Check computed styles
            border = thumbs_up.evaluate("el => getComputedStyle(el).border")
            assert "1px" in border  # Has 1px border

            # Check it has SVG
            svg = thumbs_up.locator("svg")
            expect(svg).to_be_visible()

            browser.close()

    def test_feedback_form_is_properly_styled(self):
        """Test that feedback form has proper background and spacing."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            page.wait_for_selector(".feedback-form", timeout=2000)
            feedback_form = page.locator(".feedback-form").first

            # Check it has background
            bg_color = feedback_form.evaluate("el => getComputedStyle(el).backgroundColor")
            assert bg_color  # Has background color set

            # Check it has border radius
            border_radius = feedback_form.evaluate("el => getComputedStyle(el).borderRadius")
            assert border_radius and border_radius != "0px"

            browser.close()

    def test_success_message_has_correct_color(self):
        """Test that success message uses success color."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_up = page.locator(".feedback-btn-up").first
            thumbs_up.click()

            page.wait_for_selector(".feedback-success", timeout=2000)
            success = page.locator(".feedback-success").first

            # Should use success color (greenish)
            color = success.evaluate("el => getComputedStyle(el).color")
            assert color  # Has color set

            browser.close()


# =============================================================================
# Accessibility Tests
# =============================================================================

class TestFeedbackAccessibility:
    """Test accessibility features of feedback components."""

    def test_feedback_buttons_have_aria_labels(self):
        """Test that feedback buttons have proper ARIA labels."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_up = page.locator(".feedback-btn-up").first
            thumbs_down = page.locator(".feedback-btn-down").first

            # Check ARIA labels
            assert thumbs_up.get_attribute("aria-label")
            assert thumbs_down.get_attribute("aria-label")

            browser.close()

    def test_feedback_input_has_aria_label(self):
        """Test that feedback input has proper ARIA label."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            # Mock bug filing
            page.route("**/api/feedback", lambda route: route.fulfill(
                status=200,
                body='{"success": true, "action": "bug_filed", "bug_id": "BUG-123"}',
                headers={"Content-Type": "application/json"}
            ))

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()

            page.wait_for_selector(".feedback-more-btn", timeout=5000)
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()

            page.wait_for_selector(".feedback-input", timeout=2000)
            feedback_input = page.locator(".feedback-input").first

            # Should have aria-label or placeholder
            aria_label = feedback_input.get_attribute("aria-label")
            placeholder = feedback_input.get_attribute("placeholder")

            assert aria_label or placeholder

            browser.close()

    def test_svg_icons_are_marked_aria_hidden(self):
        """Test that SVG icons are properly hidden from screen readers."""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            inject_mock_response(page, "test", "test")
            wait_for_feedback_buttons(page)

            # Check SVG has aria-hidden
            svg = page.locator(".feedback-btn-up svg").first
            aria_hidden = svg.get_attribute("aria-hidden")

            assert aria_hidden == "true"

            browser.close()


# =============================================================================
# Integration Test
# =============================================================================

class TestFeedbackEndToEnd:
    """End-to-end test of complete feedback flow."""

    def test_complete_feedback_flow_thumbs_down_to_retry(self):
        """
        Test complete user journey:
        1. Response appears with feedback buttons
        2. Click thumbs down
        3. Bug is filed
        4. Click '...' to add context
        5. Enter feedback text
        6. Submit for retry
        7. See retry result
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            login_to_app(page)

            api_call_count = [0]

            def handle_route(route):
                api_call_count[0] += 1
                if api_call_count[0] == 1:
                    route.fulfill(
                        status=200,
                        body='{"success": true, "action": "bug_filed", "bug_id": "BUG-E2E-TEST"}',
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    route.fulfill(
                        status=200,
                        body='{"success": true, "action": "retry", "response": "Successfully retried with context"}',
                        headers={"Content-Type": "application/json"}
                    )

            page.route("**/api/feedback", handle_route)

            # Step 1: Inject response with feedback buttons
            inject_mock_response(page, "turn off bedroom light", "Done!")
            wait_for_feedback_buttons(page)
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_01_initial.png"))

            # Step 2: Click thumbs down
            thumbs_down = page.locator(".feedback-btn-down").first
            thumbs_down.click()
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_02_clicked_down.png"))

            # Step 3: Wait for bug filed
            page.wait_for_selector(".feedback-bug-filed", timeout=5000)
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_03_bug_filed.png"))

            # Step 4: Click '...' button
            more_btn = page.locator(".feedback-more-btn").first
            more_btn.click()
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_04_form_opened.png"))

            # Step 5: Enter feedback
            page.wait_for_selector(".feedback-input", timeout=2000)
            feedback_input = page.locator(".feedback-input").first
            feedback_input.fill("Light is still on, please check")
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_05_text_entered.png"))

            # Step 6: Submit
            submit_btn = page.locator(".feedback-submit").first
            submit_btn.click()
            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_06_submitted.png"))

            # Step 7: See result
            page.wait_for_selector(".feedback-retry-result", timeout=5000)
            retry_result = page.locator(".feedback-retry-result").first
            expect(retry_result).to_be_visible()
            expect(retry_result).to_contain_text("Successfully retried")

            page.screenshot(path=str(SCREENSHOT_DIR / "e2e_07_complete.png"))

            browser.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
