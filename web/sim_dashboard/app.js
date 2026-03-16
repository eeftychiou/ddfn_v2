const API_BASE = "http://127.0.0.1:8050/api";
const BROKER_URL = "ws://127.0.0.1:8001/ws";

let socket;
let globalInventory = {}; // Keyed by flight_id to track latest state across nodes
let activeSearchQuery = "";

// DOM Elements
const form = document.getElementById("injection-form");
const statusDiv = document.getElementById("injection-status");
const tbody = document.querySelector("#global-inventory-table tbody");
const countSpan = document.getElementById("flight-count");
const searchInput = document.getElementById("search-flights");
const aixmPathInput = document.getElementById("aixm_path");
const loadAixmBtn = document.getElementById("load-aixm-btn");
const aixmStatus = document.getElementById("aixm-status");
const sectorListContainer = document.getElementById("sector-list-container");
const sectorPills = document.getElementById("sector-pills");

// Initialize Clock
setInterval(() => {
    document.getElementById('clock').innerText = new Date().toISOString().substr(11, 8) + ' UTC';
}, 1000);

// Search Handling
searchInput.addEventListener('input', (e) => {
    activeSearchQuery = e.target.value.toLowerCase();
    renderTable();
});

// Form Submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
        flight_id: document.getElementById('flight_id').value.toUpperCase(),
        origin: document.getElementById('origin').value.toUpperCase(),
        destination: document.getElementById('destination').value.toUpperCase(),
        route_string: document.getElementById('route_string').value.toUpperCase(),
        cruise_fl: parseInt(document.getElementById('cruise_fl').value),
        departure_offset_mins: parseInt(document.getElementById('departure_offset_mins').value)
    };

    const injectBtn = document.getElementById('inject-btn');
    injectBtn.disabled = true;
    injectBtn.innerText = "Injecting...";

    try {
        const response = await fetch(`${API_BASE}/flights/inject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            statusDiv.className = "injection-feedback success";
            statusDiv.innerText = `Success: ${result.message}`;
            form.reset(); // clear form
        } else {
            throw new Error(result.message || "Failed to inject");
        }
    } catch (err) {
        statusDiv.className = "injection-feedback error";
        statusDiv.innerText = `Error: ${err.message}`;
    } finally {
        injectBtn.disabled = false;
        injectBtn.innerText = "Inject to SWIM Network";
        setTimeout(() => {
            if (statusDiv.className.includes("success")) statusDiv.innerText = "";
        }, 5000);
    }
});

// Connect to SWIM Broker to listen for Inventory Updates
function connectWebSocket() {
    socket = new WebSocket(BROKER_URL);
    const statusEl = document.getElementById("broker-status");
    const dotEl = document.querySelector(".ddfn-dot");

    socket.onopen = () => {
        statusEl.innerText = "Broker: Connected";
        statusEl.style.color = "var(--success)";
        dotEl.style.background = "var(--success)";
        dotEl.style.boxShadow = "0 0 8px var(--success)";

        // Subscribe to Airspace Inventory Broadcasts
        socket.send(JSON.stringify({
            "action": "subscribe",
            "topic": "ddfn.airspace.inventory",
            "queue_name": "sim_dashboard_" + Math.random().toString(36).substr(2, 6)
        }));
    };

    socket.onclose = () => {
        statusEl.innerText = "Broker: Disconnected";
        statusEl.style.color = "var(--danger)";
        dotEl.style.background = "var(--danger)";
        dotEl.style.boxShadow = "0 0 8px var(--danger)";
        // Retry connection
        setTimeout(connectWebSocket, 3000);
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.topic === "ddfn.airspace.inventory") {
            handleInventoryMessage(data.message);
        }
    };
}

function handleInventoryMessage(payload) {
    const reportingNode = payload.node_id;
    const flights = payload.flights;

    // Process and update global state
    flights.forEach(f => {
        // If the reporting node sees it as active, it takes precedence.
        // Otherwise, if it's new we just add it.
        const existing = globalInventory[f.flight_id];

        if (!existing) {
            globalInventory[f.flight_id] = { ...f, reporters: [reportingNode] };
        } else {
            // Update the flight details
            globalInventory[f.flight_id].origin = f.origin;
            globalInventory[f.flight_id].destination = f.destination;
            globalInventory[f.flight_id].entry_point = f.entry_point;
            globalInventory[f.flight_id].exit_point = f.exit_point;
            globalInventory[f.flight_id].eta_entry = f.eta_entry;
            globalInventory[f.flight_id].eta_exit = f.eta_exit;

            // Manage reporters list
            if (!globalInventory[f.flight_id].reporters.includes(reportingNode)) {
                globalInventory[f.flight_id].reporters.push(reportingNode);
            }

            // Status precedence: Active > Scheduled
            if (f.status === "ACTIVE") {
                globalInventory[f.flight_id].status = "ACTIVE";
            }
        }
    });

    // Quick garbage collection: Remove nodes from reporters if they haven't reported it recently? 
    // For simplicity, we'll just keep the aggregate view. 
    // In a real system, we'd use timeouts per reporter.

    renderTable();
}

function formatTimeOnly(isoString) {
    if (!isoString) return "-";
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return isoString;
        return d.toISOString().substr(11, 5);
    } catch { return isoString; }
}

function renderTable() {
    tbody.innerHTML = "";

    let flights = Object.values(globalInventory) || [];

    // Sort logic: Active first, then by earliest entry time
    flights.sort((a, b) => {
        if (a.status !== b.status) {
            return a.status === 'ACTIVE' ? -1 : 1;
        }
        return new Date(a.eta_entry) - new Date(b.eta_entry);
    });

    // Filter Logic
    if (activeSearchQuery) {
        flights = flights.filter(f =>
            f.flight_id.toLowerCase().includes(activeSearchQuery) ||
            f.origin.toLowerCase().includes(activeSearchQuery) ||
            f.destination.toLowerCase().includes(activeSearchQuery) ||
            f.reporters.some(r => r.toLowerCase().includes(activeSearchQuery))
        );
    }

    countSpan.innerText = `Tracking: ${flights.length} flights`;

    flights.forEach(f => {
        const tr = document.createElement("tr");

        // Node Tags
        const tagsHtml = f.reporters.map(r => `<span class="node-tag">${r.split('_')[0]}</span>`).join(" ");

        const statusClass = f.status === "ACTIVE" ? "status-active" : "status-scheduled";

        tr.innerHTML = `
            <td>${tagsHtml}</td>
            <td style="font-weight: 500;">${f.flight_id}</td>
            <td>${f.origin}</td>
            <td>${f.destination}</td>
            <td class="${statusClass}">${f.status}</td>
            <td>${f.entry_point}</td>
            <td style="font-family: monospace;">${formatTimeOnly(f.eta_entry)}</td>
            <td style="font-family: monospace;">${formatTimeOnly(f.eta_exit)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// AIXM Handling
loadAixmBtn.addEventListener('click', async () => {
    const filePath = aixmPathInput.value.trim();
    if (!filePath) {
        aixmStatus.className = "injection-feedback error";
        aixmStatus.innerText = "Please provide a file path.";
        return;
    }

    loadAixmBtn.disabled = true;
    loadAixmBtn.innerText = "Loading...";

    try {
        const response = await fetch(`${API_BASE}/aixm/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });

        const result = await response.json();
        if (response.ok && result.status === 'success') {
            aixmStatus.className = "injection-feedback success";
            aixmStatus.innerText = result.message;
            fetchSectors();
        } else {
            throw new Error(result.message || "Failed to load AIXM");
        }
    } catch (err) {
        aixmStatus.className = "injection-feedback error";
        aixmStatus.innerText = `Error: ${err.message}`;
    } finally {
        loadAixmBtn.disabled = false;
        loadAixmBtn.innerText = "Load Data";
    }
});

async function fetchSectors() {
    try {
        const response = await fetch(`${API_BASE}/aixm/sectors`);
        const result = await response.json();
        
        if (response.ok && result.status === 'success' && result.sectors.length > 0) {
            sectorListContainer.style.display = "block";
            sectorPills.innerHTML = result.sectors.map(s => `
                <div class="sector-pill" title="FIR: ${s.fir}">
                    ${s.id}
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Failed to fetch sectors:", err);
    }
}

// Initial fetch
fetchSectors();

// Start
connectWebSocket();
