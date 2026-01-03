"""
Tests for Multi-User Support (WP-10.11)

These tests cover:
- User roles (owner, resident, guest)
- Guest mode with basic controls
- Password-protected guest access URLs
- Guest session expiration
- Per-user preferences and history
"""

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask, session

# We'll import from the module we're about to create
# The tests will fail initially until we implement the module


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_auth.db"
    return db_path


@pytest.fixture
def patched_db(temp_db):
    """Patch both auth modules to use the temp database."""
    with patch('src.security.user_manager.AUTH_DB_PATH', temp_db):
        with patch('src.security.auth.AUTH_DB_PATH', temp_db):
            yield temp_db


@pytest.fixture
def flask_app(tmp_path, temp_db):
    """Create a Flask app for testing."""
    from src.security.auth import auth_bp, setup_login_manager, init_auth_db

    app = Flask(__name__, template_folder=str(Path(__file__).parent.parent.parent / 'templates'))
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with patch('src.security.auth.AUTH_DB_PATH', temp_db):
        init_auth_db()
        app.register_blueprint(auth_bp)
        setup_login_manager(app)

        @app.route('/')
        def index():
            return "Home"

        yield app


@pytest.fixture
def client(flask_app):
    """Create a test client."""
    return flask_app.test_client()


# =============================================================================
# UserRole Enum Tests
# =============================================================================


class TestUserRoles:
    """Tests for user role definitions."""

    def test_role_enum_exists(self):
        """Test that UserRole enum is defined."""
        from src.security.user_manager import UserRole

        assert hasattr(UserRole, 'OWNER')
        assert hasattr(UserRole, 'RESIDENT')
        assert hasattr(UserRole, 'GUEST')

    def test_role_values(self):
        """Test role enum values."""
        from src.security.user_manager import UserRole

        assert UserRole.OWNER.value == 'owner'
        assert UserRole.RESIDENT.value == 'resident'
        assert UserRole.GUEST.value == 'guest'

    def test_role_hierarchy(self):
        """Test that roles have correct permission hierarchy."""
        from src.security.user_manager import UserRole, has_permission

        # Owner has all permissions
        assert has_permission(UserRole.OWNER, 'manage_users') is True
        assert has_permission(UserRole.OWNER, 'control_lights') is True
        assert has_permission(UserRole.OWNER, 'view_history') is True

        # Resident has most permissions but not user management
        assert has_permission(UserRole.RESIDENT, 'manage_users') is False
        assert has_permission(UserRole.RESIDENT, 'control_lights') is True
        assert has_permission(UserRole.RESIDENT, 'view_history') is True

        # Guest has limited permissions
        assert has_permission(UserRole.GUEST, 'manage_users') is False
        assert has_permission(UserRole.GUEST, 'control_lights') is True
        assert has_permission(UserRole.GUEST, 'view_history') is False


# =============================================================================
# User Profile Tests
# =============================================================================


class TestUserProfile:
    """Tests for user profile management."""

    def test_create_user_with_role(self, patched_db):
        """Test creating a user with a specific role."""
        from src.security.user_manager import create_user_with_role, get_user_role, UserRole

        result = create_user_with_role("owner_user", "password123", UserRole.OWNER)

        assert result is True
        assert get_user_role("owner_user") == UserRole.OWNER

    def test_create_resident_user(self, patched_db):
        """Test creating a resident user."""
        from src.security.user_manager import create_user_with_role, get_user_role, UserRole

        result = create_user_with_role("resident1", "password123", UserRole.RESIDENT)

        assert result is True
        assert get_user_role("resident1") == UserRole.RESIDENT

    def test_default_role_is_resident(self, patched_db):
        """Test that new users default to resident role."""
        from src.security.user_manager import create_user_with_role, get_user_role, UserRole

        # Create without explicit role
        result = create_user_with_role("newuser", "password123")

        assert result is True
        assert get_user_role("newuser") == UserRole.RESIDENT

    def test_update_user_role(self, patched_db):
        """Test updating a user's role."""
        from src.security.user_manager import create_user_with_role, update_user_role, get_user_role, UserRole

        create_user_with_role("upgradeuser", "password123", UserRole.GUEST)

        result = update_user_role("upgradeuser", UserRole.RESIDENT)

        assert result is True
        assert get_user_role("upgradeuser") == UserRole.RESIDENT

    def test_first_user_becomes_owner(self, patched_db):
        """Test that the first user created becomes owner."""
        from src.security.user_manager import create_first_user, get_user_role, UserRole

        result = create_first_user("admin", "password123")

        assert result is True
        assert get_user_role("admin") == UserRole.OWNER


