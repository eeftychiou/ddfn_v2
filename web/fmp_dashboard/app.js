let ws;
let demandChart;
const logContainer = document.getElementById('log-container');
const inboxContainer = document.getElementById('inbox-container');
let currentSlotTable = [];
let selectedFlights = [];
let currentWarningId = "";
let currentAirspaceInventory = [];
let currentDemandProfile = [];
let currentSectorCapacity = 0;
let currentSectorOverrides = [];
let currentChartBins = [];
let configMap, configSectorsLayer, configCountryLayer;
let configAirportsLayer, configWaypointsLayer, configAirwaysLayer;
let configSelectedAixmFile = "";

// CHMI Workspace Definition
const FIR_SECTORS = {
    "LFFF_DDFN_NODE": [
        { id: "LFFF1A", desc: "France NE Upper" },
        { id: "LFFF1B", desc: "France SW Upper" },
        { id: "LFPG", desc: "CDG Aerodrome" },
        { id: "LFMN", desc: "Nice Aerodrome" }
    ],
    "EDDD_DDFN_NODE": [
        { id: "EDDD2B", desc: "Germany Central" },
        { id: "EDDD2C", desc: "Germany South" },
        { id: "EDMM3A", desc: "Munich Approach" },
        { id: "EDDF", desc: "Frankfurt Aerodrome" },
        { id: "EDDM", desc: "Munich Aerodrome" }
    ],
    "EGTT_DDFN_NODE": [
        { id: "EGTT1C", desc: "London Central" },
        { id: "EGTT1D", desc: "Scotland Upper" },
        { id: "EGPX1A", desc: "Scottish ACC" },
        { id: "EGLL", desc: "Heathrow Aerodrome" },
        { id: "EGCC", desc: "Manchester Aerodrome" }
    ]
};

let currentWorkspaceSectors = [];

// UTC Clock Update
setInterval(() => {
    const el = document.getElementById('utc-clock');
    if (el) {
        const now = new Date();
        const timeStr = now.toISOString().split('T')[1].substring(0, 8);
        el.innerText = `${timeStr} UTC`;
    }
}, 1000);

function initChart() {
    const ctx = document.getElementById('demandChart').getContext('2d');

    demandChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Projected Demand',
                    data: [],
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.2)',
                },
                {
                    label: 'Sector Capacity',
                    data: [],
                    borderColor: '#2ea043',
                    borderDash: [5, 5],
                    fill: false,
                    stepped: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            onClick: (e, activeElements) => {
                if (activeElements.length > 0 && currentChartBins.length > 0) {
                    const dataIndex = activeElements[0].index;
                    renderDeepDive(currentChartBins[dataIndex]);
                }
            },
            plugins: {
                legend: { labels: { color: '#c9d1d9' } }
            },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#8b949e' }, min: 0 },
                x: { grid: { display: false }, ticks: { color: '#8b949e' } }
            }
        }
    });

    // Event listeners for new controls
    document.getElementById('chart-time-scope').addEventListener('change', updateChartFromProfile);
    document.getElementById('chart-pan-slider').addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        const label = val === 0 ? "Now" : (val > 0 ? `+${val}h` : `${val}h`);
        document.getElementById('chart-pan-label').innerText = label;
        updateChartFromProfile();
    });
}

function updateChartFromProfile() {
    if (!demandChart || currentDemandProfile.length === 0) return;

    // A full profile spans 24 hours (-12h to +12h) in 5min bins (288 bins total). 'Now' is roughly at index 144.
    const scopeHours = parseInt(document.getElementById('chart-time-scope').value);
    const panHours = parseInt(document.getElementById('chart-pan-slider').value);

    // 12 bins per hour
    const centerIdx = 144 + (panHours * 12);
    const halfScopeBins = (scopeHours * 12) / 2;

    let startIdx = Math.max(0, centerIdx - halfScopeBins);
    let endIdx = Math.min(currentDemandProfile.length, centerIdx + halfScopeBins);

    currentChartBins = currentDemandProfile.slice(startIdx, endIdx);

    const now = new Date();
    const utcNowStr = now.toISOString().split('T')[1].substring(0, 5); // HH:MM

    // Split bins into Past, Active, and Future
    // We'll use 3 datasets for demand to show different colors
    const pastDemand = [];
    const activeDemand = [];
    const futureDemand = [];
    const capacityData = [];
    const labels = [];

    currentChartBins.forEach(b => {
        labels.push(b.time_label);
        const bTime = b.time_label;

        // Define "Active" as +/- 30 mins around now (roughly 2 bins each way)
        const bHour = parseInt(bTime.split(':')[0]);
        const bMin = parseInt(bTime.split(':')[1]);
        const nHour = now.getUTCHours();
        const nMin = now.getUTCMinutes();

        const bTotalMins = bHour * 60 + bMin;
        const nTotalMins = nHour * 60 + nMin;
        const diff = bTotalMins - nTotalMins;

        if (diff < -30) {
            pastDemand.push(b.demand_count);
            activeDemand.push(null);
            futureDemand.push(null);
        } else if (diff > 120) { // Future starts after 2 hours
            pastDemand.push(null);
            activeDemand.push(null);
            futureDemand.push(b.demand_count);
        } else {
            pastDemand.push(null);
            activeDemand.push(b.demand_count);
            futureDemand.push(null);
        }

        // Capacity
        let activeCap = currentSectorCapacity;
        for (const ovr of currentSectorOverrides) {
            if (b.timestamp >= ovr.start && b.timestamp <= ovr.end) {
                activeCap = ovr.capacity;
                break;
            }
        }
        capacityData.push(activeCap);
    });

    demandChart.data.labels = labels;

    // Ensure we have enough datasets
    if (demandChart.data.datasets.length < 4) {
        demandChart.data.datasets = [
            {
                label: 'Past Demand',
                data: [],
                borderWidth: 1,
                borderColor: '#8b949e',
                backgroundColor: 'rgba(139, 148, 158, 0.6)',
                type: 'bar',
            },
            {
                label: 'Active Window',
                data: [],
                borderWidth: 1,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.6)',
                type: 'bar',
            },
            {
                label: 'Future Prediction',
                data: [],
                borderWidth: 1,
                borderColor: '#1f6feb',
                backgroundColor: 'rgba(31, 111, 235, 0.6)',
                type: 'bar',
            },
            {
                label: 'Sector Capacity',
                data: [],
                borderColor: '#2ea043',
                borderDash: [5, 5],
                fill: false,
                stepped: true,
                type: 'line',
            }
        ];
    }

    demandChart.data.datasets[0].data = pastDemand;
    demandChart.data.datasets[1].data = activeDemand;
    demandChart.data.datasets[2].data = futureDemand;
    demandChart.data.datasets[3].data = capacityData;

    // Auto scale Y axis
    const maxVal = Math.max(...currentChartBins.map(b => b.demand_count), currentSectorCapacity, 10);
    demandChart.options.scales.y.max = maxVal + 5;

    demandChart.update();
}

