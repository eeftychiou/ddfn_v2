# Architecture Overview: DDFN Prototype v2

This document describes the Decentralized Demand & Capacity Balancing (DDFN) prototype v2. It replaces traditional centralized Air Traffic Flow Management (ATFM) (like Eurocontrol NM) with a true peer-to-peer pub/sub network using SWIM (System Wide Information Management) principles.

*New Developers: Please read the [Onboarding Guide](Documentation/onboarding_guide.md) first to understand the core decentralized "swarm" paradigm and golden rules of development.*

## 1. Project Structure

```text
[Project Root]/
├── src/ddfn_v2/                        # Main package
│   ├── core/                           # Core networking and base classes
│   │   ├── audit.py                    # SQLite-based immutable SWIM audit logger
│   │   ├── broker.py                   # Central SWIM Message Broker
│   │   ├── models.py                   # Core dataclass definitions (Pydantic v2)
│   │   ├── network.py                  # Base WebSocket client
│   │   ├── node.py                     # Abstract DDFN Node class
│   │   └── persistence.py              # Node-specific state persistence
│   ├── eng/                            # Engineering and physics logic
│   │   ├── airspace.py                 # Waypoint and Sector geometry
│   │   └── trajectories.py             # 4D trajectory modeling
│   ├── services/                       # Application services
│   │   ├── airport_service.py          # Local Airport FDPS edge node
│   │   ├── aoc_service.py              # Airline Operations Center edge node
│   │   ├── fmp_service.py              # Regional Flow Management Position node
│   │   ├── rad_validator.py            # RAD validator for the edge
│   │   ├── regulation_service.py       # CASA algorithm and consensus logic
│   │   ├── schedule.py                 # Mock flight schedule generator
│   │   └── sim_manager.py              # Simulation control panel
│   └── util/                           # Utility scripts
│       └── aixm_tool.py                # AIXM 4.5 Parser utilities
├── tests/                              # Global test directory
│   ├── unit/                           # Unit tests (isolated logic)
│   ├── integration/                    # Integration tests (cross-service)
│   ├── scenarios/                      # Complex simulation scenario tests
│   └── ui/                             # UI/End-to-end tests
├── scripts/                            # Diagnostic and utility scripts
│   ├── run_all_legacy.py               # Legacy bootstrap script
│   └── run_fir_test_legacy.py          # Legacy FIR bootstrap script
├── data/                               # Static data files (AIXM, schedules)
├── web/                                # Frontend dashboards (broker, sim, node)
├── logs/                               # Output log files and audit database
├── README.md                           # System overview and quick start guide
├── Architecture.md                     # This document
└── Documentation/                      # Additional guides
    └── development_roadmap.md          # Future growth plan to rival Eurocontrol NM

## 2. High-Level System Diagram

```text
       [Global Sim Manager] --> [Broker (WebSocket Route)]
                                 ^    |                      |
[FMP Node: LFFF] <--------------+    +-> [Audit Log DB]     |
 (FMP Dashboard)                     |                      v
                                     |             [AOC Node: DLH]
[Airport Node: LFPG] <---------------+             (Fleet monitoring, RAD checks)
 (Manages AAR/ADR) 