# =============================================================================
# Guest Access Tests
# =============================================================================


class TestGuestAccess:
    """Tests for guest access via password-protected URL."""

    def test_generate_guest_link(self, patched_db):
        """Test generating a guest access link."""
        from src.security.user_manager import generate_guest_link

        link_data = generate_guest_link(
            name="Living Room Guest",
            password="guest123",
            expires_hours=24
        )

        assert 'token' in link_data
        assert 'url' in link_data
        assert len(link_data['token']) >= 32  # Secure token length
        assert 'guest_access' in link_data['url']

    def test_validate_guest_token(self, patched_db):
        """Test validating a guest access token."""
        from src.security.user_manager import generate_guest_link, validate_guest_token

        link_data = generate_guest_link(
            name="Test Guest",
            password="guest123",
            expires_hours=24
        )

        result = validate_guest_token(link_data['token'], "guest123")

        assert result is not None
        assert result['name'] == "Test Guest"

    def test_guest_token_wrong_password(self, patched_db):
        """Test that wrong password fails validation."""
        from src.security.user_manager import generate_guest_link, validate_guest_token

        link_data = generate_guest_link(
            name="Test Guest",
            password="correct123",
            expires_hours=24
        )

        result = validate_guest_token(link_data['token'], "wrongpassword")

        assert result is None

    def test_guest_token_expiration(self, patched_db):
        """Test that expired guest tokens are rejected."""
        from src.security.user_manager import generate_guest_link, validate_guest_token

        # Create token that expires in -1 hours (already expired)
        link_data = generate_guest_link(
            name="Expired Guest",
            password="guest123",
            expires_hours=-1
        )

        result = validate_guest_token(link_data['token'], "guest123")

        assert result is None

    def test_revoke_guest_link(self, patched_db):
        """Test revoking a guest access link."""
        from src.security.user_manager import generate_guest_link, validate_guest_token, revoke_guest_link

        link_data = generate_guest_link(
            name="Revokable Guest",
            password="guest123",
            expires_hours=24
        )

        # Verify it works before revocation
        assert validate_guest_token(link_data['token'], "guest123") is not None

        # Revoke the link
        revoke_guest_link(link_data['token'])

        # Should now be invalid
        assert validate_guest_token(link_data['token'], "guest123") is None

    def test_list_active_guest_links(self, patched_db):
        """Test listing all active guest links."""
        from src.security.user_manager import generate_guest_link, list_active_guest_links

        generate_guest_link("Guest 1", "pass1", 24)
        generate_guest_link("Guest 2", "pass2", 24)
        generate_guest_link("Guest 3", "pass3", 24)

        links = list_active_guest_links()

        assert len(links) == 3
        assert any(g['name'] == "Guest 1" for g in links)


# =============================================================================
# Guest Session Tests
# =============================================================================


