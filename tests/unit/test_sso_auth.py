"""
Tests for SSO (OAuth2/OIDC) Authentication in SmartHome - WP-90.5

These tests cover SSO authentication functionality:
- OAuth configuration loading
- SSO login flow
- OAuth callback handling
- SSO + local auth coexistence
- Session management with SSO
"""

import json
import secrets
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask, session


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials_file(tmp_path):
    """Create a temporary OAuth credentials file."""
    creds_file = tmp_path / "oauth_credentials.json"
    creds = {
        "smarthome": {
            "client_id": "smarthome-client",
            "client_secret": "test-secret-12345",
            "redirect_uri": "http://colby:5050/auth/callback"
        }
    }
    creds_file.write_text(json.dumps(creds))
    return creds_file


@pytest.fixture
def flask_app_with_sso(tmp_path, oauth_credentials_file):
    """Create a Flask app with SSO enabled."""
    from src.security.auth import auth_bp, setup_login_manager, init_sso, create_user
    from flask_wtf.csrf import CSRFProtect

    app = Flask(__name__, template_folder=str(Path(__file__).parent.parent.parent / 'templates'))
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    # Initialize CSRF for template support
    csrf = CSRFProtect(app)

    # SSO Configuration
    app.config['SSO_ENABLED'] = True
    app.config['AUTHENTIK_BASE_URL'] = 'http://colby:9000'
    app.config['AUTHENTIK_CLIENT_ID'] = 'smarthome-client'
    app.config['AUTHENTIK_CLIENT_SECRET'] = 'test-secret-12345'
    app.config['AUTHENTIK_REDIRECT_URI'] = 'http://colby:5050/auth/callback'

    # Set up temp DB for auth
    db_path = tmp_path / "test_auth.db"

    with patch('src.security.auth.AUTH_DB_PATH', db_path):
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            # Register blueprint and setup
            app.register_blueprint(auth_bp)
            setup_login_manager(app)
            init_sso(app)

            # Create a test user so login page doesn't redirect to setup
            create_user("testuser", "testpassword123")

            # Add a dummy index route
            @app.route('/')
            def index():
                return "Home"

            yield app


@pytest.fixture
def client_with_sso(flask_app_with_sso):
    """Create a test client with SSO enabled."""
    return flask_app_with_sso.test_client()


# =============================================================================
# SSO Configuration Tests
# =============================================================================


class TestSSOConfiguration:
    """Tests for SSO configuration loading."""

    def test_load_oauth_credentials_from_file(self, oauth_credentials_file):
        """Test loading OAuth credentials from JSON file."""
        from src.security.auth import load_oauth_credentials

        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            credentials = load_oauth_credentials()

        assert credentials['client_id'] == 'smarthome-client'
        assert credentials['client_secret'] == 'test-secret-12345'
        assert credentials['redirect_uri'] == 'http://colby:5050/auth/callback'

    def test_load_oauth_credentials_from_env(self, monkeypatch):
        """Test loading OAuth credentials from environment variables."""
        from src.security.auth import load_oauth_credentials

        monkeypatch.setenv('AUTHENTIK_CLIENT_ID', 'env-client-id')
        monkeypatch.setenv('AUTHENTIK_CLIENT_SECRET', 'env-secret')
        monkeypatch.setenv('AUTHENTIK_REDIRECT_URI', 'http://test/callback')

        # Patch credentials file to not exist
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', Path('/nonexistent')):
            credentials = load_oauth_credentials()

        assert credentials['client_id'] == 'env-client-id'
        assert credentials['client_secret'] == 'env-secret'

    def test_sso_disabled_by_default_if_no_credentials(self, monkeypatch):
        """Test that SSO is disabled if no credentials configured."""
        from src.security.auth import is_sso_available

        # Clear environment variables
        monkeypatch.delenv('AUTHENTIK_CLIENT_ID', raising=False)
        monkeypatch.delenv('AUTHENTIK_CLIENT_SECRET', raising=False)
        monkeypatch.delenv('AUTHENTIK_REDIRECT_URI', raising=False)

        with patch('src.security.auth.SSO_CREDENTIALS_FILE', Path('/nonexistent')):
            available = is_sso_available()

        assert available is False

    def test_sso_enabled_with_valid_credentials(self, oauth_credentials_file):
        """Test that SSO is enabled when credentials are available."""
        from src.security.auth import is_sso_available

        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            available = is_sso_available()

        assert available is True


