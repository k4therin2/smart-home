/**
 * Voice Pipeline Diagnostics - Frontend Logic
 *
 * WP-9.2: Voice Pipeline Diagnostic Suite (Christmas Gift 2025)
 */

document.addEventListener('DOMContentLoaded', function() {
    const runButton = document.getElementById('runDiagnostics');
    const resultsContainer = document.getElementById('results');
    const testResultsContainer = document.getElementById('testResults');

    // Test name to step mapping
    const testToStep = {
        'Voice Puck Connectivity': 'step-1',
        'HA Assist Pipeline': 'step-2',
        'SmartHome Webhook': 'step-3',
        'SmartHome Voice Endpoint': 'step-4',
        'TTS Output': 'step-5'
    };

    runButton.addEventListener('click', runDiagnostics);

    async function runDiagnostics() {
        // Disable button and show running state
        runButton.disabled = true;
        runButton.classList.add('running');
        runButton.innerHTML = '<span class="loading-spinner"></span> Running...';

        // Reset pipeline visualization
        Object.values(testToStep).forEach(stepId => {
            const icon = document.getElementById(stepId);
            icon.className = 'pipeline-icon running';
        });

        // Show results container
        resultsContainer.style.display = 'block';
        testResultsContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">Running diagnostics...</p>';

        try {
            const response = await fetch('/api/diagnostics/voice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            displayResults(data);

        } catch (error) {
            console.error('Diagnostic error:', error);
            testResultsContainer.innerHTML = `
                <div class="test-result">
                    <div class="test-header">
                        <span class="test-name">Error Running Diagnostics</span>
                        <div class="test-status">
                            <div class="test-status-icon failed">!</div>
                        </div>
                    </div>
                    <div class="test-details expanded">
                        <div class="test-message">${error.message}</div>
                        <div class="fix-suggestions">
                            <h4>Suggestions</h4>
                            <ul>
                                <li>Check if the SmartHome server is running</li>
                                <li>Verify you are logged in</li>
                                <li>Check browser console for errors</li>
                            </ul>
                        </div>
                    </div>
                </div>
            `;

            // Reset pipeline icons to failed state
            Object.values(testToStep).forEach(stepId => {
                const icon = document.getElementById(stepId);
                icon.className = 'pipeline-icon failed';
            });
        }

        // Re-enable button
        runButton.disabled = false;
        runButton.classList.remove('running');
        runButton.innerHTML = 'Run Full Diagnostic';
    }

    function displayResults(data) {
        // Update overall status
        const overallStatus = document.getElementById('overallStatus');
        const statusBadge = document.getElementById('statusBadge');

        overallStatus.className = 'overall-status ' + data.overall_status;
        statusBadge.className = 'status-badge ' + data.overall_status;
        statusBadge.textContent = data.overall_status.toUpperCase();

        // Update stats
        document.getElementById('passedCount').textContent = data.summary.passed;
        document.getElementById('failedCount').textContent = data.summary.failed;
        document.getElementById('warningCount').textContent = data.summary.warnings;
        document.getElementById('durationValue').textContent = Math.round(data.total_duration_ms);

        // Update pipeline visualization
        data.results.forEach(result => {
            const stepId = testToStep[result.name];
            if (stepId) {
                const icon = document.getElementById(stepId);
                icon.className = 'pipeline-icon ' + result.status;

                // Add checkmark/x to icon
                if (result.status === 'passed') {
                    icon.innerHTML = '<span style="font-size: 24px;">&#10003;</span>';
                } else if (result.status === 'failed') {
                    icon.innerHTML = '<span style="font-size: 24px;">&#10007;</span>';
                } else if (result.status === 'warning') {
                    icon.innerHTML = '<span style="font-size: 24px;">!</span>';
                }
            }
        });

        // Render individual test results
        testResultsContainer.innerHTML = data.results.map(result => renderTestResult(result)).join('');

        // Add click handlers for expandable details
        document.querySelectorAll('.test-header').forEach(header => {
            header.addEventListener('click', function() {
                const details = this.nextElementSibling;
                details.classList.toggle('expanded');
            });
        });
    }

    function renderTestResult(result) {
        const statusIcon = result.status === 'passed' ? '&#10003;' :
                          result.status === 'failed' ? '&#10007;' : '!';

        const fixSuggestionsHtml = result.fix_suggestions && result.fix_suggestions.length > 0
            ? `
                <div class="fix-suggestions">
                    <h4>Fix Suggestions</h4>
                    <ul>
                        ${result.fix_suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join('')}
                    </ul>
                </div>
            `
            : '';

        const detailsJson = Object.keys(result.details).length > 0
            ? `
                <details style="margin-top: 15px;">
                    <summary style="cursor: pointer; color: var(--primary-color, #4a90d9);">Technical Details</summary>
                    <pre class="details-json">${escapeHtml(JSON.stringify(result.details, null, 2))}</pre>
                </details>
            `
            : '';

        return `
            <div class="test-result">
                <div class="test-header">
                    <span class="test-name">${escapeHtml(result.name)}</span>
                    <div class="test-status">
                        <span>${result.duration_ms.toFixed(0)}ms</span>
                        <div class="test-status-icon ${result.status}">${statusIcon}</div>
                    </div>
                </div>
                <div class="test-details ${result.status !== 'passed' ? 'expanded' : ''}">
                    <div class="test-message">${escapeHtml(result.message)}</div>
                    ${fixSuggestionsHtml}
                    ${detailsJson}
                </div>
            </div>
        `;
    }

    function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return unsafe;
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
