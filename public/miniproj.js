/**
 * Samsung Innovation Campus (SIC8) - IoT Track
 * Smart Factory Telemetry & Interactive Control Dashboard
 * Features:
 *   - 24/7 Cloud Server primary connection with automatic Localhost fallback
 *   - Live latency measurement & dynamic failover recovery
 *   - Deployed site (https://iotnexa-sic.web.app) and direct cloud access support
 */

const totalMachines = 5;
const dashboard = document.getElementById('dashboard');
const telemetryStatusEl = document.getElementById('telemetry-status');
const activeUnitsEl = document.getElementById('stat-active-units');
const alertsFeedEl = document.getElementById('alerts-feed');

// Gateway toolbar elements
const gwStatusDot = document.getElementById('gw-status-dot');
const gwStatusText = document.getElementById('gw-status-text');
const activeEndpointPill = document.getElementById('active-endpoint-pill');
const gwLatencyBadge = document.getElementById('gw-latency-badge');
const blynkSyncLabel = document.getElementById('blynk-sync-label');

const modeAutoBtn = document.getElementById('mode-auto-btn');
const modeCloudBtn = document.getElementById('mode-cloud-btn');
const modeLocalBtn = document.getElementById('mode-local-btn');
const cloudUrlInput = document.getElementById('cloud-url-input');
const cloudUrlSaveBtn = document.getElementById('cloud-url-save-btn');
const testPingBtn = document.getElementById('test-ping-btn');

// --- Multi-Endpoint & 24/7 Cloud Failover Configuration ---
const LOCAL_GATEWAY_URL = 'http://localhost:8080';

function getInitialCloudUrl() {
    // 1. URL Query Param: ?server=... or ?cloud=...
    const params = new URLSearchParams(window.location.search);
    const queryServer = params.get('server') || params.get('cloud');
    if (queryServer) {
        let clean = queryServer.trim().replace(/\/+$/, '');
        if (!clean.startsWith('http://') && !clean.startsWith('https://')) clean = 'http://' + clean;
        localStorage.setItem('sic_cloud_gateway_url', clean);
        return clean;
    }
    // 2. Saved in localStorage
    const saved = localStorage.getItem('sic_cloud_gateway_url') || localStorage.getItem('sic_gateway_url');
    if (saved && !saved.includes('localhost') && !saved.includes('127.0.0.1')) {
        return saved.trim().replace(/\/+$/, '');
    }

    // 3. If accessed directly on non-localhost/Firebase IP/domain (e.g. running on Cloud VPS)
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1' && !host.includes('web.app') && !host.includes('firebaseapp.com')) {
        return window.location.origin;
    }
    return '';
}

let CLOUD_GATEWAY_URL = getInitialCloudUrl();
let connectionMode = localStorage.getItem('sic_conn_mode') || 'auto'; // 'auto' | 'cloud' | 'local'
let activeGatewayUrl = (connectionMode === 'local' || !CLOUD_GATEWAY_URL) ? LOCAL_GATEWAY_URL : CLOUD_GATEWAY_URL;
let activeSource = 'connecting'; // 'cloud' | 'local' | 'offline'
let lastCloudProbeTime = 0;
let isFetching = false;

function updateModeButtonsUI() {
    if (modeAutoBtn) modeAutoBtn.classList.toggle('active', connectionMode === 'auto');
    if (modeCloudBtn) modeCloudBtn.classList.toggle('active', connectionMode === 'cloud');
    if (modeLocalBtn) modeLocalBtn.classList.toggle('active', connectionMode === 'local');
}

function setConnectionMode(mode) {
    connectionMode = mode;
    localStorage.setItem('sic_conn_mode', mode);
    updateModeButtonsUI();
    if (mode === 'local') {
        activeGatewayUrl = LOCAL_GATEWAY_URL;
        activeSource = 'local';
    } else if (mode === 'cloud') {
        activeGatewayUrl = CLOUD_GATEWAY_URL || LOCAL_GATEWAY_URL;
        activeSource = 'cloud';
    } else {
        // Auto
        activeGatewayUrl = CLOUD_GATEWAY_URL ? CLOUD_GATEWAY_URL : LOCAL_GATEWAY_URL;
        activeSource = CLOUD_GATEWAY_URL ? 'cloud' : 'local';
    }
    fetchMachineData();
}