function renderDeepDive(binData) {
    const panel = document.getElementById('flight-deep-dive');
    const tbody = document.getElementById('deep-dive-list-body');
    if (!panel || !binData || !tbody) return;

    panel.style.display = 'flex'; // Changed to flex for the column layout
    panel.style.flexDirection = 'column';
    document.getElementById('deep-dive-time').innerText = binData.time_label;

    if (binData.flights.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:var(--text-sec); padding:20px;">No flights predicted for this window.</td></tr>';
        return;
    }

    tbody.innerHTML = binData.flights.map(fid => {
        // Enriched lookup
        const fltInfo = currentAirspaceInventory.find(f => f.flight_id === fid) || {
            flight_id: fid,
            origin: '???',
            destination: '???',
            route_string: 'No routing data'
        };

        return `
            <tr>
                <td><strong style="color:var(--accent)">${fid}</strong></td>
                <td style="font-size: 0.75rem;">${fltInfo.origin} &rarr; ${fltInfo.destination}</td>
                <td style="font-size: 0.7rem; color: var(--text-sec); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${fltInfo.route_string}">
                    ${fltInfo.route_string}
                </td>
            </tr>
        `;
    }).join('');
}

function renderActiveConstraints() {
    const tbody = document.getElementById('active-constraints-body');
    if (!tbody) return;

    if (currentSectorOverrides.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-sec); padding:10px;">No constraints active</td></tr>';
        return;
    }

    const selectedSector = document.getElementById('builder-sector').value;

    tbody.innerHTML = currentSectorOverrides.map(ovr => `
        <tr>
            <td>${new Date(ovr.start).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}</td>
            <td>${new Date(ovr.end).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}</td>
            <td style="color: #f85149; font-weight: bold;">${ovr.capacity}</td>
            <td>
                <button class="btn-reject" style="padding: 2px 8px; font-size: 0.75rem;" onclick="removeConstraint('${ovr.id}', '${selectedSector}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

window.removeConstraint = function (id, sector) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "REMOVE_CAPACITY_OVERRIDE",
            target_node: getActiveNode(),
            sector: sector,
            override_id: id
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.capacity_override", message: msg }));
        appendLog('system', `Sent constraint deletion request for ${sector} (ID: ${id})`);
    }
}

function getActiveNode() {
    return window.ACTIVE_NODE_ID;
}

function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.hostname}:8001/ws`);

    ws.onopen = () => {
        appendLog('system', 'Connected to DDFN V2 SWIM Broker.');
        // Subscribe to relevant topics
        const topics = [
            "ddfn.capacity.state",
            "ddfn.warning.trigger",
            "ddfn.negotiation.proposal",
            "ddfn.flow.consensus",
            "ddfn.ui.inbox",
            "ddfn.airspace.inventory"
        ];
        topics.forEach(t => ws.send(JSON.stringify({ action: "subscribe", topic: t })));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleSwappedMessage(msg.topic, msg.message);
    };

    ws.onclose = () => {
        appendLog('warning', 'Disconnected. Retrying...');
        setTimeout(initWebSocket, 2000);
    };
}

function handleSwappedMessage(topic, payload) {
    const msgType = payload.message_type;

    if (msgType === "CAPACITY_STATE_BROADCAST") {
        const s = payload.sector;

        // Only update the graph if this sector is currently selected in the UI
        const selectedSector = document.getElementById('builder-sector');
        if (selectedSector && s.sector_id === selectedSector.value) {
            currentSectorCapacity = s.declared_capacity_per_hour;
            currentSectorOverrides = payload.active_overrides || [];
            renderActiveConstraints();

            if (payload.demand_profile) {
                currentDemandProfile = payload.demand_profile;
                updateChartFromProfile();
            }
        }

        const el = document.getElementById(`sector-${s.sector_id}`);
        if (el) {
            el.querySelector('.demand-val').innerText = s.current_demand_per_hour;
            el.querySelector('.cap-val').innerText = s.declared_capacity_per_hour;
            const meter = el.querySelector('.meter-fill');
            let ratio = (s.current_demand_per_hour / Math.max(s.declared_capacity_per_hour, 1)) * 100;
            meter.style.width = `${Math.min(ratio, 100)}%`;
            if (s.status === "RED") {
                meter.className = 'meter-fill red';
                el.closest('.node').classList.add('constrained');
            } else {
                meter.className = 'meter-fill green';
                el.closest('.node').classList.remove('constrained');
            }
        }
    } else if (msgType === "CONSTRAINT_WARNING_TRIGGER") {
        appendLog('warning', `[${payload.originating_node}] WARNING on ${payload.constrained_sector_id}. Excess: ${payload.required_flow_reduction.amount_to_reduce}`);
    } else if (msgType === "FLOW_NEGOTIATION_PROPOSAL") {
        appendLog('proposal', `[${payload.proposing_node}] PROPOSAL offered: absorb ${payload.contribution_to_reduction} flights.`);
    } else if (msgType === "DISTRIBUTED_FLOW_CONSENSUS") {
        appendLog('consensus', `[CASA ISSUED] CTOTs published for ${payload.referencing_warning_id}.`);

        // Update Slot Table if present
        if (payload.slot_table && payload.slot_table.length > 0) {
            currentSlotTable = payload.slot_table;
            currentWarningId = payload.referencing_warning_id;
            renderSlotTable(currentSlotTable);
        }

        // Clear inbox if it was for us
        const activeNode = getActiveNode();
        if (payload.participating_nodes.includes(activeNode)) {
            inboxContainer.innerHTML = '<div class="empty-state">No pending proposals awaiting your approval.</div>';
        }
    } else if (msgType === "UI_INBOX_APPROVAL_REQUEST") {
        if (payload.target_node === getActiveNode()) {
            renderInboxItem(payload);
            appendLog('system', `HITL: CASA assignments pending FMP approval for ${payload.warning_id}.`);
        }
    } else if (msgType === "AIRSPACE_INVENTORY_UPDATE") {
        if (payload.node_id === getActiveNode()) {
            currentAirspaceInventory = payload.flights;
            renderInventoryTable();
        }
    } else if (msgType === "RAD_VIOLATION" || msgType === "SLOT_SWAP_REJECTED") {
        const flightId = payload.flight_id || payload.rejected_flight_id;
        const reason = payload.reason || "Route Availability Document (RAD) violation";
        appendLog('warning', `[SECURITY/RAD] BLOCKED: ${flightId} - ${reason}`);

        // Visual toast if supported
        if (window.showToast) {
            window.showToast(`RAD Violation: ${flightId} rejected.`, 'error');
        }
    }
}

