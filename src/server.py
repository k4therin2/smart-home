"""
Smart Home Assistant - Web Server

Flask-based web interface for the smart home assistant.
REQ-015: Web UI (Basic)
Phase 2.1: Application Security Baseline
Phase 2.2: HTTPS/TLS Configuration
WP-10.18: API Documentation with Swagger/OpenAPI
"""

import os
from pathlib import Path
import secrets
import sqlite3
import threading
from datetime import date, datetime

from flasgger import Swagger
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFError, CSRFProtect
from pydantic import BaseModel, Field, ValidationError

from src.config import (
    DATA_DIR,
    ROOM_ENTITY_MAP,
    RATE_LIMIT_DEFAULT_PER_DAY,
    RATE_LIMIT_DEFAULT_PER_HOUR,
    RATE_LIMIT_ADMIN_MULTIPLIER,
)
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


def get_rate_limit_key() -> str:
    """
    Get rate limit key based on user identity (WP-10.23).

    Returns user ID for authenticated users, IP address for anonymous.
    This enables per-user rate limiting instead of just per-IP.
    """
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{get_remote_address()}"


def is_admin_rate_limit_exempt() -> bool:
    """
    Check if current user should get increased rate limits (WP-10.23).

    Admin users get RATE_LIMIT_ADMIN_MULTIPLIER times the normal limit.
    Returns True to exempt from default limits (custom limits applied).
    """
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        # Check if user has admin role
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return True
    return False


# Initialize rate limiter with per-user keying (WP-10.23)
limiter = Limiter(
    key_func=get_rate_limit_key,
    app=app,
    default_limits=[
        f"{RATE_LIMIT_DEFAULT_PER_DAY} per day",
        f"{RATE_LIMIT_DEFAULT_PER_HOUR} per hour"
    ],
    storage_uri="memory://",
    headers_enabled=True,  # Enable X-RateLimit-* headers
)

# Initialize Flask-Login
login_manager = setup_login_manager(app)

# Register auth blueprint
app.register_blueprint(auth_bp)

# WP-10.18: Initialize Swagger/OpenAPI documentation
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "SmartHome Assistant API",
        "description": "REST API for the SmartHome Assistant - an AI-powered home automation system",
        "version": "1.0.0"
    },
    "securityDefinitions": {
        "SessionAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "session"
        },
        "BearerAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization"
        }
    }
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)


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


