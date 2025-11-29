#!/usr/bin/env python3
"""
HTTP Webhook Server for Home Automation Agent

This lightweight server wraps the agent and provides HTTP endpoints for:
- Voice assistant integrations (Alexa Lambda)
- Web UI control
- Health checks and status monitoring

Architecture:
- Agent runs locally (not in Lambda)
- Lambda function only forwards requests to this server
- Use ngrok for local development tunneling
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

# Import the agent
from agent import run_agent
from tools.lights import get_available_rooms
from tools.effects import get_hue_scenes

# Load environment
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for web UI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Simple in-memory request log (last 10 requests)
request_log = []


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "home-automation-agent",
        "version": "1.0.0"
    })


@app.route('/debug/raw', methods=['POST'])
def debug_raw():
    """
    Debug endpoint - logs and echoes back whatever JSON is sent.
    Useful for debugging Lambda/Alexa integration.
    """
    try:
        data = request.get_json()
        logger.info("="*60)
        logger.info("🔍 DEBUG RAW REQUEST:")
        logger.info(json.dumps(data, indent=2))
        logger.info("="*60)

        return jsonify({
            "success": True,
            "message": "Debug data received and logged",
            "received": data
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/command', methods=['POST'])
def process_command():
    """
    Process a natural language command.

    Request body:
    {
        "command": "turn living room to fire",
        "user_id": "optional-user-identifier"
    }

    Response:
    {
        "success": true,
        "response": "Agent's text response",
        "request_id": "uuid"
    }
    """
    try:
        data = request.get_json()

        if not data or 'command' not in data:
            logger.warning("Received request without 'command' field")
            return jsonify({
                "success": False,
                "error": "Missing 'command' in request body"
            }), 400

        command = data['command']
        user_id = data.get('user_id', 'anonymous')

        # Log incoming request
        logger.info(f"📥 INCOMING REQUEST: '{command}' (user: {user_id})")

        # Log request
        request_entry = {
            "command": command,
            "user_id": user_id,
            "timestamp": request.headers.get('X-Request-Time', 'unknown')
        }
        request_log.append(request_entry)
        if len(request_log) > 10:
            request_log.pop(0)

        # Run the agent (verbose=False for API mode)
        response = run_agent(command, verbose=False)

        # Log response
        logger.info(f"📤 RESPONSE: '{response[:100]}{'...' if len(response) > 100 else ''}'")

        return jsonify({
            "success": True,
            "response": response,
            "command": command
        })

    except Exception as e:
        logger.error(f"❌ ERROR processing command: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/rooms', methods=['GET'])
def list_rooms():
    """Get available rooms and their current state."""
    try:
        result = get_available_rooms()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/scenes/<room>', methods=['GET'])
def list_scenes(room):
    """Get available Hue scenes for a specific room."""
    try:
        result = get_hue_scenes(room)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent request logs."""
    return jsonify({
        "success": True,
        "logs": request_log
    })


