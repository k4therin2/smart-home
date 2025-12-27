/**
 * Smart Home Assistant - Web UI JavaScript
 * Handles command submission, voice input, UI updates, and PWA features
 *
 * REQ-017: Mobile-Optimized Web Interface
 * - Touch-optimized controls
 * - iOS Safari voice input (webkitSpeechRecognition)
 * - Web Notifications API support
 * - Service Worker for offline/PWA
 */

// State
const state = {
    history: [],
    isListening: false,
    recognition: null,
    serviceWorkerRegistration: null,
    notificationPermission: 'default'
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

    // PWA features
    registerServiceWorker();
    initNotifications();

    // Refresh device status every 30 seconds
    setInterval(checkSystemStatus, 30000);

    // Check for voice shortcut parameter (?voice=true)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('voice') === 'true') {
        // Small delay to ensure everything is loaded
        setTimeout(() => toggleVoiceInput(), 500);
    }
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

/**
 * Register Service Worker for PWA functionality
 */
async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
        console.log('Service Worker not supported');
        return;
    }

    try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
            scope: '/'
        });

        state.serviceWorkerRegistration = registration;
        console.log('Service Worker registered:', registration.scope);

        // Handle updates
        registration.addEventListener('updatefound', () => {
            const newWorker = registration.installing;
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    // New version available, could prompt user to refresh
                    console.log('New version available');
                }
            });
        });
    } catch (error) {
        console.error('Service Worker registration failed:', error);
    }
}

/**
 * Initialize Web Notifications
 */
function initNotifications() {
    if (!('Notification' in window)) {
        console.log('Notifications not supported');
        return;
    }

    state.notificationPermission = Notification.permission;

    // If permission is default, we'll ask later when needed
    if (Notification.permission === 'granted') {
        console.log('Notifications enabled');
    }
}

/**
 * Request notification permission
 * Call this before showing notifications
 */
async function requestNotificationPermission() {
    if (!('Notification' in window)) {
        return false;
    }

    if (Notification.permission === 'granted') {
        state.notificationPermission = 'granted';
        return true;
    }

    if (Notification.permission === 'denied') {
        state.notificationPermission = 'denied';
        return false;
    }

    // Request permission
    const permission = await Notification.requestPermission();
    state.notificationPermission = permission;
    return permission === 'granted';
}

/**
 * Show a notification to the user
 * @param {string} title - Notification title
 * @param {Object} options - Notification options
 */
async function showNotification(title, options = {}) {
    const hasPermission = await requestNotificationPermission();

    if (!hasPermission) {
        console.log('Notification permission not granted');
        return null;
    }

    const defaultOptions = {
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-72.png',
        vibrate: [100, 50, 100],
        tag: 'smarthome-notification',
        renotify: true
    };

    // Use service worker to show notification (works when app is in background)
    if (state.serviceWorkerRegistration) {
        return state.serviceWorkerRegistration.showNotification(title, {
            ...defaultOptions,
            ...options
        });
    }

    // Fallback to regular notification
    return new Notification(title, { ...defaultOptions, ...options });
}

/**
 * Show notification for command result
 * @param {string} command - The command that was executed
 * @param {Object} response - The response from the server
 */
function notifyCommandResult(command, response) {
    // Only notify if the app is in background
    if (document.visibilityState === 'visible') {
        return;
    }

    showNotification('Smart Home', {
        body: response.response || 'Command executed',
        tag: 'command-result',
        data: { command }
    });
}

/**
 * Check if app is installed as PWA
 */
function isPWA() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.navigator.standalone === true;
}

// =============================================================================
// TODO LIST FUNCTIONALITY (WP-4.1)
// =============================================================================

// Todo state
const todoState = {
    currentList: 'default',
    showCompleted: false,
    todos: []
};

/**
 * Initialize todo list functionality
 */
function initTodos() {
    const todoForm = document.getElementById('todo-add-form');
    const todoTabs = document.querySelectorAll('.todo-tab');
    const showCompletedCheckbox = document.getElementById('show-completed');

    if (todoForm) {
        todoForm.addEventListener('submit', handleAddTodo);
    }

    if (todoTabs) {
        todoTabs.forEach(tab => {
            tab.addEventListener('click', () => switchTodoList(tab.dataset.list));
        });
    }

    if (showCompletedCheckbox) {
        showCompletedCheckbox.addEventListener('change', (event) => {
            todoState.showCompleted = event.target.checked;
            loadTodos();
        });
    }

    // Load initial todos
    loadTodos();
}

