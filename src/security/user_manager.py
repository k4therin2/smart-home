"""
Smart Home Assistant - Multi-User Management Module (WP-10.11)

Provides user role management, guest access, preferences, and history tracking.
Supports three user types:
- Owner: Full control, can manage users and guests
- Resident: Most controls, can't manage users
- Guest: Basic controls (lights, temperature) with time-limited access
"""

import secrets
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_login import UserMixin

from src.config import DATA_DIR

# Database path (same as auth.py for unified user management)
AUTH_DB_PATH = DATA_DIR / "auth.db"

# Password hasher for guest access
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Guest session configuration
GUEST_SESSION_HOURS_DEFAULT = 4


class UserRole(Enum):
    """User role definitions with permission hierarchy."""
    OWNER = 'owner'
    RESIDENT = 'resident'
    GUEST = 'guest'


# Permission definitions per role
ROLE_PERMISSIONS = {
    UserRole.OWNER: {
        'manage_users',
        'manage_guests',
        'manage_automations',
        'control_lights',
        'control_temperature',
        'view_history',
        'access_security',
        'access_settings',
        'control_vacuum',
        'control_music',
    },
    UserRole.RESIDENT: {
        'manage_guests',  # Residents can invite guests
        'manage_automations',
        'control_lights',
        'control_temperature',
        'view_history',
        'access_settings',
        'control_vacuum',
        'control_music',
    },
    UserRole.GUEST: {
        'control_lights',
        'control_temperature',
        'control_music',  # Basic music control
    },
}


def has_permission(role: UserRole, permission: str) -> bool:
    """Check if a role has a specific permission."""
    if role not in ROLE_PERMISSIONS:
        return False
    return permission in ROLE_PERMISSIONS[role]


def has_permission_for_user(user, permission: str) -> bool:
    """Check if a user object has a specific permission."""
    if hasattr(user, 'is_guest') and user.is_guest:
        return has_permission(UserRole.GUEST, permission)
    if hasattr(user, 'role'):
        return has_permission(user.role, permission)
    # For standard User objects, look up role from database
    if hasattr(user, 'username'):
        role = get_user_role(user.username)
        if role:
            return has_permission(role, permission)
    return False


class GuestUser(UserMixin):
    """User class for guest users with time-limited access."""

    def __init__(self, guest_id: str, name: str, expires_at: datetime):
        self.guest_id = guest_id
        self.name = name
        self.expires_at = expires_at
        self.is_guest = True

    @property
    def id(self) -> str:
        """Return prefixed ID for Flask-Login."""
        return f"guest:{self.guest_id}"

    def get_id(self) -> str:
        """Required by Flask-Login."""
        return self.id

    @property
    def username(self) -> str:
        """Guest's display name."""
        return self.name

    def is_session_active(self) -> bool:
        """Check if the guest session has not expired."""
        return datetime.now() < self.expires_at


# =============================================================================
# Database Initialization
# =============================================================================


def init_user_management_db() -> None:
    """Initialize multi-user management tables."""
    # First ensure the base auth tables exist
    from src.security.auth import init_auth_db
    init_auth_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()

        # Add role column to users table if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'role' not in columns:
            cursor.execute("""
                ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'resident'
            """)

        # Guest links table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guest_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0
            )
        """)

        # User preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(username, preference_key)
            )
        """)

        # User command history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                command TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Create index for faster history lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_history_username
            ON user_history(username, timestamp DESC)
        """)

        conn.commit()


# =============================================================================
# User Role Management
# =============================================================================


def create_user_with_role(
    username: str,
    password: str,
    role: UserRole = None
) -> bool:
    """
    Create a new user with the specified role.

    Args:
        username: Username (must be unique)
        password: Plaintext password to hash
        role: User role (defaults to RESIDENT)

    Returns:
        True if user created, False if username exists
    """
    from src.security.auth import password_hasher as auth_hasher

    init_user_management_db()

    if role is None:
        role = UserRole.RESIDENT

    password_hash = auth_hasher.hash(password)

    try:
        with sqlite3.connect(AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, created_at, role)
                VALUES (?, ?, ?, ?)
            """,
                (username, password_hash, datetime.now().isoformat(), role.value),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def create_first_user(username: str, password: str) -> bool:
    """
    Create the first user as owner.

    Args:
        username: Username
        password: Password

    Returns:
        True if created as owner
    """
    return create_user_with_role(username, password, UserRole.OWNER)