@app.route('/', methods=['GET'])
def web_ui():
    """Simple web UI for testing and monitoring."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Home Automation Agent</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-top: 0;
        }
        h2 {
            color: #666;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }
        input[type="text"] {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
        }
        button:hover {
            background: #0056b3;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .response {
            background: #f8f9fa;
            border-left: 4px solid #007bff;
            padding: 15px;
            margin-top: 15px;
            border-radius: 4px;
        }
        .error {
            background: #fff3cd;
            border-left-color: #ffc107;
        }
        .endpoint {
            background: #f8f9fa;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }
        .endpoint-method {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: bold;
            margin-right: 10px;
        }
        .get {
            background: #28a745;
            color: white;
        }
        .post {
            background: #007bff;
            color: white;
        }
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 14px;
            font-weight: bold;
        }
        .status.online {
            background: #d4edda;
            color: #155724;
        }
        ul {
            list-style: none;
            padding: 0;
        }
        li {
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }
        li:last-child {
            border-bottom: none;
        }
        .example {
            color: #666;
            font-style: italic;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Home Automation Agent</h1>
        <p>AI-powered natural language control for smart home devices</p>
        <p><span class="status online">● ONLINE</span></p>
    </div>

    <div class="container">
        <h2>Try a Command</h2>
        <input type="text" id="commandInput" placeholder='Enter command (e.g., "turn living room to fire")' />
        <button onclick="sendCommand()">Send Command</button>
        <div id="response"></div>
    </div>

    <div class="container">
        <h2>API Endpoints</h2>

        <div class="endpoint">
            <span class="endpoint-method post">POST</span>
            <strong>/api/command</strong> - Process natural language command
            <br><span class="example">Request: {"command": "turn living room to fire"}</span>
        </div>

        <div class="endpoint">
            <span class="endpoint-method get">GET</span>
            <strong>/api/rooms</strong> - List available rooms and lights
        </div>

        <div class="endpoint">
            <span class="endpoint-method get">GET</span>
            <strong>/api/scenes/:room</strong> - Get available Hue scenes for a room
            <br><span class="example">Example: /api/scenes/living_room</span>
        </div>

        <div class="endpoint">
            <span class="endpoint-method get">GET</span>
            <strong>/api/logs</strong> - View recent command logs
        </div>

        <div class="endpoint">
            <span class="endpoint-method get">GET</span>
            <strong>/health</strong> - Health check endpoint
        </div>
    </div>

    <div class="container">
        <h2>Example Commands</h2>
        <ul>
            <li>🔥 "turn living room to fire"</li>
            <li>🌊 "make me feel like I'm under the sea"</li>
            <li>📚 "cozy reading light in the bedroom"</li>
            <li>⚡ "energizing office lighting"</li>
            <li>🌙 "romantic lighting for dinner"</li>
        </ul>
    </div>

    <div class="container">
        <h2>Integration Status</h2>
        <ul>
            <li>✅ Home Assistant - Connected</li>
            <li>✅ Philips Hue - 25 bulbs available</li>
            <li>✅ Claude API - Sonnet 4</li>
            <li>⏳ Alexa Lambda - Planned (Phase 2)</li>
        </ul>
    </div>

    <script>
        async function sendCommand() {
            const input = document.getElementById('commandInput');
            const responseDiv = document.getElementById('response');
            const button = event.target;

            const command = input.value.trim();
            if (!command) {
                alert('Please enter a command');
                return;
            }

            button.disabled = true;
            button.textContent = 'Processing...';
            responseDiv.innerHTML = '<div class="response">Sending command to agent...</div>';

            try {
                const response = await fetch('/api/command', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ command })
                });

                const data = await response.json();

                if (data.success) {
                    responseDiv.innerHTML = `
                        <div class="response">
                            <strong>Command:</strong> ${data.command}<br>
                            <strong>Response:</strong> ${data.response}
                        </div>
                    `;
                } else {
                    responseDiv.innerHTML = `
                        <div class="response error">
                            <strong>Error:</strong> ${data.error}
                        </div>
                    `;
                }
            } catch (error) {
                responseDiv.innerHTML = `
                    <div class="response error">
                        <strong>Error:</strong> ${error.message}
                    </div>
                `;
            } finally {
                button.disabled = false;
                button.textContent = 'Send Command';
            }
        }

        // Allow Enter key to submit
        document.getElementById('commandInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });
    </script>
</body>
</html>
    """
    return render_template_string(html)


if __name__ == '__main__':
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'

    print(f"\n{'='*60}")
    print(f"🏠 Home Automation Agent Server")
    print(f"{'='*60}")
    print(f"Server running on: http://localhost:{port}")
    print(f"Web UI: http://localhost:{port}/")
    print(f"API: http://localhost:{port}/api/command")
    print(f"Logging to: logs/server.log")
    print(f"{'='*60}\n")

    logger.info("Server starting up...")

    app.run(host='0.0.0.0', port=port, debug=debug)