/**
 * Load todos from API
 */
async function loadTodos() {
    const todoList = document.getElementById('todo-list');
    if (!todoList) return;

    try {
        const params = new URLSearchParams({
            list_name: todoState.currentList,
            show_completed: todoState.showCompleted.toString()
        });

        const response = await fetch(`/api/todos?${params}`);
        const data = await response.json();

        if (data.success) {
            todoState.todos = data.todos;
            renderTodos();
        } else {
            todoList.innerHTML = '<li class="todo-error">Error loading todos</li>';
        }
    } catch (error) {
        console.error('Error loading todos:', error);
        todoList.innerHTML = '<li class="todo-error">Error loading todos</li>';
    }
}

/**
 * Render todos to the list
 */
function renderTodos() {
    const todoList = document.getElementById('todo-list');
    if (!todoList) return;

    if (todoState.todos.length === 0) {
        todoList.innerHTML = '<li class="placeholder-text">No items in this list</li>';
        return;
    }

    // Group by category for shopping list
    const isShoppingList = todoState.currentList === 'shopping';
    let todos = todoState.todos;

    if (isShoppingList) {
        // Sort by category, then by priority
        todos = [...todos].sort((a, b) => {
            const catA = a.category || 'other';
            const catB = b.category || 'other';
            if (catA !== catB) return catA.localeCompare(catB);
            return b.priority - a.priority;
        });
    }

    todoList.innerHTML = todos.map(todo => {
        const priorityClass = todo.priority > 0 ? `priority-${todo.priority === 2 ? 'urgent' : 'high'}` : '';
        const completedClass = todo.status === 'completed' ? 'completed' : '';
        const categoryBadge = isShoppingList && todo.category
            ? `<span class="todo-category category-${todo.category}">${todo.category}</span>`
            : '';

        return `
            <li class="todo-item ${priorityClass} ${completedClass}" data-id="${todo.id}">
                <button
                    class="todo-checkbox"
                    onclick="toggleTodoComplete(${todo.id}, '${todo.status}')"
                    aria-label="${todo.status === 'completed' ? 'Mark incomplete' : 'Mark complete'}"
                >
                    ${todo.status === 'completed' ? '✓' : '○'}
                </button>
                <span class="todo-content">${escapeHtml(todo.content)}</span>
                ${categoryBadge}
                <button
                    class="todo-delete"
                    onclick="deleteTodoItem(${todo.id})"
                    aria-label="Delete todo"
                >
                    ×
                </button>
            </li>
        `;
    }).join('');
}

/**
 * Switch to a different todo list
 */
function switchTodoList(listName) {
    todoState.currentList = listName;

    // Update tab selection
    document.querySelectorAll('.todo-tab').forEach(tab => {
        const isSelected = tab.dataset.list === listName;
        tab.classList.toggle('active', isSelected);
        tab.setAttribute('aria-selected', isSelected.toString());
    });

    loadTodos();
}

/**
 * Handle adding a new todo
 */
async function handleAddTodo(event) {
    event.preventDefault();

    const input = document.getElementById('todo-input');
    const content = input.value.trim();

    if (!content) return;

    try {
        const response = await fetch('/api/todos', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content,
                list_name: todoState.currentList,
                priority: 'normal'
            })
        });

        const data = await response.json();

        if (data.success) {
            input.value = '';
            loadTodos();
        } else {
            alert('Error adding todo: ' + data.error);
        }
    } catch (error) {
        console.error('Error adding todo:', error);
        alert('Error adding todo');
    }
}

/**
 * Toggle todo complete/incomplete
 */
async function toggleTodoComplete(todoId, currentStatus) {
    if (currentStatus === 'completed') {
        // Already completed - no uncomplete API yet
        return;
    }

    try {
        const response = await fetch(`/api/todos/${todoId}/complete`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            loadTodos();
        }
    } catch (error) {
        console.error('Error completing todo:', error);
    }
}

/**
 * Delete a todo item
 */
