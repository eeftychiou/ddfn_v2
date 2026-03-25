# Phase 7: Strategic & Pre-Tactical Simulation Mesh

## 1. Architectural Objective
Legacy systems handle multiple timelines flawlessly—the **Strategic Phase** (months ahead), the **Pre-Tactical Phase** (D-1, D-2), and the **Tactical Phase** (Op-Day). 

DDFN_v2 is currently hardcoded for real-time tactical execution (`datetime.now(timezone.utc)` dictates trajectories). To replace Eurocontrol NM, DDFN must provide airspace planners the ability to fast-forward tomorrow's published flight schedules through the exact same distributed CASA and Ripple algorithms to proactively resolve bottlenecks before the operational day even begins.

## 2. Core Principles
*   **Algorithm Reusability**: The physics engine (`trajectories.py`) and delay solver (`regulation_service.py`) must remain identical in simulation vs. production.
*   **Time Decoupling**: The distributed mesh must support running on a synchronized "Virtual Clock."
*   **Namespace Segregation**: Tactical operational traffic must completely ignore Pre-Tactical simulation traffic over the shared SWIM Broker.

## 3. Implementation Plan

### 3.1. Publisher/Subscriber Namespace Isolation
1.  **Topic Prefixing**: Modify the base networking models in `models.py` to identify the temporal domain.
    *   `live.ddfn.capacity.state`
    *   `sim.d1.ddfn.capacity.state`
2.  **Subscription Filtering**: Update the `broker.py` to ensure that nodes subscribing to `live.*` do not receive `sim.*` packets, effectively creating parallel universes on the same WebSocket hardware.

### 3.2. Virtual Clock Synchronization
1.  **Time Abstraction Layer (`core/time_manager.py`)**: 
    - Replace all hardcoded `datetime.now()` calls in the node service loops with `TimeManager.get_current_time()`.
2.  **Tick Synchronization**: Implement a network-wide clock tick message (`ddfn.clock.tick`) emitted by the `sim_manager.py`. 
    - E.g., The SimManager pulses a tick representing 5 minutes of D-1 time every 50 milliseconds in the real world, forcing all FMP/Airport nodes to fast-forward their FDPS and CASA evaluations instantaneously.

### 3.3. D-1 Hotspot Analytics
1.  **Batch Flight Injection**: `sim_manager.py` ingests the published airline schedules (e.g., from DDR/B2B data dumps) and floods the `sim.d1.ddfn.flight.plan` topic.
2.  **Capacity Aggregation**: FMPs calculate their capacity breaches natively in the simulation namespace.
3.  **Proactive Resolution Extraction**: 
    - Instead of locking live CTOTs, FMPs export a "Pre-Tactical Hotspot Report."
    - Operators can use this report to issue `MANUAL_CAPACITY_OVERRIDE` rules or modify baseline capacities *before* the simulation switches to live Ops at midnight.

## 4. Expected Outcomes
*   Providing operators with identical confidence in tomorrow's capacity plans as the legacy pre-tactical NM workflows.
*   Validating the performance and stress thresholds of the DDFN swarm by pushing 24 hours of European schedule data through the mesh in a matter of minutes.