function renderSlotTable(slots) {
    const body = document.getElementById('slot-list-body');
    if (!body) return;

    if (!slots || slots.length === 0) {
        body.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-sec);">No active regulations for this node.</td></tr>';
        return;
    }

    body.innerHTML = slots.map(s => {
        const isSelected = selectedFlights.includes(s.flight_id);
        const statusClass = s.status === 'REGULATED' ? 'regulated' : 'swapped';
        const etot = s.etot.includes('T') ? s.etot.split('T')[1].substring(0, 5) : s.etot;
        const ctot = s.ctot.includes('T') ? s.ctot.split('T')[1].substring(0, 5) : s.ctot;

        return `
            <tr class="slot-row ${isSelected ? 'selected' : ''}" onclick="toggleFlightSelection('${s.flight_id}')">
                <td>${s.flight_id}</td>
                <td>${etot}</td>
                <td>${ctot}</td>
                <td>+${s.delay}m</td>
                <td><span class="status-tag ${statusClass}">${s.status}</span></td>
            </tr>
        `;
    }).join('');
}

window.toggleFlightSelection = function (fid) {
    const idx = selectedFlights.indexOf(fid);
    if (idx > -1) {
        selectedFlights.splice(idx, 1);
    } else {
        if (selectedFlights.length >= 2) {
            selectedFlights.shift(); // Max 2 seats in the selection
        }
        selectedFlights.push(fid);
    }

    renderSlotTable(currentSlotTable);

    const btn = document.getElementById('swap-slots-btn');
    btn.disabled = selectedFlights.length !== 2;
};

document.getElementById('swap-slots-btn').addEventListener('click', () => {
    if (selectedFlights.length === 2 && ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "FMP_SLOT_SWAP_REQUEST",
            target_node: getActiveNode(),
            flight_id_1: selectedFlights[0],
            flight_id_2: selectedFlights[1],
            warning_id: currentWarningId
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.proposal_action", message: msg }));
        appendLog('system', `FMP Manual Swap Request: ${selectedFlights[0]} <-> ${selectedFlights[1]}`);
        selectedFlights = [];
        document.getElementById('swap-slots-btn').disabled = true;
    }
});

function renderInboxItem(payload) {
    inboxContainer.innerHTML = ''; // Clear empty state
    const card = document.createElement('div');
    card.className = 'proposal-card';

    let html = `
        <div class="proposal-info">
            <strong>Pending CASA CTOTs for: ${payload.warning_id}</strong>
            <div class="proposal-details">Sector: ${payload.sector_id}</div>
            <div class="proposal-details">Impact: Demand of ${payload.demand} exceeds Capacity of ${payload.capacity}.</div>
            <div class="proposal-details" style="color: var(--danger);">Action Required: ${payload.delayed_flights} flights delayed.</div>
        </div>
        <div class="action-btns">
            <button class="btn-approve" onclick="approveProposal('${payload.warning_id}')">Approve & Issue</button>
            <button class="btn-reject" onclick="rejectProposal('${payload.warning_id}')">Reject</button>
        </div>
    `;
    card.innerHTML = html;
    inboxContainer.appendChild(card);
}

window.approveProposal = function (warningId) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "FMP_PROPOSAL_APPROVAL",
            target_node: getActiveNode(),
            warning_id: warningId,
            action: "APPROVE"
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.proposal_action", message: msg }));
        appendLog('system', `FMP Approved CASA assignments for ${warningId}.`);
    }
};

window.rejectProposal = function (warningId) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "FMP_PROPOSAL_APPROVAL",
            target_node: getActiveNode(),
            warning_id: warningId,
            action: "REJECT"
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.proposal_action", message: msg }));
        appendLog('warning', `FMP Rejected CASA assignments for ${warningId}. Regulation canceled.`);
        inboxContainer.innerHTML = '<div class="empty-state">No pending proposals awaiting your approval.</div>';
    }
}

document.getElementById('builder-sector')?.addEventListener('change', () => {
    currentDemandProfile = [];
    if (demandChart) {
        demandChart.data.datasets[0].data = [];
        demandChart.data.datasets[1].data = [];
        demandChart.update();
    }
});

// Modal Logic
const constraintModal = document.getElementById('constraint-modal');

document.getElementById('btn-open-constraint-modal')?.addEventListener('click', () => {
    constraintModal.style.display = 'flex';
});

document.getElementById('btn-close-modal')?.addEventListener('click', () => {
    constraintModal.style.display = 'none';
});

document.getElementById('btn-reset-capacity')?.addEventListener('click', () => {
    // Also acts as cancel inside modal
    constraintModal.style.display = 'none';
});

document.getElementById('btn-apply-constraint').addEventListener('click', () => {
    const sector = document.getElementById('builder-sector').value;
    const capacity = document.getElementById('builder-capacity').value;
    const start = document.getElementById('builder-start').value;
    const end = document.getElementById('builder-end').value;
    const reason = document.getElementById('builder-reason').value;

    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "MANUAL_CAPACITY_OVERRIDE",
            target_node: getActiveNode(),
            sector: sector,
            capacity: capacity,
            start_time: start,
            end_time: end,
            reason: reason
        };
        // Publish to broker
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.capacity_override", message: msg }));
        appendLog('system', `Sent constraint for ${sector}: Cap=${capacity} (${start}-${end}) Reason=${reason}`);

        // Close modal after applying
        if (constraintModal) {
            constraintModal.style.display = 'none';
        }
    }
});

