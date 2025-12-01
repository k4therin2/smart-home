#!/usr/bin/env python3
"""
HTTP Server for Home Automation Agent

This server wraps the agent and provides HTTP endpoints for:
- Web UI control (mobile and desktop)
- Health checks and status monitoring
- Future voice assistant integrations (HA voice puck)

Architecture:
- Agent runs locally on Mac
- Flask server provides REST API and web UI
- Accessible on local network (http://192.168.254.12:5001)
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
from utils import load_prompts, save_prompts, get_daily_usage, commit_prompt_changes
from tools.review_agent import get_review_agent
from tools.prompt_improvement_agent import get_improvement_agent

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
    Useful for debugging API integrations.
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


@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    """Get all agent prompts from configuration."""
    try:
        prompts = load_prompts()
        return jsonify({
            "success": True,
            "prompts": prompts
        })
    except Exception as e:
        logger.error(f"Error loading prompts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/prompts', methods=['PUT'])
def update_prompts():
    """
    Update agent prompts with AI review and auto-commit.

    Request body:
    {
        "prompts": {
            "main_agent": {...},
            "hue_specialist": {...}
        }
    }

    Returns review feedback and commit status.
    """
    try:
        data = request.get_json()

        if not data or 'prompts' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'prompts' in request body"
            }), 400

        new_prompts = data['prompts']

        # Basic validation
        if not isinstance(new_prompts, dict):
            return jsonify({
                "success": False,
                "error": "Prompts must be an object"
            }), 400

        # Load old prompts for comparison
        old_prompts = load_prompts()

        # Review the changes
        logger.info("🔍 Reviewing prompt changes...")
        review_agent = get_review_agent()
        review_result = review_agent.review_all_changes(old_prompts, new_prompts)

        if not review_result["success"]:
            return jsonify({
                "success": False,
                "error": f"Review failed: {review_result.get('error', 'Unknown error')}"
            }), 500

        # Check if changes are approved or only have warnings
        approved = review_result.get("approved", True)

        if not approved:
            logger.warning(f"⚠️  Prompt changes have critical issues but saving anyway")

        # Save prompts
        if save_prompts(new_prompts):
            logger.info("✏️ Prompts saved successfully")

            # Auto-commit to git
            commit_result = commit_prompt_changes(review_result, user="UI")

            return jsonify({
                "success": True,
                "message": "Prompts updated successfully",
                "review": review_result,
                "commit": commit_result
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save prompts"
            }), 500

    except Exception as e:
        logger.error(f"Error updating prompts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/usage', methods=['GET'])
def get_usage():
    """Get today's API usage statistics."""
    try:
        usage = get_daily_usage()
        return jsonify({
            "success": True,
            "usage": usage
        })
    except Exception as e:
        logger.error(f"Error getting usage data: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/prompts/metadata', methods=['GET'])
def get_prompts_metadata():
    """Get metadata for all agents (for UI display)."""
    try:
        # Import metadata from agents
        from agent import METADATA as main_metadata
        from tools.hue_specialist import METADATA as hue_metadata

        return jsonify({
            "success": True,
            "metadata": {
                "main_agent": main_metadata,
                "hue_specialist": hue_metadata
            }
        })
    except Exception as e:
        logger.error(f"Error loading metadata: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/prompts/improve', methods=['POST'])
def improve_prompt():
    """
    AI assistant for one-shot prompt improvement.

    Request body:
    {
        "agent_name": "main_agent" | "hue_specialist",
        "prompt_type": "system",
        "current_prompt": "<current prompt text>",
        "user_feedback": "<what the user wants to improve>"
    }

    Returns suggested improved prompt with reasoning.
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['agent_name', 'prompt_type', 'current_prompt', 'user_feedback']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400

        # Get the improvement agent
        improvement_agent = get_improvement_agent()

        # Get suggestion
        logger.info(f"💡 Improving {data['agent_name']}.{data['prompt_type']} prompt...")
        result = improvement_agent.suggest_improvement(
            agent_name=data['agent_name'],
            prompt_type=data['prompt_type'],
            current_prompt=data['current_prompt'],
            user_feedback=data['user_feedback']
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error improving prompt: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/prompts/chat', methods=['POST'])
def chat_prompt_improvement():
    """
    Multi-turn chat with AI assistant for iterative prompt refinement.

    Request body:
    {
        "agent_name": "main_agent" | "hue_specialist",
        "prompt_type": "system",
        "current_prompt": "<current prompt text>",
        "user_message": "<user's latest message>",
        "chat_history": [  // optional
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

    Returns AI response and updated chat history.
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['agent_name', 'prompt_type', 'current_prompt', 'user_message']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"Missing required field: {field}"
                }), 400

        # Get the improvement agent
        improvement_agent = get_improvement_agent()

        # Chat with the agent
        logger.info(f"💬 Chat for {data['agent_name']}.{data['prompt_type']} prompt...")
        result = improvement_agent.chat(
            agent_name=data['agent_name'],
            prompt_type=data['prompt_type'],
            current_prompt=data['current_prompt'],
            user_message=data['user_message'],
            chat_history=data.get('chat_history', None)
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


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

        /* Usage tracker in corner */
        .usage-tracker {
            position: fixed;
            top: 15px;
            right: 15px;
            background: rgba(255, 255, 255, 0.95);
            padding: 10px 16px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-size: 13px;
            font-weight: 600;
            color: #667eea;
            z-index: 1000;
        }
        @media (min-width: 768px) {
            .usage-tracker {
                top: 20px;
                right: 20px;
                padding: 12px 20px;
                font-size: 14px;
            }
        }

        /* Settings button */
        .settings-btn {
            position: fixed;
            top: 15px;
            left: 15px;
            background: rgba(255, 255, 255, 0.95);
            padding: 10px;
            border-radius: 50%;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            z-index: 1000;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            border: none;
        }
        @media (min-width: 768px) {
            .settings-btn {
                top: 20px;
                left: 20px;
            }
        }
        .settings-btn:hover {
            background: rgba(255, 255, 255, 1);
            transform: scale(1.1);
        }
    </style>
</head>
<body>
    <!-- Usage tracker -->
    <div class="usage-tracker" id="usageTracker">$0.00 today</div>

    <!-- Settings button -->
    <button class="settings-btn" onclick="window.location.href='/settings'" title="Settings">⚙️</button>

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

                // Refresh usage after command
                updateUsage();
            } catch (error) {
                responseDiv.innerHTML = `
                    <div class="response error">
                        Failed to connect to server
                    </div>
                `;
            }
        }

        async function updateUsage() {
            try {
                const response = await fetch('/api/usage');
                const data = await response.json();

                if (data.success && data.usage) {
                    const cost = data.usage.cost_usd || 0;
                    document.getElementById('usageTracker').textContent = `$${cost.toFixed(4)} today`;
                }
            } catch (error) {
                console.error('Failed to fetch usage:', error);
            }
        }

        // Update usage on page load and every 10 seconds
        updateUsage();
        setInterval(updateUsage, 10000);

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


@app.route('/settings', methods=['GET'])
def settings_ui():
    """Settings page for editing agent prompts."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>⚙️ Settings - Home Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
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
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            max-width: 900px;
            width: 100%;
            margin: 0 auto;
        }
        @media (min-width: 768px) {
            body {
                padding: 40px;
            }
            .container {
                padding: 40px;
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
        .back-btn {
            background: #e0e0e0;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }
        .back-btn:hover {
            background: #d0d0d0;
        }
        .prompt-section {
            margin-bottom: 30px;
        }
        .prompt-section h2 {
            color: #667eea;
            font-size: 18px;
            margin-bottom: 10px;
        }
        .prompt-section label {
            display: block;
            font-weight: 600;
            margin-top: 15px;
            margin-bottom: 5px;
            color: #333;
            font-size: 14px;
        }
        .prompt-section textarea {
            width: 100%;
            min-height: 150px;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 13px;
            resize: vertical;
            outline: none;
            transition: border-color 0.3s;
        }
        .prompt-section textarea:focus {
            border-color: #667eea;
        }
        .save-btn {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            transition: all 0.3s;
            margin-top: 20px;
        }
        .save-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .save-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .message {
            padding: 12px;
            border-radius: 8px;
            margin-top: 15px;
            text-align: center;
            font-weight: 600;
        }
        .message.success {
            background: #d4edda;
            color: #155724;
        }
        .message.error {
            background: #f8d7da;
            color: #721c24;
        }
        .message.warning {
            background: #fff3cd;
            color: #856404;
        }
        .review-results {
            margin-top: 15px;
            padding: 15px;
            border-radius: 8px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
        }
        .review-results h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
            color: #333;
        }
        .issue-item {
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 6px;
            font-size: 14px;
        }
        .issue-item.critical {
            background: #f8d7da;
            border-left: 3px solid #dc3545;
        }
        .issue-item.warning {
            background: #fff3cd;
            border-left: 3px solid #ffc107;
        }
        .issue-item.suggestion {
            background: #d1ecf1;
            border-left: 3px solid #17a2b8;
        }
        .issue-severity {
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11px;
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <button class="back-btn" onclick="window.location.href='/'">← Back to Home</button>

        <h1>⚙️ Settings</h1>
        <p class="subtitle">Edit agent prompts (AI-reviewed & auto-committed)</p>

        <div id="promptsContainer">
            <div class="message">Loading prompts...</div>
        </div>

        <button class="save-btn" id="saveBtn" onclick="savePrompts()" disabled>Save & Review Changes</button>

        <div id="message"></div>
    </div>

    <script>
        let prompts = {};

        async function loadPrompts() {
            try {
                const response = await fetch('/api/prompts');
                const data = await response.json();

                if (data.success) {
                    prompts = data.prompts;
                    renderPrompts();
                } else {
                    document.getElementById('promptsContainer').innerHTML =
                        '<div class="message error">Failed to load prompts</div>';
                }
            } catch (error) {
                document.getElementById('promptsContainer').innerHTML =
                    '<div class="message error">Failed to connect to server</div>';
            }
        }

        function renderPrompts() {
            const container = document.getElementById('promptsContainer');

            let html = '';

            // Main Agent Section
            html += '<div class="prompt-section">';
            html += '<h2>🏠 Main Agent</h2>';
            html += '<label>System Prompt</label>';
            html += `<textarea id="main_agent_system">${escapeHtml(prompts.main_agent?.system || '')}</textarea>`;
            html += '</div>';

            // Hue Specialist Section
            html += '<div class="prompt-section">';
            html += '<h2>💡 Hue Specialist</h2>';
            html += '<label>System Prompt</label>';
            html += `<textarea id="hue_specialist_system">${escapeHtml(prompts.hue_specialist?.system || '')}</textarea>`;
            html += '<label>Fire Flicker Template</label>';
            html += `<textarea id="hue_specialist_fire_flicker">${escapeHtml(prompts.hue_specialist?.fire_flicker || '')}</textarea>`;
            html += '<label>Effect Mapping Template</label>';
            html += `<textarea id="hue_specialist_effect_mapping">${escapeHtml(prompts.hue_specialist?.effect_mapping || '')}</textarea>`;
            html += '</div>';

            container.innerHTML = html;
            document.getElementById('saveBtn').disabled = false;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function savePrompts() {
            const saveBtn = document.getElementById('saveBtn');
            const messageDiv = document.getElementById('message');

            saveBtn.disabled = true;
            saveBtn.textContent = 'Reviewing...';
            messageDiv.innerHTML = '';

            // Collect updated prompts
            const updatedPrompts = {
                main_agent: {
                    system: document.getElementById('main_agent_system').value,
                    description: prompts.main_agent?.description || ''
                },
                hue_specialist: {
                    system: document.getElementById('hue_specialist_system').value,
                    fire_flicker: document.getElementById('hue_specialist_fire_flicker').value,
                    effect_mapping: document.getElementById('hue_specialist_effect_mapping').value,
                    description: prompts.hue_specialist?.description || ''
                }
            };

            try {
                const response = await fetch('/api/prompts', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ prompts: updatedPrompts })
                });

                const data = await response.json();

                if (data.success) {
                    prompts = updatedPrompts;

                    // Build success message with commit info
                    let html = '<div class="message success">✓ Prompts saved successfully!';
                    if (data.commit && data.commit.committed) {
                        html += ` (Committed: ${data.commit.commit_hash})`;
                    }
                    html += '</div>';

                    // Show review results
                    if (data.review && data.review.reviews) {
                        html += renderReviewResults(data.review);
                    }

                    messageDiv.innerHTML = html;
                } else {
                    messageDiv.innerHTML = `<div class="message error">Failed to save: ${data.error}</div>`;
                }
            } catch (error) {
                messageDiv.innerHTML = '<div class="message error">Failed to connect to server</div>';
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save & Review Changes';
            }
        }

        function renderReviewResults(review) {
            if (!review.reviews || Object.keys(review.reviews).length === 0) {
                return '<div class="review-results"><h3>✓ No changes detected</h3><p>No prompts were modified.</p></div>';
            }

            let html = '<div class="review-results">';

            // Show overall review status
            const approved = review.approved !== false;
            const statusIcon = approved ? '✅' : '⚠️';
            const statusText = approved ? 'Approved' : 'Has Critical Issues';

            html += `<h3>${statusIcon} AI Review: ${statusText}</h3>`;
            html += `<p><strong>Summary:</strong> ${review.summary}</p>`;
            html += `<p><strong>Total Issues Found:</strong> ${review.total_issues || 0}</p>`;

            // Go through each reviewed prompt
            for (const [key, result] of Object.entries(review.reviews)) {
                html += `<p style="margin-top: 15px;"><strong>📝 ${key}:</strong></p>`;

                if (result.issues && result.issues.length > 0) {
                    result.issues.forEach(issue => {
                        const severity = issue.severity.toLowerCase();
                        const severityIcon = severity === 'critical' ? '🔴' :
                                            severity === 'warning' ? '⚠️' : '💡';

                        html += `<div class="issue-item ${severity}">`;
                        html += `${severityIcon} <span class="issue-severity">${issue.severity}</span>`;
                        html += `<strong>${issue.category}:</strong> ${issue.message}`;
                        if (issue.suggestion) {
                            html += `<br><small>💡 <strong>Suggestion:</strong> ${issue.suggestion}</small>`;
                        }
                        html += '</div>';
                    });
                } else {
                    html += `<div class="issue-item suggestion">`;
                    html += `✅ No issues found with this prompt.`;
                    html += '</div>';
                }
            }

            if (review.total_issues === 0) {
                html += '<p style="margin-top: 15px; color: #28a745; font-weight: 600;">✓ All changes passed AI review!</p>';
            }

            html += '</div>';
            return html;
        }

        // Load prompts on page load
        loadPrompts();
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