```
*Note: The Broker contains zero business logic. It simply distributes messages on topics like `ddfn.capacity.state`, `ddfn.flow.negotiation`, etc.*

## 2.1. Security & Data Integrity Design Principles

To maintain robustness across the decentralized SWIM network, the following security and integrity principles are enforced:

- **Input Sanitization:** All user-provided file uploads (e.g., AIXM data) are sanitized. Uploaded filenames are stripped of path components and stored with UUID-based names to prevent path traversal attacks.
- **Secret Management:** API keys and other secrets are never logged to standard output. Auto-generated keys emit a generic warning without revealing the key value.
- **Audit Logging:** All significant state changes (capacity overrides, consensus proposals, and HITL approvals) are written to an append-only, tamper-evident audit log. The audit subsystem uses asynchronous I/O to avoid blocking the main event loop.
- **Idempotency & Deduplication:** Every message and consensus proposal carries a unique identifier. Nodes persist processed IDs to prevent duplicate processing, ensuring deterministic outcomes even across restarts.
- **CTOT Integrity:** The CASA (Collaborative Air Traffic Flow Management Slot Allocation) algorithm assigns CTOTs based on the computed `assigned_slot` time. This ensures that even in-flight aircraft receive correct, forward-looking departure times rather than erroneous recalculations from their original `departure_time`.

## 3. Core Decentralized Components

### 3.1. Broker (`broker.py`)
- **Role**: Purely passive message router for the distributed network.
- **State**: It holds NO ATFM state.
- **Audit**: Natively logs all pub/sub network activity into an immutable SQLite database (`logs/swim_audit.db`).
- **Security/Safety**: Enforces unique `node_id` registration to prevent impersonation or accidental routing loops.

### 3.2. FMP Nodes (`fmp_service.py`)
- **Role**: Regional Flow Management Positions.
- **Launch Modes**: FMP nodes support two distinct launch configurations:

  **1. Unconfigured State (Initial Setup)**
  - Nodes start in an **UNCONFIGURED** state by default when no prior configuration exists.
  - The user must complete initialization via the **Airspace Config** tab in the dashboard:
    1. Load an AIXM file containing airspace definitions.
    2. Select an FIR (Flight Information Region) from the parsed AIXM data.
    3. Select one or more sectors forming a contiguous airspace area of responsibility. **Partial FIR selection** is supported, allowing a node to be in charge of only a subset of an FIR's sectors. If no sub-sectors are defined in the AIXM, the FIR itself is included in the sector list to allow full FIR-level responsibility.
    4. Select any **Airports** within the FIR to be managed by the node. Choosing an airport creates a virtual 3D sector around the airport location to track local arrivals/departures.
    5. Configure the **Baseline Capacity** (default: 40 flt/hr) which is applied to all selected sectors and airports.
    6. Configure the measurement window size (default: 120 minutes).
    7. Save the configuration with a unique name (e.g., "LCCC_West").
  - The configuration is persisted to `data/node_configs/[node_id].json` and can be reused for subsequent launches.

  **2. Configured State (Reload)**
  - Nodes can be launched directly into a **CONFIGURED** state by loading a specific configuration file.
  - **Reference-Based Architecture (v2)**: To ensure versatility and small-footprint persistence, node configurations do NOT store full sector geometries. Instead, they store **references (IDs)** to AIXM elements.
  - Upon loading a configuration, the FMP performs a **two-step re-resolution**:
    1. **AIXM Registry Load**: The AIXM source file (e.g., `BD_2025...xml`) is loaded into a global memory registry (`airspace.py`), making the entire FIR's waypoints, airways, and sectors available for trajectory modeling.
    2. **Responsibility Resolution**: The node's specific Area of Responsibility (AoR) — defined as a list of sector and airport IDs — is re-resolved from the registry. This ensures the node always uses the latest geometry and parameters from the master AIXM file.
  - Configurations are stored in three ways:
    1. **Primary State**: Persistent state in `data/node_configs/[node_id].json` (the active config for that node).
    2. **Named Library**: Configurations saved with a name (e.g., "LCCC_Demo") are stored within `data/node_configs/[node_id]_saved.json`.
    3. **Standalone Files**: Named configurations are also exported as standalone `[Configuration Name].json` files in `data/node_configs/`.
  - The FMP automatically loads its local configuration on startup, restoring:
    - The selected FIR and sectors (re-resolved from AIXM)
    - Virtual sectors representing selected airports (re-reconstructed around airport coordinates)
    - The measurement window and baseline capacity settings
    - All persisted capacity overrides and state (via the linked `.db` file)

- **Domain**: Each node manages ONLY its local FIR sectors and predicts demand strictly for its local airspace. No global macroscopic view exists.
- **Responsibilities**: 
  - Subscribes to dynamic trajectory updates.
  - Predicts local capacity bottlenecks against declared capacities using a configurable sliding measurement window.
  - Emits `CONSTRAINT_WARNING_TRIGGER` to initiate downstream mitigation (CASA algorithms).
  - Emits `DISTRIBUTED_FLOW_CONSENSUS` when establishing slots (CTOTs) for arriving traffic.
  - Supports **Dynamic Re-sectorization**: Processes `MERGE_SECTORS` commands to combine multiple physical sectors into virtual operational units while preserving historic state.

### 3.3. Airspace Configuration Baseline UI Design
For a detailed breakdown of the UI components and data flow, see the [Airspace Configuration Design Specification](file:///C:/Users/eftyc/Antigravity/ddfn_v2/design_airspace_config.md).
- **Static Controls**: To ensure consistency, "Select / Unselect All" checkboxes are implemented as **static HTML elements** in the headers of the Sector and Airport lists.
- **Dynamic Synchronization**: The UI logic in `app.js` (`updateSelectAllState`) synchronizes these static checkboxes with the dynamic state of the loaded list items (checked, unchecked, or indeterminate).
- **Persistence Visibility**: The "Airspace Config" tab follows a strict auto-initialization pattern. Upon loading a saved configuration, the UI automatically restores the AIXM path, FIR selection, and the subset of sectors/airports, ensuring that the visual state always matches the node's underlying Area of Responsibility (AoR).
  - **Responsive FMP Graph**: The dashboard features a real-time demand vs. capacity graph that initializes immediately upon sector selection, even before dedicated performance data is received from the network, by utilizing local metadata for baseline capacity visualization.
  - Supports **Tactical RAD Management**: Processes `RAD_RULE_UPDATE` to activate/deactivate route restrictions in real-time.
  - **Flight Re-processing**: Implements `_reprocess_all_flights` to re-trigger route calculations whenever the AIXM configuration is updated, resolving potential race conditions and ensuring trajectories are validated against the new airspace structure.
  - **Airport Responsibility**: A node can be designated as "the airport itself" or take responsibility for specific airports within an FIR. This is implemented via **Circular Virtual Sectors** (e.g., 5NM radius) created around selected airports, allowing the FMP to track and regulate arrival/departure flows using the same demand/capacity logic as physical sectors.
  - **Partial FIR Selection**: Nodes can be responsible for either an entire FIR or a specific **sub-selection of contiguous sectors**. This allows for granular airspace delegation.
  - **Configuration Persistence**: All configurations are saved with a `baseline_capacity` which defaults to 40 but can be user-defined. This capacity is automatically applied to all selected physical and virtual sectors upon loading.
- **Dynamic Data Loading**: The FMP UI and services dynamically fetch node-specific sector and configuration metadata from centralized configuration sources or the `/metadata` endpoint, replacing legacy hardcoded definitions.
- **Dynamic Fleet Tracking (AOC)**: AOC nodes now actively update aircraft status (ETA, entry/exit points) based on real-time Distributed Airspace Inventory updates rather than relying solely on initial flight plan estimates.
- **UI Auto-Initialization**: The **Airspace Config** tab now automatically restores the last used AIXM source, FIR selection, and partial sector/airport selection on startup. This is achieved via the `/api/config/aixm_source` endpoint and a synchronized UI rendering flow that respects the active node responsibility.
- **User Interface**: Each FMP serves its own isolated UI dashboard. Initial setup is achieved through the **Airspace Config** tab. The **Overview** tab now features a dynamic Leaflet map that visualizes the polygons and statuses of all sectors managed by the node.

### 3.3. Airport Nodes (`airport_service.py`)
- **Role**: Edge nodes representing airports (FDPS).
- **Domain**: Manages Arrival Acceptance Rate (AAR) and Airport Departure Rate (ADR).
- **Responsibilities**:
  - Responds to upstream FMP capacity warnings by proposing Ground Delay Programs (GDPs - delaying own departures).
  - Emits warnings if its AAR is breached by inbound traffic.
  - Runs a clearinghouse auction for accepting proposed departure delays.
  - Executes autonomous flow scavenging utilizing "Ready-to-Fly" (REA) messages.

### 3.4. AOC Nodes (`aoc_service.py`)
- **Role**: Airline Operations Centers tracking their fleet.
- **Responsibilities**:
  - Monitors `DISTRIBUTED_FLOW_CONSENSUS` to distribute CTOT assignments to specific flights.
  - Publishes `AOCC_READY_TO_FLY` (REA messages) indicating a flight is bearded and can accept a slot swap for a better departure time.

### 3.5. RAD Validator (`rad_validator.py`)
- **Role**: Replicates Eurocontrol NM RAD (Route Availability Document).
- **Execution**: Run entirely at the edge nodes (Airport/AOC) instead of centrally. Evaluates 4D trajectories against constraint rules (e.g. FL limit at a waypoint between certain hours).
- **Impact**: Flight plans/slot swaps are automatically blocked if they violate RAD constraints.

### 3.6. Trajectory Engine (`trajectories.py` / `airspace.py`)
- **Role**: 4D trajectory modeling, Waypoints, and Sector geometry.
- **Improvements**: 
    - Moved to **strict Pydantic v2 models** for all data transfer and state objects.
    - Uses a **Spatial Filter (Bounding Box check)** to skip irrelevant sectors, significantly improving performance.
    - **Codebase Migration**: Normalized `datetime` usage to a unified granular import pattern (`from datetime import datetime, timedelta, timezone`) across all services to prevent scope-related `AttributeError` and `TypeError` issues.

### 3.7. Domain Services (`services/`)
- **RegulationService**: Extracted CASA (Computer Assisted Slot Allocation) algorithm and consensus participation logic.

### 3.8. Simulation Manager (`sim_manager.py`)
- **Role**: Overarching control panel for dynamic flight plan injection.
- **Responsibilities**:
  - Serves the Global Flight Schedule Manager UI (`sim_dashboard`) on port 8050.
  - Generates and broadcasts `FLIGHT_PLAN_FILED` events to the rest of the SWIM network.
  - Subscribes to the live `ddfn.airspace.inventory` feed for global autonomous tracking.

## 4. Data Stores 

### 4.1. Local FDPS (Memory)
- **Type**: In-Memory structures inside FMPs and Airports.
- **Purpose**: Because the system is decentralized, every Node maintains its own partial `FlightDataProcessingSystem` (`trajectories.py`) representing its isolated view of the world.

### 4.2. SWIM Audit DB (`audit.py`)
- **Type**: SQLite (`logs/swim_audit.db`).
- **Purpose**: Stores an immutable record of all topics, message payloads, and consensus algorithms taking place over the broker. Critical for post-ops analysis.

### 4.3. Node State DB (`persistence.py`)
- **Type**: SQLite (`node_configs/[node_id]_state.db`).
- **Purpose**: Stores node-specific mutable state that must survive restarts (manual capacity overrides, processed message IDs for idempotency).

## 5. Network Protocol and Communication

- **Transport**: WebSockets (`fastapi`, `uvicorn`).
- **Data Format**: JSON-serialized Pydantic Models (`models.py`).
- **Protocol Dictionary**: For a comprehensive list of all SWIM message topics, their publishers/subscribers, and exact JSON JSON-serialized Pydantic Models exchanged, refer to the [Protocol Message Dictionary](Documentation/protocol_message_dictionary.md).
- **Topics**: Subscriptions define scope (e.g., `ddfn.capacity.state`, `ddfn.relay.handover`, `ddfn.warning.trigger`).
- **Idempotency Check**: Nodes maintain a memory cache (`processed_consensus_ids`, etc.) and use `PersistenceManager` for cross-restart robustness.

## 6. Testing Strategy (New)

The DDFN project enforces a **Test-Driven Development (TDD)** workflow for all core components.

- **Persistence Testing**: `test_persistence.py` verifies SQLite-based idempotency and override persistence using unique per-test databases to handle Windows file locking.
- **SWIM Messaging Testing**: `test_broker_unit.py` uses FastAPI's `TestClient` to verify message routing, subscription logic, and node registration constraints.
- **Ripple Propagation Testing**: `test_fir_chain_propagation.py` verifies the end-to-end 5-node ripple flow, including CASA calculations, cross-node proposals, HITL approval, and consensus synchronization.
- **Airspace/Trajectory Testing**: Future tests in `test_trajectories.py` focus on 4D volume intersections and spatial filtering accuracy.

## 7. Decentralized Capacity Management (Ripple Flow)

The system implements a multi-hop, peer-to-peer capacity balancing mechanism known as **Ripple Propagation**. This allows a local constraint in one FIR to automatically re-balance traffic across the entire downstream flight chain.

*Note: For visual Mermaid diagrams documenting the internal warning states (Airport Auctions and FMP HITL), see the [Node State-Machines](Documentation/node_state_machines.md).*

### 7.1. Message Flow Lifecycle
1. **Manual Override**: A user applies a `MANUAL_CAPACITY_OVERRIDE` to a specific sector in the dashboard.
2. **Local Assessment**: The owner node detects a demand/capacity breach and runs the local **CASA (Computer Assisted Slot Allocation)** algorithm.
3. **Ripple Proposal**: The owner node identifies "First-Hop" neighbors whose flights are entering the constrained sector and emits a `CTOT_ASSIGNMENT_PROPOSAL`.
4. **HITL Approval (Downstream)**: Neighboring FMPs receive the proposal and surface a `UI_INBOX_APPROVAL_REQUEST` to their operators.
5. **Consensus**: Once an operator clicks **APPROVE**, the node emits a `DISTRIBUTED_FLOW_CONSENSUS` containing the agreed slot table.
6. **Synchronization**: All participating nodes (Origin Airport, intermediate FMPs, etc.) receive the consensus and update their local **FDPS** trajectories with the new **Most Restrictive CTOT**.

### 7.2. Collaborative Algorithms
- **CASA (FPFS)**: Implemented in `RegulationService.run_casa`, ensuring that even in total sector closures (`capacity=0`), flights are correctly delayed to the end of the constraint window.
- **Idempotency**: All nodes utilize `PersistenceManager` to ensure that a single consensus event is processed exactly once, preventing infinite routing loops in the SWIM network.

## 7. Component Specification Changes (Phase 2)

### [models.py](file:///c:/Users/eftyc/Antigravity/ddfn_v2/src/ddfn_v2/core/models.py)
Core data structures used across the system. All models are implemented using **Pydantic BaseModels** (v2) to provide strict typing, automated validation, and easy serialization/deserialization.

### [trajectories.py](file:///c:/Users/eftyc/Antigravity/ddfn_v2/src/ddfn_v2/eng/trajectories.py)
The `TrajectorySolver` now supports dependency injection for sector databases and performs a bounding box overlap check before running expensive ray-casting intersections. Added support for tracking `rad_violation` flags on the `FlightTrajectory` model for enhanced edge-based validation.

### [Data Normalization]
Normalized identifier names to `ident` across the system (specifically in `app.js`, `airspace.py`, and `aixm_tool.py`) and `.sector_id` for sectors, aligning with ICAO terminology and backend Pydantic models. Added `polygon` geometry to `SectorCapacity` to support frontend map visualization.

## 8. Configuration Management

The system uses a centralized configuration module (`core/config.py`) that loads settings from environment variables with sensible defaults.

### Environment Variables
- `DDFN_BROKER_HOST`: Broker host (default: 127.0.0.1)
- `DDFN_BROKER_PORT`: Broker port (default: 8001)
- `DDFN_FMP_MEASURE_WINDOW`: FMP measurement window in minutes (default: 120)
- `DDFN_FMP_DEFAULT_CAPACITY`: Default sector capacity (default: 40)
- `DDFN_AIRPORT_DEFAULT_AAR`: Default arrival acceptance rate (default: 30)
- `DDFN_AIRPORT_DEFAULT_ADR`: Default departure rate (default: 28)
- `DDFN_CONFIG_DIR`: Configuration directory (default: data/node_configs)
- `DDFN_LOGS_DIR`: Logs directory (default: logs)
- `DDFN_DATA_DIR`: Data directory (default: data)

## 9. Async File I/O

File operations use `aiofiles` for non-blocking I/O, improving concurrency and responsiveness. This applies to:
- Configuration saving/loading
- Audit log writing
- State persistence operations

## 10. Task Lifecycle Management

The broker implements proper task cleanup to prevent memory leaks:
- Tasks are tracked using `weakref.WeakSet`
- Tasks have a 5-second timeout for publish operations
- Cancelled tasks are properly cleaned up

## 11. Code Coverage

The project uses pytest-cov for coverage reporting:
- HTML reports: `coverage_html/index.html`
- XML reports: `coverage.xml`
- Terminal reports with missing lines

## 12. Docker Containerization

Multi-stage Docker build for optimized production deployment:
- Base image: `python:3.11-slim`
- Exposed ports: 8001, 8010, 8011, 8012, 8013, 8030, 8031, 8032, 8050
- Docker Compose configuration for full stack deployment

## 13. Glossary / Acronyms

- **AAR**: Arrival Acceptance Rate
- **ADR**: Airport Departure Rate
- **AOC**: Airline Operations Center
- **ATFM**: Air Traffic Flow Management 
- **CASA**: Computer Assisted Slot Allocation (algorithm used to delay flights)
- **CTOT**: Calculated Take-Off Time (a "slot" given to a flight)
- **FDPS**: Flight Data Processing System
- **FMP**: Flow Management Position
- **GDP**: Ground Delay Program
- **RAD**: Route Availability Document
- **REA**: Ready-to-Fly (message emitted by AOCC to scavenge earlier unutilized slots)
- **SWIM**: System Wide Information Management

## 14. Prometheus Metrics

All services expose Prometheus metrics at the `/metrics` endpoint for monitoring and observability.

### 14.1 Metrics Module (`core/metrics.py`)
The metrics module provides a centralized way to collect and expose Prometheus metrics across all services.

#### Available Metrics

**Message Metrics:**
- `ddfn_messages_published_total` - Total messages published (counter, labels: topic, node_id)
- `ddfn_messages_received_total` - Total messages received (counter, labels: topic, node_id)
- `ddfn_message_processing_seconds` - Time spent processing messages (histogram, labels: message_type, node_id)

**Node Metrics:**
- `ddfn_active_nodes` - Number of active nodes in the network (gauge, labels: node_type)
- `ddfn_node_up` - Whether the node is up (1) or down (0) (gauge, labels: node_id, service)

**FMP Metrics:**
- `ddfn_sector_capacity` - Current sector capacity (gauge, labels: sector_id, node_id)
- `ddfn_sector_demand` - Current sector demand (gauge, labels: sector_id, node_id)
- `ddfn_flights_tracked` - Number of flights being tracked (gauge, labels: node_id)

**Airport Metrics:**
- `ddfn_airport_aar` - Airport Arrival Acceptance Rate (gauge, labels: icao)
- `ddfn_airport_adr` - Airport Departure Rate (gauge, labels: icao)
- `ddfn_airport_inbound_demand` - Current inbound demand (gauge, labels: icao)

**WebSocket Metrics:**
- `ddfn_websocket_connections` - Number of active WebSocket connections (gauge, labels: service)
- `ddfn_websocket_messages_total` - Total WebSocket messages (counter, labels: direction, service)

**API Metrics:**
- `ddfn_api_requests_total` - Total API requests (counter, labels: method, endpoint, status)
- `ddfn_api_request_duration_seconds` - Time spent processing API requests (histogram, labels: endpoint)

### 14.2 Usage Example
```python
from ddfn_v2.core.metrics import (
    record_message_published, update_flight_count,
    track_processing_time, get_metrics
)

