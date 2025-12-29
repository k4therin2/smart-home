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
from datetime import date, datetime

from flask import Flask, jsonify, redirect, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError, CSRFProtect
from pydantic import BaseModel, Field, ValidationError

from src.config import DATA_DIR, ROOM_ENTITY_MAP
from src.ha_client import get_ha_client
from src.health_monitor import get_health_monitor
from src.security.auth import auth_bp, setup_login_manager
from src.security.ssl_config import certificates_exist, get_ssl_context
from src.self_healer import get_self_healer
from src.utils import get_daily_usage, log_command, setup_logging
from src.voice_handler import VoiceHandler
from src.voice_response import ResponseFormatter


# Initialize logging
logger = setup_logging("server")


# Pydantic models for input validation
class CommandRequest(BaseModel):
    """Validation schema for command API requests."""

    command: str = Field(
        min_length=1, max_length=1000, description="Natural language command to execute"
    )


class VoiceCommandRequest(BaseModel):
    """Validation schema for voice command API requests (HA format)."""

    text: str = Field(min_length=1, max_length=1000, description="Voice command text from STT")
    language: str = Field(default="en", description="Language code")
    conversation_id: str = Field(default=None, description="HA conversation ID")
    device_id: str = Field(default=None, description="Source voice device ID")


# Initialize Flask app
app = Flask(__name__, template_folder="../templates", static_folder="../static")

# Security configuration
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1 hour CSRF token expiry

# Performance optimization: use minified assets in production
# Set USE_MINIFIED_ASSETS=true or FLASK_ENV=production to enable
app.config["USE_MINIFIED_ASSETS"] = os.getenv("USE_MINIFIED_ASSETS", "false").lower() == "true"

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
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )

    # HSTS - only add when running over HTTPS
    if request.is_secure or os.getenv("FLASK_ENV") == "production":
        # max-age=31536000 (1 year), includeSubDomains for additional security
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    """Handle CSRF validation errors."""
    logger.warning(f"CSRF error from {request.remote_addr}: {error.description}")
    return jsonify(
        {"success": False, "error": "Invalid or expired security token. Please refresh the page."}
    ), 400


