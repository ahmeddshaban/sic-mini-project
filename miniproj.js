const totalMachines = 5;
const dashboard = document.getElementById('dashboard');
const telemetryStatusEl = document.getElementById('telemetry-status');
const activeUnitsEl = document.getElementById('stat-active-units');

// Pre-initialize machine baseline states for smooth, realistic telemetry
const machineStates = Array.from({ length: totalMachines }, (_, i) => ({
    id: i + 1,
    state: 'RUNNING',
    temperature: 24 + Math.floor(Math.random() * 8),
    vibration: 20 + Math.floor(Math.random() * 25),
    speed: 1500 + Math.floor(Math.random() * 300),
    proximity: 12 + Math.floor(Math.random() * 10)
}));

function initDashboard() 
{
    if (!dashboard) return;
    dashboard.innerHTML = '';

    for (let i = 1; i <= totalMachines; i++) 
    {
        const card = document.createElement('article');
        card.className = 'machine-card';
        card.id = `machine-card-${i}`;
        card.innerHTML = `
            <div class="card-top">
                <div class="m-header">
                    <span>Machine ${i}</span>
                    <span class="m-header-badge">UNIT-${i.toString().padStart(2, '0')}</span>
                </div>
                <div class="m-status status-running" id="status-m${i}">RUNNING</div>
            </div>
            <div class="m-data-container">
                <!-- Temperature -->
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">
                            <svg class="data-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"></path>
                            </svg>
                            Temp
                        </span>
                    </div>
                    <span class="data-value" id="temp-m${i}">-- °C</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-temp" id="meter-temp-m${i}" style="width: 30%;"></div>
                    </div>
                </div>

                <!-- Vibration -->
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">
                            <svg class="data-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                            </svg>
                            Vibration
                        </span>
                    </div>
                    <span class="data-value" id="vib-m${i}">-- Hz</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-vib" id="meter-vib-m${i}" style="width: 25%;"></div>
                    </div>
                </div>

                <!-- Speed -->
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">
                            <svg class="data-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>
                            Speed
                        </span>
                    </div>
                    <span class="data-value" id="speed-m${i}">-- RPM</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-speed" id="meter-speed-m${i}" style="width: 50%;"></div>
                    </div>
                </div>

                <!-- Proximity -->
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">
                            <svg class="data-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="2"></circle>
                                <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path>
                            </svg>
                            Proximity
                        </span>
                    </div>
                    <span class="data-value" id="prox-m${i}">-- mm</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-prox" id="meter-prox-m${i}" style="width: 20%;"></div>
                    </div>
                </div>
            </div>
        `;
        dashboard.appendChild(card);
    }
}

async function fetchMachineData() 
{
    try 
    {
        // Try fetching from Abo Ali's Raspberry Pi endpoint
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1200);

        const response = await fetch('http://RASPBERRY_PI_IP/api/machines', {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();

        if (telemetryStatusEl) telemetryStatusEl.textContent = 'Live Telemetry';
        updateDashboard(data);
    } 
    catch (error) 
    {
        // Smooth simulated fallback telemetry reflecting IoT factory conditions
        if (telemetryStatusEl) telemetryStatusEl.textContent = 'Live Simulation';
        generateSimulatedTelemetry();
    }
}

function generateSimulatedTelemetry() 
{
    machineStates.forEach(machine => {
        // Natural sensor jitter
        const tempDelta = (Math.random() * 1.6 - 0.8);
        machine.temperature = Math.min(65, Math.max(18, +(machine.temperature + tempDelta).toFixed(1)));

        // Vibration occasional spikes (reflecting server.py threshold logic)
        const isSpike = Math.random() < 0.08;
        if (isSpike) {
            machine.vibration = Math.floor(72 + Math.random() * 25);
        } else {
            machine.vibration = Math.floor(18 + Math.random() * 32);
        }

        // Conveyor & safety state according to server.py rule (> 70 stops conveyor)
        if (machine.vibration > 70) {
            machine.state = 'STOPPED';
            machine.speed = 0;
        } else {
            machine.state = 'RUNNING';
            machine.speed = Math.floor(1400 + Math.random() * 400);
        }

        machine.proximity = Math.floor(8 + Math.random() * 20);
    });

    updateDashboard(machineStates);
}

function updateDashboard(data) 
{
    if (!Array.isArray(data)) return;

    let activeCount = 0;

    data.forEach(machine => 
    {
        if (!machine || typeof machine.id === 'undefined') return;
        const id = machine.id;
        
        // Status Badge
        const statusElement = document.getElementById(`status-m${id}`);
        if (statusElement && machine.state) 
        {
            const isRunning = machine.state === 'RUNNING';
            statusElement.textContent = machine.state;
            statusElement.className = 'm-status ' + (isRunning ? 'status-running' : 'status-stopped');
            if (isRunning) activeCount++;
        }

        // Temperature
        const tempElement = document.getElementById(`temp-m${id}`);
        const meterTemp = document.getElementById(`meter-temp-m${id}`);
        if (tempElement && machine.temperature !== undefined) 
        {
            tempElement.textContent = `${machine.temperature} °C`;
            if (meterTemp) {
                const pct = Math.min(100, Math.max(10, (machine.temperature / 60) * 100));
                meterTemp.style.width = `${pct}%`;
            }
        }

        // Vibration
        const vibElement = document.getElementById(`vib-m${id}`);
        const meterVib = document.getElementById(`meter-vib-m${id}`);
        if (vibElement && machine.vibration !== undefined) 
        {
            vibElement.textContent = `${machine.vibration} Hz`;
            if (meterVib) {
                const pct = Math.min(100, Math.max(8, machine.vibration));
                meterVib.style.width = `${pct}%`;
            }
        }

        // Speed
        const speedElement = document.getElementById(`speed-m${id}`);
        const meterSpeed = document.getElementById(`meter-speed-m${id}`);
        if (speedElement && machine.speed !== undefined) 
        {
            speedElement.textContent = `${machine.speed} RPM`;
            if (meterSpeed) {
                const pct = Math.min(100, Math.max(0, (machine.speed / 2400) * 100));
                meterSpeed.style.width = `${pct}%`;
            }
        }

        // Proximity
        const proxElement = document.getElementById(`prox-m${id}`);
        const meterProx = document.getElementById(`meter-prox-m${id}`);
        if (proxElement && machine.proximity !== undefined) 
        {
            proxElement.textContent = `${machine.proximity} mm`;
            if (meterProx) {
                const pct = Math.min(100, Math.max(10, (machine.proximity / 40) * 100));
                meterProx.style.width = `${pct}%`;
            }
        }
    });

    if (activeUnitsEl) {
        activeUnitsEl.textContent = `${activeCount} / ${data.length} Online`;
    }
}

// Initial render
initDashboard();
generateSimulatedTelemetry();

// Regular polling
setInterval(fetchMachineData, 2000);