function appendLog(typeClass, message) {
    const el = document.createElement('div');
    el.className = `log-entry ${typeClass}`;
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    el.innerHTML = `<span class="log-meta">[${time}]</span> <span class="log-text">${message}</span>`;
    logContainer.appendChild(el);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Init defaults for the initial node selection
function initWorkspace() {
    const configName = document.getElementById('config-name-display')?.innerText.replace('Config: ', '') || 'Default';
    if (configName !== 'Default') {
        document.getElementById('active-node-badge').innerText = `Config: ${configName}`;
    } else {
        document.getElementById('active-node-badge').innerText = `Node: ${getActiveNode().split('_')[0]}`;
    }
    currentWorkspaceSectors = (FIR_SECTORS[getActiveNode()] || []).slice(0, 2).map(s => s.id);
    renderWorkspace();
    loadConfigurations();
}

async function loadConfigurations() {
    try {
        const response = await fetch('/api/configurations');
        const data = await response.json();
        const select = document.getElementById('config-select');
        if (select) {
            select.innerHTML = '<option value="">-- Select Configuration --</option>';
            data.configurations.forEach(cfg => {
                select.innerHTML += `<option value="${cfg}">${cfg}</option>`;
            });
        }
    } catch (e) {
        console.error("Failed to load configurations", e);
    }
}

function renderInventoryTable() {
    const body = document.getElementById('inventory-list-body');
    const countEl = document.getElementById('inventory-count');
    if (!body) return;

    body.innerHTML = '';
    countEl.innerText = `Tracking: ${currentAirspaceInventory.length} flights`;

    // Sort by ETA/Entry
    const sorted = [...currentAirspaceInventory].sort((a, b) => new Date(a.eta_entry) - new Date(b.eta_entry));

    sorted.forEach(flt => {
        const row = document.createElement('tr');
        const etaIn = flt.eta_entry ? flt.eta_entry.split('T')[1].substring(0, 5) : '??:??';
        const etaOut = flt.eta_exit ? flt.eta_exit.split('T')[1].substring(0, 5) : '??:??';

        const statusClass = flt.status === 'ACTIVE' ? 'active' : 'scheduled';

        row.innerHTML = `
            <td><strong>${flt.flight_id}</strong></td>
            <td><code>${flt.entry_point || '??'}</code></td>
            <td>${etaIn}</td>
            <td><code>${flt.exit_point || '??'}</code></td>
            <td>${etaOut}</td>
            <td><span class="status-indicator ${statusClass}">${flt.status}</span></td>
        `;
        body.appendChild(row);
    });
}

function renderWorkspace() {
    const container = document.getElementById('nodes-container');
    const builderSector = document.getElementById('builder-sector');
    if (!container || !builderSector) return;

    container.innerHTML = '';
    builderSector.innerHTML = '<option value="">-- Select Sector --</option>';

    currentWorkspaceSectors.forEach(sid => {
        // Find sector info
        const allSectors = FIR_SECTORS[getActiveNode()] || [];
        const info = allSectors.find(s => s.id === sid) || { id: sid, desc: "Custom Sector" };

        const card = document.createElement('div');
        card.className = 'node';
        card.id = `sector-${sid}`;
        card.innerHTML = `
            <div class="node-header">
                <span class="node-name">${sid}</span>
                <span class="node-id">${info.desc}</span>
            </div>
            <div class="demand-meter">
                <div class="meter-bar"><div class="meter-fill green" style="width: 0%"></div></div>
                <div class="meter-labels">
                    <span>Demand: <span class="demand-val">0</span></span>
                    <span>Cap: <span class="cap-val">45</span></span>
                </div>
            </div>
        `;
        container.appendChild(card);

        builderSector.innerHTML += `<option value="${sid}">${sid}</option>`;
    });

    if (!builderSector.value && currentWorkspaceSectors.length > 0) {
        builderSector.value = currentWorkspaceSectors[0];
        builderSector.dispatchEvent(new Event('change'));
    }
}

// --- Workspace Settings Modal ---
const settingsModal = document.getElementById('settings-modal');
const workspaceCheckboxes = document.getElementById('workspace-checkboxes');

document.getElementById('btn-settings').addEventListener('click', () => {
    // Populate checkboxes for current Node
    workspaceCheckboxes.innerHTML = '';
    const available = FIR_SECTORS[getActiveNode()] || [];

    available.forEach(sec => {
        const isChecked = currentWorkspaceSectors.includes(sec.id) ? 'checked' : '';
        workspaceCheckboxes.innerHTML += `
            <label class="checkbox-item">
                <input type="checkbox" value="${sec.id}" ${isChecked}>
                <div class="details">
                    <strong>${sec.id}</strong><br>
                    <small>${sec.desc}</small>
                </div>
            </label>
        `;
    });
    settingsModal.classList.remove('hidden');
});

document.getElementById('btn-close-settings').addEventListener('click', () => {
    settingsModal.classList.add('hidden');
});

document.getElementById('btn-save-settings').addEventListener('click', () => {
    const checked = Array.from(workspaceCheckboxes.querySelectorAll('input:checked')).map(cb => cb.value);
    if (checked.length === 0) {
        alert("You must select at least one Traffic Volume for your workspace.");
        return;
    }

    // Broadcast Measure Window update to our backend FMP Node
    const windowMins = document.getElementById('measurement-window-select').value;
    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "SET_MEASURE_WINDOW",
            target_node: getActiveNode(),
            minutes: windowMins
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.settings", message: msg }));
    }

    currentWorkspaceSectors = checked;
    settingsModal.classList.add('hidden');
    renderWorkspace();
    appendLog('system', `Workspace updated. Tracking ${checked.length} volumes at ${windowMins}m intervals.`);
});