async function deleteTodoItem(todoId) {
    if (!confirm('Delete this item?')) return;

    try {
        const response = await fetch(`/api/todos/${todoId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            loadTodos();
        }
    } catch (error) {
        console.error('Error deleting todo:', error);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// LOG VIEWER FUNCTIONALITY (WP-6.1)
// =============================================================================

// Log viewer state
const logState = {
    currentType: 'main',
    currentPage: 0,
    pageSize: 50,
    totalEntries: 0,
    minLevel: '',
    search: '',
    tailMode: false,
    tailInterval: null,
    lastPosition: 0
};

/**
 * Initialize log viewer functionality
 */
function initLogs() {
    const logsToggle = document.getElementById('logs-toggle');
    const logsPanel = document.getElementById('logs-panel');
    const logsTabs = document.querySelectorAll('.logs-tab');
    const levelFilter = document.getElementById('log-level-filter');
    const searchInput = document.getElementById('log-search');
    const refreshBtn = document.getElementById('logs-refresh-btn');
    const tailBtn = document.getElementById('logs-tail-btn');
    const exportBtn = document.getElementById('logs-export-btn');
    const prevBtn = document.getElementById('logs-prev');
    const nextBtn = document.getElementById('logs-next');

    // Toggle panel visibility
    if (logsToggle && logsPanel) {
        logsToggle.addEventListener('click', () => {
            const isExpanded = logsPanel.classList.toggle('collapsed');
            logsToggle.setAttribute('aria-expanded', (!isExpanded).toString());
            logsToggle.textContent = isExpanded ? '▼' : '▲';

            // Load logs on first expand
            if (!isExpanded && !logState.loaded) {
                logState.loaded = true;
                loadLogs();
            }
        });
    }

    // Log type tabs
    if (logsTabs) {
        logsTabs.forEach(tab => {
            tab.addEventListener('click', () => switchLogType(tab.dataset.logType));
        });
    }

    // Level filter
    if (levelFilter) {
        levelFilter.addEventListener('change', () => {
            logState.minLevel = levelFilter.value;
            logState.currentPage = 0;
            loadLogs();
        });
    }

    // Search with debounce
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                logState.search = searchInput.value;
                logState.currentPage = 0;
                loadLogs();
            }, 300);
        });
    }

    // Action buttons
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadLogs);
    }

    if (tailBtn) {
        tailBtn.addEventListener('click', toggleTailMode);
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', exportLogs);
    }

    // Pagination
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (logState.currentPage > 0) {
                logState.currentPage--;
                loadLogs();
            }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const maxPage = Math.ceil(logState.totalEntries / logState.pageSize) - 1;
            if (logState.currentPage < maxPage) {
                logState.currentPage++;
                loadLogs();
            }
        });
    }
}

/**
 * Switch log type tab
 */
function switchLogType(logType) {
    logState.currentType = logType;
    logState.currentPage = 0;

    // Update tab selection
    document.querySelectorAll('.logs-tab').forEach(tab => {
        const isSelected = tab.dataset.logType === logType;
        tab.classList.toggle('active', isSelected);
        tab.setAttribute('aria-selected', isSelected.toString());
    });

    loadLogs();
}

/**
 * Load logs from API
 */
async function loadLogs() {
    const container = document.getElementById('logs-container');
    if (!container) return;

    container.innerHTML = '<p class="loading-text">Loading logs...</p>';

    try {
        const params = new URLSearchParams({
            log_type: logState.currentType,
            offset: (logState.currentPage * logState.pageSize).toString(),
            limit: logState.pageSize.toString(),
            reverse: 'true'
        });

        if (logState.minLevel) {
            params.set('min_level', logState.minLevel);
        }

        if (logState.search) {
            params.set('search', logState.search);
        }

        const response = await fetch(`/api/logs?${params}`);
        const data = await response.json();

        if (data.success !== false) {
            logState.totalEntries = data.total || 0;
            renderLogs(data.entries || []);
            updateLogStats(data);
            updatePagination();
        } else {
            container.innerHTML = '<p class="error-text">Error loading logs</p>';
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        container.innerHTML = '<p class="error-text">Error loading logs</p>';
    }
}

/**
 * Render log entries
 */
function renderLogs(entries) {
    const container = document.getElementById('logs-container');
    if (!container) return;

    if (entries.length === 0) {
        container.innerHTML = '<p class="placeholder-text">No log entries found</p>';
        return;
    }

    container.innerHTML = entries.map(entry => {
        const levelClass = `log-level-${entry.level.toLowerCase()}`;
        const time = new Date(entry.timestamp).toLocaleTimeString();
        const date = new Date(entry.timestamp).toLocaleDateString();

        return `
            <div class="log-entry ${levelClass}">
                <span class="log-time" title="${date}">${time}</span>
                <span class="log-level">${entry.level}</span>
                <span class="log-module">${escapeHtml(entry.module)}</span>
                <span class="log-message">${escapeHtml(entry.message)}</span>
            </div>
        `;
    }).join('');
}

/**
 * Update log statistics display
 */
function updateLogStats(data) {
    const countEl = document.getElementById('log-count');
    if (countEl) {
        countEl.textContent = (data.total || 0).toLocaleString();
    }
}

/**
 * Update pagination controls
 */
function updatePagination() {
    const prevBtn = document.getElementById('logs-prev');
    const nextBtn = document.getElementById('logs-next');
    const pageInfo = document.getElementById('logs-page-info');

    const maxPage = Math.max(0, Math.ceil(logState.totalEntries / logState.pageSize) - 1);

    if (prevBtn) {
        prevBtn.disabled = logState.currentPage <= 0;
    }

    if (nextBtn) {
        nextBtn.disabled = logState.currentPage >= maxPage;
    }

    if (pageInfo) {
        pageInfo.textContent = `Page ${logState.currentPage + 1} of ${maxPage + 1}`;
    }
}

/**
 * Toggle real-time tail mode
 */
function toggleTailMode() {
    const tailBtn = document.getElementById('logs-tail-btn');

    logState.tailMode = !logState.tailMode;

    if (tailBtn) {
        tailBtn.classList.toggle('active', logState.tailMode);
        tailBtn.setAttribute('aria-pressed', logState.tailMode.toString());
        tailBtn.textContent = logState.tailMode ? '⏸' : '▶';
    }

    if (logState.tailMode) {
        // Start polling for new entries
        logState.currentPage = 0;
        loadLogs();
        logState.tailInterval = setInterval(tailLogs, 3000);
    } else {
        // Stop polling
        if (logState.tailInterval) {
            clearInterval(logState.tailInterval);
            logState.tailInterval = null;
        }
    }
}

/**
 * Tail logs for new entries
 */
async function tailLogs() {
    if (!logState.tailMode) return;

    try {
        const params = new URLSearchParams({
            lines: '10'
        });

        if (logState.lastPosition > 0) {
            params.set('from_position', logState.lastPosition.toString());
        }

        const response = await fetch(`/api/logs/tail?${params}`);
        const data = await response.json();

        if (data.success !== false && data.entries && data.entries.length > 0) {
            logState.lastPosition = data.position || 0;

            // Prepend new entries
            const container = document.getElementById('logs-container');
            if (container) {
                const newHtml = data.entries.map(entry => {
                    const levelClass = `log-level-${entry.level.toLowerCase()}`;
                    const time = new Date(entry.timestamp).toLocaleTimeString();
                    const date = new Date(entry.timestamp).toLocaleDateString();

                    return `
                        <div class="log-entry ${levelClass} log-entry-new">
                            <span class="log-time" title="${date}">${time}</span>
                            <span class="log-level">${entry.level}</span>
                            <span class="log-module">${escapeHtml(entry.module)}</span>
                            <span class="log-message">${escapeHtml(entry.message)}</span>
                        </div>
                    `;
                }).join('');

                container.insertAdjacentHTML('afterbegin', newHtml);

                // Limit displayed entries
                const allEntries = container.querySelectorAll('.log-entry');
                if (allEntries.length > 100) {
                    for (let i = 100; i < allEntries.length; i++) {
                        allEntries[i].remove();
                    }
                }
            }
        }
    } catch (error) {
        console.error('Error tailing logs:', error);
    }
}

/**
 * Export logs to file
 */
async function exportLogs() {
    try {
        const params = new URLSearchParams({
            format: 'json',
            download: 'true',
            log_type: logState.currentType
        });

        if (logState.minLevel) {
            params.set('min_level', logState.minLevel);
        }

        // Create download link
        const link = document.createElement('a');
        link.href = `/api/logs/export?${params}`;
        link.download = `logs_${logState.currentType}_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error exporting logs:', error);
        alert('Error exporting logs');
    }
}

// Make functions available globally
window.useHistoryCommand = useHistoryCommand;
window.toggleDevice = toggleDevice;
window.showNotification = showNotification;
window.requestNotificationPermission = requestNotificationPermission;
window.toggleTodoComplete = toggleTodoComplete;
window.deleteTodoItem = deleteTodoItem;
window.switchTodoList = switchTodoList;
window.switchLogType = switchLogType;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    init();
    initTodos();
    initLogs();
});
