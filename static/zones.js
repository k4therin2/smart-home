/**
 * Zones & Device Onboarding UI
 * WP-8.2: Device Onboarding & Organization System - Web UI
 */

// State management
const state = {
    zones: [],
    rooms: [],
    onboarding: {
        active: false,
        session: null,
        lights: [],
        mappings: {},
        selectedColor: null
    }
};

// DOM Elements
const elements = {
    // Toolbar buttons
    syncHaBtn: null,
    startOnboardingBtn: null,
    syncHueBtn: null,

    // Zones container
    zonesList: null,
    unassignedList: null,

    // Onboarding wizard
    wizard: null,
    colorBadges: null,
    roomSelection: null,
    selectedColor: null,
    roomSelect: null,
    confirmMappingBtn: null,
    identifiedItems: null,
    progressFill: null,
    progressText: null,
    cancelOnboardingBtn: null,
    applyMappingsBtn: null,
    closeWizardBtn: null
};

/**
 * Initialize the zones page
 */
async function init() {
    // Get DOM elements
    elements.syncHaBtn = document.getElementById('sync-ha-btn');
    elements.startOnboardingBtn = document.getElementById('start-onboarding-btn');
    elements.syncHueBtn = document.getElementById('sync-hue-btn');
    elements.zonesList = document.getElementById('zones-list');
    elements.unassignedList = document.getElementById('unassigned-list');
    elements.wizard = document.getElementById('onboarding-wizard');
    elements.colorBadges = document.getElementById('color-badges');
    elements.roomSelection = document.getElementById('room-selection');
    elements.selectedColor = document.getElementById('selected-color');
    elements.roomSelect = document.getElementById('room-select');
    elements.confirmMappingBtn = document.getElementById('confirm-mapping-btn');
    elements.identifiedItems = document.getElementById('identified-items');
    elements.progressFill = document.getElementById('progress-fill');
    elements.progressText = document.getElementById('progress-text');
    elements.cancelOnboardingBtn = document.getElementById('cancel-onboarding-btn');
    elements.applyMappingsBtn = document.getElementById('apply-mappings-btn');
    elements.closeWizardBtn = document.getElementById('close-wizard-btn');

    // Set up event listeners
    setupEventListeners();

    // Load initial data
    await loadZones();
    await loadRooms();
    await checkOnboardingStatus();
}

/**
 * Set up event listeners for buttons and interactions
 */
function setupEventListeners() {
    elements.syncHaBtn.addEventListener('click', handleSyncFromHA);
    elements.startOnboardingBtn.addEventListener('click', handleStartOnboarding);
    elements.syncHueBtn.addEventListener('click', handleSyncToHue);
    elements.cancelOnboardingBtn.addEventListener('click', handleCancelOnboarding);
    elements.applyMappingsBtn.addEventListener('click', handleApplyMappings);
    elements.closeWizardBtn.addEventListener('click', handleCloseWizard);
    elements.confirmMappingBtn.addEventListener('click', handleConfirmMapping);
}

/**
 * Load zones from API
 */
async function loadZones() {
    try {
        const response = await fetch('/api/zones');
        const data = await response.json();

        if (data.success) {
            state.zones = data.zones;
            renderZones();
        } else {
            showError('Failed to load zones: ' + data.error);
        }
    } catch (error) {
        showError('Network error loading zones');
        console.error('Error loading zones:', error);
    }
}

/**
 * Load rooms from API
 */
async function loadRooms() {
    try {
        const response = await fetch('/api/rooms');
        const data = await response.json();

        if (data.success) {
            state.rooms = data.rooms;
            populateRoomDropdown();
        } else {
            showError('Failed to load rooms: ' + data.error);
        }
    } catch (error) {
        showError('Network error loading rooms');
        console.error('Error loading rooms:', error);
    }
}

/**
 * Render zones in the UI
 */
