# Phase 3: Advanced P2P 4D Rerouting (The RRP Equivalent)

## 1. Architectural Objective
In the baseline DDFN_v2 implementation, the primary mechanism for resolving demand and capacity imbalances is **temporal deferment**—specifically, calculating CASA ground delays (CTOTs) natively at the edge. 

Eurocontrol NM utilizes **Rerouting Proposals (RRP)** to shift flights spatially around weather or saturated airspace rather than purely delaying them. Phase 3 aims to introduce decentralized, peer-to-peer 4D structural rerouting negotiations without sacrificing the stateless nature of the SWIM broker.

## 2. Core Principles
*   **AOC Sovereignty**: FMPs calculate geometry, but Airline Operations Centers (AOCs) own the business logic (fuel vs. time trade-offs).
*   **Stateless Routing**: The broker must remain ignorant of route strings; it solely passes negotiation envelopes.
*   **Idempotency**: Reroute proposals must be deterministic to prevent continuous spatial oscillation between adjacent FMPs.

## 3. Implementation Plan

### 3.1. Schema Modifications (`src/ddfn_v2/core/models.py`)
Introduce a new suite of models governing spatial negotiation:
```python
class RouteRenegotiationProposal(BaseModel):
    message_type: str = "ROUTE_RENEGOTIATION_PROPOSAL"
    proposal_id: str
    flight_id: str
    originating_fmp: str
    target_aoc: str
    original_route: str
    proposed_route: str
    estimated_fuel_delta: Optional[float]
    time_delta_minutes: int
```

### 3.2. FMP Geometry Engine Extensibility (`fmp_service.py` & `trajectories.py`)
1.  **Spatial Exhaustion Trigger**: Implement logic in `_sync_capacity()`—when CASA calculates a ground delay exceeding X minutes (e.g., > 120 mins), the FMP attempts a spatial resolution before emitting a `CTOT_ASSIGNMENT_PROPOSAL`.
2.  **Fluid Dynamics Masking**: The local FDPS probes adjacent sectors (via standard `CAPACITY_STATE_BROADCAST` caches). If an adjacent sector is "GREEN" (under capacity), the geometric engine generates a dog-leg via waypoints residing in the GREEN sector.
3.  **Emission**: The FMP publishes the `ROUTE_RENEGOTIATION_PROPOSAL` directed specifically to the target flight's AOC.

### 3.3. AOC Evaluation Engine (`aoc_service.py`)
1.  **Business Logic Ingestion**: The AOC dynamically receives the 4D proposal.
2.  **Cost Indexing**: Implement a mock Cost Index algorithm. If `(proposed_delay_penalty) > (fuel_burn_penalty_for_new_route)`, the AOC accepts the physical reroute.
3.  **Resolution**: The AOC replies with a `ROUTE_RENEGOTIATION_CONSENSUS`, automatically triggering a re-publication of an updated `FLIGHT_PLAN_FILED` overlay message incorporating the new route string.

## 4. Expected Outcomes
*   Reduction of average systemic ground delay during localized severe weather events by dynamically bypassing constraints.
*   Proving that multi-actor spatial routing can be established purely via pub/sub events without a centralized God-Node orchestrating the specific path.
