async function fetchNodes() {
    try {
        const res = await fetch('/api/nodes');
        const data = await res.json();
        
        const list = document.getElementById('connected-nodes-list');
        document.getElementById('node-count').innerText = data.nodes.length;
        list.innerHTML = '';
        
        data.nodes.sort().forEach(nodeId => {
            const div = document.createElement('div');
            div.className = 'node-card ' + (nodeId.includes('AIRPORT') ? 'air' : '');
            div.innerHTML = `<div class="status-dot"></div> <span>${nodeId}</span>`;
            list.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to fetch nodes', e);
    }
}

async function fetchAudit() {
    try {
        const res = await fetch('/api/audit');
        const data = await res.json();
        
        const list = document.getElementById('audit-log-list');
        list.innerHTML = '';
        
        data.logs.forEach(log => {
            const div = document.createElement('div');
            div.className = 'audit-row';
            
            if (log.message_type === 'CAPACITY_STATE_BROADCAST') div.classList.add('highlight-cap');
            else if (log.message_type.includes('CTOT')) div.classList.add('highlight-ctot');
            else if (log.message_type.includes('HANDOVER')) div.classList.add('highlight-handover');
            
            const timeStr = new Date(log.timestamp).toISOString().split('T')[1].slice(0, 8);
            const payloadStr = JSON.stringify(log.payload, null, 0);
            
            div.innerHTML = `
                <span class="time">[${timeStr}]</span>
                <span class="source">${log.source_node}</span>
                <span class="type">${log.message_type}</span>
                <span class="payload">${payloadStr}</span>
            `;
            list.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to fetch audit', e);
    }
}

// Poll every 2 seconds
setInterval(fetchNodes, 2000);
setInterval(fetchAudit, 2000);
fetchNodes();
fetchAudit();