# Record a message being published
record_message_published('ddfn.capacity.state', 'FMP_LCCC')

# Update flight count
update_flight_count('FMP_LCCC', 42)

# Track processing time with decorator
@track_processing_time('flight_plan', 'FMP_LCCC')
async def process_flight_plan(flight_plan):
    # Process flight plan
    pass

# Get metrics for Prometheus scraping
metrics_output = get_metrics()
```

## 15. UI Theming

The web dashboards support both light and dark themes with a persistent user preference.

### 15.1 Theme Management (`web/shared/theme.js`)
The theme manager handles theme switching and persistence:
- Automatic detection of system preference
- LocalStorage persistence of user choice
- Smooth transitions between themes

### 15.2 CSS Variables (`web/shared/theme.css`)
CSS custom properties enable consistent theming across all dashboards:
- Background colors (`--bg-primary`, `--bg-secondary`, `--bg-tertiary`)
- Text colors (`--text-primary`, `--text-secondary`, `--text-muted`)
- Accent colors (`--accent-primary`, `--accent-secondary`)
- Status colors (`--success`, `--warning`, `--danger`, `--info`)

### 15.3 Responsive Design (`web/shared/responsive.css`)
Mobile-first responsive design with breakpoints:
- Mobile: < 768px (single column, bottom navigation)
- Tablet: 768px - 1023px (2 columns, side navigation)
- Desktop: 1024px+ (3-4 columns, full navigation)

## 16. Kubernetes Deployment

The system includes complete Kubernetes manifests for production deployment.

### 16.1 Manifest Structure (`k8s/`)
- `namespace.yaml` - DDFN v2 namespace
- `configmap.yaml` - Environment configuration
- `secret.yaml` - Sensitive configuration (API keys)
- `broker-deployment.yaml` - Broker service
- `fmp-deployment.yaml` - FMP nodes (LCCC, LFFF)
- `airport-deployment.yaml` - Airport nodes
- `sim-manager-deployment.yaml` - Simulation manager
- `ingress.yaml` - Ingress rules and load balancer
- `kustomization.yaml` - Kustomize configuration

### 16.2 Deployment
```bash
# Deploy to Kubernetes
kubectl apply -k k8s/

