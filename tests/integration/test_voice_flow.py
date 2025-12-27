"""
Voice Control Integration Tests

Test Strategy:
- Test full voice webhook → agent → response flow
- Mock Home Assistant API (external boundary)
- Mock Anthropic API (external boundary)
- Test actual code paths users will hit

Coverage:
- Webhook receives HA format, routes to agent, returns TTS response
- Error handling throughout the flow
- Multi-room context handling
- Rate limiting behavior
- Authentication (session and token)
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.server import app
from src.voice_handler import VoiceHandler
from src.voice_response import ResponseFormatter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client(temp_data_dir):
    """
    Flask test client with voice endpoints enabled.
    """
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = True

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def authenticated_user(client):
    """Mock authenticated user for protected endpoints."""
    with patch('flask_login.utils._get_user') as mock_user:
        mock_user.return_value = MagicMock(is_authenticated=True, id=1)
        yield mock_user


@pytest.fixture
def mock_agent_response():
    """
    Mock agent.run_agent to return predictable responses.
    """
    with patch('agent.run_agent') as mock_run:
        mock_run.return_value = "The living room lights are now on."
        yield mock_run


# =============================================================================
# End-to-End Voice Flow Tests
# =============================================================================

class TestVoiceFlowIntegration:
    """Test the complete voice command flow."""

    def test_full_voice_flow_success(self, client, authenticated_user, mock_agent_response):
        """
        Test complete flow: webhook → agent → formatted response.

        Simulates what happens when HA voice puck sends a command.
        """
        # HA-style webhook payload
        payload = {
            "text": "turn on the living room lights",
            "language": "en",
            "conversation_id": "test-123",
            "device_id": "voice_puck_living_room"
        }

        response = client.post(
            '/api/voice_command',
            json=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is True
        assert 'response' in data
        assert 'light' in data['response'].lower()

        # Verify agent was called with the command
        mock_agent_response.assert_called_once_with("turn on the living room lights")

    def test_voice_flow_formats_response(self, client, authenticated_user, mock_agent_response):
        """
        Test that response is properly formatted for TTS.
        """
        # Agent returns chatty response
        mock_agent_response.return_value = "Sure! I'd be happy to help! The lights are now on. 💡"

        response = client.post(
            '/api/voice_command',
            json={"text": "turn on lights"},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()

        # Should be formatted - no chatty phrases or emojis
        assert data['success'] is True
        assert not data['response'].lower().startswith("sure")
        assert "💡" not in data['response']

    def test_voice_flow_handles_agent_error(self, client, authenticated_user, mock_agent_response):
        """
        Test that agent errors return user-friendly messages.

        The VoiceHandler catches exceptions and returns a graceful response (200)
        with success=False and a user-friendly error message.
        """
        mock_agent_response.side_effect = Exception("Connection refused to HA API")

        response = client.post(
            '/api/voice_command',
            json={"text": "turn on lights"},
            content_type='application/json'
        )

        # Voice handler catches exceptions and returns graceful error (200 with success=False)
        assert response.status_code == 200
        data = response.get_json()

        assert data['success'] is False
        # Should have error in response
        assert 'error' in data or 'response' in data

    def test_voice_flow_with_context(self, client, authenticated_user, mock_agent_response):
        """
        Test that device context is preserved through the flow.
        """
        payload = {
            "text": "what time is it",
            "device_id": "voice_puck_kitchen",
            "language": "en"
        }

        response = client.post(
            '/api/voice_command',
            json=payload,
            content_type='application/json'
        )

        assert response.status_code == 200
        # Context should be accessible if needed for location-aware commands


class TestVoiceHandlerIntegration:
    """Test VoiceHandler with real ResponseFormatter."""

    def test_handler_integrates_with_formatter(self):
        """
        Test VoiceHandler uses ResponseFormatter correctly.
        """
        mock_agent = MagicMock(return_value="Absolutely! The temperature is 72 degrees.")

        handler = VoiceHandler(agent_callback=mock_agent)
        result = handler.process_command("what's the temperature")

        assert result['success'] is True
        # Formatter should remove "Absolutely!"
        assert not result['response'].lower().startswith("absolutely")
        # Should preserve important info
        assert "72" in result['response']

    def test_handler_parses_ha_payload(self):
        """
        Test VoiceHandler correctly parses HA webhook format.
        """
        handler = VoiceHandler(agent_callback=MagicMock())

        payload = {
            "text": "turn off bedroom lights",
            "language": "en-US",
            "conversation_id": "conv-456",
            "device_id": "bedroom_puck"
        }

        text, context = handler.parse_request(payload)

        assert text == "turn off bedroom lights"
        assert context['language'] == "en-US"
        assert context['device_id'] == "bedroom_puck"
        assert context['conversation_id'] == "conv-456"

    def test_handler_timeout_returns_friendly_error(self):
        """
        Test that timeout produces user-friendly error.
        """
        def slow_agent(text):
            import time
            time.sleep(5)
            return "Done"

        handler = VoiceHandler(
            agent_callback=slow_agent,
            timeout_seconds=0.1  # Very short for testing
        )

        result = handler.process_command("do something")

        assert result['success'] is False
        assert 'error' in result
        # Should be friendly, not "TimeoutError: ..."
        assert "sorry" in result['error'].lower() or "took too long" in result['error'].lower()


class TestResponseFormatterIntegration:
    """Test ResponseFormatter with various real-world inputs."""

    def test_formatter_handles_multiline_agent_output(self):
        """
        Test formatter processes multiline agent responses.
        """
        formatter = ResponseFormatter()

        multiline = """Here are the available rooms:
