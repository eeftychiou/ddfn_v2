# DDFN v2 Testing & Simulation Roadmap

A system designed to replace Eurocontrol NM must adhere to the highest aviation-grade software reliability standards. In a decentralized publisher/subscriber mesh, unpredictable emergent behaviors (like cyclic slot-swapping or deadlocks) are the primary risk. Extensively covering code with standard unit tests is insufficient. 

This roadmap details the exhaustive testing infrastructure required to guarantee the safety, security, and resilience of the DDFN swarm.

---

## Phase 1: Formal Verification & Advanced Property Testing
**Objective:** Move beyond example-based testing to mathematically prove that the distributed algorithms (Ripple Propagation, Clearinghouse Auctions) cannot deadlock, enter infinite routing loops, or drop flights.

1. **Stateful Property-Based Testing (`tests/property/`)**:
   - Expand `test_trajectory_properties.py` using `Hypothesis` state-machine rules.
   - **Test Case**: Bombard an FMP node with thousands of randomized, intersecting `FLIGHT_PLAN_FILED` and `MANUAL_CAPACITY_OVERRIDE` events. The test must mathematically verify that `len(inventory) == expected_flights` and that no duplicate CTOTs are ever assigned to the same constraint window.
2. **Formal Modeling (TLA+)**:
   - Write TLA+ (Temporal Logic of Actions) specifications for the Node State-Machines documented in `node_state_machines.md`.
   - Use the TLC model checker to aggressively search for race conditions in the `DISTRIBUTED_FLOW_CONSENSUS` lock-in mechanism.

---

## Phase 2: Expanded Chaos Engineering (Byzantine Faults)
**Objective:** Ensure the mesh survives not just component failures, but malicious actors, extreme network latency, and severe split-brain scenarios.

1. **Byzantine Spoofing Detection (`tests/chaos/`)**:
   - Create tests that spawn rogue "Actor" nodes simulating compromised AOCs. These nodes will intentionally inject malformed, historically replayed, or wrongly-signed `CTOT_ASSIGNMENT_PROPOSAL` payloads.
   - **Expected Behavior**: Verify the framework actively terminates the rogue WebSockets locally and that honest nodes ignore the payload.
2. **Brain-Split & Merge Scenarios**:
   - Simulate a complete network partition between Regional Mesh A (e.g., UK/France) and Regional Mesh B (e.g., Germany/East).
   - Verify nodes gracefully fallback to isolated autonomous balancing, and crucially, test the reconciliation logic when the network merges back together without crashing the localized `processed_consensus` SQLite ledgers.
3. **Yo-Yo Effect Induction**:
   - Introduce chaotic flapping of sector capacities to deliberately trigger macro-disruption handling (Phase 4 of the Development Roadmap) and verify that dynamic Leader Election successfully stabilizes the cascade.

---

## Phase 3: High-Fidelity Digital Twin (Macroscopic Scale Testing)
**Objective:** Prove the underlying architecture (WebSocket routing + Pydantic serialization) can effortlessly handle the peak European summer load (35,000+ flights/day).

1. **Kubernetes Cluster Scale-Out (`tests/performance/`)**:
   - Write automated deployment scripts to spin up $100+$ simulated FMP and Airport pods across a Minikube/K8s test cluster.
2. **Historical DDR Replay**:
   - Ingest archived Eurocontrol DDR2 (Demand Data Repository) traffic logs from a historic peak day.
   - Use the `sim_manager.py` to pipe the massive schedule into the simulation namespace.
3. **Time-Compression Load Testing**:
   - Compress the 24-hour simulation into a 15-minute "Fast-Forward" replay to stress-test the `broker.py` throughput. 
   - **Success Metric**: 0% dropped packets, sub-10ms routing latency, and identical CTOT assignments compared to real-time execution.

---

## Phase 4: Continuous Fuzzing & Edge Security
**Objective:** Prevent edge-case crashes originating from malformed SWIM JSON payloads, which could take an edge node offline.

1. **SWIM Payload Fuzzing**:
   - Integrate `Atheris` (or similar native Python fuzzers) into the CI/CD pipeline. 
   - Continuously mutate routing strings, UUIDs, timestamps, and geometry arrays within `FLIGHT_PLAN_FILED` and `CAPACITY_STATE_BROADCAST` messages.
   - Ensure the strict `pydantic` validation boundaries catch all injection attempts and schema violations without bubbling up unhandled exceptions that crash the main `asyncio` loop of the Node.

---

By completing this exhaustive testing roadmap, the DDFN system will possess the demonstrable resilience required to act as mission-critical European infrastructure.
