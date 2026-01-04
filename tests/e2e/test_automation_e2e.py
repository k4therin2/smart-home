"""
E2E Tests for Automation Execution

Tests the automation and scheduling features:
- Automation creation via UI
- Automation listing and management
- Trigger execution
- Automation status display

WP-10.27: E2E Testing Suite
"""

import json
import os
import time

import pytest

from .conftest import (
    HAS_PLAYWRIGHT,
    BASE_URL,
    COMMAND_TIMEOUT,
    submit_command,
    take_screenshot,
    mock_api_response,
)

if HAS_PLAYWRIGHT:
    from playwright.sync_api import expect

pytestmark = [
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed"),
    pytest.mark.e2e,
]


class TestAutomationCreation:
    """Tests for creating automations via UI."""

    def test_create_time_based_automation(self, logged_in_page):
        """Test creating a time-based automation via command."""
        page = logged_in_page

        # Mock automation creation response
        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've created an automation: Turn on living room lights at 6:00 PM every day."
        })

        response = submit_command(
            page,
            "create an automation to turn on living room lights at 6pm every day"
        )

        expect(page.locator(".response-text").first).to_be_visible()
        assert "automation" in response.lower() or "created" in response.lower()
        take_screenshot(page, "automation_created")

    def test_create_state_based_automation(self, logged_in_page):
        """Test creating a state-based automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've created an automation: When motion is detected in the garage, turn on the garage light."
        })

        response = submit_command(
            page,
            "when motion is detected in garage turn on garage light"
        )

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "state_automation_created")

    def test_create_complex_automation(self, logged_in_page):
        """Test creating an automation with multiple conditions."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've created an automation: At sunset, if you're home, turn on the living room lights to 50% with warm white."
        })

        response = submit_command(
            page,
            "at sunset if im home turn on living room to 50% warm white"
        )

        expect(page.locator(".response-text").first).to_be_visible()


class TestAutomationListing:
    """Tests for listing and viewing automations."""

    def test_list_all_automations(self, logged_in_page):
        """Test listing all configured automations."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Here are your automations:
1. Morning Lights - Turn on kitchen lights at 7:00 AM
2. Sunset Routine - Turn on living room lights at sunset
3. Away Mode - Turn off all lights when you leave"""
        })

        response = submit_command(page, "list my automations")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "automation" in response.lower() or "routine" in response.lower()
        take_screenshot(page, "automation_list")

    def test_view_automation_details(self, logged_in_page):
        """Test viewing details of a specific automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Morning Lights automation:
- Trigger: Every day at 7:00 AM
- Actions: Turn on kitchen lights to 100%
- Status: Enabled
- Last run: Today at 7:00 AM"""
        })

        response = submit_command(page, "show me the morning lights automation")

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "automation_details")


class TestAutomationManagement:
    """Tests for managing automations."""

    def test_disable_automation(self, logged_in_page):
        """Test disabling an automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've disabled the Morning Lights automation. It won't run until you enable it again."
        })

        response = submit_command(page, "disable the morning lights automation")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "disable" in response.lower()

    def test_enable_automation(self, logged_in_page):
        """Test enabling a disabled automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've enabled the Morning Lights automation. It will run at 7:00 AM tomorrow."
        })

        response = submit_command(page, "enable the morning lights automation")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "enable" in response.lower()

    def test_delete_automation(self, logged_in_page):
        """Test deleting an automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've deleted the Morning Lights automation."
        })

        response = submit_command(page, "delete the morning lights automation")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "delete" in response.lower()

    def test_update_automation(self, logged_in_page):
        """Test modifying an existing automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've updated the Morning Lights automation. It will now run at 6:30 AM instead of 7:00 AM."
        })

        response = submit_command(
            page,
            "change the morning lights automation to run at 6:30am"
        )

        expect(page.locator(".response-text").first).to_be_visible()
        assert "update" in response.lower() or "change" in response.lower()


class TestAutomationExecution:
    """Tests for automation execution feedback."""

    def test_manual_trigger_automation(self, logged_in_page):
        """Test manually triggering an automation."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've triggered the Sunset Routine automation. The living room lights are now on."
        })

        response = submit_command(page, "run the sunset routine now")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "trigger" in response.lower() or "run" in response.lower()
        take_screenshot(page, "automation_triggered")

    def test_automation_history(self, logged_in_page):
        """Test viewing automation run history."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Recent automation runs:
1. Morning Lights - Today 7:00 AM - Success
2. Sunset Routine - Yesterday 5:30 PM - Success
3. Away Mode - Yesterday 9:15 AM - Success"""
        })

        response = submit_command(page, "show automation history")

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "automation_history")


class TestReminderAndTimer:
    """Tests for reminder and timer functionality."""

    def test_set_reminder(self, logged_in_page):
        """Test setting a reminder."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've set a reminder for 3:00 PM: Take medicine"
        })

        response = submit_command(page, "remind me to take medicine at 3pm")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "reminder" in response.lower() or "remind" in response.lower()

    def test_set_timer(self, logged_in_page):
        """Test setting a countdown timer."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've started a 10 minute timer."
        })

        response = submit_command(page, "set a timer for 10 minutes")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "timer" in response.lower()

    def test_list_reminders(self, logged_in_page):
        """Test listing active reminders."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Your upcoming reminders:
1. Take medicine - Today at 3:00 PM
2. Call mom - Tomorrow at 2:00 PM"""
        })

        response = submit_command(page, "list my reminders")

        expect(page.locator(".response-text").first).to_be_visible()

    def test_cancel_reminder(self, logged_in_page):
        """Test canceling a reminder."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've canceled the 'take medicine' reminder."
        })

        response = submit_command(page, "cancel the take medicine reminder")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "cancel" in response.lower()


class TestTodoIntegration:
    """Tests for todo list integration."""

    def test_add_todo_item(self, logged_in_page):
        """Test adding a todo item."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've added 'Buy groceries' to your todo list."
        })

        response = submit_command(page, "add buy groceries to my todo list")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "todo" in response.lower() or "added" in response.lower()

    def test_list_todos(self, logged_in_page):
        """Test listing todo items."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Your todo list:
1. Buy groceries
2. Call dentist
3. Finish project report"""
        })

        response = submit_command(page, "show my todo list")

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "todo_list")

    def test_complete_todo(self, logged_in_page):
        """Test marking a todo as complete."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've marked 'Buy groceries' as complete."
        })

        response = submit_command(page, "mark buy groceries as done")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "complete" in response.lower() or "done" in response.lower()


class TestSceneManagement:
    """Tests for scene/routine management."""

    def test_activate_scene(self, logged_in_page):
        """Test activating a predefined scene."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've activated the Movie Night scene. Lights are dimmed and the TV is on."
        })

        response = submit_command(page, "activate movie night scene")

        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "scene_activated")

    def test_create_scene(self, logged_in_page):
        """Test creating a new scene."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've created a new scene called 'Reading Time' with the current device states."
        })

        response = submit_command(
            page,
            "save the current settings as a scene called reading time"
        )

        expect(page.locator(".response-text").first).to_be_visible()

    def test_list_scenes(self, logged_in_page):
        """Test listing available scenes."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": """Available scenes:
1. Movie Night - Dim lights, TV on
2. Good Morning - Bright lights, coffee maker on
3. Reading Time - Living room at 70%, warm white"""
        })

        response = submit_command(page, "list my scenes")

        expect(page.locator(".response-text").first).to_be_visible()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
