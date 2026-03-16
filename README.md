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
- **LCCC (Cyprus)**: `http://127.0.0.1:8013` (Primary Demo)
- **LFFF (France)** : `http://127.0.0.1:8010`
- **EDDD (Germany)**: `http://127.0.0.1:8011`
- **EGTT (UK)**     : `http://127.0.0.1:8012`

**IMPORTANT**: FMP Nodes now start in an **UNCONFIGURED** state. Upon first access, you will be redirected to the **Airspace Config** tab.
1. Load the AIXM source (default: `AIXM/BD_2025-09-30_400005921419525.xml`).
2. Select the FIR of responsibility (e.g. `LCCC`, `EDDD`, `LFFF`, `EGTT`).
3. Set the Sliding Measurement Window (e.g. 60 Minutes).
4. Name your configuration and click **Save & Apply Config**.

The dashboard will reload and begin tracking traffic for the selected airspace.

## Global Network Overview
The network is intentionally designed so no node has a global macroscopic view (to ensure true distribution). However, for analytical purposes, the central SWIM broker natively logs all pub/sub network activity into an immutable SQLite database located at `logs/swim_audit.db`. You can query this database to see exactly which nodes are publishing, subscribing, or negotiating slot constraints across the entire European mesh.
