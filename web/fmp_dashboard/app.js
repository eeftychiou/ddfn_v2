let ws;
var demandChart;
const logContainer = document.getElementById('log-container');
const inboxContainer = document.getElementById('inbox-container');
let currentSlotTable = [];
let selectedFlights = [];
let currentWarningId = "";
let currentAirspaceInventory = [];
let currentDemandProfile = [];
var currentSectorCapacity = 0;
let currentSectorOverrides = [];
let currentChartBins = [];
let configMap, configSectorsLayer, configCountryLayer;
let configAirportsLayer, configWaypointsLayer, configAirwaysLayer;
let configSelectedAixmFile = "";
let overviewMap, overviewSectorsLayer;

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
    if (!demandChart) return;

    // Use a default time window if no profile is available (e.g. for initial load)
    let profileToProcess = [...currentDemandProfile];
    if (profileToProcess.length === 0) {
        // Create 24 hours of empty bins to show time scale and capacity
        const now = new Date();
        const startOfToday = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 0, 0, 0));
        const startTs = startOfToday.getTime();
        for(let i=0; i<288; i++) {
            const ts = startTs + i*5*60000;
            const d = new Date(ts);
            profileToProcess.push({
                timestamp: ts,
                time_label: d.getUTCHours().toString().padStart(2, '0') + ":" + d.getUTCMinutes().toString().padStart(2, '0'),
                demand_count: 0,
                flights: []
            });
        }
    }

    const scopeHours = parseInt(document.getElementById('chart-time-scope')?.value || 4);
    const panHours = parseInt(document.getElementById('chart-pan-slider')?.value || 0);

    const centerIdx = 144 + (panHours * 12);
    const halfScopeBins = (scopeHours * 12) / 2;

    let startIdx = Math.max(0, centerIdx - halfScopeBins);
    let endIdx = Math.min(profileToProcess.length, centerIdx + halfScopeBins);

    currentChartBins = profileToProcess.slice(startIdx, endIdx);

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
    console.log(`[DEBUG] WebSocket Message: ${msgType} | Node: ${payload.node_id} | ActiveNode: ${getActiveNode()}`);

    if (msgType === "CAPACITY_STATE_BROADCAST") {
        const s = payload.sector;

        // Update Overview Map if it exists
        if (overviewSectorsLayer) {
            overviewSectorsLayer.eachLayer(layer => {
                if (layer.options.id === `map-sector-${s.sector_id}`) {
                    layer.setStyle({
                        color: s.status === 'RED' ? '#f85149' : '#58a6ff',
                        fillColor: s.status === 'RED' ? '#f85149' : '#58a6ff'
                    });
                }
            });
        }

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
            console.log(`[DEBUG] Received Inventory Update. Flights: ${payload.flights ? payload.flights.length : 0}`);
            currentAirspaceInventory = payload.flights || [];
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

document.getElementById('builder-sector')?.addEventListener('change', (e) => {
    const sid = e.target.value;
    if (window.CURRENT_RESPONSIBILITY) {
        const meta = window.CURRENT_RESPONSIBILITY.find(s => s.sector_id === sid);
        if (meta) {
            currentSectorCapacity = meta.declared_capacity_per_hour;
        }
    }
    currentDemandProfile = [];
    if (demandChart) {
        // updateChartFromProfile will handle the 4-dataset initialization if needed
        updateChartFromProfile();
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
async function initWorkspace() {
    const configName = document.getElementById('config-name-display')?.innerText.replace('Config: ', '') || 'Default';
    
    try {
        const res = await fetch('/metadata');
        const data = await res.json();
        
        if (data.node_id) {
            window.ACTIVE_NODE_ID = data.node_id;
            const nodeShort = data.node_id.split('_')[0];
            document.getElementById('active-node-badge').innerText = configName !== 'Default' ? `Config: ${configName}` : `Node: ${nodeShort}`;
        }
        
        if (data.measure_window) {
            const select = document.getElementById('measurement-window-select');
            if (select) select.value = data.measure_window;
        }

        if (data.sectors && data.sectors.length > 0) {
            // Priority given to sectors the node actually has responsibility for
            currentWorkspaceSectors = data.sectors.map(s => s.sector_id);
            window.CURRENT_RESPONSIBILITY = data.sectors;
            
            renderWorkspace();
            initOverviewMap(data.sectors);
            
            // Auto-select first sector for the chart if none selected
            const builderSelect = document.getElementById('builder-sector');
            if (builderSelect && !builderSelect.value && currentWorkspaceSectors.length > 0) {
                builderSelect.value = currentWorkspaceSectors[0];
                builderSelect.dispatchEvent(new Event('change'));
            }
        } else {
            // Fallback for unconfigured nodes
            currentWorkspaceSectors = (FIR_SECTORS[getActiveNode()] || []).slice(0, 2).map(s => s.id);
            renderWorkspace();
        }
    } catch (e) {
        console.error("Failed to fetch node metadata:", e);
        // Fallback
        currentWorkspaceSectors = (FIR_SECTORS[getActiveNode()] || []).slice(0, 2).map(s => s.id);
        renderWorkspace();
    }
    
    loadConfigurations();
}

function initOverviewMap(sectors) {
    if (!document.getElementById('overview-map')) return;
    
    if (!overviewMap) {
        overviewMap = L.map('overview-map', {
            zoomControl: true,
            attributionControl: false
        }).setView([47.0, 2.0], 5); // Default center on Europe

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19
        }).addTo(overviewMap);

        overviewSectorsLayer = L.featureGroup().addTo(overviewMap);
    }
    
    visualizeOverviewSectors(sectors);
}

function visualizeOverviewSectors(sectors) {
    if (!overviewSectorsLayer) return;
    overviewSectorsLayer.clearLayers();
    
    let bounds = null;
    
    sectors.forEach(s => {
        if (s.geometry && s.geometry.length > 0) {
            const poly = L.polygon(s.geometry, {
                color: s.status === 'RED' ? '#f85149' : '#58a6ff',
                weight: 2,
                fillColor: s.status === 'RED' ? '#f85149' : '#58a6ff',
                fillOpacity: 0.1,
                id: `map-sector-${s.sector_id}`
            }).addTo(overviewSectorsLayer);
            
            poly.bindTooltip(s.sector_id, {
                permanent: true,
                direction: 'center',
                className: 'map-label'
            });
            
            if (!bounds) bounds = poly.getBounds();
            else bounds.extend(poly.getBounds());
        }
    });
    
    if (bounds && sectors.length > 0) {
        overviewMap.fitBounds(bounds, { padding: [20, 20] });
    }
    
    document.getElementById('map-sector-count').innerText = `${sectors.length} Sectors`;
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
        // Find sector info from metadata if available
        let desc = "Active Sector";
        if (window.CURRENT_RESPONSIBILITY) {
            const meta = window.CURRENT_RESPONSIBILITY.find(s => s.sector_id === sid);
            if (meta && meta.description) desc = meta.description;
        } else {
            const allSectors = FIR_SECTORS[getActiveNode()] || [];
            const info = allSectors.find(s => s.id === sid);
            if (info) desc = info.desc;
        }

        const card = document.createElement('div');
        card.className = 'node';
        card.id = `sector-${sid}`;
        card.innerHTML = `
            <div class="node-header">
                <span class="node-name">${sid}</span>
                <span class="node-id">${desc}</span>
            </div>
            <div class="demand-meter">
                <div class="meter-bar"><div class="meter-fill green" style="width: 0%"></div></div>
                <div class="meter-labels">
                    <span>Demand: <span class="demand-val">0</span></span>
                    <span>Cap: <span class="cap-val">--</span></span>
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

// Removed redundant initialization and duplicate listener

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
                if (data.window_size) {
                    document.getElementById('config-window-size').value = data.window_size;
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
    const select = document.getElementById('config-saved-list');
    try {
        const res = await fetch('/api/config/list');
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Server returned ${res.status}: ${errorText}`);
        }
        const data = await res.json();
        if (data.status === 'success' && select) {
            select.innerHTML = '<option value="">-- Select to Load --</option>';
            data.configs.forEach(cfg => {
                const opt = document.createElement('option');
                opt.value = cfg;
                opt.innerText = cfg;
                select.appendChild(opt);
            });
        } else if (data.status === 'error' && select) {
            select.innerHTML = '<option value="">-- Error loading configs --</option>';
            console.error("Server error loading configs:", data.message);
        }
    } catch (e) {
        console.error("Failed to load configs list:", e);
        if (select) {
            select.innerHTML = '<option value="">-- Error: ' + (e.message || 'Failed to load') + ' --</option>';
        }
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

async function initConfigTab() {
    console.log("initConfigTab: fetching aixm_source...");
    try {
        const res = await fetch('/api/config/aixm_source');
        const data = await res.json();
        console.log("initConfigTab response:", data);
        
        if (data.file_path) {
            document.getElementById('config-aixm-path').value = data.file_path;
            document.getElementById('config-baseline-capacity').value = data.baseline_capacity || 40;
            document.getElementById('config-node-name').value = data.config_name || '';
            document.getElementById('config-window-size').value = data.window_size || 5;
            
            console.log("initConfigTab: calling loadAixmSource with", data.file_path, data.fir_id);
            await loadAixmSource(data.file_path, data.fir_id);
        }
    } catch (e) {
        console.error("Failed to init config tab:", e);
    }
}

async function loadAixmSource(filePath, targetFirId = null) {
    configSelectedAixmFile = filePath; // Keep this for other functions that might rely on it
    console.log(`Loading AIXM source: ${filePath}, target FIR: ${targetFirId}`);
    try {
        const firResponse = await fetch(`/api/aixm/firs?file_path=${encodeURIComponent(filePath)}`);
        const firData = await firResponse.json();

        if (firData.status === "success") {
            const select = document.getElementById('config-fir-select');
            const currentSelected = select.value;
            select.innerHTML = '<option value="">-- Select FIR --</option>';
            firData.firs.forEach(fir => {
                const opt = document.createElement('option');
                opt.value = fir;
                opt.textContent = fir;
                if (fir === targetFirId || (!targetFirId && fir === currentSelected)) opt.selected = true;
                select.appendChild(opt);
            });

            const firToLoad = targetFirId || select.value;
            if (firToLoad) {
                await loadFirSectors(filePath, firToLoad); // Renamed from renderConfigSectors to match existing
                await renderConfigAirports(filePath, firToLoad);
            }
            appendLog('system', `Loaded AIXM info from ${filePath}. ${firData.firs.length} FIRs found.`);
            loadExtraLayers(); // Keep this for waypoints/airways
        } else {
            console.error("Error loading AIXM:", firData.message);
            appendLog('error', `Failed to load AIXM info: ${firData.message}`);
            // showToast("Error loading AIXM: " + firData.message, "error");
        }
    } catch (e) {
        console.error("Failed to load AIXM FIRs:", e);
        // showToast("Failed to connect to backend.", "error");
    }
}

async function renderConfigAirports(filePath, firId) {
    const listEl = document.getElementById('config-airport-list');
    if (!listEl) return; // Ensure element exists
    listEl.innerHTML = '<div class="loading-text">Loading airports...</div>';

    try {
        const response = await fetch(`/api/aixm/airports?file_path=${encodeURIComponent(filePath)}&fir_id=${encodeURIComponent(firId)}`);
        const data = await response.json();

        if (data.status === "success" && data.airports) {
            listEl.innerHTML = '';
            if (data.airports.length === 0) {
                listEl.innerHTML = '<div class="placeholder-text">No airports found in this FIR</div>';
                return;
            }

            data.airports.forEach(apt => {
                // Check if this airport is in active responsibility (virtual sector ID = apt.ident)
                const isActive = (window.CURRENT_RESPONSIBILITY || []).some(s => s.sector_id === apt.ident);
                const isChecked = isActive ? 'checked' : '';

                const item = document.createElement('div');
                item.className = 'config-item';
                item.innerHTML = `
                    <input type="checkbox" id="apt-${apt.ident}" class="airport-config-check" ${isChecked} data-id="${apt.ident}" data-name="${apt.name}" data-lat="${apt.lat}" data-lon="${apt.lon}">
                    <label for="apt-${apt.ident}">${apt.ident} - ${apt.name}</label>
                `;
                listEl.appendChild(item);
            });

            // Add listeners for individual airport checkboxes
            listEl.querySelectorAll('.airport-config-check').forEach(cb => {
                cb.addEventListener('change', () => {
                    updateSelectAllState('airport');
                });
            });

            // Initial state for "Select All" airport checkbox
            updateSelectAllState('airport');
        } else {
            listEl.innerHTML = '<div class="error-text">Failed to load airports</div>';
        }
    } catch (err) {
        console.error("Error fetching airports:", err);
        listEl.innerHTML = '<div class="error-text">Network error</div>';
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
            
            // Only update map after selections are potentially restored by renderConfigSectors
            updateMapSectorsFromUI();
        }
    } catch (e) {
        console.error(e);
    }
}