def get_user_role(username: str) -> Optional[UserRole]:
    """
    Get a user's role.

    Args:
        username: Username to look up

    Returns:
        UserRole enum value or None if user not found
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()

        if row and row[0]:
            try:
                return UserRole(row[0])
            except ValueError:
                return UserRole.RESIDENT  # Default if invalid role
        return None


def update_user_role(username: str, new_role: UserRole) -> bool:
    """
    Update a user's role.

    Args:
        username: Username to update
        new_role: New role to assign

    Returns:
        True if updated, False if user not found
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users SET role = ? WHERE username = ?
        """,
            (new_role.value, username)
        )
        conn.commit()
        return cursor.rowcount > 0


# =============================================================================
# Guest Access Management
# =============================================================================


def generate_guest_link(
    name: str,
    password: str,
    expires_hours: int = GUEST_SESSION_HOURS_DEFAULT
) -> dict:
    """
    Generate a guest access link with password protection.

    Args:
        name: Display name for the guest
        password: Password required to access
        expires_hours: Hours until the link expires (can be negative for testing)

    Returns:
        Dictionary with 'token' and 'url' keys
    """
    init_user_management_db()

    token = secrets.token_urlsafe(32)
    password_hash = password_hasher.hash(password)
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=expires_hours)

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO guest_links (token, name, password_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (token, name, password_hash, created_at.isoformat(), expires_at.isoformat())
        )
        conn.commit()

    return {
        'token': token,
        'url': f'/auth/guest_access/{token}',
        'expires_at': expires_at,
    }


def validate_guest_token(token: str, password: str) -> Optional[dict]:
    """
    Validate a guest token and password.

    Args:
        token: Guest access token
        password: Password to verify

    Returns:
        Guest info dict if valid, None if invalid or expired
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, password_hash, expires_at, revoked
            FROM guest_links WHERE token = ?
        """,
            (token,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        name, password_hash, expires_at_str, revoked = row

        # Check if revoked
        if revoked:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now() > expires_at:
            return None

        # Verify password
        try:
            password_hasher.verify(password_hash, password)
        except VerifyMismatchError:
            return None

        return {
            'name': name,
            'expires_at': expires_at,
            'token': token,
        }


def revoke_guest_link(token: str) -> bool:
    """
    Revoke a guest access link.

    Args:
        token: Token to revoke

    Returns:
        True if revoked, False if not found
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE guest_links SET revoked = 1 WHERE token = ?
        """,
            (token,)
        )
        conn.commit()
        return cursor.rowcount > 0


def list_active_guest_links() -> list:
    """
    List all active (non-expired, non-revoked) guest links.

    Returns:
        List of guest link info dictionaries
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT token, name, created_at, expires_at
            FROM guest_links
            WHERE revoked = 0 AND expires_at > ?
            ORDER BY created_at DESC
        """,
            (datetime.now().isoformat(),)
        )
        rows = cursor.fetchall()

        return [
            {
                'token': row[0],
                'name': row[1],
                'created_at': datetime.fromisoformat(row[2]),
                'expires_at': datetime.fromisoformat(row[3]),
            }
            for row in rows
        ]


# =============================================================================
# User Preferences
# =============================================================================


def save_user_preference(username: str, key: str, value: str) -> bool:
    """
    Save or update a user preference.

    Args:
        username: Username
        key: Preference key
        value: Preference value

    Returns:
        True if saved
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_preferences (username, preference_key, preference_value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username, preference_key)
            DO UPDATE SET preference_value = excluded.preference_value,
                          updated_at = excluded.updated_at
        """,
            (username, key, value, datetime.now().isoformat())
        )
        conn.commit()
        return True


def get_user_preference(username: str, key: str, default: str = None) -> Optional[str]:
    """
    Get a user preference value.

    Args:
        username: Username
        key: Preference key
        default: Default value if not found

    Returns:
        Preference value or default
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT preference_value FROM user_preferences
            WHERE username = ? AND preference_key = ?
        """,
            (username, key)
        )
        row = cursor.fetchone()

        return row[0] if row else default


def get_all_preferences(username: str) -> dict:
    """
    Get all preferences for a user.

    Args:
        username: Username

    Returns:
        Dictionary of all preferences
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT preference_key, preference_value FROM user_preferences
            WHERE username = ?
        """,
            (username,)
        )
        rows = cursor.fetchall()

        return {row[0]: row[1] for row in rows}


# =============================================================================
# User Command History
# =============================================================================


def log_user_command(username: str, command: str, result: str) -> None:
    """
    Log a command to user history.

    Args:
        username: Username who executed command
        command: The command text
        result: Result of the command (success/error/etc)
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_history (username, command, result, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            (username, command, result, datetime.now().isoformat())
        )
        conn.commit()


def get_user_history(username: str, limit: int = 50) -> list:
    """
    Get command history for a user.

    Args:
        username: Username
        limit: Maximum number of entries to return

    Returns:
        List of history entries, newest first
    """
    init_user_management_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT command, result, timestamp FROM user_history
            WHERE username = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (username, limit)
        )
        rows = cursor.fetchall()

        return [
            {
                'command': row[0],
                'result': row[1],
                'timestamp': datetime.fromisoformat(row[2]),
            }
            for row in rows
        ]