if (modeAutoBtn) modeAutoBtn.addEventListener('click', () => setConnectionMode('auto'));
if (modeCloudBtn) modeCloudBtn.addEventListener('click', () => setConnectionMode('cloud'));
if (modeLocalBtn) modeLocalBtn.addEventListener('click', () => setConnectionMode('local'));

if (cloudUrlInput) {
    cloudUrlInput.value = CLOUD_GATEWAY_URL;
}

if (cloudUrlSaveBtn) {
    cloudUrlSaveBtn.addEventListener('click', () => {
        let val = (cloudUrlInput.value || '').trim().replace(/\/+$/, '');
        if (val && !val.startsWith('http://') && !val.startsWith('https://')) {
            val = 'http://' + val;
        }
        CLOUD_GATEWAY_URL = val;
        localStorage.setItem('sic_cloud_gateway_url', val);
        if (cloudUrlInput) cloudUrlInput.value = val;
        if (connectionMode === 'local') {
            setConnectionMode('auto');
        } else {
            activeGatewayUrl = CLOUD_GATEWAY_URL || LOCAL_GATEWAY_URL;
            activeSource = 'cloud';
            fetchMachineData();
        }
    });
}

if (testPingBtn) {
    testPingBtn.addEventListener('click', async () => {
        const target = activeGatewayUrl || LOCAL_GATEWAY_URL;
        testPingBtn.textContent = '⏳ ...';
        const start = performance.now();
        try {
            const res = await fetch(`${target}/api/health`, {
                signal: AbortSignal.timeout(3000),
                headers: { 'Accept': 'application/json' }
            });
            const ping = Math.round(performance.now() - start);
            if (res.ok) {
                testPingBtn.textContent = `✓ ${ping}ms`;
                testPingBtn.style.color = '#10b981';
            } else {
                testPingBtn.textContent = `✗ HTTP ${res.status}`;
                testPingBtn.style.color = '#f43f5e';
            }
        } catch (err) {
            testPingBtn.textContent = '✗ Fail';
            testPingBtn.style.color = '#f43f5e';
        }
        setTimeout(() => {
            testPingBtn.textContent = '⚡ Test';
            testPingBtn.style.color = '';
        }, 2500);
    });
}

updateModeButtonsUI();

function checkMixedContent(targetUrl) {
    const banner = document.getElementById('mixed-content-banner');
    const directLink = document.getElementById('direct-cloud-link');
    const originCode = document.getElementById('page-origin-code');
    if (!banner) return;

    const isPageHttps = window.location.protocol === 'https:';
    const isTargetHttp = targetUrl && targetUrl.startsWith('http://') && !targetUrl.includes('localhost') && !targetUrl.includes('127.0.0.1');

    if (isPageHttps && isTargetHttp) {
        banner.style.display = 'flex';
        if (originCode) originCode.textContent = window.location.origin;
        if (directLink) {
            directLink.href = targetUrl;
            directLink.textContent = `🚀 Open Direct Cloud Dashboard: ${targetUrl}`;
        }
    } else {
        banner.style.display = 'none';
    }
}

