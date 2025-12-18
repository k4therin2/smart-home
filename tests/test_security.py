"""
Tests for security modules (Phase 2.1 & 2.2)
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Mock the DATA_DIR before importing modules
@pytest.fixture(autouse=True)
def mock_data_dir(tmp_path):
    """Use temporary directory for all database operations."""
    with patch('src.security.auth.DATA_DIR', tmp_path):
        with patch('src.security.auth.AUTH_DB_PATH', tmp_path / "auth.db"):
            yield tmp_path


class TestPasswordHashing:
    """Test Argon2 password hashing."""

    def test_password_hash_is_not_plaintext(self, mock_data_dir):
        from src.security.auth import password_hasher

        password = "test_password_123"
        hashed = password_hasher.hash(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_password_verification_succeeds(self, mock_data_dir):
        from src.security.auth import password_hasher

        password = "secure_password_456"
        hashed = password_hasher.hash(password)

        # Should not raise
        password_hasher.verify(hashed, password)

    def test_password_verification_fails_wrong_password(self, mock_data_dir):
        from src.security.auth import password_hasher
        from argon2.exceptions import VerifyMismatchError

        password = "correct_password"
        hashed = password_hasher.hash(password)

        with pytest.raises(VerifyMismatchError):
            password_hasher.verify(hashed, "wrong_password")


class TestUserManagement:
    """Test user creation and verification."""

    def test_create_user_success(self, mock_data_dir):
        from src.security.auth import create_user, user_exists

        result = create_user("testuser", "password123")

        assert result is True
        assert user_exists() is True

    def test_create_duplicate_user_fails(self, mock_data_dir):
        from src.security.auth import create_user

        create_user("duplicate", "password1")
        result = create_user("duplicate", "password2")

        assert result is False

    def test_verify_user_success(self, mock_data_dir):
        from src.security.auth import create_user, verify_user

        create_user("verifytest", "mypassword")
        user = verify_user("verifytest", "mypassword")

        assert user is not None
        assert user.username == "verifytest"

    def test_verify_user_wrong_password(self, mock_data_dir):
        from src.security.auth import create_user, verify_user

        create_user("wrongpw", "correctpassword")
        user = verify_user("wrongpw", "incorrectpassword")

        assert user is None

    def test_verify_user_nonexistent(self, mock_data_dir):
        from src.security.auth import verify_user

        user = verify_user("nonexistent", "anypassword")

        assert user is None

    def test_user_exists_empty_db(self, mock_data_dir):
        from src.security.auth import user_exists

        assert user_exists() is False


class TestLoginAttemptTracking:
    """Test login attempt logging for security monitoring."""

    def test_log_login_attempt_success(self, mock_data_dir):
        from src.security.auth import log_login_attempt, get_recent_failed_attempts

        log_login_attempt("testuser", "192.168.1.100", True)
        failed = get_recent_failed_attempts("192.168.1.100")

        assert failed == 0

    def test_log_login_attempt_failure(self, mock_data_dir):
        from src.security.auth import log_login_attempt, get_recent_failed_attempts

        log_login_attempt("testuser", "192.168.1.101", False)
        log_login_attempt("testuser", "192.168.1.101", False)
        log_login_attempt("testuser", "192.168.1.101", False)

        failed = get_recent_failed_attempts("192.168.1.101")

        assert failed == 3

    def test_failed_attempts_per_ip(self, mock_data_dir):
        from src.security.auth import log_login_attempt, get_recent_failed_attempts

        # Different IPs
        log_login_attempt("user1", "10.0.0.1", False)
        log_login_attempt("user2", "10.0.0.2", False)
        log_login_attempt("user3", "10.0.0.2", False)

        assert get_recent_failed_attempts("10.0.0.1") == 1
        assert get_recent_failed_attempts("10.0.0.2") == 2


class TestUserClass:
    """Test User class for Flask-Login."""

    def test_user_is_authenticated(self, mock_data_dir):
        from src.security.auth import User

        user = User(1, "testuser")

        assert user.is_authenticated is True
        assert user.is_active is True
        assert user.is_anonymous is False

    def test_user_get_id(self, mock_data_dir):
        from src.security.auth import User

        user = User(42, "testuser")

        assert user.get_id() == "42"


class TestInitialPasswordGeneration:
    """Test secure password generation for initial setup."""

    def test_generate_initial_password_length(self, mock_data_dir):
        from src.security.auth import generate_initial_password

        password = generate_initial_password()

        # secrets.token_urlsafe(16) produces ~22 characters
        assert len(password) >= 16

    def test_generate_initial_password_uniqueness(self, mock_data_dir):
        from src.security.auth import generate_initial_password

        passwords = [generate_initial_password() for _ in range(10)]

        # All passwords should be unique
        assert len(set(passwords)) == 10


class TestSSLConfig:
    """Test SSL/TLS configuration."""

    def test_certificates_exist_checks_both_files(self, tmp_path):
        """Test that certificates_exist checks for both cert and key files."""
        from src.security.ssl_config import CERT_FILE, KEY_FILE

        # If certs exist (from generate_cert.py run), both files should exist
        if CERT_FILE.exists() and KEY_FILE.exists():
            from src.security.ssl_config import certificates_exist
            assert certificates_exist() is True
        else:
            # If no certs, function should return False
            from src.security.ssl_config import certificates_exist
            assert certificates_exist() is False

    def test_get_ssl_context_returns_context_when_certs_exist(self):
        """Test that get_ssl_context returns SSLContext when certs exist."""
        from src.security.ssl_config import get_ssl_context, certificates_exist

        context = get_ssl_context()

        if certificates_exist():
            assert context is not None
            import ssl
            assert isinstance(context, ssl.SSLContext)
        else:
            assert context is None

    def test_check_cert_expiry_returns_datetime_when_certs_exist(self):
        """Test that check_cert_expiry returns datetime when certs exist."""
        from src.security.ssl_config import check_cert_expiry, certificates_exist
        from datetime import datetime

        expiry = check_cert_expiry()

        if certificates_exist():
            assert expiry is not None
            assert isinstance(expiry, datetime)
            # Should be in the future
            assert expiry > datetime.now()
        else:
            assert expiry is None

    def test_cert_needs_renewal_logic(self):
        """Test cert_needs_renewal returns correct value based on cert state."""
        from src.security.ssl_config import cert_needs_renewal, certificates_exist

        needs_renewal = cert_needs_renewal()

        if certificates_exist():
            # Cert was just created, shouldn't need renewal
            assert needs_renewal is False
        else:
            # No cert means it needs "renewal" (creation)
            assert needs_renewal is True


class TestPydanticValidation:
    """Test Pydantic input validation."""

    def test_command_request_valid(self):
        from src.server import CommandRequest

        request = CommandRequest(command="turn on the lights")

        assert request.command == "turn on the lights"

    def test_command_request_empty_fails(self):
        from src.server import CommandRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CommandRequest(command="")

    def test_command_request_too_long_fails(self):
        from src.server import CommandRequest
        from pydantic import ValidationError

        long_command = "x" * 1001

        with pytest.raises(ValidationError):
            CommandRequest(command=long_command)

    def test_command_request_max_length_ok(self):
        from src.server import CommandRequest

        command = "x" * 1000
        request = CommandRequest(command=command)

        assert len(request.command) == 1000


class TestSecurityHeaders:
    """Test that security headers are applied."""

    def test_security_headers_present(self):
        from src.server import app

        with app.test_client() as client:
            # Access login page (doesn't require auth)
            response = client.get('/auth/login')

            assert response.headers.get('X-Content-Type-Options') == 'nosniff'
            assert response.headers.get('X-Frame-Options') == 'DENY'
            assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
            assert response.headers.get('X-XSS-Protection') == '1; mode=block'
            assert 'Content-Security-Policy' in response.headers

    def test_csp_header_content(self):
        from src.server import app

        with app.test_client() as client:
            response = client.get('/auth/login')

            csp = response.headers.get('Content-Security-Policy')

            assert "default-src 'self'" in csp
            assert "frame-ancestors 'none'" in csp


class TestAuthenticationRequired:
    """Test that routes require authentication."""

    def test_index_redirects_to_login(self):
        from src.server import app

        with app.test_client() as client:
            response = client.get('/')

            assert response.status_code == 302
            assert '/auth/login' in response.location

    def test_api_command_requires_auth(self):
        from src.server import app

        with app.test_client() as client:
            response = client.post('/api/command',
                                  json={"command": "test"},
                                  content_type='application/json')

            # Should redirect to login
            assert response.status_code == 302

    def test_api_status_requires_auth(self):
        from src.server import app

        with app.test_client() as client:
            response = client.get('/api/status')

            assert response.status_code == 302

    def test_api_history_requires_auth(self):
        from src.server import app

        with app.test_client() as client:
            response = client.get('/api/history')

            assert response.status_code == 302