class TestGuestSession:
    """Tests for guest session management."""

    def test_guest_session_expiration_config(self):
        """Test that guest session expiration is configurable."""
        from src.security.user_manager import GUEST_SESSION_HOURS_DEFAULT

        assert GUEST_SESSION_HOURS_DEFAULT == 4  # 4 hours default

    def test_guest_user_class(self):
        """Test GuestUser class properties."""
        from src.security.user_manager import GuestUser

        guest = GuestUser(
            guest_id="guest-token-123",
            name="Party Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        assert guest.id == "guest:guest-token-123"
        assert guest.name == "Party Guest"
        assert guest.is_authenticated is True
        assert guest.is_guest is True

    def test_guest_session_is_active(self):
        """Test checking if guest session is still active."""
        from src.security.user_manager import GuestUser

        # Active guest
        active_guest = GuestUser(
            guest_id="guest-123",
            name="Active",
            expires_at=datetime.now() + timedelta(hours=2)
        )
        assert active_guest.is_session_active() is True

        # Expired guest
        expired_guest = GuestUser(
            guest_id="guest-456",
            name="Expired",
            expires_at=datetime.now() - timedelta(hours=1)
        )
        assert expired_guest.is_session_active() is False


# =============================================================================
# Guest Permissions Tests
# =============================================================================


class TestGuestPermissions:
    """Tests for guest permission restrictions."""

    def test_guest_can_control_lights(self):
        """Test that guests can control lights."""
        from src.security.user_manager import GuestUser, has_permission_for_user

        guest = GuestUser(
            guest_id="guest-123",
            name="Light Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        assert has_permission_for_user(guest, 'control_lights') is True

    def test_guest_can_control_temperature(self):
        """Test that guests can control temperature (if thermostat available)."""
        from src.security.user_manager import GuestUser, has_permission_for_user

        guest = GuestUser(
            guest_id="guest-123",
            name="Temp Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        # Basic temperature control allowed for guests
        assert has_permission_for_user(guest, 'control_temperature') is True

    def test_guest_cannot_access_history(self):
        """Test that guests cannot access command history."""
        from src.security.user_manager import GuestUser, has_permission_for_user

        guest = GuestUser(
            guest_id="guest-123",
            name="No History Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        assert has_permission_for_user(guest, 'view_history') is False

    def test_guest_cannot_manage_automations(self):
        """Test that guests cannot create/modify automations."""
        from src.security.user_manager import GuestUser, has_permission_for_user

        guest = GuestUser(
            guest_id="guest-123",
            name="Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        assert has_permission_for_user(guest, 'manage_automations') is False

    def test_guest_cannot_access_security(self):
        """Test that guests cannot access security settings."""
        from src.security.user_manager import GuestUser, has_permission_for_user

        guest = GuestUser(
            guest_id="guest-123",
            name="Guest",
            expires_at=datetime.now() + timedelta(hours=4)
        )

        assert has_permission_for_user(guest, 'access_security') is False


# =============================================================================
# User Preferences Tests
# =============================================================================


class TestUserPreferences:
    """Tests for per-user preferences."""

    def test_save_user_preference(self, patched_db):
        """Test saving a user preference."""
        from src.security.user_manager import create_user_with_role, save_user_preference, get_user_preference, UserRole

        create_user_with_role("prefuser", "password", UserRole.RESIDENT)

        save_user_preference("prefuser", "theme", "dark")

        result = get_user_preference("prefuser", "theme")
        assert result == "dark"

    def test_get_default_preference(self, patched_db):
        """Test getting a preference with default value."""
        from src.security.user_manager import create_user_with_role, get_user_preference, UserRole

        create_user_with_role("newuser", "password", UserRole.RESIDENT)

        result = get_user_preference("newuser", "nonexistent", default="default_value")
        assert result == "default_value"

    def test_update_preference(self, patched_db):
        """Test updating an existing preference."""
        from src.security.user_manager import create_user_with_role, save_user_preference, get_user_preference, UserRole

        create_user_with_role("updateuser", "password", UserRole.RESIDENT)

        save_user_preference("updateuser", "language", "en")
        save_user_preference("updateuser", "language", "es")

        result = get_user_preference("updateuser", "language")
        assert result == "es"

    def test_get_all_preferences(self, patched_db):
        """Test getting all preferences for a user."""
        from src.security.user_manager import create_user_with_role, save_user_preference, get_all_preferences, UserRole

        create_user_with_role("allprefuser", "password", UserRole.RESIDENT)

        save_user_preference("allprefuser", "theme", "dark")
        save_user_preference("allprefuser", "language", "en")
        save_user_preference("allprefuser", "notifications", "enabled")

        prefs = get_all_preferences("allprefuser")

        assert len(prefs) == 3
        assert prefs['theme'] == "dark"
        assert prefs['language'] == "en"


# =============================================================================
# User History Tests
# =============================================================================


class TestUserHistory:
    """Tests for per-user command history."""

    def test_log_user_command(self, patched_db):
        """Test logging a command for a user."""
        from src.security.user_manager import create_user_with_role, log_user_command, get_user_history, UserRole

        create_user_with_role("histuser", "password", UserRole.RESIDENT)

        log_user_command("histuser", "turn on living room lights", "success")

        history = get_user_history("histuser", limit=10)

        assert len(history) == 1
        assert history[0]['command'] == "turn on living room lights"

    def test_history_ordered_by_time(self, patched_db):
        """Test that history is ordered newest first."""
        from src.security.user_manager import create_user_with_role, log_user_command, get_user_history, UserRole

        create_user_with_role("orderuser", "password", UserRole.RESIDENT)

        log_user_command("orderuser", "first command", "success")
        log_user_command("orderuser", "second command", "success")
        log_user_command("orderuser", "third command", "success")

        history = get_user_history("orderuser", limit=10)

        assert history[0]['command'] == "third command"
        assert history[2]['command'] == "first command"

    def test_history_limit(self, patched_db):
        """Test that history respects limit parameter."""
        from src.security.user_manager import create_user_with_role, log_user_command, get_user_history, UserRole

        create_user_with_role("limituser", "password", UserRole.RESIDENT)

        for i in range(10):
            log_user_command("limituser", f"command {i}", "success")

        history = get_user_history("limituser", limit=5)

        assert len(history) == 5


# =============================================================================
# Database Schema Tests
# =============================================================================


class TestDatabaseSchema:
    """Tests for multi-user database schema."""

    def test_init_creates_user_roles_column(self, patched_db):
        """Test that init adds role column to users table."""
        from src.security.user_manager import init_user_management_db

        init_user_management_db()

        with sqlite3.connect(patched_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]

            assert 'role' in columns

    def test_init_creates_guest_links_table(self, patched_db):
        """Test that init creates guest_links table."""
        from src.security.user_manager import init_user_management_db

        init_user_management_db()

        with sqlite3.connect(patched_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='guest_links'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_user_preferences_table(self, patched_db):
        """Test that init creates user_preferences table."""
        from src.security.user_manager import init_user_management_db

        init_user_management_db()

        with sqlite3.connect(patched_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
            )
            assert cursor.fetchone() is not None

    def test_init_creates_user_history_table(self, patched_db):
        """Test that init creates user_history table."""
        from src.security.user_manager import init_user_management_db

        init_user_management_db()

        with sqlite3.connect(patched_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_history'"
            )
            assert cursor.fetchone() is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestMultiUserIntegration:
    """Integration tests for multi-user system."""

    def test_owner_can_create_guest_link(self, patched_db):
        """Test that owner can create guest links."""
        from src.security.user_manager import (
            create_user_with_role,
            generate_guest_link,
            get_user_role,
            has_permission,
            UserRole
        )

        # Create owner
        create_user_with_role("admin", "password", UserRole.OWNER)

        # Owner should have permission
        assert has_permission(get_user_role("admin"), 'manage_guests') is True

        # Create guest link
        link = generate_guest_link("Party Guest", "party123", 8)
        assert link is not None

    def test_resident_cannot_manage_users(self, patched_db):
        """Test that residents cannot manage users."""
        from src.security.user_manager import (
            create_user_with_role,
            get_user_role,
            has_permission,
            UserRole
        )

        create_user_with_role("resident", "password", UserRole.RESIDENT)

        assert has_permission(get_user_role("resident"), 'manage_users') is False

    def test_guest_access_flow(self, patched_db):
        """Test complete guest access flow."""
        from src.security.user_manager import (
            generate_guest_link,
            validate_guest_token,
            GuestUser,
            has_permission_for_user
        )

        # Create guest link
        link_data = generate_guest_link(
            name="Dinner Guest",
            password="dinner2024",
            expires_hours=4
        )

        # Validate token
        guest_info = validate_guest_token(link_data['token'], "dinner2024")
        assert guest_info is not None

        # Create guest user
        guest = GuestUser(
            guest_id=link_data['token'],
            name=guest_info['name'],
            expires_at=guest_info['expires_at']
        )

        # Check permissions
        assert has_permission_for_user(guest, 'control_lights') is True
        assert has_permission_for_user(guest, 'view_history') is False