function updateGatewayStatusUI(source, statusMsg, endpointUrl, latencyMs) {
    if (activeEndpointPill) {
        activeEndpointPill.textContent = endpointUrl || '--';
        activeEndpointPill.title = `Active Gateway Endpoint: ${endpointUrl || 'None'}`;
    }

    if (gwLatencyBadge) {
        if (latencyMs !== null && latencyMs !== undefined) {
            gwLatencyBadge.textContent = `${latencyMs} ms`;
            gwLatencyBadge.className = latencyMs < 150 ? 'latency-badge' : (latencyMs < 400 ? 'latency-badge warn' : 'latency-badge offline');
        } else {
            gwLatencyBadge.textContent = '-- ms';
            gwLatencyBadge.className = 'latency-badge offline';
        }
    }

    if (gwStatusDot && gwStatusText) {
        if (source === 'cloud') {
            gwStatusDot.style.background = '#10b981';
            gwStatusDot.style.boxShadow = '0 0 10px #10b981';
            gwStatusText.textContent = 'Cloud Connected (24/7)';
            gwStatusText.style.color = '#10b981';
            if (telemetryStatusEl) telemetryStatusEl.textContent = 'Live Cloud Telemetry';
        } else if (source === 'local') {
            if (connectionMode === 'auto') {
                gwStatusDot.style.background = '#f59e0b';
                gwStatusDot.style.boxShadow = '0 0 10px #f59e0b';
                gwStatusText.textContent = 'Local Fallback (Cloud Offline)';
                gwStatusText.style.color = '#fbbf24';
                if (telemetryStatusEl) telemetryStatusEl.textContent = 'Local Telemetry (Fallback)';
            } else {
                gwStatusDot.style.background = '#06b6d4';
                gwStatusDot.style.boxShadow = '0 0 10px #06b6d4';
                gwStatusText.textContent = 'Localhost (Port 8080)';
                gwStatusText.style.color = '#38bdf8';
                if (telemetryStatusEl) telemetryStatusEl.textContent = 'Local Telemetry';
            }
        } else {
            // offline
            gwStatusDot.style.background = '#f43f5e';
            gwStatusDot.style.boxShadow = '0 0 8px #f43f5e';
            gwStatusText.textContent = statusMsg || 'Disconnected (Offline)';
            gwStatusText.style.color = '#fb7185';
            if (telemetryStatusEl) telemetryStatusEl.textContent = 'Gateway Offline';
        }
    }

    checkMixedContent(endpointUrl);
}

// --- Dashboard Card Initialization ---
function initDashboard() {
    if (!dashboard) return;
    dashboard.innerHTML = '';

    for (let i = 1; i <= totalMachines; i++) {
        const card = document.createElement('article');
        card.className = 'machine-card';
        card.id = `machine-card-${i}`;
        card.innerHTML = `
            <div class="card-top">
                <div class="m-header">
                    <span>Machine ${i}</span>
                    <span class="m-header-badge">UNIT-${i.toString().padStart(2, '0')}</span>
                </div>
                <div class="m-status status-stopped" id="status-m${i}">STOPPED</div>
            </div>

            <!-- Actuators: Conveyor Motor & Solenoid Valve -->
            <div class="m-actuators-bar">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span class="actuator-label">Valve:</span>
                    <span class="valve-badge valve-closed" id="valve-m${i}">CLOSED</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px;">
                    <span class="actuator-label">TCP:</span>
                    <span style="font-size:11px; font-weight:700; color:var(--text-dim);" id="tcp-m${i}">OFFLINE</span>
                </div>
            </div>

            <!-- Sensor Telemetry Metrics -->
            <div class="m-data-container">
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Temp</span>
                    </div>
                    <span class="data-value" id="temp-m${i}">-- °C</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-temp" id="meter-temp-m${i}" style="width: 25%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Vibration</span>
                    </div>
                    <span class="data-value" id="vib-m${i}">-- Hz</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-vib" id="meter-vib-m${i}" style="width: 20%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Speed</span>
                    </div>
                    <span class="data-value" id="speed-m${i}">-- RPM</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-speed" id="meter-speed-m${i}" style="width: 0%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Proximity</span>
                    </div>
                    <span class="data-value" id="prox-m${i}">--</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-prox" id="meter-prox-m${i}" style="width: 0%;"></div>
                    </div>
                </div>
            </div>

            <!-- Blynk Sync Status Row -->
            <div class="blynk-selector-row">
                <span style="font-size:11px; color:var(--text-dim); font-weight:600;">Blynk Cloud:</span>
                <span class="blynk-badge blynk-inactive" id="blynk-badge-m${i}" onclick="selectBlynkMachine(${i})">
                    <span>📡 Mirror V0-V4</span>
                </span>
            </div>

            <!-- Interactive Control Panel (TCP START/STOP, RESET, SET_SPEED) -->
            <div class="m-control-panel">
                <div class="control-btn-group">
                    <button class="ctrl-btn ctrl-btn-start" onclick="sendCommand(${i}, 'START')">▶ START</button>
                    <button class="ctrl-btn ctrl-btn-stop" onclick="sendCommand(${i}, 'STOP')">⏹ STOP</button>
                    <button class="ctrl-btn ctrl-btn-reset" onclick="sendCommand(${i}, 'RESET')">↺ RESET</button>
                </div>
                <div class="speed-slider-row">
                    <span>Speed</span>
                    <input type="range" class="speed-slider" id="slider-m${i}" min="0" max="2400" step="100" value="0"
                           onchange="setMachineSpeed(${i}, this.value)"
                           oninput="document.getElementById('speed-preview-m${i}').textContent = this.value + ' RPM'" />
                    <span id="speed-preview-m${i}" style="font-family:var(--font-mono); font-size:11px; min-width:55px;">0 RPM</span>
                </div>
            </div>
        `;
        dashboard.appendChild(card);
    }
}