@app.errorhandler(429)
def handle_rate_limit_error(error):
    """Handle rate limit exceeded errors."""
    logger.warning(f"Rate limit exceeded for {request.remote_addr}")
    return jsonify(
        {"success": False, "error": "Too many requests. Please wait a moment before trying again."}
    ), 429


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

        return {"success": True, "response": response_text, "command": command}
    except Exception as error:
        logger.error(f"Agent error: {error}")
        # In production, don't leak error details to client
        if app.debug:
            error_message = f"Error processing command: {error!s}"
            error_detail = str(error)
        else:
            error_message = "Error processing command. Please try again."
            error_detail = "Internal server error"

        return {
            "success": False,
            "response": error_message,
            "command": command,
            "error": error_detail,
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
            return jsonify({"success": False, "error": "Request body must be JSON"}), 400

        # Validate with Pydantic
        try:
            validated = CommandRequest(**data)
        except ValidationError as validation_error:
            errors = validation_error.errors()
            error_msg = errors[0].get("msg", "Invalid input") if errors else "Invalid input"
            return jsonify({"success": False, "error": error_msg}), 400

        command = validated.command.strip()

        if not command:
            return jsonify({"success": False, "error": "Command cannot be empty"}), 400

        result = process_command(command)
        return jsonify(result)

    except Exception as error:
        logger.error(f"Error processing command: {error}")
        # In production, don't leak error details to client
        error_detail = str(error) if app.debug else "Internal server error"
        return jsonify({"success": False, "error": error_detail}), 500


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
                        devices.append(
                            {
                                "entity_id": entity_id,
                                "name": state.get(
                                    "friendly_name", room_name.replace("_", " ").title()
                                ),
                                "type": "light",
                                "state": state.get("state", "unknown"),
                                "brightness": state.get("brightness"),
                                "room": room_name,
                            }
                        )
        else:
            system_status = "warning"

        daily_cost = get_daily_usage()

        return jsonify(
            {
                "system": system_status,
                "agent": "ready",
                "home_assistant": "connected" if ha_connected else "disconnected",
                "daily_cost_usd": round(daily_cost, 4),
                "devices": devices,
            }
        )

    except Exception as error:
        logger.error(f"Status check error: {error}")
        # In production, don't leak error details to client
        error_detail = str(error) if app.debug else "Status check failed"
        return jsonify(
            {
                "system": "error",
                "agent": "error",
                "home_assistant": "error",
                "error": error_detail,
                "devices": [],
            }
        )


@app.route("/api/health")
@login_required
@limiter.limit("30 per minute")
def get_health():
    """
    Return comprehensive system health status.

    REQ-021: Self-Monitoring & Self-Healing
    Provides detailed health status for all system components including:
    - Home Assistant connectivity
    - Cache performance
    - Database health
    - Anthropic API usage

    Also triggers automatic healing actions for degraded components.
    """
    try:
        health_monitor = get_health_monitor()
        self_healer = get_self_healer()

        # Get system health
        health_data = health_monitor.get_system_health()

        # Attempt healing for any unhealthy/degraded components
        healing_results = []
        for component in health_data["components"]:
            if component["status"] in ["degraded", "unhealthy"]:
                from src.health_monitor import ComponentHealth, HealthStatus

                # Recreate ComponentHealth from dict for healer
                status_map = {
                    "healthy": HealthStatus.HEALTHY,
                    "degraded": HealthStatus.DEGRADED,
                    "unhealthy": HealthStatus.UNHEALTHY,
                }
                component_health = ComponentHealth(
                    name=component["name"],
                    status=status_map[component["status"]],
                    message=component["message"],
                    last_check=health_data["timestamp"],
                    details=component.get("details", {}),
                )

                result = self_healer.attempt_healing(component["name"], component_health)
                if result["attempted"]:
                    healing_results.append(
                        {
                            "component": component["name"],
                            "success": result["success"],
                            "actions": result.get("actions", []),
                        }
                    )

        return jsonify(
            {
                **health_data,
                "healing_attempted": len(healing_results) > 0,
                "healing_results": healing_results,
            }
        )

    except Exception as error:
        logger.error(f"Health check error: {error}")
        error_detail = str(error) if app.debug else "Health check failed"
        return jsonify(
            {
                "status": "error",
                "error": error_detail,
                "components": [],
            }
        ), 500


@app.route("/api/health/history")
@login_required
@limiter.limit("10 per minute")
def get_health_history():
    """
    Return health check history for trending and analysis.
    """
    try:
        health_monitor = get_health_monitor()
        component = request.args.get("component")
        limit = min(int(request.args.get("limit", 50)), 100)

        if component:
            history = health_monitor.get_health_history(component, limit=limit)
        else:
            # Get history for all components (including llm_provider from WP-10.21)
            history = {}
            for comp in ["home_assistant", "cache", "database", "anthropic_api", "llm_provider"]:
                history[comp] = health_monitor.get_health_history(comp, limit=limit)

        return jsonify({"history": history})

    except Exception as error:
        logger.error(f"Health history error: {error}")
        return jsonify({"error": str(error)}), 500


@app.route("/api/health/healing")
@login_required
@limiter.limit("10 per minute")
def get_healing_history():
    """
    Return self-healing action history.
    """
    try:
        self_healer = get_self_healer()
        component = request.args.get("component")
        limit = min(int(request.args.get("limit", 50)), 100)

        history = self_healer.get_healing_history(component=component, limit=limit)

        return jsonify({"healing_history": history})

    except Exception as error:
        logger.error(f"Healing history error: {error}")
        return jsonify({"error": str(error)}), 500


# ========== WP-10.21: Kubernetes-style Health Probes ==========


@app.route("/healthz")
@limiter.limit("60 per minute")
def healthz():
    """
    Liveness probe endpoint (WP-10.21).

    Kubernetes-style liveness check. Returns 200 if the process is alive.
    Does NOT require authentication - this is intentional for k8s probes.

    Returns:
        200: Process is alive and can respond
        503: Process is not responding (should be restarted)
    """
    try:
        health_monitor = get_health_monitor()
        liveness = health_monitor.get_liveness()

        return jsonify(liveness), 200

    except Exception as error:
        logger.error(f"Liveness check failed: {error}")
        return jsonify({"status": "error", "error": str(error)}), 503


@app.route("/readyz")
@limiter.limit("30 per minute")
def readyz():
    """
    Readiness probe endpoint (WP-10.21).

    Kubernetes-style readiness check. Returns 200 if all critical dependencies
    are healthy and the service can accept traffic.
    Does NOT require authentication - this is intentional for k8s probes.

    Returns:
        200: All dependencies healthy, can accept traffic
        503: One or more dependencies unhealthy, should not receive traffic
    """
    try:
        health_monitor = get_health_monitor()
        readiness = health_monitor.get_readiness()

        if readiness["ready"]:
            return jsonify(readiness), 200
        else:
            return jsonify(readiness), 503

    except Exception as error:
        logger.error(f"Readiness check failed: {error}")
        return jsonify({"ready": False, "error": str(error)}), 503


@app.route("/api/health/trigger/<component>", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def trigger_healing(component: str):
    """
    Manually trigger healing for a component (WP-10.21).

    POST /api/health/trigger/home_assistant

    Args:
        component: Name of the component to heal

    Returns:
        Healing result with success status
    """
    try:
        health_monitor = get_health_monitor()
        self_healer = get_self_healer()

        # Set the healer on the health monitor
        health_monitor.set_healer(self_healer)

        result = health_monitor.trigger_healing(component)

        return jsonify(result)

    except Exception as error:
        logger.error(f"Manual healing trigger error: {error}")
        return jsonify({
            "attempted": False,
            "success": False,
            "error": str(error)
        }), 500


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


# =============================================================================
# Voice Pipeline Diagnostics Routes (WP-9.2: Christmas Gift 2025)
# =============================================================================


@app.route("/diagnostics")
@login_required
def diagnostics_page():
    """
    Render the voice pipeline diagnostics dashboard.

    WP-9.2: Voice Pipeline Diagnostic Suite (Christmas Gift 2025)
    Addresses: BUG-001 (Voice Puck not responding)
    """
    return render_template("diagnostics.html")


@app.route("/api/diagnostics/voice", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@csrf.exempt  # Diagnostics page uses JS fetch
def run_voice_diagnostics():
    """
    Run the full voice pipeline diagnostic suite.

    WP-9.2: Voice Pipeline Diagnostic Suite
    Tests the entire voice pipeline from puck to TTS response:
    1. Voice Puck connectivity
    2. HA Assist pipeline configuration
    3. SmartHome webhook reachability
    4. SmartHome voice endpoint functionality
    5. TTS output verification

    Returns:
        JSON with diagnostic results and fix suggestions
    """
    try:
        from src.voice_diagnostics import VoicePipelineDiagnostics

        diagnostics = VoicePipelineDiagnostics()
        summary = diagnostics.run_all_diagnostics()
        result = diagnostics.to_dict(summary)

        logger.info(
            f"Voice diagnostics complete: {result['summary']['passed']} passed, "
            f"{result['summary']['failed']} failed, {result['summary']['warnings']} warnings"
        )

        return jsonify(result)

    except Exception as error:
        logger.error(f"Voice diagnostics error: {error}")
        error_detail = str(error) if app.debug else "Diagnostics failed"
        return jsonify(
            {
                "overall_status": "failed",
                "error": error_detail,
                "summary": {"passed": 0, "failed": 1, "warnings": 0, "total": 1},
                "results": [
                    {
                        "name": "Diagnostic Suite",
                        "status": "failed",
                        "message": error_detail,
                        "details": {"exception": str(error)},
                        "fix_suggestions": [
                            "Check server logs for detailed error",
                            "Verify all dependencies are installed",
                            "Ensure Home Assistant is reachable",
                        ],
                        "duration_ms": 0,
                    }
                ],
            }
        ), 500


# =============================================================================
# Voice Command Routes (REQ-016: Voice Control via HA Voice Puck)
# =============================================================================


def _verify_webhook_token() -> bool:
    """
    Verify Bearer token for webhook authentication.

    Returns:
        True if token is valid or no token is configured, False otherwise
    """
    webhook_token = os.getenv("VOICE_WEBHOOK_TOKEN")
    if not webhook_token:
        # No token configured - rely on session auth
        return True

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        provided_token = auth_header[7:]
        return secrets.compare_digest(provided_token, webhook_token)

    return False


def _get_voice_handler() -> VoiceHandler:
    """
    Get or create VoiceHandler instance with agent callback.

    Returns:
        Configured VoiceHandler instance
    """
    from agent import run_agent

    return VoiceHandler(agent_callback=run_agent)


@app.route("/api/voice_command", methods=["POST"])
@limiter.limit("20 per minute")
@csrf.exempt  # Webhook uses token auth instead
def handle_voice_command():
    """
    Handle voice commands from Home Assistant conversation agent webhook.

    Expects JSON: {"text": "voice command text", "language": "en", ...}
    Returns JSON: {"success": bool, "response": str}

    Authentication: Either session auth OR Bearer token from VOICE_WEBHOOK_TOKEN env var.
    Rate limited to 20 requests per minute per IP.
    """
    # Check authentication (session or webhook token)
    if not current_user.is_authenticated:
        if not _verify_webhook_token():
            logger.warning(f"Unauthorized voice command from {request.remote_addr}")
            return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body must be JSON"}), 400

        # Validate with Pydantic
        try:
            validated = VoiceCommandRequest(**data)
        except ValidationError as validation_error:
            errors = validation_error.errors()
            error_msg = errors[0].get("msg", "Invalid input") if errors else "Invalid input"
            return jsonify({"success": False, "error": error_msg}), 400

        text = validated.text.strip()

        if not text:
            return jsonify({"success": False, "error": "Voice command text cannot be empty"}), 400

        # Build context from validated data
        context = {}
        if validated.device_id:
            context["device_id"] = validated.device_id
        if validated.language:
            context["language"] = validated.language
        if validated.conversation_id:
            context["conversation_id"] = validated.conversation_id

        # Process through voice handler
        handler = _get_voice_handler()
        result = handler.process_command(text, context)

        log_command(text, source="voice")
        return jsonify(result)

    except Exception as error:
        logger.error(f"Voice command error: {error}")
        formatter = ResponseFormatter()
        return jsonify({"success": False, "error": formatter.error(str(error))}), 500


# =============================================================================
# PWA Routes (REQ-017: Mobile-Optimized Web Interface)
# =============================================================================


@app.route("/manifest.json")
def serve_manifest():
    """
    Serve PWA manifest file.

    Required for "Add to Home Screen" and PWA installation.
    """
    return app.send_static_file("manifest.json")


@app.route("/sw.js")
def serve_service_worker():
    """
    Serve service worker from root scope.

    Service workers must be served from root to control the entire app.
    Sets appropriate headers for service worker registration.
    Uses minified version in production for performance.
    """
    # Use minified version in production
    if app.config.get("USE_MINIFIED_ASSETS") or os.getenv("FLASK_ENV") == "production":
        sw_path = "build/sw.min.js"
    else:
        sw_path = "sw.js"

    response = app.send_static_file(sw_path)
    response.headers["Content-Type"] = "application/javascript"
    response.headers["Service-Worker-Allowed"] = "/"
    # Prevent caching of service worker to ensure updates propagate
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.route("/api/notifications/subscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt
def subscribe_notifications():
    """
    Handle push notification subscription.

    Stores the push subscription endpoint for later notification delivery.
    Currently a placeholder - full implementation requires web-push library.
    """
    try:
        data = request.get_json()

        if not data or "endpoint" not in data:
            return jsonify({"success": False, "error": "Missing subscription endpoint"}), 400

        # Log the subscription (full implementation would store in database)
        logger.info(f"Notification subscription received: {data.get('endpoint', '')[:50]}...")

        return jsonify({"success": True, "message": "Subscription registered"}), 201

    except Exception as error:
        logger.error(f"Notification subscription error: {error}")
        return jsonify({"success": False, "error": "Subscription failed"}), 500


# =============================================================================
# TODO LIST & REMINDERS API ENDPOINTS (WP-4.1)
# =============================================================================


@app.route("/api/todos", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_todos():
    """
    Get todos from a list.

    Query params:
    - list_name: Name of the list (default: 'default')
    - show_completed: Include completed items (default: false)

    Returns JSON with todos array.
    """
    from src.todo_manager import get_todo_manager

    try:
        list_name = request.args.get("list_name", "default")
        show_completed = request.args.get("show_completed", "false").lower() == "true"

        manager = get_todo_manager()
        todos = manager.get_todos(list_name=list_name, include_completed=show_completed)

        return jsonify(
            {"success": True, "todos": todos, "count": len(todos), "list_name": list_name}
        )

    except Exception as error:
        logger.error(f"Error getting todos: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error fetching todos"}
        ), 500


@app.route("/api/todos", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@csrf.exempt
def add_todo():
    """
    Add a new todo item.

    Expects JSON: {"content": "...", "list_name": "...", "priority": "normal|high|urgent"}
    """
    from src.todo_manager import get_todo_manager

    try:
        data = request.get_json()

        if not data or not data.get("content"):
            return jsonify({"success": False, "error": "Content is required"}), 400

        content = data.get("content", "").strip()
        list_name = data.get("list_name", "default")
        priority_str = data.get("priority", "normal")

        priority_map = {"normal": 0, "high": 1, "urgent": 2}
        priority = priority_map.get(priority_str.lower(), 0)

        manager = get_todo_manager()
        todo_id = manager.add_todo(content=content, list_name=list_name, priority=priority)

        return jsonify(
            {"success": True, "todo_id": todo_id, "content": content, "list_name": list_name}
        ), 201

    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400

    except Exception as error:
        logger.error(f"Error adding todo: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error adding todo"}
        ), 500


@app.route("/api/todos/<int:todo_id>/complete", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@csrf.exempt
def complete_todo(todo_id):
    """Mark a todo as completed."""
    from src.todo_manager import get_todo_manager

    try:
        manager = get_todo_manager()
        success = manager.complete_todo(todo_id)

        if success:
            return jsonify({"success": True, "message": f"Todo {todo_id} marked complete"})
        else:
            return jsonify({"success": False, "error": "Todo not found"}), 404

    except Exception as error:
        logger.error(f"Error completing todo: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error completing todo"}
        ), 500


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
@login_required
@limiter.limit("20 per minute")
@csrf.exempt
def delete_todo(todo_id):
    """Delete a todo item."""
    from src.todo_manager import get_todo_manager

    try:
        manager = get_todo_manager()
        success = manager.delete_todo(todo_id)

        if success:
            return jsonify({"success": True, "message": f"Todo {todo_id} deleted"})
        else:
            return jsonify({"success": False, "error": "Todo not found"}), 404

    except Exception as error:
        logger.error(f"Error deleting todo: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error deleting todo"}
        ), 500


@app.route("/api/lists", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_todo_lists():
    """Get all todo lists with item counts."""
    from src.todo_manager import get_todo_manager

    try:
        manager = get_todo_manager()
        lists = manager.get_lists()

        return jsonify({"success": True, "lists": lists})

    except Exception as error:
        logger.error(f"Error getting lists: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error fetching lists"}
        ), 500


@app.route("/api/reminders", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_reminders():
    """Get pending reminders."""
    from src.reminder_manager import get_reminder_manager

    try:
        manager = get_reminder_manager()
        reminders = manager.get_pending_reminders()

        return jsonify({"success": True, "reminders": reminders, "count": len(reminders)})

    except Exception as error:
        logger.error(f"Error getting reminders: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error fetching reminders"}
        ), 500


@app.route("/api/reminders/<int:reminder_id>/dismiss", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@csrf.exempt
def dismiss_reminder(reminder_id):
    """Dismiss a reminder."""
    from src.reminder_manager import get_reminder_manager

    try:
        manager = get_reminder_manager()
        success = manager.dismiss_reminder(reminder_id)

        if success:
            return jsonify({"success": True, "message": f"Reminder {reminder_id} dismissed"})
        else:
            return jsonify({"success": False, "error": "Reminder not found"}), 404

    except Exception as error:
        logger.error(f"Error dismissing reminder: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error dismissing reminder"}
        ), 500


# =============================================================================
# AUTOMATION API ENDPOINTS (WP-4.2: Simple Automation Creation)
# =============================================================================


@app.route("/api/automations", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_automations():
    """
    Get all automations.

    Query params:
    - enabled_only: Only return enabled automations (default: false)
    - trigger_type: Filter by trigger type ('time' or 'state')

    Returns JSON with automations array.
    """
    from src.automation_manager import get_automation_manager

    try:
        enabled_only = request.args.get("enabled_only", "false").lower() == "true"
        trigger_type = request.args.get("trigger_type")

        manager = get_automation_manager()
        automations = manager.get_automations(enabled_only=enabled_only, trigger_type=trigger_type)
        stats = manager.get_stats()

        return jsonify(
            {"success": True, "automations": automations, "count": len(automations), "stats": stats}
        )

    except Exception as error:
        logger.error(f"Error getting automations: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error fetching automations"}
        ), 500


@app.route("/api/automations", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt
def create_automation():
    """
    Create a new automation.

    Request JSON:
    {
        "name": "string",
        "trigger_type": "time" | "state",
        "trigger_config": {...},
        "action_type": "agent_command" | "ha_service",
        "action_config": {...},
        "description": "string" (optional)
    }
    """
    from src.automation_manager import get_automation_manager

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        required = ["name", "trigger_type", "trigger_config", "action_type", "action_config"]
        for field in required:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400

        manager = get_automation_manager()
        automation_id = manager.create_automation(
            name=data["name"],
            trigger_type=data["trigger_type"],
            trigger_config=data["trigger_config"],
            action_type=data["action_type"],
            action_config=data["action_config"],
            description=data.get("description"),
        )

        return jsonify(
            {
                "success": True,
                "automation_id": automation_id,
                "message": f"Created automation '{data['name']}'",
            }
        ), 201

    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400

    except Exception as error:
        logger.error(f"Error creating automation: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error creating automation"}
        ), 500


@app.route("/api/automations/<int:automation_id>", methods=["PUT"])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt
def update_automation(automation_id: int):
    """
    Update an existing automation.

    Request JSON can include: name, description, trigger_config, action_config, enabled
    """
    from src.automation_manager import get_automation_manager

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        manager = get_automation_manager()
        success = manager.update_automation(automation_id, **data)

        if success:
            return jsonify({"success": True, "message": "Automation updated"})
        else:
            return jsonify({"success": False, "error": "Automation not found"}), 404

    except Exception as error:
        logger.error(f"Error updating automation: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error updating automation"}
        ), 500


@app.route("/api/automations/<int:automation_id>", methods=["DELETE"])
@login_required
@limiter.limit("10 per minute")
@csrf.exempt
def delete_automation(automation_id: int):
    """Delete an automation by ID."""
    from src.automation_manager import get_automation_manager

    try:
        manager = get_automation_manager()
        success = manager.delete_automation(automation_id)

        if success:
            return jsonify({"success": True, "message": "Automation deleted"})
        else:
            return jsonify({"success": False, "error": "Automation not found"}), 404

    except Exception as error:
        logger.error(f"Error deleting automation: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error deleting automation"}
        ), 500


@app.route("/api/automations/<int:automation_id>/toggle", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@csrf.exempt
def toggle_automation(automation_id: int):
    """Toggle automation enabled/disabled state."""
    from src.automation_manager import get_automation_manager

    try:
        manager = get_automation_manager()

        # Get current state first
        automation = manager.get_automation(automation_id)
        if not automation:
            return jsonify({"success": False, "error": "Automation not found"}), 404

        success = manager.toggle_automation(automation_id)

        if success:
            new_state = "disabled" if automation["enabled"] else "enabled"
            return jsonify(
                {
                    "success": True,
                    "message": f"Automation {new_state}",
                    "enabled": not automation["enabled"],
                }
            )
        else:
            return jsonify({"success": False, "error": "Failed to toggle automation"}), 500

    except Exception as error:
        logger.error(f"Error toggling automation: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error toggling automation"}
        ), 500


# =============================================================================
# LOGS API ENDPOINTS (WP-6.1: Log Viewer UI)
# =============================================================================


@app.route("/api/logs/files", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_log_files():
    """
    List available log files.

    Query params:
    - type: Filter by log type ('main', 'error', 'api') or None for all

    Returns JSON with list of log files and their metadata.
    """
    from src.log_reader import LogReader

    try:
        log_type = request.args.get("type")

        reader = LogReader()
        files = reader.list_log_files(log_type=log_type)

        file_list = []
        for log_file in files:
            stat = log_file.stat()
            file_list.append(
                {
                    "name": log_file.name,
                    "path": str(log_file),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return jsonify(
            {
                "success": True,
                "files": file_list,
                "count": len(file_list),
            }
        )

    except Exception as error:
        logger.error(f"Error listing log files: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error listing log files"}
        ), 500


@app.route("/api/logs", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_logs():
    """
    Read and filter log entries.

    Query params:
    - log_type: Type of log ('main', 'error', 'api')
    - offset: Number of entries to skip (default: 0)
    - limit: Max entries to return (default: 100, max: 1000)
    - reverse: Return entries newest first (default: true)
    - min_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - levels: Comma-separated specific levels to include
    - start_time: Filter entries after this ISO datetime
    - end_time: Filter entries before this ISO datetime
    - module: Exact module name to filter
    - search: Text to search in log messages

    Returns JSON with log entries and statistics.
    """
    from src.log_reader import LogLevel, LogReader

    try:
        reader = LogReader()

        # Get log file
        log_type = request.args.get("log_type")
        log_files = reader.list_log_files(log_type=log_type)
        if not log_files:
            return jsonify(
                {
                    "success": True,
                    "entries": [],
                    "total": 0,
                    "stats": {},
                }
            )

        file_path = log_files[0]

        # Pagination
        offset = max(0, int(request.args.get("offset", 0)))
        limit = min(1000, max(1, int(request.args.get("limit", 100))))

        # Ordering
        reverse = request.args.get("reverse", "true").lower() == "true"

        # Level filtering
        min_level = None
        min_level_str = request.args.get("min_level")
        if min_level_str:
            min_level = LogLevel.from_string(min_level_str)

        levels = None
        levels_str = request.args.get("levels")
        if levels_str:
            levels = [LogLevel.from_string(lvl.strip()) for lvl in levels_str.split(",")]
            levels = [lvl for lvl in levels if lvl is not None]

        # Time filtering
        start_time = None
        start_time_str = request.args.get("start_time")
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except ValueError:
                pass  # Ignore invalid date

        end_time = None
        end_time_str = request.args.get("end_time")
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str)
            except ValueError:
                pass  # Ignore invalid date

        # Module and search filtering
        module = request.args.get("module")
        search = request.args.get("search")

        # Read entries
        entries = reader.read(
            file_path=file_path,
            offset=offset,
            limit=limit,
            reverse=reverse,
            min_level=min_level,
            levels=levels,
            start_time=start_time,
            end_time=end_time,
            module=module,
            search=search,
        )

        # Get stats
        stats = reader.get_stats(file_path=file_path)
        # Convert datetime objects for JSON
        if stats.get("first_entry"):
            stats["first_entry"] = stats["first_entry"].isoformat()
        if stats.get("last_entry"):
            stats["last_entry"] = stats["last_entry"].isoformat()

        return jsonify(
            {
                "success": True,
                "entries": [entry.to_dict() for entry in entries],
                "total": stats["total_entries"],
                "stats": stats,
            }
        )

    except Exception as error:
        logger.error(f"Error reading logs: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error reading logs"}
        ), 500


@app.route("/api/logs/export", methods=["GET"])
@login_required
@limiter.limit("10 per minute")
def export_logs():
    """
    Export log entries in JSON or text format.

    Query params:
    - format: Export format ('json' or 'text', default: 'json')
    - download: If 'true', set Content-Disposition for download
    - (All filter params from /api/logs also supported)

    Returns log data in requested format.
    """
    from flask import Response

    from src.log_reader import LogLevel, LogReader

    try:
        reader = LogReader()

        # Get log file
        log_type = request.args.get("log_type")
        log_files = reader.list_log_files(log_type=log_type)
        if not log_files:
            return jsonify({"entries": [], "stats": {}})

        file_path = log_files[0]

        # Format
        export_format = request.args.get("format", "json")
        download = request.args.get("download", "false").lower() == "true"

        # Level filtering for export
        min_level = None
        min_level_str = request.args.get("min_level")
        if min_level_str:
            min_level = LogLevel.from_string(min_level_str)

        # Export
        output = reader.export(
            file_path=file_path,
            format=export_format,
            min_level=min_level,
        )

        # Set response type
        if export_format == "json":
            content_type = "application/json"
            filename = f"logs_{date.today().isoformat()}.json"
        else:
            content_type = "text/plain"
            filename = f"logs_{date.today().isoformat()}.log"

        response = Response(output, mimetype=content_type)

        if download:
            response.headers["Content-Disposition"] = f"attachment; filename={filename}"

        return response

    except Exception as error:
        logger.error(f"Error exporting logs: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error exporting logs"}
        ), 500


@app.route("/api/logs/tail", methods=["GET"])
@login_required
@limiter.limit("60 per minute")
def tail_logs():
    """
    Get the latest log entries (tail functionality).

    Query params:
    - lines: Number of lines to return (default: 50, max: 500)
    - from_position: File position to read from (for follow mode)

    Returns JSON with entries and current file position for follow-up requests.
    """
    from src.log_reader import LogReader

    try:
        reader = LogReader()

        # Get main log file
        log_files = reader.list_log_files(log_type="main")
        if not log_files:
            return jsonify(
                {
                    "success": True,
                    "entries": [],
                    "position": 0,
                }
            )

        file_path = log_files[0]

        lines = min(500, max(1, int(request.args.get("lines", 50))))
        from_position = request.args.get("from_position")

        if from_position:
            # Follow mode - read from position
            position = int(from_position)
            entries = reader.read_from_position(file_path=file_path, position=position)
            new_position = file_path.stat().st_size
        else:
            # Initial tail
            entries, new_position = reader.tail_with_position(file_path=file_path, lines=lines)

        return jsonify(
            {
                "success": True,
                "entries": [entry.to_dict() for entry in entries],
                "position": new_position,
            }
        )

    except Exception as error:
        logger.error(f"Error tailing logs: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error tailing logs"}
        ), 500