document.getElementById('btn-merge-sectors').addEventListener('click', () => {
    const checked = Array.from(workspaceCheckboxes.querySelectorAll('input:checked')).map(cb => cb.value);
    const newId = document.getElementById('merge-sector-id').value;

    if (checked.length < 2) {
        alert("You must select at least two sectors to merge.");
        return;
    }
    if (!newId) {
        alert("Please provide a new Virtual ID.");
        return;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        const msg = {
            message_type: "MERGE_SECTORS",
            target_node: getActiveNode(),
            sectors: checked,
            new_id: newId
        };
        ws.send(JSON.stringify({ action: "publish", topic: "ddfn.ui.settings", message: msg }));

        // Optimistic UI update for the checkboxes
        FIR_SECTORS[getActiveNode()].push({ id: newId, desc: `Virtual (${checked.join('+')})` });
        appendLog('system', `Requested sector merger: ${checked.join('+')} -> ${newId}. Please re-open settings.`);
        settingsModal.classList.add('hidden');
    }
});

document.getElementById('btn-apply-config').addEventListener('click', async () => {
    const configName = document.getElementById('config-select').value;
    if (!configName) return;

    try {
        await fetch('/api/configurations/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_node: getActiveNode(),
                config_name: configName
            })
        });
        appendLog('system', `Applied configuration: ${configName}. Reloading dashboard...`);
        settingsModal.classList.add('hidden');
        setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
        console.error("Failed to apply configuration", e);
        alert("Failed to apply configuration.");
    }
});

// Init defaults for the initial node selection
setTimeout(initWorkspace, 500); // Give active node injection time to settle

initChart();
initWebSocket();

// Tab Navigation Logic
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all buttons and panes
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            // Add active class to clicked button and target pane
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');

            // Resize Chart.js if the flow tab is activated
            if (targetId === 'tab-flow' && demandChart) {
                demandChart.resize();
            }

            if (targetId === 'tab-config') {
                initAirspaceConfigTab();
            }
        });
    });
});

// AIRSPACE CONFIGURATION LOGIC
function initAirspaceConfigTab() {
    if (!configMap) {
        configMap = L.map('airspace-map', {
            zoomControl: true,
            attributionControl: false
        }).setView([35.0, 33.0], 5); // Default to East Med

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19
        }).addTo(configMap);

        configSectorsLayer = L.featureGroup().addTo(configMap);
        configAirportsLayer = L.featureGroup();
        configWaypointsLayer = L.featureGroup();
        configAirwaysLayer = L.featureGroup();
        
        if (document.getElementById('toggle-airports')?.checked) configAirportsLayer.addTo(configMap);
        if (document.getElementById('toggle-waypoints')?.checked) configWaypointsLayer.addTo(configMap);
        if (document.getElementById('toggle-airways')?.checked) configAirwaysLayer.addTo(configMap);
        
        configCountryLayer = L.geoJSON(null, {
            style: {
                color: '#30363d',
                weight: 1,
                fillColor: 'transparent',
                dashArray: '3'
            }
        }).addTo(configMap);

        // Load country outlines for realism
        fetch('https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json')
            .then(res => res.json())
            .then(data => {
                configCountryLayer.addData(data);
            });
            
        // Persistence: Check for previous source
        fetch('/api/config/aixm_source')
            .then(res => res.json())
            .then(data => {
                if (data.file_path) {
                    document.getElementById('config-aixm-path').value = data.file_path;
                    loadAixmSource(data.file_path, data.fir_id);
                }
                if (data.config_name) {
                    document.getElementById('config-node-name').value = data.config_name;
                    document.getElementById('config-name-display').innerText = `Config: ${data.config_name}`;
                }
            });

        // Load saved configurations list
        loadSavedConfigsList();

        // Fetch current node sectors (Responsibility)
        fetch('/metadata')
            .then(res => res.json())
            .then(data => {
                if (data.sectors) {
                    renderActiveResponsibility(data.sectors);
                }
            });
    }

    // Leaflet needs an invalidatesize call if initialized while hidden
    setTimeout(() => { configMap.invalidateSize(); }, 200);
}