document.getElementById('config-fir-select')?.addEventListener('change', async (e) => {
    const firId = e.target.value;
    if (!firId) return;
    loadFirSectors(configSelectedAixmFile, firId);
    renderConfigAirports(configSelectedAixmFile, firId);
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
    if (!list) return;

    list.innerHTML = sectors.map(s => {
        // Find if this sector is in active responsibility
        const activeSec = (window.CURRENT_RESPONSIBILITY || []).find(rs => rs.sector_id === s.sector_id);
        const isChecked = activeSec ? 'checked' : '';
        const flLower = activeSec ? activeSec.fl_lower : s.fl_lower;
        const flUpper = activeSec ? activeSec.fl_upper : s.fl_upper;

        return `
            <div class="sector-config-item" data-id="${s.sector_id}" style="border-bottom: 1px solid var(--glass-border); padding: 5px 0;">
                <label style="display: flex; align-items: flex-start; gap: 10px; cursor: pointer;">
                    <input type="checkbox" value="${s.sector_id}" class="sector-config-check" ${isChecked} data-id="${s.sector_id}" data-name="${s.name}" data-fl-lower="${flLower}" data-fl-upper="${flUpper}">
                    <div style="flex: 1;">
                        <strong style="color: var(--text-main); font-size: 0.9rem;">${s.sector_id}</strong><br>
                        <small style="color: var(--text-sec); font-size: 0.75rem;">${s.name}</small>
                    </div>
                </label>
                <div style="display: flex; gap: 10px; margin-top: 5px; margin-left: 25px;">
                    <div style="display:flex; flex-direction:column;">
                        <label style="font-size: 0.65rem; color:var(--text-sec);">Min FL</label>
                        <input type="number" class="fl-min-input" value="${flLower}" style="width: 50px; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); color: var(--text-main); font-size: 0.7rem; padding: 2px; border-radius: 2px;">
                    </div>
                    <div style="display:flex; flex-direction:column;">
                        <label style="font-size: 0.65rem; color:var(--text-sec);">Max FL</label>
                        <input type="number" class="fl-max-input" value="${flUpper}" style="width: 50px; background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); color: var(--text-main); font-size: 0.7rem; padding: 2px; border-radius: 2px;">
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add listeners for individual checkboxes
    list.querySelectorAll('.sector-config-check').forEach(cb => {
        cb.addEventListener('change', () => {
            updateMapSectorsFromUI();
            updateSelectAllState('sector');
        });
    });

    // Initial state for "Select All" checkbox
    updateSelectAllState('sector');

    // Add listeners for FL inputs to update data attributes
    list.querySelectorAll('.fl-min-input, .fl-max-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const checkbox = e.target.closest('.sector-config-item').querySelector('.sector-config-check');
            if (e.target.classList.contains('fl-min-input')) {
                checkbox.dataset.flLower = e.target.value;
            } else {
                checkbox.dataset.flUpper = e.target.value;
            }
        });
    });
}

function updateMapSectorsFromUI() {
    if (!configSectorsLayer) return;
    configSectorsLayer.clearLayers();
    const bounds = L.latLngBounds();

    // 1. Collect and visualize sectors
    const sectorChecks = document.querySelectorAll('.sector-config-check:checked');
    const selectedSectorIds = Array.from(sectorChecks).map(c => c.value);
    const selectedSectors = (window.CURRENT_AIXM_SECTORS || []).filter(s => selectedSectorIds.includes(s.sector_id));

    selectedSectors.forEach(s => {
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

    // 2. Collect and visualize airports
    const airportChecks = document.querySelectorAll('.airport-config-check:checked');
    airportChecks.forEach(cb => {
        const id = cb.dataset.id;
        const name = cb.dataset.name;
        const lat = parseFloat(cb.dataset.lat);
        const lon = parseFloat(cb.dataset.lon);

        if (!isNaN(lat) && !isNaN(lon)) {
            const circle = L.circleMarker([lat, lon], {
                radius: 6,
                fillColor: "#ffca28",
                color: "#ffca28",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).bindTooltip(`Airport Responsibility: ${id} (${name})`);
            
            configSectorsLayer.addLayer(circle);
            bounds.extend([lat, lon]);
        }
    });

    if (bounds.isValid()) {
        configMap.fitBounds(bounds, { padding: [20, 20] });
    }
}

function updateSelectAllState(type) {
    const listId = type === 'sector' ? 'config-sector-list' : 'config-airport-list';
    const checkAllId = type === 'sector' ? 'check-all-sectors' : 'check-all-airports';
    const checkClass = type === 'sector' ? '.sector-config-check' : '.airport-config-check';
    
    const list = document.getElementById(listId);
    const checkAll = document.getElementById(checkAllId);
    if (!list || !checkAll) return;

    const allChecks = list.querySelectorAll(checkClass);
    if (allChecks.length === 0) {
        checkAll.checked = false;
        checkAll.indeterminate = false;
        return;
    }

    const checkedCount = Array.from(allChecks).filter(c => c.checked).length;
    const allChecked = checkedCount === allChecks.length;
    const someChecked = checkedCount > 0 && !allChecked;

    checkAll.checked = allChecked;
    checkAll.indeterminate = someChecked;
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
                    marker.bindTooltip(`Airport: ${adp.ident} (${adp.name})`, {
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
                    marker.bindTooltip(`${wpt.ident}`, {
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
    
    const filePath = document.getElementById('config-aixm-path').value;
    const firId = document.getElementById('config-fir-select').value;
    const windowSize = document.getElementById('config-window-size').value;
    const baselineCapacity = document.getElementById('config-baseline-capacity').value;
    const configName = document.getElementById('config-node-name').value;

    if (!filePath || !firId) {
        showToast("Please select AIXM file and FIR", "warning");
        return;
    }

    // Collect selected sectors
    const selectedSectors = [];
    document.querySelectorAll('#config-sector-list .sector-config-check:checked').forEach(cb => {
        selectedSectors.push({
            id: cb.dataset.id,
            fl_lower: parseInt(cb.dataset.flLower || 0),
            fl_upper: parseInt(cb.dataset.flUpper || 660)
        });
    });

    // Collect selected airports
    const selectedAirports = [];
    document.querySelectorAll('#config-airport-list .airport-config-check:checked').forEach(cb => {
        selectedAirports.push({
            id: cb.dataset.id,
            name: cb.dataset.name,
            lat: parseFloat(cb.dataset.lat),
            lon: parseFloat(cb.dataset.lon)
        });
    });

    const payload = {
        file_path: filePath,
        fir_id: firId,
        sectors: selectedSectors,
        airports: selectedAirports,
        window_size: parseInt(windowSize),
        baseline_capacity: parseInt(baselineCapacity),
        config_name: configName
    };

    console.log("Saving configuration:", payload);
    showToast("Saving configuration...", "info");

    try {
        const statusEl = document.getElementById('config-save-status') || { set style(v) {}, set innerText(v) {} };
        statusEl.innerText = "Applying configuration and initializing node...";
        statusEl.style.color = "var(--accent)";

        const response = await fetch(`/api/config/apply_aixm`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-API-Key': window.API_KEY || ''
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.status === 'success') {
            statusEl.innerText = "Success! Node configured. Reloading dashboard...";
            statusEl.style.color = "var(--success)";
            appendLog('system', `FMP Node configured for ${firId} (${configName}). RESTARTING.`);
            showToast("Configuration applied successfully", "success");
            setTimeout(() => window.location.reload(), 1500);
        } else {
            const msg = data.message || (data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : "Unknown error");
            statusEl.innerText = "Error: " + msg;
            statusEl.style.color = "var(--danger)";
            showToast(`Error: ${msg}`, "error");
        }
    } catch (e) {
        const errorMsg = e.message || "Unknown error occurred";
        const statusEl = document.getElementById('config-save-status') || { set style(v) {}, set innerText(v) {} };
        statusEl.innerText = "Error: " + errorMsg;
        statusEl.style.color = "var(--danger)";
        console.error("Save config error:", e);
        showToast(`Save failed: ${errorMsg}`, "error");
    }
});

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        backdrop-filter: blur(12px);
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: fadeIn 0.3s ease-out;
    `;
    
    const colors = {
        'info': 'var(--accent)',
        'success': 'var(--success)',
        'warning': 'var(--warning)',
        'error': 'var(--danger)'
    };
    
    toast.style.borderLeft = `4px solid ${colors[type] || colors.info}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
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
            const msg = data.message || (data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : "Unknown error");
            statusMsg.innerText = "Initialization failed: " + msg;
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
            
            // Resize Chart.js if the flow tab is activated
            if (targetId === 'tab-flow' && demandChart) {
                demandChart.resize();
            }

            if (targetId === 'tab-rad') fetchRadRules();
            if (targetId === 'tab-config') {
                initAirspaceConfigTab(); // Initialize the Map
                initConfigTab();         // Load the Data
            }
        });
    });

    // Initialize the app workspace and then the components
    initChart();
    
    initWorkspace().then(() => {
        // After workspace is initialized (metadata fetched), pre-fill the config tab
        initConfigTab();
        // Start WebSocket ONLY after ACTIVE_NODE_ID is set
        initWebSocket();
    });

    // Global Select All listeners
    document.getElementById('check-all-sectors')?.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        document.querySelectorAll('.sector-config-check').forEach(cb => {
            cb.checked = isChecked;
        });
        updateMapSectorsFromUI();
    });

    document.getElementById('check-all-airports')?.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        document.querySelectorAll('.airport-config-check').forEach(cb => {
            cb.checked = isChecked;
        });
    });
});
