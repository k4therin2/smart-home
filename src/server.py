"""
Smart Home Assistant - Web Server

Flask-based web interface for the smart home assistant.
REQ-015: Web UI (Basic)
Phase 2.1: Application Security Baseline
Phase 2.2: HTTPS/TLS Configuration
"""

import os
import secrets
import sqlite3
import threading
from datetime import date

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, Field, ValidationError

from src.config import DATA_DIR, ROOM_ENTITY_MAP
from src.utils import setup_logging, log_command, get_daily_usage
from src.ha_client import get_ha_client
from src.security.auth import auth_bp, setup_login_manager
from src.security.ssl_config import get_ssl_context, certificates_exist

# Initialize logging
logger = setup_logging("server")


# Pydantic models for input validation
class CommandRequest(BaseModel):
    """Validation schema for command API requests."""
    command: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural language command to execute"
    )


# Initialize Flask app
app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

# Security configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour CSRF token expiry

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Initialize Flask-Login
login_manager = setup_login_manager(app)

# Register auth blueprint
app.register_blueprint(auth_bp)


@app.after_request
def add_security_headers(response):
    """
    Add security headers to all responses.

    Security headers implemented:
    - X-Content-Type-Options: Prevents MIME sniffing attacks
    - X-Frame-Options: Prevents clickjacking attacks
    - Referrer-Policy: Controls referrer information leakage
    - X-XSS-Protection: Legacy XSS protection (for older browsers)
    - Content-Security-Policy: Restricts resource loading
    - Strict-Transport-Security: Enforces HTTPS (HSTS)
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )

    # HSTS - only add when running over HTTPS
    if request.is_secure or os.getenv('FLASK_ENV') == 'production':
        # max-age=31536000 (1 year), includeSubDomains for additional security
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    """Handle CSRF validation errors."""
    logger.warning(f"CSRF error from {request.remote_addr}: {error.description}")
    return jsonify({
        "success": False,
        "error": "Invalid or expired security token. Please refresh the page."
    }), 400


@app.errorhandler(429)
def handle_rate_limit_error(error):
    """Handle rate limit exceeded errors."""
    logger.warning(f"Rate limit exceeded for {request.remote_addr}")
    return jsonify({
        "success": False,
        "error": "Too many requests. Please wait a moment before trying again."
    }), 429


def process_command(command: str) -> dict:
    """
    Process a user command through the agent and return the response.

    Args:
        command: User's text command

    Returns:
        Dictionary with response data
    """
    log_command(command, source="web")
    logger.info(f"Processing command: {command}")

    try:
        # Import here to avoid circular imports
        from agent import run_agent

        response_text = run_agent(command)

        return {
            "success": True,
            "response": response_text,
            "command": command
        }
    except Exception as error:
        logger.error(f"Agent error: {error}")
        # In production, don't leak error details to client
        if app.debug:
            error_message = f"Error processing command: {str(error)}"
            error_detail = str(error)
        else:
            error_message = "Error processing command. Please try again."
            error_detail = "Internal server error"

        return {
            "success": False,
            "response": error_message,
            "command": command,
            "error": error_detail
        }


@app.route("/")
@login_required
def index():
    """Render the main web interface."""
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt  # API uses token in header instead
def handle_command():
    """
    Handle incoming commands from the web interface.

    Expects JSON: {"command": "user command text"}
    Returns JSON: {"success": bool, "response": str, ...}

    Rate limited to 10 requests per minute per IP.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body must be JSON"
            }), 400

        # Validate with Pydantic
        try:
            validated = CommandRequest(**data)
        except ValidationError as validation_error:
            errors = validation_error.errors()
            error_msg = errors[0].get('msg', 'Invalid input') if errors else 'Invalid input'
            return jsonify({
                "success": False,
                "error": error_msg
            }), 400

        command = validated.command.strip()

        if not command:
            return jsonify({
                "success": False,
                "error": "Command cannot be empty"
            }), 400

        result = process_command(command)
        return jsonify(result)

    except Exception as error:
        logger.error(f"Error processing command: {error}")
        # In production, don't leak error details to client
        error_detail = str(error) if app.debug else "Internal server error"
        return jsonify({
            "success": False,
            "error": error_detail
        }), 500


