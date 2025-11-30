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
    """Mobile-optimized web UI for text control."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>🏠 Home Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 15px;
            display: flex;
            flex-direction: column;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            max-width: 600px;
            width: 100%;
            margin: 0 auto;
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        @media (min-width: 768px) {
            body {
                padding: 40px;
            }
            .container {
                padding: 40px;
                min-height: 500px;
            }
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 24px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 25px;
            font-size: 14px;
        }
        @media (min-width: 768px) {
            h1 {
                font-size: 32px;
                margin-bottom: 15px;
            }
            .subtitle {
                font-size: 16px;
                margin-bottom: 35px;
            }
        }
        input[type="text"] {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            outline: none;
            transition: border-color 0.3s;
            margin-bottom: 15px;
        }
        input[type="text"]:focus {
            border-color: #667eea;
        }
        .btn {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            touch-action: manipulation;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        @media (min-width: 768px) {
            .btn {
                padding: 18px;
                font-size: 18px;
            }
        }
        .btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn:active {
            transform: scale(0.98);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .response-area {
            flex: 1;
            min-height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: 20px;
        }
        @media (min-width: 768px) {
            .response-area {
                min-height: 250px;
            }
        }
        .response {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 18px;
            line-height: 1.6;
            white-space: pre-wrap;
            width: 100%;
            font-size: 15px;
        }
        @media (min-width: 768px) {
            .response {
                padding: 24px;
                font-size: 16px;
            }
        }
        .response.success {
            border-left: 4px solid #28a745;
        }
        .response.error {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        .response.loading {
            text-align: center;
            color: #667eea;
            font-style: italic;
        }
        .placeholder {
            text-align: center;
            color: #ccc;
            font-size: 16px;
        }
        @media (min-width: 768px) {
            .placeholder {
                font-size: 18px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Home Control</h1>
        <p class="subtitle">Tell me what you want</p>

        <input
            type="text"
            id="commandInput"
            placeholder='Try "turn living room to fire"'
            autocomplete="off"
        />

        <button class="btn" onclick="sendCommand()">Send</button>

        <div class="response-area">
            <div id="response">
                <div class="placeholder">Your response will appear here</div>
            </div>
        </div>
    </div>

    <script>
        async function sendCommand() {
            const input = document.getElementById('commandInput');
            const responseDiv = document.getElementById('response');

            const command = input.value.trim();
            if (!command) {
                return;
            }

            responseDiv.innerHTML = '<div class="response loading">Processing...</div>';

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
                        <div class="response success">
                            ${data.response}
                        </div>
                    `;
                } else {
                    responseDiv.innerHTML = `
                        <div class="response error">
                            ${data.error}
                        </div>
                    `;
                }
            } catch (error) {
                responseDiv.innerHTML = `
                    <div class="response error">
                        Failed to connect to server
                    </div>
                `;
            }
        }

        // Enter key to submit
        document.getElementById('commandInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendCommand();
            }
        });

        // Prevent zoom on double-tap
        let lastTouchEnd = 0;
        document.addEventListener('touchend', (e) => {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                e.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
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
