# Architecture Overview: DDFN Prototype v2

This document describes the Decentralized Demand & Capacity Balancing (DDFN) prototype v2. It replaces traditional centralized Air Traffic Flow Management (ATFM) (like Eurocontrol NM) with a true peer-to-peer pub/sub network using SWIM (System Wide Information Management) principles.

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
└── Architecture.md                     # This document
```

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

## 3. Core Decentralized Components

### 3.1. Broker (`broker.py`)
- **Role**: Purely passive message router for the distributed network.
- **State**: It holds NO ATFM state.
- **Audit**: Natively logs all pub/sub network activity into an immutable SQLite database (`logs/swim_audit.db`).
- **Security/Safety**: Enforces unique `node_id` registration to prevent impersonation or accidental routing loops.

### 3.2. FMP Nodes (`fmp_service.py`)
- **Role**: Regional Flow Management Positions.
- **Startup**: Nodes start in an **UNCONFIGURED** state by default. They must be initialized via the "Airspace Config" dashboard by providing an AIXM source and selecting an FIR of responsibility.
- **Domain**: Each node manages ONLY its local FIR sectors and predicts demand strictly for its local airspace. No global macroscopic view exists.
- **Responsibilities**: 
  - Subscribes to dynamic trajectory updates.
  - Predicts local capacity bottlenecks against declared capacities using a configurable sliding measurement window.
  - Emits `CONSTRAINT_WARNING_TRIGGER` to initiate downstream mitigation (CASA algorithms).
  - Emits `DISTRIBUTED_FLOW_CONSENSUS` when establishing slots (CTOTs) for arriving traffic.
  - Supports **Dynamic Re-sectorization**: Processes `MERGE_SECTORS` commands to combine multiple physical sectors into virtual operational units while preserving historic state.
  - Supports **Tactical RAD Management**: Processes `RAD_RULE_UPDATE` to activate/deactivate route restrictions in real-time.
  - **Flight Re-processing**: Implements `_reprocess_all_flights` to re-trigger route calculations whenever the AIXM configuration is updated, resolving potential race conditions.
- **User Interface**: Each FMP serves its own isolated UI dashboard. Initial setup is achieved through the **Airspace Config** tab.

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
- **Topics**: Subscriptions define scope (e.g., `ddfn.capacity.state`, `ddfn.relay.handover`, `ddfn.warning.trigger`).
- **Idempotency Check**: Nodes maintain a memory cache (`processed_consensus_ids`, etc.) and use `PersistenceManager` for cross-restart robustness.

## 6. Testing Strategy (New)

The DDFN project enforces a **Test-Driven Development (TDD)** workflow for all core components.

- **Persistence Testing**: `test_persistence.py` verifies SQLite-based idempotency and override persistence using unique per-test databases to handle Windows file locking.
- **SWIM Messaging Testing**: `test_broker_unit.py` uses FastAPI's `TestClient` to verify message routing, subscription logic, and node registration constraints.
- **Airspace/Trajectory Testing**: Future tests in `test_trajectories.py` focus on 4D volume intersections and spatial filtering accuracy.

## 7. Component Specification Changes (Phase 2)

### [models.py](file:///c:/Users/eftyc/Antigravity/ddfn_v2/src/ddfn_v2/core/models.py)
Core data structures used across the system. All models are implemented using **Pydantic BaseModels** (v2) to provide strict typing, automated validation, and easy serialization/deserialization.

### [trajectories.py](file:///c:/Users/eftyc/Antigravity/ddfn_v2/src/ddfn_v2/eng/trajectories.py)
The `TrajectorySolver` now supports dependency injection for sector databases and performs a bounding box overlap check before running expensive ray-casting intersections. Added support for tracking `rad_violation` flags on the `FlightTrajectory` model for enhanced edge-based validation.

### [Data Normalization]
Normalized identifier names to `ident` across the system (specifically in `app.js`, `airspace.py`, and `aixm_tool.py`) and `.sector_id` for sectors, aligning with ICAO terminology and backend Pydantic models.

## 8. Glossary / Acronyms

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