@app.route("/api/logs/stats", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_log_stats():
    """
    Get statistics for log files.

    Query params:
    - log_type: Type of log ('main', 'error', 'api')

    Returns JSON with log statistics.
    """
    from src.log_reader import LogReader

    try:
        reader = LogReader()

        log_type = request.args.get("log_type")
        log_files = reader.list_log_files(log_type=log_type)
        if not log_files:
            return jsonify(
                {
                    "success": True,
                    "total_entries": 0,
                    "level_counts": {},
                }
            )

        file_path = log_files[0]
        stats = reader.get_stats(file_path=file_path)

        # Convert datetime for JSON
        if stats.get("first_entry"):
            stats["first_entry"] = stats["first_entry"].isoformat()
        if stats.get("last_entry"):
            stats["last_entry"] = stats["last_entry"].isoformat()

        return jsonify(
            {
                "success": True,
                **stats,
            }
        )

    except Exception as error:
        logger.error(f"Error getting log stats: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error getting log stats"}
        ), 500


def is_tailscale_ip(ip: str) -> bool:
    """Check if IP is from Tailscale (100.x.x.x range)."""
    if not ip:
        return False
    return ip.startswith("100.")


def create_redirect_app(https_port: int = 5050):
    """
    Create a simple Flask app that redirects HTTP to HTTPS.
    Tailscale IPs (100.x.x.x) are NOT redirected - they can use HTTP directly.

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

        # Don't redirect Tailscale IPs - they can use HTTP
        client_ip = request.remote_addr
        if is_tailscale_ip(client_ip):
            return None  # Allow HTTP for Tailscale

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


def run_http_server(host: str, http_port: int):
    """
    Run HTTP server for Tailscale access (no SSL required since Tailscale encrypts).

    Args:
        host: Host to bind to
        http_port: HTTP port (typically 5049)
    """
    logger.info(f"Starting HTTP server on {host}:{http_port} (for Tailscale access)")

    # Run the main app on HTTP - Tailscale already encrypts traffic
    app.run(host=host, port=http_port, debug=False, threaded=True)


def run_server(
    host: str = "0.0.0.0",
    port: int = 5050,
    debug: bool = False,
    use_https: bool = True,
    http_redirect: bool = True,
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
        logger.info("HTTPS enabled with SSL certificates")

        # Start HTTP server on port-1 (e.g., 5049) for Tailscale access
        # Tailscale encrypts traffic, so HTTP is fine - avoids cert warnings on mobile
        if http_redirect and not debug:
            http_port = port - 1
            http_thread = threading.Thread(
                target=run_http_server, args=(host, http_port), daemon=True
            )
            http_thread.start()
            logger.info(f"HTTP server for Tailscale: http://{host}:{http_port}")
    elif use_https:
        logger.warning(
            "HTTPS requested but no certificates found. Run: python scripts/generate_cert.py"
        )
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
