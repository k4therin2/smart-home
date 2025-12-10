"""
Smart Home Assistant - Web Server

Flask-based web interface for the smart home assistant.
REQ-015: Web UI (Basic)
"""

import json
import sqlite3
from datetime import date
from flask import Flask, render_template, request, jsonify
from src.config import DATA_DIR, ROOM_ENTITY_MAP
from src.utils import setup_logging, log_command, get_daily_usage
from src.ha_client import get_ha_client

# Initialize logging
logger = setup_logging("server")

# Initialize Flask app
app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


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
        return {
            "success": False,
            "response": f"Error processing command: {str(error)}",
            "command": command,
            "error": str(error)
        }


@app.route("/")
def index():
    """Render the main web interface."""
    return render_template("index.html")


@app.route("/api/command", methods=["POST"])
def handle_command():
    """
    Handle incoming commands from the web interface.

    Expects JSON: {"command": "user command text"}
    Returns JSON: {"success": bool, "response": str, ...}
    """
    try:
        data = request.get_json()

        if not data or "command" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'command' field in request"
            }), 400

        command = data["command"].strip()

        if not command:
            return jsonify({
                "success": False,
                "error": "Command cannot be empty"
            }), 400

        result = process_command(command)
        return jsonify(result)

    except Exception as error:
        logger.error(f"Error processing command: {error}")
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


@app.route("/api/status")
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
        return jsonify({
            "system": "error",
            "agent": "error",
            "home_assistant": "error",
            "error": str(error),
            "devices": []
        })


@app.route("/api/history")
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
        return jsonify({"history": [], "error": str(error)})


def run_server(host: str = "0.0.0.0", port: int = 5050, debug: bool = False):
    """
    Run the Flask development server.

    Args:
        host: Host to bind to
        port: Port number
        debug: Enable debug mode
    """
    logger.info(f"Starting web server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