// --- Dashboard Telemetry & State Updates ---
function updateDashboard(payload) {
    if (!payload || !payload.machines) return;

    if (telemetryStatusEl) telemetryStatusEl.textContent = 'Live Telemetry';
    if (gwStatusDot) {
        gwStatusDot.style.background = '#10b981';
        gwStatusDot.style.boxShadow = '0 0 8px #10b981';
    }
    if (gwStatusText) {
        gwStatusText.textContent = 'Online';
        gwStatusText.style.color = '#34d399';
    }

    const blynkActive = payload.blynk_active_machine || 1;
    if (blynkSyncLabel) {
        blynkSyncLabel.textContent = `Machine ${blynkActive} (V0-V4)`;
    }

    let activeCount = 0;
    const machines = payload.machines;

    machines.forEach(machine => {
        if (!machine || typeof machine.id === 'undefined') return;
        const id = machine.id;

        // Machine Status
        const statusElement = document.getElementById(`status-m${id}`);
        if (statusElement) {
            const isRunning = machine.state === 'RUNNING';
            statusElement.textContent = machine.state;
            statusElement.className = 'm-status ' + (isRunning ? 'status-running' : 'status-stopped');
            if (isRunning) activeCount++;
        }

        // Valve State
        const valveEl = document.getElementById(`valve-m${id}`);
        if (valveEl) {
            const isOpen = machine.valve_state === 'OPEN';
            valveEl.textContent = machine.valve_state || 'CLOSED';
            valveEl.className = 'valve-badge ' + (isOpen ? 'valve-open' : 'valve-closed');
        }

        // TCP status
        const tcpEl = document.getElementById(`tcp-m${id}`);
        if (tcpEl) {
            tcpEl.textContent = machine.connected_tcp ? 'CONNECTED' : 'OFFLINE';
            tcpEl.style.color = machine.connected_tcp ? 'var(--cyan)' : 'var(--text-dim)';
        }

        // Temperature
        const tempElement = document.getElementById(`temp-m${id}`);
        const meterTemp = document.getElementById(`meter-temp-m${id}`);
        if (tempElement && machine.temperature !== undefined) {
            tempElement.textContent = `${machine.temperature.toFixed(1)} °C`;
            if (meterTemp) {
                const pct = Math.min(100, Math.max(10, (machine.temperature / 90) * 100));
                meterTemp.style.width = `${pct}%`;
            }
        }

        // Vibration
        const vibElement = document.getElementById(`vib-m${id}`);
        const meterVib = document.getElementById(`meter-vib-m${id}`);
        if (vibElement && machine.vibration !== undefined) {
            vibElement.textContent = `${machine.vibration.toFixed(1)} Hz`;
            if (meterVib) {
                const pct = Math.min(100, Math.max(8, machine.vibration));
                meterVib.style.width = `${pct}%`;
            }
        }

        // Motor Speed
        const speedElement = document.getElementById(`speed-m${id}`);
        const meterSpeed = document.getElementById(`meter-speed-m${id}`);
        const sliderEl = document.getElementById(`slider-m${id}`);
        const previewEl = document.getElementById(`speed-preview-m${id}`);
        if (speedElement && machine.motor_speed !== undefined) {
            speedElement.textContent = `${machine.motor_speed} RPM`;
            if (meterSpeed) {
                const pct = Math.min(100, Math.max(0, (machine.motor_speed / 2400) * 100));
                meterSpeed.style.width = `${pct}%`;
            }
            if (sliderEl && document.activeElement !== sliderEl) {
                sliderEl.value = machine.motor_speed;
                if (previewEl) previewEl.textContent = `${machine.motor_speed} RPM`;
            }
        }

        // Proximity
        const proxElement = document.getElementById(`prox-m${id}`);
        const meterProx = document.getElementById(`meter-prox-m${id}`);
        if (proxElement && machine.proximity !== undefined) {
            proxElement.textContent = machine.proximity === 1 ? 'DETECTED' : 'CLEAR';
            proxElement.style.color = machine.proximity === 1 ? 'var(--cyan)' : 'var(--text-muted)';
            if (meterProx) {
                meterProx.style.width = machine.proximity === 1 ? '100%' : '15%';
            }
        }

        // Blynk Mirroring Badge
        const blynkBadge = document.getElementById(`blynk-badge-m${id}`);
        if (blynkBadge) {
            if (id === blynkActive) {
                blynkBadge.className = 'blynk-badge blynk-active';
                blynkBadge.innerHTML = '<span>⚡ Linked (V0-V4)</span>';
            } else {
                blynkBadge.className = 'blynk-badge blynk-inactive';
                blynkBadge.innerHTML = '<span>📡 Mirror V0-V4</span>';
            }
        }
    });

    if (activeUnitsEl) {
        activeUnitsEl.textContent = `${activeCount} / ${machines.length} Online`;
    }

    // Update Alerts Feed
    if (alertsFeedEl && payload.alerts) {
        if (payload.alerts.length === 0) {
            alertsFeedEl.innerHTML = '<span style="font-size: 12px; color: var(--text-dim); font-style: italic;">No active critical alerts. System nominal.</span>';
        } else {
            alertsFeedEl.innerHTML = payload.alerts.slice(-6).reverse().map(a => {
                let chipClass = 'chip-sensor';
                if (a.alert === 'TEMP_HIGH') chipClass = 'chip-temp';
                else if (a.alert === 'VIB_HIGH') chipClass = 'chip-vib';
                return `<span class="alert-chip ${chipClass}">[${a.time_str || 'ALERT'}] M${a.machine_id}: ${a.alert}</span>`;
            }).join('');
        }
    }
}

