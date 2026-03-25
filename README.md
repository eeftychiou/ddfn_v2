# Distributed Demand & Capacity Balancing (DDFN) prototype v2

This system is a truly decentralized, drop-in replacement for traditional centralized Air Traffic Flow Management (ATFM) systems (like the Eurocontrol NM). It utilizes a peer-to-peer pub/sub SWIM network to coordinate traffic flows, assign CASA delays, and renegotiate trajectories without any single node having global authority over the airspace.

## Architecture Overview
- **Central SWIM Broker (`broker.py`)**: Acts purely as a passive message router for the distributed network and an Audit Logger. It holds no business logic or ATFM state.
- **FMP Nodes (`fmp_service.py`)**: Regional Flow Management Positions. Each node runs its own isolated UI, manages ONLY its local FIR sectors, and predicts demand strictly for its local airspace.
- **Airport Nodes (`airport_service.py`)**: Local Airport Flight Data Processing Systems (FDPS). These manage ground delay programs and slot auctions at the edge.
- **AOC Nodes (`aoc_service.py`)**: Airline Operations Centers. These track fleet schedules, negotiate slot swaps, and validate routes.
- **Simulation Manager (`sim_manager.py`)**: A centralized testing interface to dynamically inject new flights and view the global simulation state.

## Prerequisites
- Python 3.10+
- Required pip packages: `fastapi`, `uvicorn`, `websockets`, `python-multipart`

## How to Run the System

### Method 1: Full Simulation Cluster (Recommended)
To launch the complete European simulation including the Broker, 3 FMP hubs (France, Germany, UK), and 3 Airport FDPS nodes, run:
```bash
python run_all.py
```
All microservices will spin up locally. Check the `logs/` directory for individual node outputs. The SWIM audit trail is saved securely to `logs/swim_audit.db`.

### Method 2: Manual Distributed Startup
If you want to simulate running nodes across different terminals or different virtual machines:

1. **Start the Network Broker:**
   ```bash
   python broker.py
   ```
   *Runs on `http://127.0.0.1:8080` by default.*

2. **Start an FMP Node:**
   ```bash
   python fmp_service.py LFFF
   ```
   *Available nodes: `LFFF`, `EDDD`, `EGTT`.*
   *Each node embeds its own dashboard on a dedicated port (e.g., LFFF=8010, EDDD=8011).*

3. **Start an Airport Node:**
   ```bash
   python airport_service.py LFPG
   ```
   *Available nodes: `LFPG`, `EDDF`, `EGLL`.*

4. **Start an AOC Node:**
   ```bash
   python aoc_service.py AFR
   ```
   *Available airlines: `AFR`, `DLH`, `BAW`.*

5. **Start the Simulation Manager:**
   ```bash
   python sim_manager.py
   ```
   *Runs on `http://127.0.0.1:8050`.*

### Method 3: One-Click Demo Script (Recommended for Windows)
Launch the full simulation (Broker, 4 FMPs, 3 Airports, 3 AOCs, and Sim Manager) with a single command:
```powershell
./start_demo.ps1
```
This script launches all components as background jobs in the current terminal and provides a list of dashboard URLs. Use `Ctrl+C` to stop the entire cluster.

## FMP Dashboard Configuration
Once an FMP node is running, access its isolated UI via browser:
- **HECC (Cairo)**: `http://127.0.0.1:8010` (CONFIGURED)
- **LGGG (Athens)**: `http://127.0.0.1:8011` (CONFIGURED)
- **LCCC (Nicosia)**: `http://127.0.0.1:8012` (CONFIGURED)
- **FMP Lab**: `http://127.0.0.1:8013` (UNCONFIGURED - for manual setup practice)

**Note**: In the default demo (`start_demo.ps1`), three nodes are pre-configured using **reference-based JSON files** that re-resolve sector geometries from the high-fidelity AIXM source on startup. This ensures that the node's configuration is lightweight and always synchronized with the master airspace definition. For a technical breakdown of this architecture, see [Airspace Configuration Design Specification](file:///C:/Users/eftyc/Antigravity/ddfn_v2/design_airspace_config.md).

## Global Network Overview
The network is intentionally designed so no node has a global macroscopic view (to ensure true distribution). However, for analytical purposes, the central SWIM broker natively logs all pub/sub network activity into an immutable SQLite database located at `logs/swim_audit.db`. You can query this database to see exactly which nodes are publishing, subscribing, or negotiating slot constraints across the entire European mesh.

**Important Documentation Reference:**
- **[Developer Onboarding Guide](Documentation/onboarding_guide.md)**: Start here if you are new to the project. It explains the decentralized "swarm" paradigm and how to navigate the codebase safely.
- For a complete reference of the exact message payloads and topics navigating the simulation mesh, see the [Protocol Message Dictionary](Documentation/protocol_message_dictionary.md).
- To view the internal state-machine transitions (such as the Airport Auto-Auction or FMP HITL loops) visualized with Mermaid diagrams, see [Node State-Machines](Documentation/node_state_machines.md).
- For the strategic vision and upcoming developmental phases needed to rival Eurocontrol NM, see the [Future Development Roadmap](Documentation/development_roadmap.md).


