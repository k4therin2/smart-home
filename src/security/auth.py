"""
Smart Home Assistant - Authentication Module

Session-based authentication for the web UI.
Phase 2.1: Application Security Baseline
"""

import secrets
import sqlite3
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, Flask, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from src.config import DATA_DIR
from src.utils import send_health_alert


# Auth database path
AUTH_DB_PATH = DATA_DIR / "auth.db"

# Alert thresholds
AUTH_FAILURE_ALERT_THRESHOLD = 3  # Alert after N failed attempts from same IP

# Password hasher with secure defaults
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Session configuration
SESSION_DURATION_HOURS = 24


class User(UserMixin):
    """Simple user class for Flask-Login."""

    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username


def init_auth_db() -> None:
    """Initialize the authentication database."""
    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        # Login attempts table for security monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                success INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        conn.commit()


def create_user(username: str, password: str) -> bool:
    """
    Create a new user with hashed password.

    Args:
        username: Username (must be unique)
        password: Plaintext password to hash

    Returns:
        True if user created, False if username exists
    """
    init_auth_db()

    password_hash = password_hasher.hash(password)

    try:
        with sqlite3.connect(AUTH_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """,
                (username, password_hash, datetime.now().isoformat()),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> User | None:
    """
    Verify user credentials.

    Args:
        username: Username
        password: Plaintext password

    Returns:
        User object if valid, None otherwise
    """
    init_auth_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, password_hash FROM users WHERE username = ?
        """,
            (username,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        user_id, password_hash = row

        try:
            password_hasher.verify(password_hash, password)

            # Update last login
            cursor.execute(
                """
                UPDATE users SET last_login = ? WHERE id = ?
            """,
                (datetime.now().isoformat(), user_id),
            )
            conn.commit()

            # Rehash if needed (parameters changed)
            if password_hasher.check_needs_rehash(password_hash):
                new_hash = password_hasher.hash(password)
                cursor.execute(
                    """
                    UPDATE users SET password_hash = ? WHERE id = ?
                """,
                    (new_hash, user_id),
                )
                conn.commit()

            return User(user_id, username)
        except VerifyMismatchError:
            return None


def log_login_attempt(username: str, ip_address: str, success: bool) -> None:
    """
    Log login attempt for security monitoring.

    Sends a Slack health alert when failed attempts exceed the threshold.
    """
    init_auth_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO login_attempts (username, ip_address, success, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            (username, ip_address, 1 if success else 0, datetime.now().isoformat()),
        )
        conn.commit()

    # Check for repeated failures and alert
    if not success:
        failed_count = get_recent_failed_attempts(ip_address, minutes=15)
        if failed_count == AUTH_FAILURE_ALERT_THRESHOLD:
            # Alert on threshold hit (not on every subsequent failure)
            send_health_alert(
                title="Authentication Failures Detected",
                message=f"*{failed_count}* failed login attempts from IP `{ip_address}` in the last 15 minutes",
                severity="warning",
                component="auth",
                details={
                    "ip_address": ip_address,
                    "username_attempted": username,
                    "failed_attempts": failed_count,
                    "action": "Consider reviewing access logs",
                },
            )
        elif failed_count >= 5:
            # Alert on lockout (rate limit triggered)
            if failed_count == 5:
                send_health_alert(
                    title="IP Address Locked Out",
                    message=f"IP `{ip_address}` has been temporarily locked out after *{failed_count}* failed login attempts",
                    severity="critical",
                    component="auth",
                    details={
                        "ip_address": ip_address,
                        "username_attempted": username,
                        "failed_attempts": failed_count,
                        "action": "Rate limiting active for 15 minutes",
                    },
                )


def get_recent_failed_attempts(ip_address: str, minutes: int = 15) -> int:
    """Get count of failed login attempts from an IP in the last N minutes."""
    init_auth_db()

    cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM login_attempts
            WHERE ip_address = ? AND success = 0 AND timestamp > ?
        """,
            (ip_address, cutoff),
        )
        return cursor.fetchone()[0]


def user_exists() -> bool:
    """Check if any user exists in the database."""
    init_auth_db()

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0] > 0


def get_user_by_id(user_id: int) -> User | None:
    """Load user by ID for Flask-Login."""
    if not AUTH_DB_PATH.exists():
        return None

    with sqlite3.connect(AUTH_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()

        if row:
            return User(row[0], row[1])
        return None


def setup_login_manager(app: Flask) -> LoginManager:
    """
    Configure Flask-Login for the application.

    Args:
        app: Flask application instance

    Returns:
        Configured LoginManager
    """
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(int(user_id))

    return login_manager


def generate_initial_password() -> str:
    """Generate a secure random password for initial setup."""
    return secrets.token_urlsafe(16)


# Blueprint for auth routes
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    # Check if any user exists
    if not user_exists():
        return redirect(url_for("auth.setup"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip_address = request.remote_addr

        # Check for too many failed attempts
        failed_attempts = get_recent_failed_attempts(ip_address)
        if failed_attempts >= 5:
            error = "Too many failed attempts. Please try again later."
            log_login_attempt(username, ip_address, False)
        else:
            user = verify_user(username, password)

            if user:
                login_user(user, remember=False)
                log_login_attempt(username, ip_address, True)

                next_page = request.args.get("next")
                if next_page and next_page.startswith("/"):
                    return redirect(next_page)
                return redirect(url_for("index"))
            else:
                error = "Invalid username or password."
                log_login_attempt(username, ip_address, False)

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Initial setup - create first user account."""
    if user_exists():
        return redirect(url_for("auth.login"))

    generated_password = None
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username:
            error = "Username is required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif not password:
            error = "Password is required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            if create_user(username, password):
                user = verify_user(username, password)
                if user:
                    login_user(user)
                    return redirect(url_for("index"))
            else:
                error = "Failed to create user."
    else:
        # Generate a suggested password
        generated_password = generate_initial_password()

    return render_template("auth/setup.html", error=error, generated_password=generated_password)