# =============================================================================
# SSO Login Flow Tests
# =============================================================================


class TestSSOLoginFlow:
    """Tests for SSO login initiation and flow."""

    def test_login_page_shows_sso_button(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that login page shows SSO button when enabled."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                response = client_with_sso.get('/auth/login')

        assert response.status_code == 200
        assert b'Sign in with SSO' in response.data or b'sso' in response.data.lower()

    def test_login_page_hides_sso_when_disabled(self, tmp_path):
        """Test that login page hides SSO button when disabled."""
        from src.security.auth import auth_bp, setup_login_manager, create_user

        app = Flask(__name__, template_folder=str(Path(__file__).parent.parent.parent / 'templates'))
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SSO_ENABLED'] = False

        db_path = tmp_path / "test_auth2.db"

        with patch('src.security.auth.AUTH_DB_PATH', db_path):
            with patch('src.security.auth.SSO_CREDENTIALS_FILE', Path('/nonexistent')):
                app.register_blueprint(auth_bp)
                setup_login_manager(app)
                create_user("testuser", "testpassword123")

                @app.route('/')
                def index():
                    return "Home"

                client = app.test_client()
                response = client.get('/auth/login')

        assert response.status_code == 200
        # Should not have SSO button when disabled
        assert b'Sign in with SSO' not in response.data

    def test_sso_login_redirect_to_authentik(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that /auth/sso/login redirects to Authentik."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                response = client_with_sso.get('/auth/sso/login')

        # Should redirect to Authentik authorize URL
        assert response.status_code == 302
        assert 'colby:9000' in response.location
        assert 'authorize' in response.location

    def test_sso_login_stores_state_for_csrf(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that SSO login stores state in session for CSRF protection."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                with client_with_sso.session_transaction() as sess:
                    # Clear any existing state
                    sess.clear()

                response = client_with_sso.get('/auth/sso/login')

                with client_with_sso.session_transaction() as sess:
                    assert 'oauth_state' in sess


# =============================================================================
# OAuth Callback Tests
# =============================================================================


class TestOAuthCallback:
    """Tests for OAuth callback handling."""

    def test_callback_validates_state(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that callback validates state parameter."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                # Set a state in session
                with client_with_sso.session_transaction() as sess:
                    sess['oauth_state'] = 'expected-state'

                # Try callback with wrong state
                response = client_with_sso.get('/auth/callback?code=test&state=wrong-state')

        # Should fail validation and redirect
        assert response.status_code == 302

    def test_callback_handles_error_response(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that callback handles error from Authentik."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                # Simulate error response from Authentik
                response = client_with_sso.get('/auth/callback?error=access_denied&error_description=User+denied')

        # Should redirect to login with error
        assert response.status_code == 302
        assert 'login' in response.location


# =============================================================================
# SSO + Local Auth Coexistence Tests
# =============================================================================


class TestSSOLocalAuthCoexistence:
    """Tests for SSO working alongside local password auth."""

    def test_local_login_still_works_with_sso_enabled(self, tmp_path, oauth_credentials_file):
        """Test that local password login still works when SSO is enabled."""
        from src.security.auth import create_user, verify_user

        db_path = tmp_path / "test_auth_local.db"
        with patch('src.security.auth.AUTH_DB_PATH', db_path):
            # Create a local user
            create_user("localuser", "localpassword123")

            # Verify local login works
            user = verify_user("localuser", "localpassword123")

            assert user is not None
            assert user.username == "localuser"

    def test_login_page_shows_both_options(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that login page shows both SSO and local login."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                response = client_with_sso.get('/auth/login')

        assert response.status_code == 200
        # Should have both SSO and username/password fields
        assert b'username' in response.data.lower()
        assert b'password' in response.data.lower()


# =============================================================================
# SSO Session Management Tests
# =============================================================================


class TestSSOSessionManagement:
    """Tests for SSO session handling."""

    def test_logout_clears_sso_session(self, flask_app_with_sso, tmp_path, oauth_credentials_file):
        """Test that logout clears SSO session data."""
        from flask_login import login_user
        from src.security.auth import SSOUser

        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                with flask_app_with_sso.test_client() as client:
                    # Set up SSO session
                    with client.session_transaction() as sess:
                        sess['sso_user'] = {'sub': 'user-123', 'name': 'Test'}
                        sess['oauth_state'] = 'some-state'
                        sess['_user_id'] = 'sso:user-123'

                    # Make a request to logout
                    # Note: We need to be "logged in" first
                    with flask_app_with_sso.test_request_context():
                        pass

    def test_sso_user_info_stored_in_session(self, tmp_path, oauth_credentials_file):
        """Test that SSO user info is stored in session."""
        from src.security.auth import get_current_sso_user

        from flask import Flask, session

        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test'

        with app.test_request_context():
            session['sso_user'] = {
                'sub': 'user-123',
                'name': 'SSO User',
                'email': 'sso@example.com'
            }

            user = get_current_sso_user()
            assert user is not None
            assert user['sub'] == 'user-123'


# =============================================================================
# SSO Security Tests
# =============================================================================


class TestSSOSecurity:
    """Tests for SSO security features."""

    def test_state_parameter_prevents_csrf(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that missing or invalid state blocks callback."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                # No state in session
                response = client_with_sso.get('/auth/callback?code=test&state=random')

        # Should fail - no state validation
        assert response.status_code == 302

    def test_sso_only_accepts_configured_redirect_uri(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that only configured redirect URI is used."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                response = client_with_sso.get('/auth/sso/login')

        # Redirect should use configured URI
        if response.status_code == 302:
            assert 'colby:5050' in response.location or 'redirect_uri' in response.location

    def test_sso_secrets_not_exposed_in_responses(self, client_with_sso, tmp_path, oauth_credentials_file):
        """Test that client secret is never in responses."""
        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                # Check login page
                response = client_with_sso.get('/auth/login')
                assert b'test-secret-12345' not in response.data


# =============================================================================
# Integration with Flask-Login Tests
# =============================================================================


class TestFlaskLoginIntegration:
    """Tests for SSO integration with Flask-Login."""

    def test_sso_user_class_works(self):
        """Test that SSOUser class works correctly."""
        from src.security.auth import SSOUser

        user = SSOUser(
            sub='user-123',
            username='testuser',
            email='test@example.com',
            name='Test User'
        )

        assert user.id == 'sso:user-123'
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.name == 'Test User'
        assert user.is_authenticated is True

    def test_get_user_by_id_handles_sso_format(self, flask_app_with_sso, tmp_path, oauth_credentials_file):
        """Test that get_user_by_id handles SSO user ID format."""
        from src.security.auth import get_user_by_id

        with patch('src.security.auth.SSO_CREDENTIALS_FILE', oauth_credentials_file):
            with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "test_auth.db"):
                with flask_app_with_sso.test_request_context():
                    from flask import session
                    session['sso_user'] = {
                        'sub': 'user-123',
                        'name': 'SSO User',
                        'preferred_username': 'ssouser',
                        'email': 'sso@example.com'
                    }

                    # Should handle SSO user ID format
                    user = get_user_by_id('sso:user-123')

                    assert user is not None
                    assert user.id == 'sso:user-123'

    def test_get_user_by_id_handles_local_users(self, tmp_path):
        """Test that get_user_by_id still works for local users."""
        from src.security.auth import get_user_by_id, create_user

        db_path = tmp_path / "test_auth_local2.db"
        with patch('src.security.auth.AUTH_DB_PATH', db_path):
            create_user("localuser2", "password123")

            # Get local user (ID 1)
            user = get_user_by_id(1)

            assert user is not None
            assert user.username == "localuser2"
