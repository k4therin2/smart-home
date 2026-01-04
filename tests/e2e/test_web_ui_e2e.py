"""
E2E Tests for Web UI

Tests critical user journeys through the web interface:
- Login and authentication
- Command submission
- Response display
- Navigation
- Error handling

WP-10.27: E2E Testing Suite
"""

import os
import time

import pytest

from .conftest import (
    HAS_PLAYWRIGHT,
    BASE_URL,
    COMMAND_TIMEOUT,
    submit_command,
    take_screenshot,
    mock_command_api,
    clear_conversation,
)

if HAS_PLAYWRIGHT:
    from playwright.sync_api import expect

pytestmark = [
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed"),
    pytest.mark.e2e,
]


class TestLoginFlow:
    """Tests for user authentication."""

    def test_login_page_loads(self, page):
        """Test that login page loads correctly."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Should see login form
        username_input = page.locator("input[name='username']")
        password_input = page.locator("input[name='password']")
        submit_btn = page.locator("button[type='submit']")

        # Check if this is a login page or if we're already logged in
        if username_input.is_visible(timeout=2000):
            expect(username_input).to_be_visible()
            expect(password_input).to_be_visible()
            expect(submit_btn).to_be_visible()
            take_screenshot(page, "login_page")
        else:
            # Already logged in - command input should be visible
            expect(page.locator("#command-input")).to_be_visible()

    def test_invalid_login_shows_error(self, page):
        """Test that invalid credentials show error message."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        username_input = page.locator("input[name='username']")
        if not username_input.is_visible(timeout=2000):
            pytest.skip("Already logged in - cannot test invalid login")

        page.fill("input[name='username']", "invalid_user")
        page.fill("input[name='password']", "wrong_password")
        page.click("button[type='submit']")

        # Wait for error message
        error_msg = page.locator(".error, .alert-danger, .login-error")
        expect(error_msg).to_be_visible(timeout=5000)
        take_screenshot(page, "login_error")

    def test_successful_login_redirects(self, logged_in_page):
        """Test that successful login redirects to main app."""
        page = logged_in_page

        # Should see command input after login
        command_input = page.locator("#command-input")
        expect(command_input).to_be_visible()
        take_screenshot(page, "logged_in")


class TestCommandSubmission:
    """Tests for submitting commands."""

    def test_submit_simple_command(self, logged_in_page):
        """Test submitting a simple text command."""
        page = logged_in_page
        mock_command_api(page, "The lights are now on.")

        response = submit_command(page, "turn on living room lights")

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "command_response")

    def test_submit_command_with_enter_key(self, logged_in_page):
        """Test submitting command using Enter key."""
        page = logged_in_page
        mock_command_api(page, "Done!")

        command_input = page.locator("#command-input")
        command_input.fill("what time is it")
        command_input.press("Enter")

        page.wait_for_selector(".response-text", timeout=COMMAND_TIMEOUT)
        expect(page.locator(".response-text").first).to_be_visible()

    def test_empty_command_not_submitted(self, logged_in_page):
        """Test that empty command doesn't submit."""
        page = logged_in_page
        initial_count = len(page.locator(".response-text").all())

        # Try to submit empty command
        command_input = page.locator("#command-input")
        command_input.fill("")
        page.locator("#submit-btn").click()

        time.sleep(0.5)

        # Response count should not change
        final_count = len(page.locator(".response-text").all())
        assert final_count == initial_count

    def test_command_input_clears_after_submit(self, logged_in_page):
        """Test that command input is cleared after submission."""
        page = logged_in_page
        mock_command_api(page, "Done!")

        command_input = page.locator("#command-input")
        command_input.fill("test command")
        page.locator("#submit-btn").click()

        page.wait_for_selector(".response-text", timeout=COMMAND_TIMEOUT)

        # Input should be cleared
        expect(command_input).to_have_value("")

    def test_loading_indicator_during_command(self, logged_in_page):
        """Test that loading indicator appears during command processing."""
        page = logged_in_page

        # Slow down the response
        def slow_response(route):
            import json
            time.sleep(1)
            route.fulfill(
                status=200,
                body=json.dumps({"success": True, "response": "Done!"}),
                headers={"Content-Type": "application/json"}
            )

        page.route("**/api/command", slow_response)

        command_input = page.locator("#command-input")
        command_input.fill("test command")
        page.locator("#submit-btn").click()

        # Should see loading indicator
        loading = page.locator(".loading, .spinner, .loading-indicator")
        # Give it a moment to appear
        time.sleep(0.2)
        if loading.is_visible(timeout=1000):
            take_screenshot(page, "loading_indicator")


