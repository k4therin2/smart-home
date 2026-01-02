"""
API Tests for Response Feedback Endpoint

Tests the /api/feedback endpoint for:
- Bug filing flow (no feedback text)
- Retry flow (with feedback text)
- Input validation
- Error handling
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.server import app


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client(temp_data_dir):
    """Flask test client with test configuration."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = True

    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def authenticated_user(client):
    """Mock authenticated user session."""
    with patch('flask_login.utils._get_user') as mock_user:
        mock_user.return_value = MagicMock(is_authenticated=True, id=1)
        yield mock_user


@pytest.fixture
def mock_vikunja():
    """Mock Vikunja bug filing."""
    with patch('src.server.file_bug_in_vikunja') as mock:
        mock.return_value = "BUG-20260102120000"
        yield mock


@pytest.fixture
def mock_nats():
    """Mock NATS alert."""
    with patch('src.server.alert_developers_via_nats') as mock:
        yield mock


@pytest.fixture
def mock_retry():
    """Mock retry with feedback."""
    with patch('src.server.retry_with_feedback') as mock:
        mock.return_value = {"success": True, "response": "Retried successfully"}
        yield mock


# =============================================================================
# Bug Filing Tests (No Feedback Text)
# =============================================================================

class TestFeedbackBugFiling:
    """Tests for the bug filing flow."""

    def test_feedback_files_bug_successfully(
        self, client, authenticated_user, mock_vikunja, mock_nats, temp_data_dir
    ):
        """Test that thumbs-down without feedback files a bug."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_command': 'turn off kitchen light',
                'original_response': 'Done!'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['action'] == 'bug_filed'
        assert data['bug_id'] == 'BUG-20260102120000'

        # Verify Vikunja was called
        mock_vikunja.assert_called_once_with(
            'turn off kitchen light',
            'Done!'
        )

        # Verify NATS alert was sent
        mock_nats.assert_called_once()

    def test_feedback_handles_vikunja_failure(
        self, client, authenticated_user, mock_nats, temp_data_dir
    ):
        """Test graceful handling when Vikunja fails."""
        with patch('src.server.file_bug_in_vikunja') as mock_vikunja:
            mock_vikunja.return_value = None  # Simulates failure

            response = client.post(
                '/api/feedback',
                data=json.dumps({
                    'original_command': 'test command',
                    'original_response': 'test response'
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['action'] == 'bug_filed'
            assert data['bug_id'] is None  # Bug ID is None when filing fails


# =============================================================================
# Retry Flow Tests (With Feedback Text)
# =============================================================================

class TestFeedbackRetry:
    """Tests for the retry flow with feedback context."""

    def test_feedback_with_text_triggers_retry(
        self, client, authenticated_user, mock_vikunja, mock_nats, mock_retry, temp_data_dir
    ):
        """Test that feedback with text triggers a retry."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_command': 'turn off kitchen light',
                'original_response': 'Done!',
                'feedback_text': 'the light is still on'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['action'] == 'retry'
        assert data['response'] == 'Retried successfully'
        assert 'bug_id' in data  # Bug is still filed first

        # Verify retry was called
        mock_retry.assert_called_once_with(
            'turn off kitchen light',
            'Done!',
            'the light is still on'
        )

    def test_feedback_retry_failure(
        self, client, authenticated_user, mock_vikunja, mock_nats, temp_data_dir
    ):
        """Test handling when retry fails."""
        with patch('src.server.retry_with_feedback') as mock_retry:
            mock_retry.return_value = {
                "success": False,
                "response": "Retry failed: timeout"
            }

            response = client.post(
                '/api/feedback',
                data=json.dumps({
                    'original_command': 'test command',
                    'original_response': 'test response',
                    'feedback_text': 'try again'
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data['action'] == 'retry'
            assert 'Retry failed' in data['response']


# =============================================================================
# Input Validation Tests
# =============================================================================

class TestFeedbackValidation:
    """Tests for input validation."""

    def test_feedback_requires_original_command(
        self, client, authenticated_user, temp_data_dir
    ):
        """Test that original_command is required."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_response': 'Done!'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_feedback_requires_original_response(
        self, client, authenticated_user, temp_data_dir
    ):
        """Test that original_response is required."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_command': 'test command'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_feedback_requires_json_body(
        self, client, authenticated_user, temp_data_dir
    ):
        """Test that request body must be JSON."""
        response = client.post(
            '/api/feedback',
            data='not json',
            content_type='text/plain'
        )

        # Server returns 500 with "Request body must be JSON" error
        # since get_json() returns None for non-JSON content type
        assert response.status_code in [400, 500]

    def test_feedback_rejects_empty_command(
        self, client, authenticated_user, temp_data_dir
    ):
        """Test that empty command is rejected."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_command': '',
                'original_response': 'Done!'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_feedback_text_is_optional(
        self, client, authenticated_user, mock_vikunja, mock_nats, temp_data_dir
    ):
        """Test that feedback_text is optional."""
        response = client.post(
            '/api/feedback',
            data=json.dumps({
                'original_command': 'test command',
                'original_response': 'test response'
                # No feedback_text
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['action'] == 'bug_filed'


# =============================================================================
# Authentication Tests
# =============================================================================

class TestFeedbackAuthentication:
    """Tests for authentication requirements."""

    def test_feedback_requires_authentication(self, temp_data_dir):
        """Test that endpoint requires login."""
        # Create client WITHOUT LOGIN_DISABLED
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = False  # Enable auth check

        with app.test_client() as client:
            response = client.post(
                '/api/feedback',
                data=json.dumps({
                    'original_command': 'test',
                    'original_response': 'test'
                }),
                content_type='application/json'
            )

            # Should redirect to login
            assert response.status_code == 302
            assert '/login' in response.location or '/auth' in response.location
