/**
 * Smart Home Assistant - Web UI JavaScript
 * Handles command submission, voice input, and UI updates
 */

// State
const state = {
    history: [],
    isListening: false,
    recognition: null
};

// DOM Elements
const elements = {
    commandForm: document.getElementById("command-form"),
    commandInput: document.getElementById("command-input"),
    submitBtn: document.getElementById("submit-btn"),
    voiceBtn: document.getElementById("voice-btn"),
    responseArea: document.getElementById("response-area"),
    historyList: document.getElementById("history-list"),
    devicesGrid: document.getElementById("devices-grid"),
    statusIndicator: document.getElementById("status-indicator"),
    statusText: document.getElementById("status-text")
};

/**
 * Initialize the application
 */
function init() {
    setupEventListeners();
    initVoiceRecognition();
    checkSystemStatus();
    loadHistory();

    // Refresh device status every 30 seconds
    setInterval(checkSystemStatus, 30000);
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    elements.commandForm.addEventListener("submit", handleCommandSubmit);
    elements.voiceBtn.addEventListener("click", toggleVoiceInput);

    // Allow pressing Enter in input
    elements.commandInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            elements.commandForm.dispatchEvent(new Event("submit"));
        }
    });
}

/**
 * Handle command form submission
 */
async function handleCommandSubmit(event) {
    event.preventDefault();

    const command = elements.commandInput.value.trim();
    if (!command) return;

    // Disable input while processing
    setLoading(true);

    try {
        const response = await sendCommand(command);
        displayResponse(command, response);
        addToHistory(command);
        elements.commandInput.value = "";
    } catch (error) {
        displayError(command, error.message);
    } finally {
        setLoading(false);
        elements.commandInput.focus();
    }
}

/**
 * Send command to server
 */
async function sendCommand(command) {
    const response = await fetch("/api/command", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ command })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
        throw new Error(data.error || "Unknown error occurred");
    }

    return data;
}

/**
 * Display command response in UI
 */
function displayResponse(command, response) {
    const responseHtml = `
        <div class="response-message">
            <div class="response-command">${escapeHtml(command)}</div>
            <div class="response-text">${escapeHtml(response.response)}</div>
        </div>
    `;

    // Replace placeholder or prepend new response
    if (elements.responseArea.querySelector(".placeholder-text")) {
        elements.responseArea.innerHTML = responseHtml;
    } else {
        elements.responseArea.insertAdjacentHTML("afterbegin", responseHtml);
    }

    // Limit displayed responses
    const messages = elements.responseArea.querySelectorAll(".response-message");
    if (messages.length > 5) {
        messages[messages.length - 1].remove();
    }
}

/**
 * Display error message
 */
function displayError(command, errorMessage) {
    const responseHtml = `
        <div class="response-message">
            <div class="response-command">${escapeHtml(command)}</div>
            <div class="response-text response-error">Error: ${escapeHtml(errorMessage)}</div>
        </div>
    `;

    if (elements.responseArea.querySelector(".placeholder-text")) {
        elements.responseArea.innerHTML = responseHtml;
    } else {
        elements.responseArea.insertAdjacentHTML("afterbegin", responseHtml);
    }
}

/**
 * Add command to history
 */
function addToHistory(command) {
    state.history.unshift(command);

    // Limit history size
    if (state.history.length > 10) {
        state.history.pop();
    }

    // Save to localStorage
    localStorage.setItem("commandHistory", JSON.stringify(state.history));

    renderHistory();
}

/**
 * Load history from localStorage and server
 */
async function loadHistory() {
    // First load from localStorage for immediate display
    try {
        const stored = localStorage.getItem("commandHistory");
        if (stored) {
            state.history = JSON.parse(stored);
            renderHistory();
        }
    } catch (error) {
        console.error("Failed to load local history:", error);
    }

    // Then fetch from server to merge with any commands from other sessions
    try {
        const response = await fetch("/api/history");
        const data = await response.json();

        if (data.history && data.history.length > 0) {
            // Merge server history with local (prioritize local for recent commands)
            const serverCommands = data.history.map(item => item.command);
            const merged = [...new Set([...state.history, ...serverCommands])].slice(0, 10);
            state.history = merged;
            localStorage.setItem("commandHistory", JSON.stringify(state.history));
            renderHistory();
        }
    } catch (error) {
        console.error("Failed to load server history:", error);
    }
}

/**
 * Render history list
 */
function renderHistory() {
    if (state.history.length === 0) {
        elements.historyList.innerHTML = '<li class="placeholder-text">No commands yet</li>';
        return;
    }

    elements.historyList.innerHTML = state.history
        .map(cmd => `<li onclick="useHistoryCommand(this)">${escapeHtml(cmd)}</li>`)
        .join("");
}