## Authentication

The DDFN system now requires API authentication for sensitive endpoints.

### Environment Variables
- DDFN_API_KEY: Set this to configure a custom API key. If not set, a secure key is auto-generated on startup.

### Using Authentication
Include the X-API-Key header in requests to protected endpoints:

`ash
# Health check (no auth required)
curl http://127.0.0.1:8001/health

# Protected endpoint - requires API key
curl -H "X-API-Key: your-api-key" http://127.0.0.1:8001/api/nodes
``n
### Protected Endpoints
The following endpoints require authentication:
- **Broker**: /api/nodes, /api/audit`n- **FMP Service**: All POST endpoints (/api/sectors/*, /api/config/*, /api/aixm/upload, /api/rad/toggle)
- **Airport Service**: /api/aar/override`n- **Sim Manager**: /api/flights/inject`n
### Public Endpoints
The following endpoints remain public:
- All /health endpoints (for monitoring)
- **FMP Service**: /metadata (for service discovery)



## Environment Configuration

The system can be configured via environment variables. Create a .env file or set variables directly:

\\\ash
# Broker configuration
export DDFN_BROKER_HOST=127.0.0.1
export DDFN_BROKER_PORT=8001

# FMP configuration
export DDFN_FMP_MEASURE_WINDOW=120
export DDFN_FMP_DEFAULT_CAPACITY=40

# Airport configuration
export DDFN_AIRPORT_DEFAULT_AAR=30
export DDFN_AIRPORT_DEFAULT_ADR=28

# Paths
export DDFN_CONFIG_DIR=data/node_configs
export DDFN_LOGS_DIR=logs
export DDFN_DATA_DIR=data
\\\

## Docker Deployment

### Building the Image
\\\ash
docker build -t ddfn-v2 .
\\\

### Running with Docker Compose
\\\ash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
\\\

### Individual Service Deployment
\\\ash
# Run broker only
docker run -p 8001:8001 ddfn-v2 python -m ddfn_v2.core.broker

# Run FMP node
docker run -p 8010:8010 -e DDFN_BROKER_HOST=host.docker.internal ddfn-v2 python -m ddfn_v2.services.fmp_service --port 8010
```

## Features

- **Decentralized Architecture**: True peer-to-peer pub/sub network with no single point of failure
- **Health Check Endpoints**: All services expose `/health` for monitoring
- **API Authentication**: Secure endpoints with API key authentication
- **Prometheus Metrics**: Complete observability with metrics export at `/metrics`
- **Dark Mode Support**: All dashboards support light and dark themes
- **Responsive Design**: Mobile-first design optimized for all devices
- **Kubernetes Ready**: Complete K8s manifests for production deployment
- **Chaos Engineering**: Resilience testing framework included

## Monitoring with Prometheus

All services expose Prometheus metrics at `/metrics`:

```bash
# Scrape metrics from broker
curl http://127.0.0.1:8001/metrics

# Scrape metrics from FMP node
curl http://127.0.0.1:8010/metrics
```

Available metrics include:
- Message throughput (published/received)
- Node health and status
- Sector capacity and demand
- WebSocket connection counts
- API request latency

## UI Customization

### Dark Mode
All dashboards support dark mode:
- Click the theme toggle button (🌙/☀️) in the top navigation
- Theme preference is saved to localStorage
- System preference is respected on first visit

### Mobile Support
Dashboards are fully responsive:
- Optimized for mobile, tablet, and desktop
- Touch-friendly controls
- Adaptive navigation

## Kubernetes Deployment

### Prerequisites
- Kubernetes 1.24+
- kubectl configured
- Ingress controller (nginx recommended)

### Deploy to Kubernetes
```bash
# Apply all manifests
kubectl apply -k k8s/

# Verify deployment
kubectl get pods -n ddfn-v2
kubectl get svc -n ddfn-v2
```

### Access Services
After deployment, services are available via Ingress:
- Broker: `http://ddfn.local/broker`
- FMP LCCC: `http://ddfn.local/fmp-lccc`
- FMP LFFF: `http://ddfn.local/fmp-lfff`
- Sim Manager: `http://ddfn.local/sim`

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/ddfn_v2 --cov-report=html

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/ui/ -v           # Basic UI tests
python tests/ui/test_airspace_config_stories.py # Airspace config user stories
python -m pytest tests/chaos/ -v
```

### Chaos Engineering Tests
```bash
# Run chaos experiments
python -m pytest tests/chaos/ -v

# Run chaos runner
python tests/chaos/chaos_runner.py --duration 30
```

### Coverage Reports
After running tests with coverage, view the HTML report:

```bash
open coverage_html/index.html
```