async function loadSavedConfigsList() {
    try {
        const res = await fetch('/api/config/list');
        const data = await res.json();
        const select = document.getElementById('config-saved-list');
        if (data.status === 'success' && select) {
            select.innerHTML = '<option value="">-- Select to Load --</option>';
            data.configs.forEach(cfg => {
                const opt = document.createElement('option');
                opt.value = cfg;
                opt.innerText = cfg;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.error("Failed to load configs list", e);
    }
}

document.getElementById('config-saved-list')?.addEventListener('change', async (e) => {
    const name = e.target.value;
    if (!name) return;

    try {
        const res = await fetch(`/api/config/load?name=${encodeURIComponent(name)}`);
        const data = await res.json();
        if (data.status === 'success') {
            appendLog('system', `Loaded configuration: ${name}. Reloading...`);
            setTimeout(() => window.location.reload(), 1000);
        }
    } catch (e) {
        alert("Failed to load configuration.");
    }
});

document.getElementById('btn-delete-airspace-config')?.addEventListener('click', async () => {
    const name = document.getElementById('config-saved-list').value;
    if (!name) {
        alert("Please select a configuration from the list to delete.");
        return;
    }

    if (!confirm(`Are you sure you want to delete '${name}'?`)) return;

    try {
        const res = await fetch(`/api/config/delete/${encodeURIComponent(name)}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'success') {
            appendLog('system', `Deleted configuration: ${name}`);
            loadSavedConfigsList();
        }
    } catch (e) {
        alert("Failed to delete configuration.");
    }
});

document.getElementById('config-aixm-upload')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    const statusEl = document.getElementById('config-save-status');
    try {
        if (statusEl) {
            statusEl.innerText = "Uploading AIXM file...";
            statusEl.style.color = "var(--accent)";
        }
        
        const res = await fetch('/api/aixm/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.status === 'success') {
            document.getElementById('config-aixm-path').value = data.file_path;
            if (statusEl) {
                statusEl.innerText = "Upload complete! Scanning...";
                statusEl.style.color = "var(--success)";
            }
            loadAixmSource(data.file_path);
        } else {
            alert("Upload failed: " + data.message);
        }
    } catch (err) {
        console.error("Upload error", err);
        alert("Upload failed.");
    }
});

document.getElementById('btn-load-aixm')?.addEventListener('click', () => {
    const filePath = document.getElementById('config-aixm-path').value || "AIXM/BD_2025-09-30_400005921419525.xml";
    loadAixmSource(filePath);
});

async function loadAixmSource(filePath, targetFirId = null) {
    configSelectedAixmFile = filePath;
    try {
        const res = await fetch(`/api/aixm/firs?file_path=${encodeURIComponent(filePath)}`);
        const data = await res.json();

        if (data.status === 'success') {
            const select = document.getElementById('config-fir-select');
            select.innerHTML = '<option value="">-- Select FIR --</option>';
            data.firs.forEach(fir => {
                select.innerHTML += `<option value="${fir}">${fir}</option>`;
            });
            if (targetFirId) {
                select.value = targetFirId;
                select.dispatchEvent(new Event('change'));
            }
            appendLog('system', `Loaded AIXM info from ${filePath}. ${data.firs.length} FIRs found.`);
            
            // Background load airports/waypoints if toggled (or just cache them)
            loadExtraLayers();
        } else {
            console.error("Error loading AIXM:", data.message);
            appendLog('error', `Failed to load AIXM info: ${data.message}`);
            alert("Error loading AIXM: " + data.message);
        }
    } catch (e) {
        console.error(e);
        alert("Failed to connect to backend.");
    }
}

// Helper to load FIR sectors
async function loadFirSectors(filePath, firId) {
    try {
        const res = await fetch(`/api/aixm/sectors?file_path=${encodeURIComponent(filePath)}&fir_id=${firId}`);
        const data = await res.json();

        if (data.status === 'success') {
            window.CURRENT_AIXM_SECTORS = data.sectors; // Store globally for filtering
            renderConfigSectors(data.sectors);
            visualizeSectors(data.sectors);
        }
    } catch (e) {
        console.error(e);
    }
}

document.getElementById('config-fir-select')?.addEventListener('change', async (e) => {
    const firId = e.target.value;
    if (!firId) return;
    loadFirSectors(configSelectedAixmFile, firId);
    loadExtraLayers();
});

function renderActiveResponsibility(sectors) {
    const list = document.getElementById('active-responsibility-list');
    if (!list) return;

    if (sectors.length === 0) {
        list.innerHTML = '<div style="text-align:center; color: var(--text-sec); padding: 5px;">No active responsibility.</div>';
        return;
    }

    list.innerHTML = sectors.map(s => `
        <div style="background: rgba(88, 166, 255, 0.1); border-radius: 4px; padding: 4px 8px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
            <span><strong>${s.sector_id}</strong> <small style="color:var(--text-sec)">FL${s.fl_lower}-${s.fl_upper}</small></span>
        </div>
    `).join('');
}

function renderConfigSectors(sectors) {
    const list = document.getElementById('config-sector-list');
    list.innerHTML = sectors.map(s => `
        <div class="sector-config-item" data-id="${s.sector_id}" style="border-bottom: 1px solid var(--glass-border); padding: 5px 0;">
            <label style="display: flex; align-items: flex-start; gap: 10px; cursor: pointer;">
                <input type="checkbox" value="${s.sector_id}" class="sector-config-check" checked data-name="${s.name}">
                <div style="flex: 1;">
                    <strong>${s.sector_id}</strong><br>
                    <small>${s.name}</small>
                </div>
            </label>
            <div style="display: flex; gap: 10px; margin-top: 5px; margin-left: 25px;">
                <div style="display:flex; flex-direction:column;">
                    <label style="font-size: 0.65rem; color:var(--text-sec);">Min FL</label>
                    <input type="number" class="fl-min-input" value="${s.fl_lower}" style="width: 50px; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); color: var(--text-main); font-size: 0.7rem; padding: 2px;">
                </div>
                <div style="display:flex; flex-direction:column;">
                    <label style="font-size: 0.65rem; color:var(--text-sec);">Max FL</label>
                    <input type="number" class="fl-max-input" value="${s.fl_upper}" style="width: 50px; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); color: var(--text-main); font-size: 0.7rem; padding: 2px;">
                </div>
            </div>
        </div>
    `).join('');

    // Add listeners for live updates
    list.querySelectorAll('.sector-config-check').forEach(cb => {
        cb.addEventListener('change', () => {
            updateMapSectorsFromUI();
        });
    });
}

function updateMapSectorsFromUI() {
    const checks = document.querySelectorAll('.sector-config-check');
    const selectedIds = Array.from(checks).filter(c => c.checked).map(c => c.value);
    const filtered = (window.CURRENT_AIXM_SECTORS || []).filter(s => selectedIds.includes(s.sector_id));
    visualizeSectors(filtered, false); // false = don't fitBounds on every toggle
}

async function loadExtraLayers() {
    console.log("loadExtraLayers called. AIXM File:", configSelectedAixmFile);
    if (!configSelectedAixmFile) return;
    const firSelect = document.getElementById('config-fir-select');
    const selectedFir = firSelect ? firSelect.value : '';
    console.log("Selected FIR:", selectedFir);
    if (!selectedFir) return;

    const showWptLabels = document.getElementById('toggle-labels-wpt')?.checked;
    const showRteLabels = document.getElementById('toggle-labels-rte')?.checked;
    console.log("Labels State - WPT:", showWptLabels, "RTE:", showRteLabels);

    const commonParams = `file_path=${encodeURIComponent(configSelectedAixmFile)}&fir_id=${encodeURIComponent(selectedFir)}`;

    // Airports (ICAO: Circle with cross)
    fetch(`/api/aixm/airports?${commonParams}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                configAirportsLayer.clearLayers();
                data.airports.forEach(adp => {
                    const icon = L.divIcon({
                        className: 'icao-airport-icon',
                        html: `<svg width="12" height="12" viewBox="0 0 12 12">
                                <circle cx="6" cy="6" r="4" stroke="#f0ad4e" stroke-width="1" fill="none" />
                                <line x1="6" y1="2" x2="6" y2="10" stroke="#f0ad4e" stroke-width="1" />
                                <line x1="2" y1="6" x2="10" y2="6" stroke="#f0ad4e" stroke-width="1" />
                               </svg>`,
                        iconSize: [12, 12],
                        iconAnchor: [6, 6]
                    });
                    const marker = L.marker([adp.lat, adp.lon], { icon: icon });
                    marker.bindTooltip(`Airport: ${adp.id} (${adp.name})`, {
                        permanent: document.getElementById('toggle-labels-wpt')?.checked, // Latest state
                        direction: 'right',
                        className: 'map-label',
                        offset: [6, 0]
                    });
                    configAirportsLayer.addLayer(marker);
                });
                // Sync layer visibility
                if (document.getElementById('toggle-airports')?.checked) configMap.addLayer(configAirportsLayer);
                else configMap.removeLayer(configAirportsLayer);
            }
        });

    // Waypoints (ICAO: Triangle)
    fetch(`/api/aixm/waypoints?${commonParams}`)
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                configWaypointsLayer.clearLayers();
                data.waypoints.forEach(wpt => {
                    const typeColor = (wpt.type === 'TERMINAL' || wpt.type === 'APPROACH') ? '#ffaaff' : '#00d4ff';
                    const icon = L.divIcon({
                        className: 'icao-waypoint-icon',
                        html: `<svg width="10" height="10" viewBox="0 0 10 10">
                                <polygon points="5,1 9,9 1,9" fill="${typeColor}" stroke="white" stroke-width="0.5" />
                               </svg>`,
                        iconSize: [10, 10],
                        iconAnchor: [5, 5]
                    });
                    const marker = L.marker([wpt.lat, wpt.lon], { icon: icon });
                    marker.bindTooltip(`${wpt.id}`, {
                        permanent: document.getElementById('toggle-labels-wpt')?.checked, // Latest state
                        direction: 'right',
                        className: 'map-label',
                        offset: [5, 0]
                    });
                    configWaypointsLayer.addLayer(marker);
                });
                // Sync layer visibility
                if (document.getElementById('toggle-waypoints')?.checked) configMap.addLayer(configWaypointsLayer);
                else configMap.removeLayer(configWaypointsLayer);
            }
        });

    // Routes/Airways (Midpoint labels)
    fetch(`/api/aixm/routes?${commonParams}`)
        .then(res => res.json())
        .then(data => {
            const currentShowRte = document.getElementById('toggle-labels-rte')?.checked;
            console.log("Processing routes:", data.routes?.length, "Labels enabled:", currentShowRte);
            if (data.status === 'success') {
                configAirwaysLayer.clearLayers();
                data.routes.forEach(rte => {
                    const polyline = L.polyline([[rte.start_lat, rte.start_lon], [rte.end_lat, rte.end_lon]], {
                        color: '#2ea043',
                        weight: 1,
                        opacity: 0.6,
                        dashArray: '5, 5'
                    });
                    
                    if (currentShowRte) {
                        const midLat = (rte.start_lat + rte.end_lat) / 2;
                        const midLon = (rte.start_lon + rte.end_lon) / 2;
                        const labelText = (rte.route_name && rte.route_name !== 'UNKNOWN') ? rte.route_name : `${rte.start_id}→${rte.end_id}`;
                        polyline.bindTooltip(labelText, {
                            permanent: true,
                            direction: 'center',
                            className: 'route-label'
                        });
                    } else {
                        const name = (rte.route_name && rte.route_name !== 'UNKNOWN') ? rte.route_name : "Unknown Route";
                        polyline.bindTooltip(`${name}: ${rte.start_id} -> ${rte.end_id}`);
                    }
                    
                    configAirwaysLayer.addLayer(polyline);
                });
                // Sync layer visibility
                if (document.getElementById('toggle-airways')?.checked) configMap.addLayer(configAirwaysLayer);
                else configMap.removeLayer(configAirwaysLayer);
            }
        });
}