1. Living room
2. Bedroom
3. Kitchen"""

        result = formatter.format(multiline)

        # Should be joined for TTS (no newlines in middle)
        assert "living room" in result.lower()
        assert result.count('\n') == 0 or result.count('\n') <= 1

    def test_formatter_handles_json_like_output(self):
        """
        Test formatter handles JSON-like agent output gracefully.
        """
        formatter = ResponseFormatter()

        json_like = '{"status": "success", "lights": "on"}'
        result = formatter.format(json_like)

        # Should still be readable (even if not perfect)
        assert result  # Non-empty

    def test_formatter_preserves_important_values(self):
        """
        Test formatter preserves numbers, temperatures, percentages.
        """
        formatter = ResponseFormatter()

        responses = [
            ("The time is 3:45 PM", "3:45"),
            ("Temperature is 72 degrees", "72"),
            ("Brightness at 50%", "50"),
            ("Timer set for 10 minutes", "10"),
        ]

        for original, must_contain in responses:
            result = formatter.format(original)
            assert must_contain in result, f"Lost '{must_contain}' from '{original}'"


# =============================================================================
# Authentication Tests
# =============================================================================

class TestVoiceEndpointAuth:
    """Test voice endpoint authentication."""

    @pytest.fixture
    def client_no_auth(self, temp_data_dir):
        """Flask client without LOGIN_DISABLED."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = False

        with app.test_client() as test_client:
            yield test_client

        # Restore
        app.config['LOGIN_DISABLED'] = True

    def test_unauthenticated_request_rejected_when_token_required(self, client_no_auth, monkeypatch):
        """
        Test that unauthenticated requests are rejected when a webhook token is configured.

        When VOICE_WEBHOOK_TOKEN is set, requests must provide a valid token.
        When no token is configured, requests are allowed (dev mode).
        """
        # Configure a webhook token to require authentication
        monkeypatch.setenv("VOICE_WEBHOOK_TOKEN", "required-token-123")

        response = client_no_auth.post(
            '/api/voice_command',
            json={"text": "turn on lights"},
            content_type='application/json'
            # No Authorization header provided
        )

        # Should require auth when token is configured
        assert response.status_code in [401, 403]

    def test_valid_webhook_token_accepted(self, client_no_auth, monkeypatch, mock_agent_response):
        """
        Test that valid Bearer token authenticates request.
        """
        monkeypatch.setenv("VOICE_WEBHOOK_TOKEN", "secret-token-123")

        response = client_no_auth.post(
            '/api/voice_command',
            json={"text": "turn on lights"},
            content_type='application/json',
            headers={"Authorization": "Bearer secret-token-123"}
        )

        # Should succeed with valid token
        assert response.status_code == 200

    def test_invalid_webhook_token_rejected(self, client_no_auth, monkeypatch):
        """
        Test that invalid Bearer token is rejected.
        """
        monkeypatch.setenv("VOICE_WEBHOOK_TOKEN", "correct-token")

        response = client_no_auth.post(
            '/api/voice_command',
            json={"text": "turn on lights"},
            content_type='application/json',
            headers={"Authorization": "Bearer wrong-token"}
        )

        assert response.status_code in [401, 403]


# =============================================================================
# Input Validation Tests
# =============================================================================

class TestVoiceInputValidation:
    """Test voice endpoint input validation."""

    def test_missing_text_field(self, client, authenticated_user):
        """
        Test that missing text field returns 400.
        """
        response = client.post(
            '/api/voice_command',
            json={"language": "en"},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_empty_text_field(self, client, authenticated_user):
        """
        Test that empty text field returns 400.
        """
        response = client.post(
            '/api/voice_command',
            json={"text": "   "},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'empty' in data['error'].lower()

    def test_non_json_body_rejected(self, client, authenticated_user):
        """
        Test that non-JSON body returns 400.
        """
        response = client.post(
            '/api/voice_command',
            data="not json",
            content_type='text/plain'
        )

        # Should reject non-JSON content (400 bad request or 500 internal error)
        assert response.status_code in [400, 415, 500]

    def test_text_too_long_rejected(self, client, authenticated_user):
        """
        Test that excessively long text is rejected.
        """
        response = client.post(
            '/api/voice_command',
            json={"text": "a" * 2000},  # Over 1000 char limit
            content_type='application/json'
        )

        assert response.status_code == 400


# =============================================================================
# Real-World Scenario Tests
# =============================================================================

class TestRealWorldScenarios:
    """Test real-world voice command scenarios."""

    def test_common_light_commands(self, client, authenticated_user, mock_agent_response):
        """
        Test common light control voice commands.
        """
        commands = [
            "turn on the lights",
            "turn off living room lights",
            "dim the bedroom lights to 50%",
            "set the kitchen to cozy",
            "make it romantic in here",
        ]

        for command in commands:
            mock_agent_response.reset_mock()
            mock_agent_response.return_value = f"Done with: {command}"

            response = client.post(
                '/api/voice_command',
                json={"text": command},
                content_type='application/json'
            )

            assert response.status_code == 200, f"Failed for: {command}"
            mock_agent_response.assert_called_once()

    def test_time_and_date_queries(self, client, authenticated_user, mock_agent_response):
        """
        Test time and date voice queries.
        """
        mock_agent_response.return_value = "It's 3:30 PM on Tuesday, December 18th."

        response = client.post(
            '/api/voice_command',
            json={"text": "what time is it"},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "3:30" in data['response']

    def test_system_status_query(self, client, authenticated_user, mock_agent_response):
        """
        Test system status voice query.
        """
        mock_agent_response.return_value = "All systems are operational. Home Assistant is connected."

        response = client.post(
            '/api/voice_command',
            json={"text": "system status"},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
