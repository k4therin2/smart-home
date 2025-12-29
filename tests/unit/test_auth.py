"""
Tests for src/security/auth.py - Authentication Module

These tests cover user creation, verification, login attempt tracking,
session management, and the auth blueprint routes.
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest
from flask import Flask

from src.security.auth import (
    User,
    init_auth_db,
    create_user,
    verify_user,
    log_login_attempt,
    get_recent_failed_attempts,
    user_exists,
    get_user_by_id,
    setup_login_manager,
    generate_initial_password,
    auth_bp,
    AUTH_FAILURE_ALERT_THRESHOLD,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_auth.db"
    with patch('src.security.auth.AUTH_DB_PATH', db_path):
        yield db_path


@pytest.fixture
def initialized_db(temp_db):
    """Create and initialize a temporary database."""
    with patch('src.security.auth.AUTH_DB_PATH', temp_db):
        init_auth_db()
        yield temp_db


@pytest.fixture
def flask_app(initialized_db):
    """Create a Flask app with auth blueprint."""
    with patch('src.security.auth.AUTH_DB_PATH', initialized_db):
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.config['TESTING'] = True
        app.register_blueprint(auth_bp)

        # Add a dummy index route
        @app.route('/')
        def index():
            return "Home"

        setup_login_manager(app)

        yield app


@pytest.fixture
def client(flask_app):
    """Create a test client."""
    return flask_app.test_client()


# =============================================================================
# User Class Tests
# =============================================================================


class TestUser:
    """Tests for the User class."""

    def test_user_creation(self):
        """Test User object creation."""
        user = User(user_id=1, username="testuser")

        assert user.id == 1
        assert user.username == "testuser"

    def test_user_is_authenticated(self):
        """Test that User is authenticated (UserMixin)."""
        user = User(user_id=1, username="testuser")

        assert user.is_authenticated is True

    def test_user_is_active(self):
        """Test that User is active by default (UserMixin)."""
        user = User(user_id=1, username="testuser")

        assert user.is_active is True

    def test_user_get_id(self):
        """Test that get_id returns string id (UserMixin)."""
        user = User(user_id=42, username="testuser")

        assert user.get_id() == "42"


# =============================================================================
# Database Initialization Tests
# =============================================================================


class TestInitAuthDb:
    """Tests for database initialization."""

    def test_init_creates_users_table(self, temp_db):
        """Test that init creates users table."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()

            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                )
                assert cursor.fetchone() is not None

    def test_init_creates_login_attempts_table(self, temp_db):
        """Test that init creates login_attempts table."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()

            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'"
                )
                assert cursor.fetchone() is not None

    def test_init_is_idempotent(self, temp_db):
        """Test that calling init multiple times is safe."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()
            init_auth_db()
            init_auth_db()

            # Should still work
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                assert cursor.fetchone()[0] >= 0


# =============================================================================
# User Management Tests
# =============================================================================


