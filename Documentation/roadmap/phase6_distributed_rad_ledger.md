# Phase 6: Distributed RAD Ledger

## 1. Architectural Objective
The Eurocontrol Route Availability Document (RAD) is an enormous, highly complex series of routing restrictions designed to maximize network efficiency. 

DDFN_v2 successfully moved RAD validation to the edge (`rad_validator.py`), empowering node autonomy. However, reading from a static local JSON file (`rad_rules.json`) does not scale for the live, real-time tactical environment of European airspace, where rules are continuously toggled, suspended, or amended dynamically. Phase 6 aims to implement a **Replicated State Machine** to synchronize the complete RAD across thousands of edge nodes in milliseconds.

## 2. Core Principles
*   **Eventual Consistency with High Availability**: RAD changes must propagate globally without a single central database cluster.
*   **Complex Conditional Logic**: Moving beyond simple altitude/waypoint blocks to full multi-variable Eurocontrol RAD constraints.
*   **Edge Autonomy**: If an AOC goes offline from the primary network, it still queries its local replica to validate flight plans until reconnection.

## 3. Implementation Plan

### 3.1. Replicated State Machine Integration
1.  **Distributed Ledger Technology**: Integrate a fast distributed key-value store (such as a Redis Cluster abstraction layer, Apache Kafka compacted topics, or a lightweight Distributed Hash Table via IPFS pub/sub) to host the Master RAD state.
2.  **Continuous Subscription**: Ensure `rad_validator.py` natively connects to this synchronized state layer rather than polling a local disk file.

### 3.2. Advanced RAD Rule Schema Enhancement
Ensure the Pydantic models can represent the extreme complexity of Eurocontrol RAD logic:
```python
class ComplexRADRule(BaseModel):
    rule_id: str
    active: bool
    conditional_constraints: List[ConstraintGroup]
    # e.g., "IF AircraftType == A380 AND DayOfWeek IN [SAT, SUN] AND Time BETWEEN 0600-1200 THEN MaxFL = 310"
    applicable_fir: List[str]
    exempt_operator: List[str]
```

### 3.3. Dynamic Edge Synchronization Mechanism
1.  **Topic Segregation**: Introduce the `ddfn.rad.updates` SWIM topic.
2.  **Modification Protocol**: When an authorized Airspace Manager (acting via an FMP UI command) submits a `RAD_RULE_UPDATE`:
    *   The rule payload is cryptographically signed (Phase 5 check).
    *   The ledger receives the append-only transaction.
    *   The ledger publishes the delta to `ddfn.rad.updates`.
3.  **Local Memory Re-build**: Edge nodes cache the latest states in RAM for ultra-fast validation during the trajectory-generation RayCasting phase.

## 4. Expected Outcomes
*   Ability to accurately simulate the complete structural rigidness of Eurocontrol's RAD.
*   Elimination of synchronization lag; all edge nodes validate trajectories against an identical, globally updated rule schema, drastically reducing "Rejected" flight plan errors post-submission.