document.getElementById('toggle-airports')?.addEventListener('change', (e) => {
    console.log("Toggle Airports:", e.target.checked);
    if (e.target.checked) configMap.addLayer(configAirportsLayer);
    else configMap.removeLayer(configAirportsLayer);
});

document.getElementById('toggle-waypoints')?.addEventListener('change', (e) => {
    console.log("Toggle Waypoints:", e.target.checked);
    if (e.target.checked) configMap.addLayer(configWaypointsLayer);
    else configMap.removeLayer(configWaypointsLayer);
});

document.getElementById('toggle-airways')?.addEventListener('change', (e) => {
    console.log("Toggle Airways:", e.target.checked);
    if (e.target.checked) configMap.addLayer(configAirwaysLayer);
    else configMap.removeLayer(configAirwaysLayer);
});

document.getElementById('toggle-labels-wpt')?.addEventListener('change', () => {
    console.log("toggle-labels-wpt changed");
    loadExtraLayers();
});

document.getElementById('toggle-labels-rte')?.addEventListener('change', () => {
    console.log("toggle-labels-rte changed");
    loadExtraLayers();
});

function visualizeSectors(sectors) {
    if (!configSectorsLayer) return;
    configSectorsLayer.clearLayers();

    const bounds = L.latLngBounds();

    sectors.forEach(s => {
        if (s.polygon && s.polygon.length > 0) {
            const latlngs = s.polygon.map(pt => [pt[0], pt[1]]);
            const poly = L.polygon(latlngs, {
                color: '#58a6ff',
                weight: 2,
                fillColor: '#58a6ff',
                fillOpacity: 0.2
            }).bindTooltip(`${s.sector_id}: ${s.name} (FL${s.fl_lower} - FL${s.fl_upper})`);
            
            configSectorsLayer.addLayer(poly);
            latlngs.forEach(ll => bounds.extend(ll));
        }
    });

    if (sectors.length > 0) {
        configMap.fitBounds(bounds);
    }
}

document.getElementById('btn-select-all-sectors')?.addEventListener('click', () => {
    const checks = document.querySelectorAll('.sector-config-check');
    const allChecked = Array.from(checks).every(c => c.checked);
    checks.forEach(c => c.checked = !allChecked);
    updateMapSectorsFromUI();
});