/**
 * Use a command from history
 */
function useHistoryCommand(element) {
    elements.commandInput.value = element.textContent;
    elements.commandInput.focus();
}

/**
 * Initialize Web Speech API for voice input
 */
function initVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        elements.voiceBtn.style.display = "none";
        console.log("Speech recognition not supported");
        return;
    }

    state.recognition = new SpeechRecognition();
    state.recognition.continuous = false;
    state.recognition.interimResults = false;
    state.recognition.lang = "en-US";

    state.recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        elements.commandInput.value = transcript;
        stopListening();

        // Auto-submit after voice input
        elements.commandForm.dispatchEvent(new Event("submit"));
    };

    state.recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        stopListening();
    };

    state.recognition.onend = () => {
        stopListening();
    };
}

/**
 * Toggle voice input
 */
function toggleVoiceInput() {
    if (state.isListening) {
        stopListening();
    } else {
        startListening();
    }
}

/**
 * Start listening for voice input
 */
function startListening() {
    if (!state.recognition) return;

    state.isListening = true;
    elements.voiceBtn.classList.add("listening");
    elements.commandInput.placeholder = "Listening...";

    try {
        state.recognition.start();
    } catch (error) {
        console.error("Failed to start recognition:", error);
        stopListening();
    }
}

/**
 * Stop listening for voice input
 */
function stopListening() {
    state.isListening = false;
    elements.voiceBtn.classList.remove("listening");
    elements.commandInput.placeholder = "Enter a command... (e.g., 'turn on living room lights')";

    if (state.recognition) {
        try {
            state.recognition.stop();
        } catch (error) {
            // Ignore errors when stopping
        }
    }
}

/**
 * Set loading state
 */
function setLoading(loading) {
    elements.submitBtn.disabled = loading;
    elements.commandInput.disabled = loading;

    if (loading) {
        elements.submitBtn.innerHTML = '<span class="spinner"></span>';
    } else {
        elements.submitBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 2L11 13M22 2L15 22L11 13L2 9L22 2Z"/>
            </svg>
        `;
    }
}

/**
 * Check system status and render devices
 */
async function checkSystemStatus() {
    try {
        const response = await fetch("/api/status");
        const data = await response.json();

        updateStatusIndicator(data.system);
        renderDevices(data.devices || []);
    } catch (error) {
        updateStatusIndicator("error");
        renderDevices([]);
    }
}

/**
 * Render device cards in the dashboard
 */
function renderDevices(devices) {
    if (!devices || devices.length === 0) {
        elements.devicesGrid.innerHTML = '<p class="placeholder-text">No devices connected</p>';
        return;
    }

    elements.devicesGrid.innerHTML = devices.map(device => {
        const isOn = device.state === "on";
        const brightness = device.brightness ? Math.round((device.brightness / 255) * 100) : null;
        const stateText = isOn ? (brightness ? `On (${brightness}%)` : "On") : "Off";
        const icon = getDeviceIcon(device.type);

        return `
            <div class="device-card ${isOn ? 'device-on' : ''}"
                 role="listitem"
                 onclick="toggleDevice('${device.entity_id}')"
                 title="Click to toggle ${device.name}">
                <div class="device-icon" aria-hidden="true">${icon}</div>
                <div class="device-name">${escapeHtml(device.name)}</div>
                <div class="device-state">${stateText}</div>
            </div>
        `;
    }).join("");
}

/**
 * Get icon for device type
 */
function getDeviceIcon(type) {
    const icons = {
        light: "💡",
        switch: "🔌",
        sensor: "📊",
        thermostat: "🌡️",
        lock: "🔒",
        camera: "📷",
        vacuum: "🧹"
    };
    return icons[type] || "📦";
}

/**
 * Toggle a device on/off via voice command
 */
function toggleDevice(entityId) {
    const roomName = entityId.replace("light.", "").replace(/_/g, " ");
    elements.commandInput.value = `toggle ${roomName} lights`;
    elements.commandForm.dispatchEvent(new Event("submit"));
}

/**
 * Update status indicator
 */
function updateStatusIndicator(status) {
    elements.statusIndicator.className = "status-badge";

    switch (status) {
        case "operational":
            elements.statusIndicator.classList.add("status-operational");
            elements.statusText.textContent = "Online";
            break;
        case "warning":
            elements.statusIndicator.classList.add("status-warning");
            elements.statusText.textContent = "Degraded";
            break;
        case "error":
            elements.statusIndicator.classList.add("status-error");
            elements.statusText.textContent = "Offline";
            break;
        default:
            elements.statusIndicator.classList.add("status-unknown");
            elements.statusText.textContent = "Unknown";
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// Make functions available globally
window.useHistoryCommand = useHistoryCommand;
window.toggleDevice = toggleDevice;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", init);
