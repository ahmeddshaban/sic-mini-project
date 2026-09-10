/**
 * Samsung Innovation Campus (SIC8) - IoT Track
 * Smart Factory Telemetry & Interactive Control Dashboard
 * Works both locally (http://localhost:8080) and on deployed site (https://iotnexa-sic.web.app)
 */

const totalMachines = 5;
const dashboard = document.getElementById('dashboard');
const telemetryStatusEl = document.getElementById('telemetry-status');
const activeUnitsEl = document.getElementById('stat-active-units');
const alertsFeedEl = document.getElementById('alerts-feed');
const gwStatusDot = document.getElementById('gw-status-dot');
const gwStatusText = document.getElementById('gw-status-text');
const blynkSyncLabel = document.getElementById('blynk-sync-label');
const gwUrlInput = document.getElementById('gw-url-input');
const gwUrlSaveBtn = document.getElementById('gw-url-save-btn');

// --- Gateway URL Management ---
function getGatewayBaseUrl() {
    const saved = localStorage.getItem('sic_gateway_url');
    if (saved) return saved.replace(/\/+$/, '');
    // If running on localhost/127.0.0.1 directly served by Gateway
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return window.location.origin;
    }
    // Default fallback for deployed frontend (https://iotnexa-sic.web.app)
    return 'http://localhost:8080';
}

let GATEWAY_URL = getGatewayBaseUrl();
if (gwUrlInput) {
    gwUrlInput.value = GATEWAY_URL;
}

if (gwUrlSaveBtn) {
    gwUrlSaveBtn.addEventListener('click', () => {
        let val = gwUrlInput.value.trim().replace(/\/+$/, '');
        if (!val.startsWith('http://') && !val.startsWith('https://')) {
            val = 'http://' + val;
        }
        GATEWAY_URL = val;
        localStorage.setItem('sic_gateway_url', val);
        gwUrlInput.value = val;
        fetchMachineData();
    });
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

// --- Fetch Telemetry Loop ---
async function fetchMachineData() {
    try {
        const response = await fetch(`${GATEWAY_URL}/api/status`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) throw new Error(`HTTP error ${response.status}`);
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        if (telemetryStatusEl) telemetryStatusEl.textContent = 'Gateway Offline';
        if (gwStatusDot) {
            gwStatusDot.style.background = '#f43f5e';
            gwStatusDot.style.boxShadow = '0 0 8px #f43f5e';
        }
        if (gwStatusText) {
            gwStatusText.textContent = 'Disconnected';
            gwStatusText.style.color = '#fb7185';
        }
    }
}

// --- Command Dispatch via Gateway TCP REST API ---
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

    try {
        const response = await fetch(`${GATEWAY_URL}/api/command`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                machine_id: machineId,
                command: command,
                value: value
            })
        });
        const result = await response.json();
        console.log(`[Command ${command}] Machine ${machineId}:`, result);
        setTimeout(fetchMachineData, 400);
    } catch (err) {
        console.error('Error sending command:', err);
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
    try {
        const response = await fetch(`${GATEWAY_URL}/api/blynk/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ machine_id: machineId })
        });
        const res = await response.json();
        if (res.success) {
            fetchMachineData();
        }
    } catch (err) {
        console.error('Error selecting Blynk machine:', err);
    }
}

// --- Fault Simulation Trigger (Testing UDP Alerts) ---
async function simulateFault(machineId, faultType) {
    try {
        await fetch(`${GATEWAY_URL}/api/simulate/fault`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ machine_id: machineId, fault: faultType })
        });
        setTimeout(fetchMachineData, 400);
    } catch (err) {
        console.error('Error simulating fault:', err);
    }
}

// Global expose for HTML onclick handlers
window.sendCommand = sendCommand;
window.setMachineSpeed = setMachineSpeed;
window.selectBlynkMachine = selectBlynkMachine;
window.simulateFault = simulateFault;

initDashboard();
fetchMachineData();
setInterval(fetchMachineData, 1500);