// --- Smart Auto-Failover Telemetry & Probe Engine ---
async function probeCloudServer() {
    if (!CLOUD_GATEWAY_URL) return false;
    try {
        const res = await fetch(`${CLOUD_GATEWAY_URL}/api/health`, {
            signal: AbortSignal.timeout(2500),
            headers: { 'Accept': 'application/json' }
        });
        return res.ok;
    } catch {
        return false;
    }
}

async function fetchFromEndpoint(url, timeoutMs = 3000) {
    const res = await fetch(`${url}/api/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(timeoutMs)
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return await res.json();
}

// --- Fetch Telemetry Loop with 24/7 Cloud Resilience ---
async function fetchMachineData() {
    if (isFetching) return;
    isFetching = true;

    try {
        if (connectionMode === 'cloud') {
            // Mode: Cloud Only
            if (!CLOUD_GATEWAY_URL) {
                updateGatewayStatusUI('offline', 'Configure Cloud Server URL Above', null, null);
                return;
            }
            const start = performance.now();
            try {
                const data = await fetchFromEndpoint(CLOUD_GATEWAY_URL, 3500);
                const latency = Math.round(performance.now() - start);
                activeGatewayUrl = CLOUD_GATEWAY_URL;
                activeSource = 'cloud';
                updateGatewayStatusUI('cloud', 'Cloud Connected (24/7)', CLOUD_GATEWAY_URL, latency);
                updateDashboard(data);
            } catch (err) {
                activeSource = 'offline';
                updateGatewayStatusUI('offline', 'Cloud Server Offline / Unreachable', CLOUD_GATEWAY_URL, null);
            }

        } else if (connectionMode === 'local') {
            // Mode: Local Only
            const start = performance.now();
            try {
                const data = await fetchFromEndpoint(LOCAL_GATEWAY_URL, 2000);
                const latency = Math.round(performance.now() - start);
                activeGatewayUrl = LOCAL_GATEWAY_URL;
                activeSource = 'local';
                updateGatewayStatusUI('local', 'Localhost Connected', LOCAL_GATEWAY_URL, latency);
                updateDashboard(data);
            } catch (err) {
                activeSource = 'offline';
                updateGatewayStatusUI('offline', 'Local Gateway Offline (Port 8080)', LOCAL_GATEWAY_URL, null);
            }

        } else {
            // Mode: Auto (Cloud first with automatic Localhost Fallback)
            const now = Date.now();

            // When in local fallback mode, probe cloud in background every 10 seconds
            if (activeSource === 'local' && CLOUD_GATEWAY_URL && (now - lastCloudProbeTime > 10000)) {
                lastCloudProbeTime = now;
                const cloudIsAlive = await probeCloudServer();
                if (cloudIsAlive) {
                    console.log('[Auto-Failover] Cloud Server restored! Resuming Cloud stream...');
                    activeSource = 'cloud';
                }
            }

            // Attempt Cloud Server if activeSource is 'cloud' or on startup
            if (activeSource !== 'local' && CLOUD_GATEWAY_URL) {
                const start = performance.now();
                try {
                    const data = await fetchFromEndpoint(CLOUD_GATEWAY_URL, 2500);
                    const latency = Math.round(performance.now() - start);
                    activeGatewayUrl = CLOUD_GATEWAY_URL;
                    activeSource = 'cloud';
                    updateGatewayStatusUI('cloud', 'Cloud Connected (24/7)', CLOUD_GATEWAY_URL, latency);
                    updateDashboard(data);
                    return;
                } catch (cloudErr) {
                    console.warn('[Auto-Failover] Cloud Server unavailable. Falling back to Localhost...');
                    activeSource = 'local';
                    lastCloudProbeTime = Date.now();
                }
            }

            // Fallback: Fetch from Localhost Gateway
            const localStart = performance.now();
            try {
                const data = await fetchFromEndpoint(LOCAL_GATEWAY_URL, 2000);
                const latency = Math.round(performance.now() - localStart);
                activeGatewayUrl = LOCAL_GATEWAY_URL;
                activeSource = 'local';
                const statusMsg = CLOUD_GATEWAY_URL ? 'Local Fallback (Cloud Offline)' : 'Localhost Active';
                updateGatewayStatusUI('local', statusMsg, LOCAL_GATEWAY_URL, latency);
                updateDashboard(data);
            } catch (localErr) {
                activeSource = 'offline';
                const msg = CLOUD_GATEWAY_URL ? 'Both Cloud & Local Offline' : 'Local Gateway Offline (Port 8080)';
                updateGatewayStatusUI('offline', msg, null, null);
            }
        }
    } finally {
        isFetching = false;
    }
}

// --- Command Dispatch via Active Gateway REST API ---
async function sendCommand(machineId, command, value = null) {
    const statusElement = document.getElementById(`status-m${machineId}`);
    const valveEl = document.getElementById(`valve-m${machineId}`);
    const speedElement = document.getElementById(`speed-m${machineId}`);
    const meterSpeed = document.getElementById(`meter-speed-m${machineId}`);
    const sliderEl = document.getElementById(`slider-m${machineId}`);
    const previewEl = document.getElementById(`speed-preview-m${machineId}`);

    if (command === 'START') {
        if (statusElement) {
            statusElement.textContent = 'RUNNING';
            statusElement.className = 'm-status status-running';
        }
        if (valveEl) {
            valveEl.textContent = 'OPEN';
            valveEl.className = 'valve-badge valve-open';
        }
        const spd = (sliderEl && parseInt(sliderEl.value, 10) > 0) ? parseInt(sliderEl.value, 10) : 1500;
        if (speedElement) speedElement.textContent = `${spd} RPM`;
        if (previewEl) previewEl.textContent = `${spd} RPM`;
        if (sliderEl) sliderEl.value = spd;
        if (meterSpeed) meterSpeed.style.width = `${Math.min(100, (spd / 2400) * 100)}%`;
    } else if (command === 'STOP' || command === 'RESET') {
        if (statusElement) {
            statusElement.textContent = 'STOPPED';
            statusElement.className = 'm-status status-stopped';
        }
        if (valveEl) {
            valveEl.textContent = 'CLOSED';
            valveEl.className = 'valve-badge valve-closed';
        }
        if (speedElement) speedElement.textContent = '0 RPM';
        if (previewEl) previewEl.textContent = '0 RPM';
        if (sliderEl) sliderEl.value = 0;
        if (meterSpeed) meterSpeed.style.width = '0%';
    } else if (command === 'SET_SPEED') {
        const spd = parseInt(value, 10) || 0;
        if (speedElement) speedElement.textContent = `${spd} RPM`;
        if (previewEl) previewEl.textContent = `${spd} RPM`;
        if (meterSpeed) meterSpeed.style.width = `${Math.min(100, (spd / 2400) * 100)}%`;
        if (spd > 0 && statusElement) {
            statusElement.textContent = 'RUNNING';
            statusElement.className = 'm-status status-running';
            if (valveEl) {
                valveEl.textContent = 'OPEN';
                valveEl.className = 'valve-badge valve-open';
            }
        }
    }

    const targetUrl = activeGatewayUrl || LOCAL_GATEWAY_URL;
    try {
        const response = await fetch(`${targetUrl}/api/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            signal: AbortSignal.timeout(4000),
            body: JSON.stringify({
                machine_id: machineId,
                command: command,
                value: value
            })
        });
        const result = await response.json();
        console.log(`[Command ${command}] Machine ${machineId} (${targetUrl}):`, result);
        setTimeout(fetchMachineData, 300);
    } catch (err) {
        console.error(`Error sending command to ${targetUrl}:`, err);
    }
}

