# Phase 9: Fast-Sync & Node Disaster Bootstrapping

## 1. Architectural Objective
In DDFN_v2, FMP and Airport nodes build their Flight Data Processing Systems (FDPS) completely from scratch by listening to the SWIM mesh. If an FMP node crashes and restarts mid-day, it will only hear *new* `FLIGHT_PLAN_FILED` events. It will be "blind" to the hundreds of flights already active in its airspace, resulting in catastrophically inaccurate CASA capacity calculations until the airspace clears out hours later.

## 2. Core Principles
*   **Event Sourcing Replacements**: Using peer-to-peer state transfer instead of relying on a centralized historical database.
*   **Sub-Second Recovery**: A crashed node must rebuild its internal FDPS and capacity tables within 3 seconds of the process restarting.

## 3. Implementation Plan

### 3.1. Peer-to-Peer State Request
1.  **Boot Phase**: When an `fmp_service.py` or `airport_service.py` process boots, before it begins emitting `CAPACITY_STATE_BROADCAST` messages, it emits a `STATE_TRANSFER_REQUEST` containing its node ID and target FIR.
2.  **Neighbor Responses**: Adjacent FMP nodes natively cache trajectories that pass through their neighbors. When they hear the request, they package all active `Flight` objects that intersect the recovering node's FIR into a compressed binary blob (or batched JSON array) and emit a `STATE_TRANSFER_RESPONSE`.

### 3.2. Reconciliation Logic
1.  **Deduplication**: The recovering node ingests the responses from its peers. Because multiple peers might send the same flight, the node deduplicates them using the unique `flight_id` and the most recent `last_updated` timestamp.
2.  **CASA Re-Warm**: Once the memory bank is populated (fast-sync complete), the node triggers an immediate `_sync_capacity()` run in `regulation_service.py` to regenerate the baseline delay tables before opening its WebSocket to normal tactical negotiation.

## 4. Expected Outcomes
*   Fault-tolerant recovery allowing edge components to crash, reboot, and resume full situational awareness almost instantaneously.