# Verify deployment
kubectl get pods -n ddfn-v2
kubectl get svc -n ddfn-v2
```

### 16.3 Health Checks
All deployments include liveness and readiness probes:
- Liveness probe: `/health` endpoint
- Readiness probe: `/health` endpoint
- Resource limits and requests defined

## 17. Chaos Engineering

The system includes chaos engineering tests to verify resilience under failure conditions.

### 17.1 Test Categories (`tests/chaos/`)
- **Broker Failure**: Tests node reconnection, message durability
- **Network Partition**: Tests split-brain prevention
- **Node Failure**: Tests graceful shutdown and failover
- **Load Spikes**: Tests behavior under sudden load
- **Resource Exhaustion**: Tests memory and CPU pressure handling

### 17.2 Chaos Runner (`tests/chaos/chaos_runner.py`)
Interactive chaos experiment runner:
```bash
# Run chaos experiments for 30 minutes
python tests/chaos/chaos_runner.py --duration 30

# Run specific experiment
python tests/chaos/chaos_runner.py --experiment broker_restart
```

## 6. Health Check Endpoints

All services expose a `/health` endpoint for monitoring and orchestration:

### 6.1 Broker Health (`GET /health`)
Returns broker operational status:
```json
{
  "status": "healthy",
  "service": "broker",
  "active_nodes": 5,
  "active_topics": 3,
  "timestamp": "2026-03-21T15:00:00+00:00"
}
```

### 6.2 FMP Service Health (`GET /health`)
Returns FMP node status:
```json
{
  "status": "healthy",
  "service": "fmp",
  "node_id": "FMP_LFFF_DDFN_NODE",
  "configured": true,
  "sectors_count": 12,
  "flights_tracked": 45,
  "timestamp": "2026-03-21T15:00:00+00:00"
}
```

### 6.3 Airport Service Health (`GET /health`)
Returns airport node status:
```json
{
  "status": "healthy",
  "service": "airport",
  "icao": "LFPG",
  "aar": 35,
  "adr": 30,
  "flights_tracked": 8,
  "timestamp": "2026-03-21T15:00:00+00:00"
}
```

### 6.4 AOC Service Health (`GET /health`)
Returns AOC node status:
```json
{
  "status": "healthy",
  "service": "aoc",
  "node_id": "AFR",
  "flights_managed": 25,
  "timestamp": "2026-03-21T15:00:00+00:00"
}
```

### 6.5 Sim Manager Health (`GET /health`)
Returns simulation manager status:
```json
{
  "status": "healthy",
  "service": "sim_manager",
  "broker_connected": true,
  "timestamp": "2026-03-21T15:00:00+00:00"
}
```

## 7. API Authentication

All sensitive API endpoints (except health checks) require authentication via the `X-API-Key` header.

### 7.1 Authentication Module (`core/auth.py`)
- **API Key Source**: Loaded from `DDFN_API_KEY` environment variable
- **Auto-Generation**: If not set, a secure key is auto-generated and logged on startup
- **Header Name**: `X-API-Key`

### 7.2 Protected Endpoints
The following endpoints require authentication:
- **Broker**: `/api/nodes`, `/api/audit`
- **FMP Service**: All POST endpoints (`/api/sectors/*`, `/api/config/*`, `/api/aixm/upload`, `/api/rad/toggle`)
- **Airport Service**: `/api/aar/override`
- **Sim Manager**: `/api/flights/inject`

### 7.3 Public Endpoints
The following endpoints remain public:
- All `/health` endpoints (for monitoring)
- **FMP Service**: `/metadata` (for service discovery)

### 7.4 Example Usage
```bash
# Health check (no auth required)
curl http://127.0.0.1:8001/health

# Protected endpoint (auth required)
curl -H "X-API-Key: your-api-key" http://127.0.0.1:8001/api/nodes
```