function setMachineSpeed(machineId, speed) {
    const spd = parseInt(speed, 10) || 0;
    const previewEl = document.getElementById(`speed-preview-m${machineId}`);
    const meterSpeed = document.getElementById(`meter-speed-m${machineId}`);
    const speedElement = document.getElementById(`speed-m${machineId}`);
    if (previewEl) previewEl.textContent = `${spd} RPM`;
    if (speedElement) speedElement.textContent = `${spd} RPM`;
    if (meterSpeed) meterSpeed.style.width = `${Math.min(100, (spd / 2400) * 100)}%`;
    sendCommand(machineId, 'SET_SPEED', spd);
}

// --- Blynk Active Machine Selection ---
async function selectBlynkMachine(machineId) {
    const targetUrl = activeGatewayUrl || LOCAL_GATEWAY_URL;
    try {
        const response = await fetch(`${targetUrl}/api/blynk/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: AbortSignal.timeout(4000),
            body: JSON.stringify({ machine_id: machineId })
        });
        const res = await response.json();
        if (res.success) {
            fetchMachineData();
        }
    } catch (err) {
        console.error(`Error selecting Blynk machine on ${targetUrl}:`, err);
    }
}

// --- Fault Simulation Trigger (Testing UDP Alerts) ---
async function simulateFault(machineId, faultType) {
    const targetUrl = activeGatewayUrl || LOCAL_GATEWAY_URL;
    try {
        await fetch(`${targetUrl}/api/simulate/fault`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: AbortSignal.timeout(4000),
            body: JSON.stringify({ machine_id: machineId, fault: faultType })
        });
        setTimeout(fetchMachineData, 300);
    } catch (err) {
        console.error(`Error simulating fault on ${targetUrl}:`, err);
    }
}

// Global expose for HTML onclick handlers
window.sendCommand = sendCommand;
window.setMachineSpeed = setMachineSpeed;
window.selectBlynkMachine = selectBlynkMachine;
window.simulateFault = simulateFault;

initDashboard();
fetchMachineData();
setInterval(fetchMachineData, 1800);