class TestCreateUser:
    """Tests for create_user function."""

    def test_create_user_success(self, temp_db):
        """Test successful user creation."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            result = create_user("testuser", "password123")

            assert result is True

    def test_create_user_duplicate_fails(self, temp_db):
        """Test that duplicate username fails."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("duplicate", "password1")
            result = create_user("duplicate", "password2")

            assert result is False

    def test_create_user_stores_hashed_password(self, temp_db):
        """Test that password is hashed, not stored plaintext."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("hasheduser", "mypassword")

            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT password_hash FROM users WHERE username = ?",
                    ("hasheduser",)
                )
                password_hash = cursor.fetchone()[0]

                assert password_hash != "mypassword"
                assert password_hash.startswith("$argon2")


class TestVerifyUser:
    """Tests for verify_user function."""

    def test_verify_correct_password(self, temp_db):
        """Test verification with correct password."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("verifyuser", "correctpassword")
            user = verify_user("verifyuser", "correctpassword")

            assert user is not None
            assert user.username == "verifyuser"

    def test_verify_wrong_password(self, temp_db):
        """Test verification with wrong password."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("verifyuser", "correctpassword")
            user = verify_user("verifyuser", "wrongpassword")

            assert user is None

    def test_verify_nonexistent_user(self, temp_db):
        """Test verification of nonexistent user."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()
            user = verify_user("nonexistent", "anypassword")

            assert user is None

    def test_verify_updates_last_login(self, temp_db):
        """Test that successful verification updates last_login."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("loginuser", "password")
            verify_user("loginuser", "password")

            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT last_login FROM users WHERE username = ?",
                    ("loginuser",)
                )
                last_login = cursor.fetchone()[0]

                assert last_login is not None


# =============================================================================
# Login Attempt Tracking Tests
# =============================================================================


class TestLoginAttemptTracking:
    """Tests for login attempt tracking."""

    def test_log_successful_attempt(self, temp_db):
        """Test logging successful login attempt."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            with patch('src.security.auth.send_health_alert'):
                init_auth_db()
                log_login_attempt("testuser", "192.168.1.1", True)

                with sqlite3.connect(temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM login_attempts")
                    row = cursor.fetchone()

                    assert row is not None
                    assert row[1] == "testuser"  # username
                    assert row[2] == "192.168.1.1"  # ip_address
                    assert row[3] == 1  # success

    def test_log_failed_attempt(self, temp_db):
        """Test logging failed login attempt."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            with patch('src.security.auth.send_health_alert'):
                init_auth_db()
                log_login_attempt("testuser", "192.168.1.1", False)

                with sqlite3.connect(temp_db) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT success FROM login_attempts")
                    success = cursor.fetchone()[0]

                    assert success == 0

    def test_get_recent_failed_attempts(self, temp_db):
        """Test counting recent failed attempts."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            with patch('src.security.auth.send_health_alert'):
                init_auth_db()

                # Log several failed attempts
                for _ in range(3):
                    log_login_attempt("user", "10.0.0.1", False)

                count = get_recent_failed_attempts("10.0.0.1", minutes=15)
                assert count == 3

    def test_get_recent_failed_attempts_ignores_success(self, temp_db):
        """Test that successful attempts aren't counted."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            with patch('src.security.auth.send_health_alert'):
                init_auth_db()

                log_login_attempt("user", "10.0.0.1", True)
                log_login_attempt("user", "10.0.0.1", False)
                log_login_attempt("user", "10.0.0.1", True)

                count = get_recent_failed_attempts("10.0.0.1", minutes=15)
                assert count == 1

    def test_alert_on_threshold(self, temp_db):
        """Test that alert is sent on threshold."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            with patch('src.security.auth.send_health_alert') as mock_alert:
                init_auth_db()

                # Log failures up to threshold
                for i in range(AUTH_FAILURE_ALERT_THRESHOLD):
                    log_login_attempt("user", "10.0.0.1", False)

                # Alert should have been called once (at threshold)
                assert mock_alert.call_count >= 1


class TestUserExists:
    """Tests for user_exists function."""

    def test_no_users_returns_false(self, temp_db):
        """Test returns False when no users exist."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()
            assert user_exists() is False

    def test_with_users_returns_true(self, temp_db):
        """Test returns True when users exist."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("existinguser", "password")
            assert user_exists() is True


class TestGetUserById:
    """Tests for get_user_by_id function."""

    def test_get_existing_user(self, temp_db):
        """Test getting an existing user by ID."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            create_user("iduser", "password")

            # Get user ID
            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", ("iduser",))
                user_id = cursor.fetchone()[0]

            user = get_user_by_id(user_id)

            assert user is not None
            assert user.username == "iduser"

    def test_get_nonexistent_user(self, temp_db):
        """Test getting a nonexistent user."""
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            init_auth_db()
            user = get_user_by_id(999)

            assert user is None

    def test_get_user_no_db(self, tmp_path):
        """Test when database doesn't exist."""
        nonexistent_db = tmp_path / "nonexistent.db"
        with patch('src.security.auth.AUTH_DB_PATH', nonexistent_db):
            user = get_user_by_id(1)

            assert user is None


# =============================================================================
# Login Manager Tests
# =============================================================================


class TestSetupLoginManager:
    """Tests for setup_login_manager function."""

    def test_returns_login_manager(self, initialized_db):
        """Test that it returns a LoginManager."""
        with patch('src.security.auth.AUTH_DB_PATH', initialized_db):
            from flask_login import LoginManager

            app = Flask(__name__)
            app.config['SECRET_KEY'] = 'test'

            manager = setup_login_manager(app)

            assert isinstance(manager, LoginManager)

    def test_configures_login_view(self, initialized_db):
        """Test that login view is configured."""
        with patch('src.security.auth.AUTH_DB_PATH', initialized_db):
            app = Flask(__name__)
            app.config['SECRET_KEY'] = 'test'

            manager = setup_login_manager(app)

            assert manager.login_view == "auth.login"


# =============================================================================
# Password Generation Tests
# =============================================================================


class TestGenerateInitialPassword:
    """Tests for generate_initial_password function."""

    def test_generates_string(self):
        """Test that it generates a string."""
        password = generate_initial_password()

        assert isinstance(password, str)

    def test_generates_secure_length(self):
        """Test that password is sufficiently long."""
        password = generate_initial_password()

        # token_urlsafe(16) generates ~22 chars
        assert len(password) >= 16

    def test_generates_unique_passwords(self):
        """Test that consecutive calls generate different passwords."""
        passwords = [generate_initial_password() for _ in range(10)]

        assert len(set(passwords)) == 10  # All unique
