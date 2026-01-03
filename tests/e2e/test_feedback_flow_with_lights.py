"""
E2E Test for Feedback Flow with Real Light Control

This test verifies the complete feedback flow including:
1. User submits a command to control lights
2. Response appears with feedback buttons
3. User clicks thumbs down -> bug is filed in Vikunja
4. User adds feedback context via "..." button
5. User submits feedback -> retry is triggered AND bug is updated
6. Verifies actual light state changed in Home Assistant

**UX Issue Being Tested:**
The current feedback flow has a confusing UX where:
- Thumbs down files a bug with only the original command/response
- Adding feedback triggers a retry BUT doesn't update the bug
- The bug in Vikunja doesn't have the retry result or user's context

This test documents the expected behavior and can be used to verify fixes.
"""

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

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

pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT,
    reason="playwright not installed - run 'pip install playwright && playwright install'"
)

# Test configuration
BASE_URL = os.getenv("TEST_URL", "http://localhost:5049")
TEST_USERNAME = os.getenv("TEST_USERNAME", "uitest")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "uitest123")
SCREENSHOT_DIR = Path(__file__).parent.parent / "screenshots" / "feedback_e2e"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def ensure_test_user_exists():
    """Create test user for UI tests if it doesn't exist."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.security.auth import create_user, verify_user

        if verify_user(TEST_USERNAME, TEST_PASSWORD) is None:
            create_user(TEST_USERNAME, TEST_PASSWORD)
    except Exception as e:
        print(f"Warning: Could not ensure test user: {e}")


def login_to_app(page):
    """Log in to the app with test credentials."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle", timeout=10000)

    try:
        username_input = page.locator("input[name='username']")
        if username_input.is_visible(timeout=2000):
            page.fill("input[name='username']", TEST_USERNAME)
            page.fill("input[name='password']", TEST_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    page.wait_for_selector("#command-input", timeout=10000)


def get_light_state_from_ha(entity_id: str) -> dict:
    """Get light state directly from Home Assistant API."""
    from src.ha_client import get_ha_client

    ha_client = get_ha_client()
    return ha_client.get_light_state(entity_id)


def get_vikunja_task(bug_id: str) -> dict | None:
    """Get task from Vikunja by bug ID in title."""
    sys.path.insert(0, str(Path.home() / "projects" / "agent-automation" / "orchestrator" / "vikunja-migration"))
    from vikunja_client import VikunjaClient, VikunjaConfig

    config = VikunjaConfig.from_env()
    client = VikunjaClient(config)

    # Get Smarthome project
    project = client.get_project(93)  # Smarthome project ID
    if not project:
        return None

    # Search for task with bug_id in title
    tasks = client.list_tasks(project_id=93)
    for task in tasks:
        if bug_id in task.get("title", ""):
            return task

    return None


# Ensure test user exists before running tests
ensure_test_user_exists()


class TestFeedbackFlowWithLightControl:
    """Test complete feedback flow with actual light control."""

    @pytest.mark.skipif(
        os.getenv("SKIP_HARDWARE_TESTS") == "true",
        reason="Hardware tests skipped"
    )
    def test_complete_feedback_flow_with_kitchen_light(self):
        """
        Complete E2E test of feedback flow:
        1. Submit command to turn off kitchen lights
        2. Verify response appears
        3. Click thumbs down -> bug is filed
        4. Verify bug exists in Vikunja with original command/response
        5. Click "..." to add context
        6. Submit feedback text -> triggers retry
        7. Verify retry response appears
        8. Verify kitchen light is actually off in Home Assistant
        9. **EXPECTED FAILURE**: Bug should be updated with feedback/retry but currently isn't
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                # Step 1: Login
                login_to_app(page)
                page.screenshot(path=str(SCREENSHOT_DIR / "01_logged_in.png"))

                # Step 2: Submit command to turn off kitchen lights
                command_input = page.locator("#command-input")
                command_input.fill("turn off kitchen lights")
                page.screenshot(path=str(SCREENSHOT_DIR / "02_command_entered.png"))

                submit_btn = page.locator("#submit-btn")
                submit_btn.click()

                # Wait for response
                page.wait_for_selector(".response-text", timeout=15000)
                page.screenshot(path=str(SCREENSHOT_DIR / "03_response_received.png"))

                # Capture the response text
                response_text = page.locator(".response-text").first.text_content()
                print(f"Response: {response_text}")

                # Step 3: Wait for feedback buttons
                page.wait_for_selector(".feedback-btn-down", timeout=5000)
                page.screenshot(path=str(SCREENSHOT_DIR / "04_feedback_buttons.png"))

                # Step 4: Click thumbs down
                thumbs_down = page.locator(".feedback-btn-down").first
                thumbs_down.click()
                page.screenshot(path=str(SCREENSHOT_DIR / "05_clicked_thumbs_down.png"))

                # Wait for bug filed confirmation
                page.wait_for_selector(".feedback-bug-filed", timeout=10000)
                bug_filed_text = page.locator(".feedback-bug-filed").first.text_content()
                print(f"Bug filed: {bug_filed_text}")
                page.screenshot(path=str(SCREENSHOT_DIR / "06_bug_filed.png"))

                # Extract bug ID
                import re
                bug_id_match = re.search(r'BUG-\d+', bug_filed_text)
                assert bug_id_match, "Bug ID not found in confirmation"
                bug_id = bug_id_match.group(0)
                print(f"Bug ID: {bug_id}")

                # Step 5: Verify bug exists in Vikunja
                time.sleep(2)  # Give Vikunja time to process
                vikunja_task = get_vikunja_task(bug_id)
                assert vikunja_task is not None, f"Bug {bug_id} not found in Vikunja"
                print(f"Vikunja task found: {vikunja_task['title']}")

                # Verify original bug has command/response
                original_description = vikunja_task.get("description", "")
                assert "turn off kitchen lights" in original_description
                assert response_text in original_description or response_text[:50] in original_description

                # Step 6: Click "..." to add feedback context
                more_btn = page.locator(".feedback-more-btn").first
                more_btn.click()
                page.wait_for_selector(".feedback-form", timeout=5000)
                page.screenshot(path=str(SCREENSHOT_DIR / "07_feedback_form.png"))

                # Step 7: Enter feedback text
                feedback_input = page.locator(".feedback-input").first
                feedback_text = "The kitchen lights are still on. Please check the device connection."
                feedback_input.fill(feedback_text)
                page.screenshot(path=str(SCREENSHOT_DIR / "08_feedback_entered.png"))

                # Step 8: Submit feedback (triggers retry)
                submit_btn = page.locator(".feedback-submit").first
                submit_btn.click()

                # Wait for retry result
                page.wait_for_selector(".feedback-retry-result", timeout=20000)
                retry_result = page.locator(".feedback-retry-result").first
                expect(retry_result).to_be_visible()

                retry_response = retry_result.text_content()
                print(f"Retry response: {retry_response}")
                page.screenshot(path=str(SCREENSHOT_DIR / "09_retry_result.png"))

                # Step 9: Verify kitchen light state in Home Assistant
                time.sleep(2)  # Give HA time to process command
                kitchen_light_state = get_light_state_from_ha("light.kitchen")
                print(f"Kitchen light state: {kitchen_light_state}")

                if kitchen_light_state:
                    light_is_off = kitchen_light_state.get("state") == "off"
                    print(f"Kitchen light is off: {light_is_off}")

                    # Document whether light is actually off
                    # This verifies the command worked, regardless of feedback flow
                    assert light_is_off, "Kitchen light should be off after retry"

                # Step 10: **CRITICAL TEST** - Check if bug was updated with feedback
                # This is the UX issue we're testing for
                time.sleep(3)  # Give system time to update bug
                updated_task = get_vikunja_task(bug_id)
                assert updated_task is not None

                updated_description = updated_task.get("description", "")
                print(f"Updated bug description preview: {updated_description[:200]}...")

                # **EXPECTED FAILURE**: The bug should contain:
                # 1. The user's feedback text
                # 2. The retry response
                # But currently it doesn't get updated

                has_feedback = feedback_text in updated_description
                has_retry_response = any(word in updated_description for word in retry_response.split()[:5])

                if not has_feedback:
                    print("⚠️  UX ISSUE: Bug does not contain user feedback text")
                if not has_retry_response:
                    print("⚠️  UX ISSUE: Bug does not contain retry response")

                # Document the issue for developers
                assert has_feedback, (
                    "BUG IN FEEDBACK FLOW: User's feedback text should be added to the bug "
                    "so developers can see what the user reported"
                )
                assert has_retry_response, (
                    "BUG IN FEEDBACK FLOW: Retry response should be added to the bug "
                    "so developers can see if the retry succeeded"
                )

                page.screenshot(path=str(SCREENSHOT_DIR / "10_test_complete.png"))

            finally:
                browser.close()

    def test_feedback_flow_documents_bug_update_issue(self):
        """
        Simplified test that documents the bug update issue without requiring hardware.

        This test mocks the API but verifies the UI flow works correctly.
        The issue is that when feedback is submitted with retry:
        1. Bug gets filed with original command/response ✓
        2. Retry happens with feedback context ✓
        3. Bug does NOT get updated with feedback or retry result ✗ <- THE BUG
        """
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                login_to_app(page)

                # Track API calls to understand the flow
                api_calls = []

                def handle_feedback_route(route):
                    request_data = route.request.post_data_json
                    api_calls.append({
                        "endpoint": "/api/feedback",
                        "data": request_data,
                        "timestamp": time.time()
                    })

                    # First call: bug filing
                    if len(api_calls) == 1:
                        route.fulfill(
                            status=200,
                            body=json.dumps({
                                "success": True,
                                "action": "bug_filed",
                                "bug_id": "BUG-TEST-001"
                            }),
                            headers={"Content-Type": "application/json"}
                        )
                    # Second call: retry with feedback
                    else:
                        route.fulfill(
                            status=200,
                            body=json.dumps({
                                "success": True,
                                "action": "retry",
                                "response": "I've turned off the kitchen lights.",
                                "bug_id": "BUG-TEST-001"  # Same bug ID
                            }),
                            headers={"Content-Type": "application/json"}
                        )

                # Mock the command submission
                def handle_command_route(route):
                    route.fulfill(
                        status=200,
                        body=json.dumps({
                            "success": True,
                            "response": "Done!"
                        }),
                        headers={"Content-Type": "application/json"}
                    )

                page.route("**/api/command", handle_command_route)
                page.route("**/api/feedback", handle_feedback_route)

                # Execute the flow
                command_input = page.locator("#command-input")
                command_input.fill("turn off kitchen lights")
                page.locator("#submit-btn").click()

                page.wait_for_selector(".feedback-btn-down", timeout=5000)
                page.locator(".feedback-btn-down").first.click()

                page.wait_for_selector(".feedback-more-btn", timeout=5000)
                page.locator(".feedback-more-btn").first.click()

                page.wait_for_selector(".feedback-input", timeout=2000)
                page.locator(".feedback-input").first.fill("lights still on")
                page.locator(".feedback-submit").first.click()

                page.wait_for_selector(".feedback-retry-result", timeout=5000)

                # Analyze the API calls
                assert len(api_calls) == 2, "Should have 2 feedback API calls"

                # First call: just bug filing
                first_call = api_calls[0]["data"]
                assert "original_command" in first_call
                assert "original_response" in first_call
                assert "feedback_text" not in first_call or first_call["feedback_text"] is None

                # Second call: retry with feedback
                second_call = api_calls[1]["data"]
                assert "feedback_text" in second_call
                assert second_call["feedback_text"] == "lights still on"

                print("\n=== FEEDBACK FLOW ANALYSIS ===")
                print(f"Call 1 (Bug Filing): {json.dumps(first_call, indent=2)}")
                print(f"Call 2 (Retry): {json.dumps(second_call, indent=2)}")
                print("\n⚠️  UX ISSUE DOCUMENTED:")
                print("   - Bug is filed with original command/response only")
                print("   - When user adds feedback and retries:")
                print("     ✓ Retry happens with feedback context")
                print("     ✓ Retry response is shown to user")
                print("     ✗ Bug is NOT updated with feedback or retry result")
                print("\n   RECOMMENDATION:")
                print("   - In server.py submit_feedback(), after successful retry,")
                print("     update the Vikunja bug with:")
                print("       1. User's feedback_text")
                print("       2. Retry response")
                print("       3. Timestamp of retry")
                print("   - This gives developers complete context when reviewing bugs")

            finally:
                browser.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
