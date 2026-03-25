# Phase 8: Seamless AIRAC Geometry Updates (Hot-Swapping)

## 1. Architectural Objective
Eurocontrol relies on the 28-day AIRAC cycle to synchronize thousands of waypoint and sector geometry changes globally at exactly 00:00 UTC. 
Currently, DDFN nodes parse a static AIXM file upon boot (`aixm_tool.py`). If a live FMP node must be restarted to load the new AIRAC cycle, it causes unacceptable downtime and drops tracking of mid-air flights. Decentralized nodes must be able to "hot-swap" their geometry databases seamlessly while live tracking.

## 2. Core Principles
*   **Zero Downtime**: The tracking loops (`trajectories.py` raycasting) must not pause during the memory swap.
*   **Dual-Bank Memory**: Nodes must hold two sets of airspace geometry in RAM during the transition window.
*   **Deterministic Cutover**: All nodes must enforce the exact same temporal boundary for the new geometry to prevent P2P trajectory mismatches.

## 3. Implementation Plan

### 3.1. Dual-Bank Airspace State
1.  **AIXM Engine Refactor**: Modify the `AirspaceDef` class to support `active_airac` and `pending_airac` data structures.
2.  **Pre-Loading Payload**: Introduce a `SYSTEM_AIRAC_PRELOAD` SWIM payload containing the URL/Hash of the upcoming AIXM XML file. Nodes download and parse this file into the `pending_airac` bank 24 hours before the cycle switch.

### 3.2. The 00:00 UTC Hot-Swap
1.  **Temporal Trigger**: At exactly 00:00:00 UTC, the `fmp_service.py` tracking loop mathematically swaps the pointer: `current_airac = pending_airac`.
2.  **Ghost Flights Mitigation**: Flights airborne *during* the transition might refer to waypoints that were just deleted. Implement a backward-compatibility layer: if a flight's EOBT was before 00:00 UTC, the raycaster validates its trajectory against the *old* AIRAC structure until it lands.

## 4. Expected Outcomes
*   Continuous 24/7/365 node uptime without requiring container re-deployments for structural airspace changes, matching Eurocontrol's stringent availability SLS.
