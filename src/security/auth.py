"""
Smart Home Assistant - Authentication Module

Session-based authentication for the web UI.
Phase 2.1: Application Security Baseline
WP-90.5: SSO Integration with Authentik
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, Flask, redirect, render_template, request, session, url_for
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

# SSO Configuration
DEFAULT_AUTHENTIK_BASE_URL = "http://colby:9000"
DEFAULT_CLIENT_ID = "smarthome-client"
SSO_CREDENTIALS_FILE = Path("/opt/authentik/oauth_credentials.json")

# OAuth client - initialized by init_sso()
oauth = None


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

    def __init__(self, user_id: int | str, username: str):
        self.id = user_id
        self.username = username


class SSOUser(UserMixin):
    """User class for SSO-authenticated users."""

    def __init__(self, sub: str, username: str, email: str = None, name: str = None):
        self.id = f"sso:{sub}"  # Prefix with 'sso:' to distinguish from local users
        self.sub = sub
        self.username = username
        self.email = email
        self.name = name or username

    def get_id(self) -> str:
        return self.id


# =============================================================================
# SSO Configuration Functions
# =============================================================================


def load_oauth_credentials() -> dict:
    """Load OAuth credentials from file or environment."""
    credentials = {
        'client_id': os.environ.get('AUTHENTIK_CLIENT_ID'),
        'client_secret': os.environ.get('AUTHENTIK_CLIENT_SECRET'),
        'redirect_uri': os.environ.get('AUTHENTIK_REDIRECT_URI'),
    }

    # Try to load from file if env vars not set
    if not credentials['client_id'] and SSO_CREDENTIALS_FILE.exists():
        try:
            with open(SSO_CREDENTIALS_FILE) as f:
                all_creds = json.load(f)
                if 'smarthome' in all_creds:
                    creds = all_creds['smarthome']
                    credentials['client_id'] = creds.get('client_id')
                    credentials['client_secret'] = creds.get('client_secret')
                    credentials['redirect_uri'] = creds.get('redirect_uri')
        except (json.JSONDecodeError, IOError):
            pass

    # Set defaults for missing values
    if not credentials['client_id']:
        credentials['client_id'] = DEFAULT_CLIENT_ID
    if not credentials['redirect_uri']:
        credentials['redirect_uri'] = 'http://colby:5050/auth/callback'

    return credentials


def is_sso_available() -> bool:
    """Check if SSO is properly configured and available."""
    # Check environment variable first
    if os.environ.get('SSO_ENABLED', '').lower() == 'false':
        return False

    credentials = load_oauth_credentials()

    # SSO is available if we have client_id and client_secret
    if credentials.get('client_secret'):
        return True

    # Also check if credentials file exists with valid data
    if SSO_CREDENTIALS_FILE.exists():
        try:
            with open(SSO_CREDENTIALS_FILE) as f:
                all_creds = json.load(f)
                if 'smarthome' in all_creds and all_creds['smarthome'].get('client_secret'):
                    return True
        except (json.JSONDecodeError, IOError):
            pass

    return False


def get_current_sso_user() -> Optional[dict]:
    """Get the current SSO user from session."""
    return session.get('sso_user')


def init_sso(app: Flask) -> None:
    """Initialize SSO authentication for the Flask app."""
    global oauth

    # Only initialize if SSO is available
    if not is_sso_available():
        app.config['SSO_ENABLED'] = False
        return

    from authlib.integrations.flask_client import OAuth

    # Load credentials
    credentials = load_oauth_credentials()

    # Store in app config
    app.config['SSO_ENABLED'] = True
    app.config['AUTHENTIK_CLIENT_ID'] = credentials['client_id']
    app.config['AUTHENTIK_CLIENT_SECRET'] = credentials['client_secret']
    app.config['AUTHENTIK_REDIRECT_URI'] = credentials['redirect_uri']
    app.config['AUTHENTIK_BASE_URL'] = os.environ.get(
        'AUTHENTIK_BASE_URL', DEFAULT_AUTHENTIK_BASE_URL
    )

    # Initialize OAuth
    oauth = OAuth(app)

    # Register Authentik as OAuth provider
    base_url = app.config['AUTHENTIK_BASE_URL']
    oauth.register(
        name='authentik',
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        access_token_url=f'{base_url}/application/o/token/',
        authorize_url=f'{base_url}/application/o/authorize/',
        api_base_url=f'{base_url}/application/o/',
        userinfo_endpoint=f'{base_url}/application/o/userinfo/',
        client_kwargs={
            'scope': 'openid email profile',
        },
        jwks_uri=f'{base_url}/application/o/smarthome-client/jwks/',
    )


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


def get_user_by_id(user_id: int | str) -> User | SSOUser | None:
    """Load user by ID for Flask-Login.

    Handles both local users (integer IDs) and SSO users (string IDs starting with 'sso:').
    """
    # Handle SSO users
    if isinstance(user_id, str):
        if user_id.startswith('sso:'):
            # Load SSO user from session
            sso_user = session.get('sso_user')
            if sso_user and sso_user.get('sub') == user_id[4:]:  # Strip 'sso:' prefix
                return SSOUser(
                    sub=sso_user['sub'],
                    username=sso_user.get('preferred_username', sso_user.get('name', 'SSO User')),
                    email=sso_user.get('email'),
                    name=sso_user.get('name')
                )
            return None
        # Try to parse as integer for local users
        try:
            user_id = int(user_id)
        except ValueError:
            return None

    # Load local user from database
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
        return get_user_by_id(user_id)

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
    sso_available = is_sso_available()

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

    return render_template("auth/login.html", error=error, sso_available=sso_available)


@auth_bp.route("/logout")
@login_required
def logout():
    """Handle user logout."""
    # Clear SSO session data
    session.pop('sso_user', None)
    session.pop('oauth_state', None)
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


# =============================================================================
# SSO Routes
# =============================================================================


@auth_bp.route("/sso/login")
def sso_login():
    """Initiate SSO login flow with Authentik."""
    global oauth

    if not is_sso_available() or oauth is None:
        return redirect(url_for("auth.login"))

    # Generate and store state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    # Store original URL for redirect after login
    next_url = request.args.get('next')
    if next_url:
        session['next'] = next_url

    # Get redirect URI from config
    from flask import current_app
    redirect_uri = current_app.config.get('AUTHENTIK_REDIRECT_URI', 'http://colby:5050/auth/callback')

    # Redirect to Authentik
    return oauth.authentik.authorize_redirect(redirect_uri, state=state)


@auth_bp.route("/callback")
def sso_callback():
    """Handle OAuth callback from Authentik."""
    global oauth

    # Check for errors from Authentik
    error = request.args.get('error')
    if error:
        error_desc = request.args.get('error_description', 'Unknown error')
        return redirect(url_for('auth.login', error=error_desc))

    # Verify state for CSRF protection
    state = request.args.get('state')
    expected_state = session.get('oauth_state')
    if not state or state != expected_state:
        return redirect(url_for('auth.login', error='State validation failed'))

    # Exchange code for token
    if oauth is None:
        return redirect(url_for('auth.login', error='SSO not configured'))

    try:
        token = oauth.authentik.authorize_access_token()
    except Exception as e:
        return redirect(url_for('auth.login', error='Token exchange failed'))

    # Get user info
    try:
        userinfo = token.get('userinfo')
        if not userinfo:
            userinfo = oauth.authentik.userinfo()
    except Exception as e:
        return redirect(url_for('auth.login', error='Failed to get user info'))

    # Store SSO user in session
    session['sso_user'] = {
        'sub': userinfo.get('sub'),
        'name': userinfo.get('name') or userinfo.get('preferred_username'),
        'email': userinfo.get('email'),
        'preferred_username': userinfo.get('preferred_username'),
    }

    # Create SSOUser and log in with Flask-Login
    sso_user = SSOUser(
        sub=userinfo.get('sub'),
        username=userinfo.get('preferred_username') or userinfo.get('name'),
        email=userinfo.get('email'),
        name=userinfo.get('name')
    )
    login_user(sso_user, remember=False)

    # Enable session timeout (WP-10.10: Secure Remote Access)
    # Sessions expire after PERMANENT_SESSION_LIFETIME of inactivity
    session.permanent = True

    # Clear OAuth state
    session.pop('oauth_state', None)

    # Redirect to original URL or home
    next_url = session.pop('next', None) or url_for('index')
    return redirect(next_url)
