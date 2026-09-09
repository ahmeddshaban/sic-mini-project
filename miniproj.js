const totalMachines = 5;
const dashboard = document.getElementById('dashboard');

function initDashboard() 
{
    for (let i = 1; i <= totalMachines; i++) {
        const card = document.createElement('div');
        card.className = 'machine-card';
        card.innerHTML = `
            <div class="m-header">Machine ${i}</div>
            <div class="m-status" id="status-m${i}">WAITING</div>
            <div class="m-data-container">
                <div class="m-col">
                    <div class="data-item">
                        <span class="data-label">Temp</span>
                        <span class="data-value" id="temp-m${i}">-- °C</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Vibration</span>
                        <span class="data-value" id="vib-m${i}">-- Hz</span>
                    </div>
                </div>
                <div class="m-col">
                    <div class="data-item">
                        <span class="data-label">Speed</span>
                        <span class="data-value" id="speed-m${i}">-- RPM</span>
                    </div>
                    <div class="data-item">
                        <span class="data-label">Proximity</span>
                        <span class="data-value" id="prox-m${i}">-- mm</span>
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
       
        const response = await fetch('http://RASPBERRY_PI_IP/api/machines'); 
        
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error("Connection Error:", error);
    }
}

function updateDashboard(data) 
{
    data.forEach(machine => 
    {
        const id = machine.id;
        
        // تحديث الحالة
        const statusElement = document.getElementById(`status-m${id}`);
        statusElement.textContent = machine.state;
        statusElement.className = 'm-status ' + (machine.state === 'RUNNING' ? 'status-running' : 'status-stopped');

        document.getElementById(`temp-m${id}`).textContent = `${machine.temperature} °C`;
        document.getElementById(`vib-m${id}`).textContent = `${machine.vibration} Hz`;
        document.getElementById(`speed-m${id}`).textContent = `${machine.speed} RPM`;
        document.getElementById(`prox-m${id}`).textContent = `${machine.proximity} mm`;
    });
}

initDashboard();

setInterval(fetchMachineData, 2000);