@app.route("/api/status")
@login_required
@limiter.limit("30 per minute")
def get_status():
    """
    Return system status for the dashboard including connected devices.
    """
    try:
        ha_client = get_ha_client()
        ha_connected = ha_client.check_connection()

        devices = []
        system_status = "operational"

        if ha_connected:
            # Get light states from configured rooms
            for room_name, room_config in ROOM_ENTITY_MAP.items():
                entity_id = room_config.get("default_light")
                if entity_id:
                    state = ha_client.get_light_state(entity_id)
                    if state:
                        devices.append({
                            "entity_id": entity_id,
                            "name": state.get("friendly_name", room_name.replace("_", " ").title()),
                            "type": "light",
                            "state": state.get("state", "unknown"),
                            "brightness": state.get("brightness"),
                            "room": room_name
                        })
        else:
            system_status = "warning"

        daily_cost = get_daily_usage()

        return jsonify({
            "system": system_status,
            "agent": "ready",
            "home_assistant": "connected" if ha_connected else "disconnected",
            "daily_cost_usd": round(daily_cost, 4),
            "devices": devices
        })

    except Exception as error:
        logger.error(f"Status check error: {error}")
        # In production, don't leak error details to client
        error_detail = str(error) if app.debug else "Status check failed"
        return jsonify({
            "system": "error",
            "agent": "error",
            "home_assistant": "error",
            "error": error_detail,
            "devices": []
        })


@app.route("/api/history")
@login_required
@limiter.limit("30 per minute")
def get_history():
    """
    Return recent command history from the usage database.
    """
    try:
        usage_db = DATA_DIR / "usage.db"

        if not usage_db.exists():
            return jsonify({"history": []})

        with sqlite3.connect(usage_db) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT command, timestamp
                FROM api_usage
                WHERE command IS NOT NULL AND command != ''
                ORDER BY timestamp DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()

            history = [
                {"command": row[0], "timestamp": row[1]}
                for row in rows
                if row[0]  # Filter out any null/empty
            ]

        return jsonify({"history": history})

    except Exception as error:
        logger.error(f"History fetch error: {error}")
        # In production, don't leak error details to client
        error_detail = str(error) if app.debug else "History fetch failed"
        return jsonify({"history": [], "error": error_detail})


@app.route("/api/csrf-token")
@login_required
def get_csrf_token():
    """Return a CSRF token for API clients."""
    from flask_wtf.csrf import generate_csrf
    return jsonify({"csrf_token": generate_csrf()})


def create_redirect_app(https_port: int = 5050):
    """
    Create a simple Flask app that redirects HTTP to HTTPS.

    Args:
        https_port: The HTTPS port to redirect to

    Returns:
        Flask app for HTTP->HTTPS redirection
    """
    redirect_app = Flask(__name__)

    @redirect_app.before_request
    def redirect_to_https():
        if request.is_secure:
            return None

        url = request.url.replace("http://", "https://", 1)
        # Update port in URL if needed
        if f":{https_port - 1}" in url:
            url = url.replace(f":{https_port - 1}", f":{https_port}")
        elif ":" not in url.split("/")[2]:
            # No port specified, add HTTPS port
            parts = url.split("/")
            parts[2] = f"{parts[2]}:{https_port}"
            url = "/".join(parts)

        return redirect(url, code=301)

    return redirect_app


def run_http_redirect_server(host: str, http_port: int, https_port: int):
    """
    Run HTTP redirect server in a background thread.

    Args:
        host: Host to bind to
        http_port: HTTP port (typically 5049 or 80)
        https_port: HTTPS port to redirect to
    """
    redirect_app = create_redirect_app(https_port)
    logger.info(f"Starting HTTP redirect server on {host}:{http_port} -> HTTPS:{https_port}")

    # Run without debug and with threading
    redirect_app.run(host=host, port=http_port, debug=False, threaded=True)


def run_server(
    host: str = "0.0.0.0",
    port: int = 5050,
    debug: bool = False,
    use_https: bool = True,
    http_redirect: bool = True
):
    """
    Run the Flask server with optional HTTPS support.

    Args:
        host: Host to bind to
        port: Port number (HTTPS port if use_https=True)
        debug: Enable debug mode
        use_https: Enable HTTPS if certificates exist
        http_redirect: Start HTTP redirect server (only when using HTTPS)
    """
    ssl_context = None

    if use_https and certificates_exist():
        ssl_context = get_ssl_context()
        logger.info(f"HTTPS enabled with SSL certificates")

        # Start HTTP redirect server on port-1 (e.g., 5049 -> 5050)
        if http_redirect and not debug:
            http_port = port - 1
            redirect_thread = threading.Thread(
                target=run_http_redirect_server,
                args=(host, http_port, port),
                daemon=True
            )
            redirect_thread.start()
            logger.info(f"HTTP redirect: http://{host}:{http_port} -> https://{host}:{port}")
    elif use_https:
        logger.warning("HTTPS requested but no certificates found. Run: python scripts/generate_cert.py")
        logger.info("Falling back to HTTP")

    if ssl_context:
        logger.info(f"Starting HTTPS server on {host}:{port}")
        app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)
    else:
        logger.info(f"Starting HTTP server on {host}:{port}")
        app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    # Read configuration from environment variables
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    use_https = os.getenv("USE_HTTPS", "True").lower() == "true"
    http_redirect = os.getenv("HTTP_REDIRECT", "True").lower() == "true"

    run_server(debug=debug, use_https=use_https, http_redirect=http_redirect)