@app.route("/.well-known/security.txt")
def security_txt():
    """Serve security.txt for vulnerability disclosure."""
    return send_from_directory(
        app.static_folder, ".well-known/security.txt", mimetype="text/plain"
    )


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
    Execute a natural language command
    ---
    tags:
      - Voice & Commands
    security:
      - SessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - command
          properties:
            command:
              type: string
              description: Natural language command to execute
              example: "Turn on the living room lights"
    responses:
      200:
        description: Command executed successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            response:
              type: string
              example: "I've turned on the living room lights."
      400:
        description: Bad request
      429:
        description: Rate limit exceeded
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
    Get system status
    ---
    tags:
      - System
    security:
      - SessionAuth: []
    responses:
      200:
        description: System status
        schema:
          type: object
          properties:
            system:
              type: string
              enum: [ready, error]
              example: ready
            agent:
              type: string
              enum: [ready, error]
              example: ready
            home_assistant:
              type: string
              enum: [connected, disconnected, error]
              example: connected
            devices:
              type: array
              items:
                type: object
                properties:
                  entity_id:
                    type: string
                  friendly_name:
                    type: string
                  state:
                    type: string
      500:
        description: Server error
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
    Get comprehensive system health
    ---
    tags:
      - Health & Monitoring
    security:
      - SessionAuth: []
    description: |
      Returns health status of all system components with automatic
      self-healing for degraded components.

      REQ-021: Self-Monitoring & Self-Healing
    responses:
      200:
        description: System health status
        schema:
          type: object
          properties:
            timestamp:
              type: string
              format: date-time
            status:
              type: string
              enum: [healthy, degraded, unhealthy]
            components:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  status:
                    type: string
                  message:
                    type: string
            healing_attempted:
              type: boolean
            healing_results:
              type: array
              items:
                type: object
      500:
        description: Health check error
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
    Get health check history for trending
    ---
    tags:
      - Health & Monitoring
    security:
      - SessionAuth: []
    parameters:
      - name: component
        in: query
        type: string
        description: Filter by component name
        required: false
      - name: limit
        in: query
        type: integer
        default: 50
        maximum: 100
        description: Maximum entries to return
    responses:
      200:
        description: Health history data
        schema:
          type: object
          properties:
            history:
              type: object
              additionalProperties:
                type: array
                items:
                  type: object
      500:
        description: Server error
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
    Get self-healing action history
    ---
    tags:
      - Health & Monitoring
    security:
      - SessionAuth: []
    parameters:
      - name: component
        in: query
        type: string
        description: Filter by component name
        required: false
      - name: limit
        in: query
        type: integer
        default: 50
        maximum: 100
        description: Maximum entries to return
    responses:
      200:
        description: Healing action history
        schema:
          type: object
          properties:
            healing_history:
              type: array
              items:
                type: object
                properties:
                  component:
                    type: string
                  action:
                    type: string
                  success:
                    type: boolean
                  timestamp:
                    type: string
                    format: date-time
      500:
        description: Server error
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
    Liveness probe (Kubernetes-style)
    ---
    tags:
      - Health & Monitoring
    description: |
      Kubernetes-style liveness check. Returns 200 if the process is alive.
      Does NOT require authentication - this is intentional for k8s probes.
    responses:
      200:
        description: Process is alive
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            timestamp:
              type: string
              format: date-time
      503:
        description: Process not responding
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
    Readiness probe (Kubernetes-style)
    ---
    tags:
      - Health & Monitoring
    description: |
      Kubernetes-style readiness check. Returns 200 if all critical dependencies
      are healthy and the service can accept traffic.
      Does NOT require authentication - this is intentional for k8s probes.
    responses:
      200:
        description: Ready to accept traffic
        schema:
          type: object
          properties:
            ready:
              type: boolean
              example: true
            timestamp:
              type: string
              format: date-time
      503:
        description: Not ready - one or more dependencies unhealthy
        schema:
          type: object
          properties:
            ready:
              type: boolean
              example: false
            failing:
              type: array
              items:
                type: string
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
    Manually trigger healing for a component
    ---
    tags:
      - Health & Monitoring
    security:
      - SessionAuth: []
    parameters:
      - name: component
        in: path
        type: string
        required: true
        description: Name of the component to heal
        enum: [home_assistant, cache, database, llm_provider]
    responses:
      200:
        description: Healing result
        schema:
          type: object
          properties:
            attempted:
              type: boolean
            success:
              type: boolean
            actions:
              type: array
              items:
                type: string
      500:
        description: Healing trigger failed
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
    Get recent command history
    ---
    tags:
      - Voice & Commands
    security:
      - SessionAuth: []
    responses:
      200:
        description: Command history
        schema:
          type: object
          properties:
            history:
              type: array
              items:
                type: object
                properties:
                  command:
                    type: string
                  timestamp:
                    type: string
                    format: date-time
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
    """
    Get a CSRF token for API clients
    ---
    tags:
      - Authentication
    security:
      - SessionAuth: []
    responses:
      200:
        description: CSRF token
        schema:
          type: object
          properties:
            csrf_token:
              type: string
              description: Token to include in X-CSRFToken header
    """
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
    Run voice pipeline diagnostics
    ---
    tags:
      - Voice & Commands
    security:
      - SessionAuth: []
    description: |
      Tests the entire voice pipeline from puck to TTS response:
      1. Voice Puck connectivity
      2. HA Assist pipeline configuration
      3. SmartHome webhook reachability
      4. SmartHome voice endpoint functionality
      5. TTS output verification
    responses:
      200:
        description: Diagnostic results
        schema:
          type: object
          properties:
            overall_status:
              type: string
              enum: [passed, failed, warning]
            summary:
              type: object
              properties:
                passed:
                  type: integer
                failed:
                  type: integer
                warnings:
                  type: integer
                total:
                  type: integer
            results:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  status:
                    type: string
                  message:
                    type: string
                  fix_suggestions:
                    type: array
                    items:
                      type: string
      500:
        description: Diagnostics failed
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
    Handle voice commands from Home Assistant
    ---
    tags:
      - Voice & Commands
    security:
      - SessionAuth: []
      - BearerAuth: []
    description: |
      Webhook endpoint for Home Assistant conversation agent.
      Authentication: Either session auth OR Bearer token (VOICE_WEBHOOK_TOKEN env var).
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - text
          properties:
            text:
              type: string
              description: Voice command text from STT
              example: "Turn on the kitchen lights"
            language:
              type: string
              default: en
            conversation_id:
              type: string
            device_id:
              type: string
    responses:
      200:
        description: Command result
        schema:
          type: object
          properties:
            success:
              type: boolean
            response:
              type: string
      400:
        description: Invalid request
      401:
        description: Unauthorized
      429:
        description: Rate limit exceeded
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
    Subscribe to push notifications
    ---
    tags:
      - Notifications
    security:
      - SessionAuth: []
    description: |
      Register for push notifications (PWA feature).
      Currently a placeholder - full implementation requires web-push library.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - endpoint
          properties:
            endpoint:
              type: string
              description: Push subscription endpoint URL
            keys:
              type: object
              properties:
                p256dh:
                  type: string
                auth:
                  type: string
    responses:
      201:
        description: Subscription registered
      400:
        description: Missing endpoint
      500:
        description: Subscription failed
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
    Get todos from a list
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    parameters:
      - name: list_name
        in: query
        type: string
        default: default
        description: Name of the list
      - name: show_completed
        in: query
        type: boolean
        default: false
        description: Include completed items
    responses:
      200:
        description: Todo list
        schema:
          type: object
          properties:
            success:
              type: boolean
            todos:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  content:
                    type: string
                  completed:
                    type: boolean
                  priority:
                    type: integer
                  created_at:
                    type: string
            count:
              type: integer
            list_name:
              type: string
      500:
        description: Server error
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
    Add a new todo item
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - content
          properties:
            content:
              type: string
              description: Todo item text
            list_name:
              type: string
              default: default
            priority:
              type: string
              enum: [normal, high, urgent]
              default: normal
    responses:
      201:
        description: Todo created
        schema:
          type: object
          properties:
            success:
              type: boolean
            todo_id:
              type: integer
            content:
              type: string
            list_name:
              type: string
      400:
        description: Invalid input
      500:
        description: Server error
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
    """
    Mark a todo as completed
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    parameters:
      - name: todo_id
        in: path
        type: integer
        required: true
        description: ID of the todo to complete
    responses:
      200:
        description: Todo completed
      404:
        description: Todo not found
      500:
        description: Server error
    """
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
    """
    Delete a todo item
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    parameters:
      - name: todo_id
        in: path
        type: integer
        required: true
        description: ID of the todo to delete
    responses:
      200:
        description: Todo deleted
      404:
        description: Todo not found
      500:
        description: Server error
    """
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
    """
    Get all todo lists with item counts
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    responses:
      200:
        description: List of todo lists
        schema:
          type: object
          properties:
            success:
              type: boolean
            lists:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  count:
                    type: integer
      500:
        description: Server error
    """
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
    """
    Get pending reminders
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    responses:
      200:
        description: List of pending reminders
        schema:
          type: object
          properties:
            success:
              type: boolean
            reminders:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  message:
                    type: string
                  due_at:
                    type: string
                    format: date-time
            count:
              type: integer
      500:
        description: Server error
    """
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
    """
    Dismiss a reminder
    ---
    tags:
      - Todos & Reminders
    security:
      - SessionAuth: []
    parameters:
      - name: reminder_id
        in: path
        type: integer
        required: true
        description: ID of the reminder to dismiss
    responses:
      200:
        description: Reminder dismissed
      404:
        description: Reminder not found
      500:
        description: Server error
    """
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
    Get all automations
    ---
    tags:
      - Automations
    security:
      - SessionAuth: []
    parameters:
      - name: enabled_only
        in: query
        type: boolean
        default: false
        description: Only return enabled automations
      - name: trigger_type
        in: query
        type: string
        enum: [time, state]
        description: Filter by trigger type
    responses:
      200:
        description: List of automations
        schema:
          type: object
          properties:
            success:
              type: boolean
            automations:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  trigger_type:
                    type: string
                  action_type:
                    type: string
                  enabled:
                    type: boolean
            count:
              type: integer
            stats:
              type: object
      500:
        description: Server error
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
    Create a new automation
    ---
    tags:
      - Automations
    security:
      - SessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - trigger_type
            - trigger_config
            - action_type
            - action_config
          properties:
            name:
              type: string
              description: Automation name
            trigger_type:
              type: string
              enum: [time, state]
            trigger_config:
              type: object
              description: Trigger-specific configuration
            action_type:
              type: string
              enum: [agent_command, ha_service]
            action_config:
              type: object
              description: Action-specific configuration
            description:
              type: string
    responses:
      201:
        description: Automation created
        schema:
          type: object
          properties:
            success:
              type: boolean
            automation_id:
              type: integer
            message:
              type: string
      400:
        description: Invalid input
      500:
        description: Server error
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
    Update an existing automation
    ---
    tags:
      - Automations
    security:
      - SessionAuth: []
    parameters:
      - name: automation_id
        in: path
        type: integer
        required: true
        description: ID of the automation to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            description:
              type: string
            trigger_config:
              type: object
            action_config:
              type: object
            enabled:
              type: boolean
    responses:
      200:
        description: Automation updated
      404:
        description: Automation not found
      500:
        description: Server error
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
    """
    Delete an automation
    ---
    tags:
      - Automations
    security:
      - SessionAuth: []
    parameters:
      - name: automation_id
        in: path
        type: integer
        required: true
        description: ID of the automation to delete
    responses:
      200:
        description: Automation deleted
      404:
        description: Automation not found
      500:
        description: Server error
    """
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
    """
    Toggle automation enabled/disabled state
    ---
    tags:
      - Automations
    security:
      - SessionAuth: []
    parameters:
      - name: automation_id
        in: path
        type: integer
        required: true
        description: ID of the automation to toggle
    responses:
      200:
        description: Automation toggled
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            enabled:
              type: boolean
      404:
        description: Automation not found
      500:
        description: Server error
    """
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
    List available log files
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    parameters:
      - name: type
        in: query
        type: string
        enum: [main, error, api]
        description: Filter by log type
    responses:
      200:
        description: List of log files
        schema:
          type: object
          properties:
            success:
              type: boolean
            files:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  path:
                    type: string
                  size:
                    type: integer
                  modified:
                    type: string
                    format: date-time
            count:
              type: integer
      500:
        description: Server error
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
    Read and filter log entries
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    parameters:
      - name: log_type
        in: query
        type: string
        enum: [main, error, api]
        description: Type of log to read
      - name: offset
        in: query
        type: integer
        default: 0
        description: Number of entries to skip
      - name: limit
        in: query
        type: integer
        default: 100
        maximum: 1000
        description: Max entries to return
      - name: reverse
        in: query
        type: boolean
        default: true
        description: Return entries newest first
      - name: min_level
        in: query
        type: string
        enum: [DEBUG, INFO, WARNING, ERROR, CRITICAL]
        description: Minimum log level
      - name: levels
        in: query
        type: string
        description: Comma-separated specific levels to include
      - name: start_time
        in: query
        type: string
        format: date-time
        description: Filter entries after this time
      - name: end_time
        in: query
        type: string
        format: date-time
        description: Filter entries before this time
      - name: module
        in: query
        type: string
        description: Exact module name to filter
      - name: search
        in: query
        type: string
        description: Text to search in log messages
    responses:
      200:
        description: Log entries
        schema:
          type: object
          properties:
            success:
              type: boolean
            entries:
              type: array
              items:
                type: object
            total:
              type: integer
            stats:
              type: object
      500:
        description: Server error
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
    Export log entries
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    parameters:
      - name: format
        in: query
        type: string
        enum: [json, text]
        default: json
        description: Export format
      - name: download
        in: query
        type: boolean
        default: false
        description: Set Content-Disposition for download
      - name: log_type
        in: query
        type: string
        enum: [main, error, api]
      - name: min_level
        in: query
        type: string
        enum: [DEBUG, INFO, WARNING, ERROR, CRITICAL]
    responses:
      200:
        description: Log data in requested format
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
    Get latest log entries (tail)
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    description: |
      Tail the log file. Use from_position for follow mode to get new entries since last request.
    parameters:
      - name: lines
        in: query
        type: integer
        default: 50
        maximum: 500
        description: Number of lines to return
      - name: from_position
        in: query
        type: integer
        description: File position to read from (for follow mode)
    responses:
      200:
        description: Log entries with position for follow-up
        schema:
          type: object
          properties:
            success:
              type: boolean
            entries:
              type: array
              items:
                type: object
            position:
              type: integer
              description: Current file position for follow mode
      500:
        description: Server error
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
    Get log file statistics
    ---
    tags:
      - Logs
    security:
      - SessionAuth: []
    parameters:
      - name: log_type
        in: query
        type: string
        enum: [main, error, api]
        description: Type of log
    responses:
      200:
        description: Log statistics
        schema:
          type: object
          properties:
            success:
              type: boolean
            total_entries:
              type: integer
            level_counts:
              type: object
            first_entry:
              type: string
              format: date-time
            last_entry:
              type: string
              format: date-time
      500:
        description: Server error
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