function renderZones() {
    if (state.zones.length === 0) {
        elements.zonesList.innerHTML = '<p class="empty-message">No zones configured. Use "Sync from HA" to import devices.</p>';
        return;
    }

    let html = '';

    state.zones.forEach(zone => {
        html += \`
            <div class="zone-card" data-zone="\${zone.name}">
                <div class="zone-header">
                    <h3 class="zone-title">\${zone.display_name || zone.name}</h3>
                    <span class="zone-count">\${zone.rooms?.length || 0} rooms</span>
                </div>
                <div class="zone-rooms">
        \`;

        if (zone.rooms && zone.rooms.length > 0) {
            zone.rooms.forEach(room => {
                html += \`
                    <div class="room-card" data-room="\${room.name}">
                        <span class="room-name">\${room.display_name || room.name}</span>
                        <span class="device-count">\${room.device_count || 0} devices</span>
                    </div>
                \`;
            });
        } else {
            html += '<p class="empty-rooms">No rooms in this zone</p>';
        }

        html += \`
                </div>
            </div>
        \`;
    });

    elements.zonesList.innerHTML = html;
}

/**
 * Populate room dropdown for onboarding wizard
 */
function populateRoomDropdown() {
    // Clear existing options except the placeholder
    elements.roomSelect.innerHTML = '<option value="">Select a room...</option>';

    // Add "Create new room" option
    elements.roomSelect.innerHTML += '<option value="__new__">+ Create new room</option>';

    // Add existing rooms
    state.rooms.forEach(room => {
        elements.roomSelect.innerHTML += \`<option value="\${room.name}">\${room.display_name || room.name}</option>\`;
    });
}

/**
 * Check if there's an active onboarding session
 */
async function checkOnboardingStatus() {
    try {
        const response = await fetch('/api/onboarding/status');
        const data = await response.json();

        if (data.success && data.active) {
            state.onboarding.active = true;
            state.onboarding.session = data.session;
            state.onboarding.lights = data.lights || [];
            showOnboardingWizard();
            renderColorBadges();
            updateProgress();
        }
    } catch (error) {
        console.error('Error checking onboarding status:', error);
    }
}

/**
 * Handle Sync from HA button click
 */
async function handleSyncFromHA() {
    elements.syncHaBtn.disabled = true;
    elements.syncHaBtn.textContent = 'Syncing...';

    try {
        const response = await fetch('/api/devices/sync-ha', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showSuccess(\`Synced \${data.result?.synced || 0} devices from Home Assistant\`);
            await loadZones();
            await loadRooms();
        } else {
            showError('Sync failed: ' + data.error);
        }
    } catch (error) {
        showError('Network error during sync');
        console.error('Error syncing from HA:', error);
    } finally {
        elements.syncHaBtn.disabled = false;
        elements.syncHaBtn.innerHTML = \`
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16"/>
            </svg>
            Sync from HA
        \`;
    }
}

/**
 * Handle Start Onboarding button click
 */
async function handleStartOnboarding() {
    elements.startOnboardingBtn.disabled = true;

    try {
        const response = await fetch('/api/onboarding/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skip_organized: true })
        });
        const data = await response.json();

        if (data.success) {
            state.onboarding.active = true;
            state.onboarding.session = data.session;
            state.onboarding.lights = data.lights || [];
            state.onboarding.mappings = {};
            showOnboardingWizard();
            renderColorBadges();
            updateProgress();
            showSuccess('Onboarding started! Identify each light by its color.');
        } else {
            showError('Failed to start onboarding: ' + data.error);
        }
    } catch (error) {
        showError('Network error starting onboarding');
        console.error('Error starting onboarding:', error);
    } finally {
        elements.startOnboardingBtn.disabled = false;
    }
}

/**
 * Handle Sync to Hue button click
 */
async function handleSyncToHue() {
    elements.syncHueBtn.disabled = true;
    elements.syncHueBtn.textContent = 'Syncing...';

    try {
        const response = await fetch('/api/onboarding/sync-hue', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showSuccess('Room mappings synced to Hue bridge!');
        } else {
            showError('Hue sync failed: ' + data.error);
        }
    } catch (error) {
        showError('Network error syncing to Hue');
        console.error('Error syncing to Hue:', error);
    } finally {
        elements.syncHueBtn.disabled = false;
        elements.syncHueBtn.innerHTML = \`
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8"/>
            </svg>
            Sync to Hue
        \`;
    }
}

/**
 * Show the onboarding wizard
 */
function showOnboardingWizard() {
    elements.wizard.classList.remove('hidden');
}

/**
 * Hide the onboarding wizard
 */
function hideOnboardingWizard() {
    elements.wizard.classList.add('hidden');
    elements.roomSelection.classList.add('hidden');
    state.onboarding.selectedColor = null;
}

/**
 * Render color badges for each light
 */
function renderColorBadges() {
    if (!state.onboarding.lights || state.onboarding.lights.length === 0) {
        elements.colorBadges.innerHTML = '<p class="empty-message">No lights found to onboard.</p>';
        return;
    }

    let html = '';
    state.onboarding.lights.forEach(light => {
        const identified = state.onboarding.mappings[light.color_name];
        const identifiedClass = identified ? 'identified' : '';

        html += \`
            <button
                class="color-badge \${identifiedClass}"
                data-color="\${light.color_name}"
                style="background-color: \${getColorValue(light.color_name)}"
                title="\${light.entity_id}"
            >
                \${light.color_name}
                \${identified ? '<span class="check-mark">&#10003;</span>' : ''}
            </button>
        \`;
    });

    elements.colorBadges.innerHTML = html;

    // Add click handlers to badges
    document.querySelectorAll('.color-badge').forEach(badge => {
        badge.addEventListener('click', (e) => handleColorBadgeClick(e.currentTarget.dataset.color));
    });
}

/**
 * Handle color badge click
 */
function handleColorBadgeClick(colorName) {
    state.onboarding.selectedColor = colorName;
    elements.selectedColor.textContent = colorName;
    elements.roomSelection.classList.remove('hidden');

    // Highlight selected badge
    document.querySelectorAll('.color-badge').forEach(badge => {
        badge.classList.toggle('selected', badge.dataset.color === colorName);
    });
}

/**
 * Handle confirm mapping button click
 */
async function handleConfirmMapping() {
    const colorName = state.onboarding.selectedColor;
    const roomValue = elements.roomSelect.value;

    if (!colorName || !roomValue) {
        showError('Please select a room');
        return;
    }

    let roomName = roomValue;

    // Handle "Create new room" option
    if (roomValue === '__new__') {
        roomName = prompt('Enter the name for the new room:');
        if (!roomName) return;
        roomName = roomName.trim().toLowerCase().replace(/\s+/g, '_');
    }

    elements.confirmMappingBtn.disabled = true;

    try {
        const response = await fetch('/api/onboarding/identify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                color_name: colorName,
                room_name: roomName
            })
        });
        const data = await response.json();

        if (data.success) {
            state.onboarding.mappings[colorName] = roomName;
            renderColorBadges();
            updateProgress();
            updateIdentifiedList();
            elements.roomSelection.classList.add('hidden');
            elements.roomSelect.value = '';
        } else {
            showError('Failed to identify light: ' + data.error);
        }
    } catch (error) {
        showError('Network error');
        console.error('Error identifying light:', error);
    } finally {
        elements.confirmMappingBtn.disabled = false;
    }
}

/**
 * Update progress bar and text
 */
function updateProgress() {
    const total = state.onboarding.lights.length;
    const identified = Object.keys(state.onboarding.mappings).length;
    const percentage = total > 0 ? Math.round((identified / total) * 100) : 0;

    elements.progressFill.style.width = \`\${percentage}%\`;
    elements.progressText.textContent = \`\${identified} / \${total} lights identified (\${percentage}%)\`;

    // Enable apply button when all lights are identified
    elements.applyMappingsBtn.disabled = identified === 0 || identified < total;
}

/**
 * Update the identified lights list
 */
function updateIdentifiedList() {
    let html = '';
    Object.entries(state.onboarding.mappings).forEach(([color, room]) => {
        html += \`<li><span class="color-label" style="background: \${getColorValue(color)}">\${color}</span> &rarr; \${room}</li>\`;
    });
    elements.identifiedItems.innerHTML = html || '<li class="empty">No lights identified yet</li>';
}

/**
 * Handle cancel onboarding button click
 */
async function handleCancelOnboarding() {
    if (!confirm('Cancel onboarding? All progress will be lost.')) return;

    try {
        const response = await fetch('/api/onboarding/cancel', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            resetOnboardingState();
            hideOnboardingWizard();
            showSuccess('Onboarding cancelled');
        } else {
            showError('Failed to cancel: ' + data.error);
        }
    } catch (error) {
        showError('Network error');
        console.error('Error cancelling onboarding:', error);
    }
}

/**
 * Handle close wizard button (X button)
 */
function handleCloseWizard() {
    handleCancelOnboarding();
}

/**
 * Handle apply mappings button click
 */
async function handleApplyMappings() {
    elements.applyMappingsBtn.disabled = true;
    elements.applyMappingsBtn.textContent = 'Applying...';

    try {
        const response = await fetch('/api/onboarding/apply', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showSuccess(\`Applied \${data.result?.mapped_count || 0} room mappings!\`);
            resetOnboardingState();
            hideOnboardingWizard();
            await loadZones();
            await loadRooms();
        } else {
            showError('Failed to apply mappings: ' + data.error);
        }
    } catch (error) {
        showError('Network error');
        console.error('Error applying mappings:', error);
    } finally {
        elements.applyMappingsBtn.disabled = false;
        elements.applyMappingsBtn.textContent = 'Apply All Mappings';
    }
}

/**
 * Reset onboarding state
 */
function resetOnboardingState() {
    state.onboarding.active = false;
    state.onboarding.session = null;
    state.onboarding.lights = [];
    state.onboarding.mappings = {};
    state.onboarding.selectedColor = null;
    elements.identifiedItems.innerHTML = '';
    elements.progressFill.style.width = '0%';
    elements.progressText.textContent = '0 / 0 lights identified (0%)';
}

/**
 * Get CSS color value for a color name
 */
function getColorValue(colorName) {
    const colorMap = {
        red: '#ff4444',
        orange: '#ff8c00',
        yellow: '#ffdd00',
        green: '#44ff44',
        cyan: '#00ddff',
        blue: '#4444ff',
        purple: '#9944ff',
        pink: '#ff44aa',
        white: '#ffffff',
        magenta: '#ff00ff',
        lime: '#00ff00',
        teal: '#008888',
        coral: '#ff7f50',
        gold: '#ffd700',
        lavender: '#e6e6fa'
    };
    return colorMap[colorName.toLowerCase()] || '#888888';
}

/**
 * Show a success message
 */
function showSuccess(message) {
    showNotification(message, 'success');
}

/**
 * Show an error message
 */
function showError(message) {
    showNotification(message, 'error');
}

/**
 * Show a notification toast
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    document.querySelectorAll('.notification').forEach(n => n.remove());

    const notification = document.createElement('div');
    notification.className = \`notification notification-\${type}\`;
    notification.textContent = message;
    document.body.appendChild(notification);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