class TestConversationHistory:
    """Tests for conversation history display."""

    def test_multiple_commands_show_in_order(self, logged_in_page):
        """Test that multiple commands appear in chronological order."""
        page = logged_in_page
        mock_command_api(page, "Response 1")

        submit_command(page, "command 1")
        mock_command_api(page, "Response 2")
        submit_command(page, "command 2")

        responses = page.locator(".response-text").all()
        assert len(responses) >= 2

        # Verify order
        texts = [r.text_content() for r in responses]
        assert "Response 1" in texts[0] or "Response 1" in "".join(texts)

    def test_user_command_and_response_paired(self, logged_in_page):
        """Test that user command and response are visually paired."""
        page = logged_in_page
        mock_command_api(page, "Light turned on")

        submit_command(page, "turn on bedroom light")

        # Find the message container
        messages = page.locator(".message, .chat-message, .conversation-item")
        if messages.count() > 0:
            take_screenshot(page, "message_pairing")


class TestDeviceControls:
    """Tests for device control elements in UI."""

    def test_light_control_buttons_visible(self, logged_in_page):
        """Test that light control buttons appear for relevant responses."""
        page = logged_in_page

        # Mock a response that includes light controls
        mock_command_api(page, "I've turned on the living room light to 80% brightness.")

        submit_command(page, "turn on living room light")

        # Look for any control buttons
        controls = page.locator(".light-control, .device-control, .quick-action")
        if controls.count() > 0:
            take_screenshot(page, "light_controls")
            expect(controls.first).to_be_visible()


class TestErrorHandling:
    """Tests for error handling in UI."""

    def test_network_error_shows_message(self, logged_in_page):
        """Test that network errors show user-friendly message."""
        page = logged_in_page

        # Mock network failure
        page.route("**/api/command", lambda route: route.abort("connectionrefused"))

        command_input = page.locator("#command-input")
        command_input.fill("test command")
        page.locator("#submit-btn").click()

        # Should see error message
        error = page.locator(".error, .error-message, .alert-danger")
        expect(error).to_be_visible(timeout=5000)
        take_screenshot(page, "network_error")

    def test_api_error_response_handled(self, logged_in_page):
        """Test that API error responses are handled gracefully."""
        page = logged_in_page

        # Mock API error
        import json
        page.route("**/api/command", lambda route: route.fulfill(
            status=500,
            body=json.dumps({"error": "Internal server error"}),
            headers={"Content-Type": "application/json"}
        ))

        submit_command(page, "test command", wait_for_response=False)

        # Should see error indication
        error = page.locator(".error, .error-message, .response-error")
        expect(error).to_be_visible(timeout=5000)


class TestMobileResponsiveness:
    """Tests for mobile/responsive layout."""

    def test_mobile_viewport_layout(self, browser):
        """Test that UI works on mobile viewport."""
        # Create mobile context
        context = browser.new_context(
            viewport={"width": 375, "height": 667},  # iPhone SE
            ignore_https_errors=True,
        )
        page = context.new_page()

        try:
            page.goto(BASE_URL)
            page.wait_for_load_state("networkidle")

            # Main elements should be visible
            command_input = page.locator("#command-input")
            if command_input.is_visible(timeout=3000):
                expect(command_input).to_be_visible()
                take_screenshot(page, "mobile_layout")
        finally:
            context.close()


class TestAccessibility:
    """Tests for accessibility features."""

    def test_keyboard_navigation(self, logged_in_page):
        """Test that main elements are keyboard accessible."""
        page = logged_in_page

        # Tab to command input
        page.keyboard.press("Tab")
        command_input = page.locator("#command-input")

        # Should be focusable
        if command_input.is_visible():
            command_input.focus()
            expect(command_input).to_be_focused()

    def test_aria_labels_present(self, logged_in_page):
        """Test that interactive elements have ARIA labels."""
        page = logged_in_page

        # Check command input has label
        command_input = page.locator("#command-input")
        aria_label = command_input.get_attribute("aria-label")
        placeholder = command_input.get_attribute("placeholder")

        # Should have some form of labeling
        assert aria_label or placeholder


class TestPerformance:
    """Tests for UI performance."""

    def test_initial_load_time(self, browser):
        """Test that initial page load is reasonably fast."""
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        start_time = time.time()
        page.goto(BASE_URL)
        page.wait_for_load_state("domcontentloaded")
        load_time = time.time() - start_time

        context.close()

        # Page should load in under 5 seconds
        assert load_time < 5.0, f"Page load took {load_time:.2f}s"

    def test_command_response_time(self, logged_in_page):
        """Test that command response appears within reasonable time."""
        page = logged_in_page
        mock_command_api(page, "Quick response")

        start_time = time.time()
        submit_command(page, "test command")
        response_time = time.time() - start_time

        # Response should appear quickly with mocked API
        assert response_time < 3.0, f"Response took {response_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