@app.route("/api/export", methods=["GET"])
@login_required
@limiter.limit("5 per minute")
def export_data():
    """
    Export all user data (WP-10.35)
    ---
    tags:
      - Data Management
    security:
      - SessionAuth: []
    parameters:
      - name: format
        in: query
        type: string
        enum: [json, csv]
        default: json
        description: Export format
    responses:
      200:
        description: Exported data
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      500:
        description: Server error
    """
    from src.data_export import DataExporter

    try:
        exporter = DataExporter()
        export_format = request.args.get("format", "json").lower()

        if export_format == "csv":
            csv_data = exporter.export_as_csv()
            return jsonify({"success": True, "format": "csv", "data": csv_data})
        else:
            # Default to JSON
            data = exporter.export_all()
            return jsonify({"success": True, "format": "json", "data": data})

    except Exception as error:
        logger.error(f"Error exporting data: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error exporting data"}
        ), 500


@app.route("/api/import", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def import_data():
    """
    Import user data for migration (WP-10.35)
    ---
    tags:
      - Data Management
    security:
      - SessionAuth: []
    parameters:
      - name: preview
        in: query
        type: boolean
        default: false
        description: Preview import without applying
      - name: merge
        in: query
        type: boolean
        default: true
        description: Merge with existing data (false = replace)
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
    responses:
      200:
        description: Import result or preview
        schema:
          type: object
          properties:
            success:
              type: boolean
            imported:
              type: object
      400:
        description: Invalid import data
      500:
        description: Server error
    """
    from src.data_export import DataImporter

    try:
        importer = DataImporter()
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Validate first
        is_valid, errors = importer.validate_import_data(data)
        if not is_valid:
            return jsonify({"success": False, "errors": errors}), 400

        preview = request.args.get("preview", "false").lower() == "true"
        if preview:
            preview_data = importer.get_import_preview(data)
            return jsonify({"success": True, "preview": True, "changes": preview_data})

        # Perform import
        merge = request.args.get("merge", "true").lower() == "true"
        imported = importer.import_data(data, merge=merge)
        return jsonify({"success": True, "preview": False, "imported": imported})

    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        logger.error(f"Error importing data: {error}")
        return jsonify(
            {"success": False, "error": str(error) if app.debug else "Error importing data"}
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
