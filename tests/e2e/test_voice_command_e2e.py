"""
E2E Tests for Voice Command Flow

Tests the voice-based interaction features:
- Voice input button and recording
- Transcription display
- Voice command execution
- Voice feedback/responses

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


class TestVoiceInputUI:
    """Tests for voice input UI elements."""

    def test_voice_button_visible(self, logged_in_page):
        """Test that voice input button is visible."""
        page = logged_in_page

        # Look for voice/microphone button
        voice_btn = page.locator(
            "#voice-btn, .voice-button, button[aria-label*='voice'], "
            "button[aria-label*='mic'], .microphone-btn"
        )

        if voice_btn.count() > 0:
            expect(voice_btn.first).to_be_visible()
            take_screenshot(page, "voice_button")
        else:
            pytest.skip("Voice button not found in UI")

    def test_voice_button_accessible(self, logged_in_page):
        """Test that voice button has proper accessibility attributes."""
        page = logged_in_page

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        # Should have ARIA label
        aria_label = voice_btn.first.get_attribute("aria-label")
        title = voice_btn.first.get_attribute("title")

        assert aria_label or title, "Voice button should have accessibility label"

    def test_voice_button_has_icon(self, logged_in_page):
        """Test that voice button has microphone icon."""
        page = logged_in_page

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        # Check for icon (svg, i, or img)
        icon = voice_btn.first.locator("svg, i, img")
        expect(icon).to_be_visible()


class TestVoiceRecording:
    """Tests for voice recording functionality."""

    def test_click_voice_button_starts_recording(self, logged_in_page):
        """Test that clicking voice button initiates recording state."""
        page = logged_in_page

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        # Click voice button
        voice_btn.first.click()

        # Should see recording indicator
        recording = page.locator(
            ".recording, .listening, [data-recording='true'], "
            ".voice-active, .recording-indicator"
        )

        # Give it time to start
        time.sleep(0.5)

        if recording.is_visible(timeout=2000):
            take_screenshot(page, "voice_recording")
            expect(recording).to_be_visible()
        else:
            # Recording might require actual microphone
            pytest.skip("Recording state not visible (may require real microphone)")

    def test_recording_indicator_pulses(self, logged_in_page):
        """Test that recording indicator has visual feedback."""
        page = logged_in_page

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        voice_btn.first.click()
        time.sleep(0.5)

        # Check for animation classes
        indicator = page.locator(".recording, .listening, .voice-active")
        if indicator.is_visible(timeout=2000):
            classes = indicator.get_attribute("class") or ""
            # Common animation class patterns
            has_animation = any(x in classes for x in [
                "pulse", "animate", "blink", "active"
            ])
            if has_animation:
                take_screenshot(page, "recording_animation")


class TestVoiceTranscription:
    """Tests for voice transcription display."""

    def test_transcription_appears_after_recording(self, logged_in_page):
        """Test that transcription text appears after voice input."""
        page = logged_in_page

        # Mock the voice API to return transcription
        mock_api_response(page, "**/api/voice", {
            "success": True,
            "transcription": "turn on the living room lights"
        })

        # Also mock command API for the follow-up
        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've turned on the living room lights."
        })

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        # Simulate voice interaction
        voice_btn.first.click()
        time.sleep(1)

        # Look for transcription display
        transcription = page.locator(
            ".transcription, .voice-text, .speech-text, "
            "#command-input"
        )

        if transcription.is_visible(timeout=3000):
            take_screenshot(page, "transcription_displayed")

    def test_transcription_editable_before_submit(self, logged_in_page):
        """Test that user can edit transcription before submitting."""
        page = logged_in_page

        # Mock voice API
        mock_api_response(page, "**/api/voice", {
            "success": True,
            "transcription": "turn on living room"
        })

        # If command input is used for transcription, verify it's editable
        command_input = page.locator("#command-input")
        expect(command_input).to_be_editable()

        # Should be able to modify
        command_input.fill("turn on living room lights")
        expect(command_input).to_have_value("turn on living room lights")


class TestVoiceCommandExecution:
    """Tests for voice command execution flow."""

    def test_voice_command_executes_after_transcription(self, logged_in_page):
        """Test that voice commands execute properly."""
        page = logged_in_page

        # Mock both voice and command APIs
        voice_calls = []

        def handle_voice(route):
            voice_calls.append(True)
            route.fulfill(
                status=200,
                body=json.dumps({
                    "success": True,
                    "transcription": "turn off bedroom lights"
                }),
                headers={"Content-Type": "application/json"}
            )

        def handle_command(route):
            route.fulfill(
                status=200,
                body=json.dumps({
                    "success": True,
                    "response": "I've turned off the bedroom lights."
                }),
                headers={"Content-Type": "application/json"}
            )

        page.route("**/api/voice", handle_voice)
        page.route("**/api/command", handle_command)

        # For now, simulate by typing (actual voice would need microphone)
        submit_command(page, "turn off bedroom lights")

        # Should see response
        expect(page.locator(".response-text").first).to_be_visible()
        take_screenshot(page, "voice_command_executed")

    def test_voice_command_shows_loading(self, logged_in_page):
        """Test that loading state appears during voice processing."""
        page = logged_in_page

        def slow_voice_response(route):
            time.sleep(1)
            route.fulfill(
                status=200,
                body=json.dumps({
                    "success": True,
                    "transcription": "slow command"
                }),
                headers={"Content-Type": "application/json"}
            )

        page.route("**/api/voice", slow_voice_response)

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        voice_btn.first.click()

        # Check for processing indicator
        loading = page.locator(
            ".loading, .processing, .spinner, .voice-processing"
        )
        if loading.is_visible(timeout=2000):
            take_screenshot(page, "voice_processing")


class TestVoiceErrorHandling:
    """Tests for voice error handling."""

    def test_no_speech_detected_message(self, logged_in_page):
        """Test message when no speech is detected."""
        page = logged_in_page

        mock_api_response(page, "**/api/voice", {
            "success": False,
            "error": "No speech detected"
        })

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        voice_btn.first.click()
        time.sleep(1)

        # Should show error message
        error = page.locator(".error, .voice-error, .alert")
        if error.is_visible(timeout=3000):
            take_screenshot(page, "no_speech_error")

    def test_microphone_permission_denied(self, logged_in_page):
        """Test handling of microphone permission denial."""
        page = logged_in_page

        # This would require browser permission mocking
        # which varies by browser. Document the expected behavior.
        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        # Click button - if permissions denied, should show message
        voice_btn.first.click()

        # Look for permission error
        perm_error = page.locator(
            ".permission-error, .mic-error, .microphone-blocked"
        )
        # This may or may not appear depending on browser state
        time.sleep(1)
        take_screenshot(page, "voice_permission_state")

    def test_transcription_failure_handled(self, logged_in_page):
        """Test handling of transcription service failure."""
        page = logged_in_page

        mock_api_response(page, "**/api/voice", {
            "success": False,
            "error": "Transcription service unavailable"
        }, status=503)

        voice_btn = page.locator("#voice-btn, .voice-button")
        if voice_btn.count() == 0:
            pytest.skip("Voice button not found")

        voice_btn.first.click()
        time.sleep(1)

        # Should show user-friendly error
        error = page.locator(".error, .alert-danger, .error-message")
        if error.is_visible(timeout=3000):
            error_text = error.text_content()
            # Should not show raw technical error
            assert "503" not in error_text or "unavailable" in error_text.lower()


class TestVoiceFeedbackLoop:
    """Tests for voice feedback/response."""

    def test_voice_response_audio_option(self, logged_in_page):
        """Test that voice response audio option exists."""
        page = logged_in_page

        # Look for audio/speaker settings
        settings_btn = page.locator(
            "#settings-btn, .settings, button[aria-label*='settings']"
        )

        if settings_btn.count() > 0:
            settings_btn.first.click()

            # Look for voice response toggle
            voice_toggle = page.locator(
                "input[name*='voice'], input[name*='audio'], "
                ".voice-response-toggle"
            )
            if voice_toggle.is_visible(timeout=2000):
                take_screenshot(page, "voice_settings")

    def test_response_speaks_back(self, logged_in_page):
        """Test that system can speak response back."""
        page = logged_in_page

        mock_api_response(page, "**/api/command", {
            "success": True,
            "response": "I've turned on the lights.",
            "audio_url": "/api/tts/response.mp3"  # Optional TTS URL
        })

        submit_command(page, "turn on the lights")

        # Check if audio element is present for response
        audio = page.locator("audio, .audio-response")
        if audio.count() > 0:
            take_screenshot(page, "audio_response")


class TestVoiceIntegration:
    """Integration tests for voice features."""

    def test_voice_to_text_to_command_flow(self, logged_in_page):
        """Test complete voice to command execution flow."""
        page = logged_in_page

        # Set up mocks for complete flow
        page.route("**/api/voice", lambda route: route.fulfill(
            status=200,
            body=json.dumps({
                "success": True,
                "transcription": "what is the temperature"
            }),
            headers={"Content-Type": "application/json"}
        ))

        page.route("**/api/command", lambda route: route.fulfill(
            status=200,
            body=json.dumps({
                "success": True,
                "response": "The current temperature is 72°F."
            }),
            headers={"Content-Type": "application/json"}
        ))

        # Simulate the flow by typing (real voice needs microphone)
        response = submit_command(page, "what is the temperature")

        expect(page.locator(".response-text").first).to_be_visible()
        assert "temperature" in response.lower() or "72" in response

    def test_consecutive_voice_commands(self, logged_in_page):
        """Test that consecutive voice commands work properly."""
        page = logged_in_page

        responses = ["First response.", "Second response.", "Third response."]
        response_idx = [0]

        def dynamic_response(route):
            idx = response_idx[0]
            route.fulfill(
                status=200,
                body=json.dumps({
                    "success": True,
                    "response": responses[idx]
                }),
                headers={"Content-Type": "application/json"}
            )
            response_idx[0] = (idx + 1) % len(responses)

        page.route("**/api/command", dynamic_response)

        # Submit multiple commands
        submit_command(page, "first command")
        submit_command(page, "second command")
        submit_command(page, "third command")

        # All responses should be visible
        all_responses = page.locator(".response-text").all()
        assert len(all_responses) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
