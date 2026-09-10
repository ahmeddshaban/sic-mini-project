const totalMachines = 5;
const dashboard = document.getElementById('dashboard');
const telemetryStatusEl = document.getElementById('telemetry-status');
const activeUnitsEl = document.getElementById('stat-active-units');

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
                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Temp</span>
                    </div>
                    <span class="data-value" id="temp-m${i}">-- °C</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-temp" id="meter-temp-m${i}" style="width: 30%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Vibration</span>
                    </div>
                    <span class="data-value" id="vib-m${i}">-- Hz</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-vib" id="meter-vib-m${i}" style="width: 25%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Speed</span>
                    </div>
                    <span class="data-value" id="speed-m${i}">-- RPM</span>
                    <div class="meter-bar">
                        <div class="meter-fill meter-speed" id="meter-speed-m${i}" style="width: 50%;"></div>
                    </div>
                </div>

                <div class="data-item">
                    <div class="data-header">
                        <span class="data-label">Proximity</span>
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

function updateDashboard(data) {
    if (!Array.isArray(data)) return;

    if (telemetryStatusEl) telemetryStatusEl.textContent = 'Live Telemetry';

    let activeCount = 0;

    data.forEach(machine => {
        if (!machine || typeof machine.id === 'undefined') return;
        const id = machine.id;
        
        const statusElement = document.getElementById(`status-m${id}`);
        if (statusElement && machine.state) {
            const isRunning = machine.state === 'RUNNING';
            statusElement.textContent = machine.state;
            statusElement.className = 'm-status ' + (isRunning ? 'status-running' : 'status-stopped');
            if (isRunning) activeCount++;
        }

        const tempElement = document.getElementById(`temp-m${id}`);
        const meterTemp = document.getElementById(`meter-temp-m${id}`);
        if (tempElement && machine.temperature !== undefined) {
            tempElement.textContent = `${machine.temperature} °C`;
            if (meterTemp) {
                const pct = Math.min(100, Math.max(10, (machine.temperature / 60) * 100));
                meterTemp.style.width = `${pct}%`;
            }
        }

        const vibElement = document.getElementById(`vib-m${id}`);
        const meterVib = document.getElementById(`meter-vib-m${id}`);
        if (vibElement && machine.vibration !== undefined) {
            vibElement.textContent = `${machine.vibration} Hz`;
            if (meterVib) {
                const pct = Math.min(100, Math.max(8, machine.vibration));
                meterVib.style.width = `${pct}%`;
            }
        }

        const speedElement = document.getElementById(`speed-m${id}`);
        const meterSpeed = document.getElementById(`meter-speed-m${id}`);
        if (speedElement && machine.speed !== undefined) {
            speedElement.textContent = `${machine.speed} RPM`;
            if (meterSpeed) {
                const pct = Math.min(100, Math.max(0, (machine.speed / 2400) * 100));
                meterSpeed.style.width = `${pct}%`;
            }
        }

        const proxElement = document.getElementById(`prox-m${id}`);
        const meterProx = document.getElementById(`meter-prox-m${id}`);
        if (proxElement && machine.proximity !== undefined) {
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

// karim added
async function fetchMachineData() {
    try {
        const response = await fetch('http://127.0.0.1:5000');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        if (telemetryStatusEl) telemetryStatusEl.textContent = 'Server Offline';
    }
}

initDashboard();
setInterval(fetchMachineData, 2000);