document.getElementById('btn-save-airspace-config')?.addEventListener('click', async () => {
    console.log("Save & Apply Config clicked");
    
    const filePath = document.getElementById('config-aixm-path').value || configSelectedAixmFile;
    const firId = document.getElementById('config-fir-select').value;
    const windowSize = document.getElementById('config-window-size').value;
    const configName = document.getElementById('config-node-name').value;
    
    const statusEl = document.getElementById('config-save-status');

    if (!filePath || !firId) {
        alert("Please load an AIXM file and select an FIR first.");
        return;
    }

    try {
        statusEl.innerText = "Applying configuration and initializing node...";
        statusEl.style.color = "var(--accent)";

        console.log(`Sending setup/configure request for FIR: ${firId}, Window: ${windowSize}, Name: ${configName}`);
        
        const res = await fetch('/api/setup/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_path: filePath,
                fir_id: firId,
                window_size: parseInt(windowSize),
                config_name: configName
            })
        });
        const data = await res.json();

        if (data.status === 'success') {
            statusEl.innerText = "Success! Node configured. Reloading dashboard...";
            statusEl.style.color = "var(--success)";
            appendLog('system', `FMP Node configured for ${firId} (${configName}). RESTARTING.`);
            setTimeout(() => window.location.reload(), 1500);
        } else {
            statusEl.innerText = "Error: " + data.message;
            statusEl.style.color = "var(--danger)";
        }
    } catch (e) {
        statusEl.innerText = "Connection failed.";
        statusEl.style.color = "var(--danger)";
    }
});
async function fetchRadRules() {
    try {
        const res = await fetch('/api/rad');
        const data = await res.json();
        const tbody = document.getElementById('rad-rules-body');
        if (!tbody) return;

        tbody.innerHTML = data.rules.map(r => {
            let constraints = [];
            if (r.min_fl) constraints.push(`FL > ${r.min_fl}`);
            if (r.max_fl) constraints.push(`FL < ${r.max_fl}`);
            if (r.start_time) constraints.push(`${r.start_time}-${r.end_time}`);
            if (r.forbidden_origins && r.forbidden_origins.length) constraints.push(`From: !${r.forbidden_origins.join(',')}`);
            
            const constraintStr = constraints.join(' | ') || 'No spatial/time restrict';
            const statusClass = r.active ? 'active' : 'scheduled';
            const btnText = r.active ? 'Deactivate' : 'Activate';
            const btnClass = r.active ? 'btn-reject' : 'btn-approve';

            return `
                <tr>
                    <td><strong style="color:var(--accent)">${r.rule_id}</strong></td>
                    <td style="font-size: 0.85rem;">${r.description}</td>
                    <td><code>${r.waypoint}</code></td>
                    <td style="font-size: 0.8rem; color: var(--text-sec);">${constraintStr}</td>
                    <td><span class="status-indicator ${statusClass}">${r.active ? 'ACTIVE' : 'INACTIVE'}</span></td>
                    <td>
                        <button class="${btnClass}" style="padding: 4px 12px; font-size: 0.75rem;" onclick="toggleRadRule('${r.rule_id}', ${!r.active})">${btnText}</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('Failed to fetch RAD rules', e);
    }
}

window.toggleRadRule = async function(ruleId, active) {
    try {
        await fetch('/api/rad/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rule_id: ruleId, active: active })
        });
        fetchRadRules();
    } catch (e) {
        console.error('Failed to toggle RAD rule', e);
    }
};

document.getElementById('btn-refresh-rad')?.addEventListener('click', fetchRadRules);

// Setup Wizard Flow
async function checkSetupStatus() {
    try {
        const res = await fetch('/api/setup/status');
        const data = await res.json();
        
        if (!data.is_configured) {
            appendLog('warning', `CRITICAL: Node ${data.node_id} is UNCONFIGURED.`);
            // Auto-switch to Config Tab
            const configTabBtn = document.querySelector('[data-target="tab-config"]');
            if (configTabBtn) {
                configTabBtn.click();
            }
            
            const statusEl = document.getElementById('config-save-status');
            if (statusEl) {
                statusEl.innerHTML = `<div style="background: rgba(248, 81, 73, 0.2); border: 1px solid var(--danger); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3 style="color: var(--danger); margin-top: 0;">Initialization Required</h3>
                    <p style="font-size: 0.9rem;">This FMP node is currently running in an unconfigured state. Please load an AIXM file and select your FIR of responsibility to continue.</p>
                </div>`;
            }
        }
    } catch (e) {
        console.error('Failed to check setup status', e);
    }
}

document.getElementById('btn-fetch-firs')?.addEventListener('click', async () => {
    const filePath = document.getElementById('setup-aixm-path').value;
    const statusMsg = document.getElementById('setup-status-msg');
    
    if (!filePath) {
        statusMsg.innerText = "Please enter an AIXM file path.";
        return;
    }

    try {
        statusMsg.innerText = "Scanning AIXM file...";
        const res = await fetch(`/api/aixm/firs?file_path=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        
        if (data.status === 'success') {
            const dropdown = document.getElementById('setup-fir-dropdown');
            dropdown.innerHTML = data.firs.map(f => `<option value="${f}">${f}</option>`).join('');
            document.getElementById('setup-fir-list-container').style.display = 'block';
            statusMsg.innerText = `Detected ${data.firs.length} FIRs. Select one above.`;
            // Auto-fill ID from first entry if empty
            if (data.firs.length > 0 && !document.getElementById('setup-fir-id').value) {
                document.getElementById('setup-fir-id').value = data.firs[0];
            }
        } else {
            statusMsg.innerText = "Error scanning file: " + data.message;
        }
    } catch (e) {
        statusMsg.innerText = "Failed to reach backend.";
    }
});

document.getElementById('setup-fir-dropdown')?.addEventListener('change', (e) => {
    document.getElementById('setup-fir-id').value = e.target.value;
});

document.getElementById('btn-initialize-node')?.addEventListener('click', async () => {
    const filePath = document.getElementById('setup-aixm-path').value;
    const firId = document.getElementById('setup-fir-id').value;
    const windowSize = document.getElementById('setup-window-size').value;
    const statusMsg = document.getElementById('setup-status-msg');

    if (!filePath || !firId) {
        statusMsg.innerText = "AIXM Path and FIR ID are required.";
        return;
    }

    try {
        statusMsg.innerText = "Initializing node... system will reload.";
        const res = await fetch('/api/setup/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_path: filePath,
                fir_id: firId,
                window_size: parseInt(windowSize)
            })
        });
        const data = await res.json();
        
        if (data.status === 'success') {
            statusMsg.innerText = "Initialization complete! Reloading...";
            statusMsg.style.color = "var(--success)";
            setTimeout(() => window.location.reload(), 2000);
        } else {
            statusMsg.innerText = "Initialization failed: " + data.message;
            statusMsg.style.color = "var(--danger)";
        }
    } catch (e) {
        statusMsg.innerText = "Connection failed.";
    }
});

// Update Tab Logic to include RAD
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    checkSetupStatus();

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
            
            if (targetId === 'tab-rad') fetchRadRules();
        });
    });
});
