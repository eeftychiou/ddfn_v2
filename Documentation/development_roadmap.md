# DDFN v2 Future Development Roadmap

This document outlines the phased development roadmap to elevate the **Decentralized Demand & Capacity Balancing (DDFN)** prototype into a production-ready, peer-to-peer rival to the centralized Eurocontrol Network Manager (NM). 

It is designed to be executed sequentially by development agents, building upon the core SWIM and Pydantic architecture established in the baseline documentation.

For a detailed breakdown of each future developmental phase, please refer to the specific architectural documents linked below:

---

## Phase 1 & 2: Core Prototype & Architecture Stabilization (Completed ✅)
**Current State (`ddfn_v2` baseline)**
Phase 1 established the initial decentralized SWIM pub/sub mesh, proving that temporal delays (CTOTs) could be negotiated peer-to-peer between autonomous FMP, Airport, and AOC edge nodes without a central "God Node."
Phase 2 (the current system baseline) stabilized this architecture by enforcing strict `Pydantic v2` data contracts, implementing spatial filtering for aerodynamic trajectory calculations, decentralizing node configurations, and establishing secure API authentication.

---

## [Phase 3: Advanced P2P 4D Rerouting (The RRP Equivalent)](roadmap/phase3_p2p_4d_rerouting.md)
**Goal:** Transitioning from temporal-only deferment (CASA ground delays) to peer-to-peer structural airspace management. Introduces `ROUTE_RENEGOTIATION_PROPOSAL` to allow AOCs and FMPs to negotiate 4D spatial rerouting fluidly around saturated sectors.

## [Phase 4: Network Stability & Leader Election (Anti Yo-Yo)](roadmap/phase4_network_stability.md)
**Goal:** Preventing cascaded slot-swapping (the "yo-yo" effect) during severe macro-disruptions (e.g., squall lines). Introduces transient Raft/Bully leader election to establish dynamic Crisis Zones, enabling single-source, unified macro-CASA assignments temporarily.

## [Phase 5: Zero-Trust Security & Cryptographic Trajectories](roadmap/phase5_zero_trust_security.md)
**Goal:** Implementing structural security across the decentralized swarm. Introduces Node PKI infrastructure, Ed25519 payload signing for `DISTRIBUTED_FLOW_CONSENSUS`, and broker-layer signature verification to prevent spoofing and slot-stealing.

## [Phase 6: Distributed RAD Ledger](roadmap/phase6_distributed_rad_ledger.md)
**Goal:** Scaling edge-based validation of the Route Availability Document (RAD). Migrates the rule engine from static JSON files to a sub-millisecond globally synchronized Replicated State Machine (e.g., Redis Cluster or IPFS pub/sub).

## [Phase 7: Strategic & Pre-Tactical Simulation Mesh](roadmap/phase7_strategic_simulation.md)
**Goal:** Replicating Eurocontrol NM's D-1 and D-2 capacity planning. Introduces P2P namespace isolation and fast-forward virtual clocks, allowing nodes to collaboratively simulate tomorrow's flight schedules and baseline capacities without affecting live operational traffic.

## [Phase 8: Seamless AIRAC Geometry Updates (Hot-Swapping)](roadmap/phase8_seamless_airac_updates.md)
**Goal:** Prevent 00:00 UTC downtime during the 28-day AIRAC airspace structural updates by implementing dual-bank memory swapping in the FMP geometry raycasters.

## [Phase 9: Fast-Sync & Node Disaster Bootstrapping](roadmap/phase9_fast_sync_bootstrapping.md)
**Goal:** Enable sub-second topological fault recovery by allowing crashed FMP/Airport nodes to reconstruct their tracking tables via peer-to-peer `STATE_TRANSFER_REQUEST`s instantly upon boot.

## [Phase 10: Third-Party "Observer" APIs (The B2B Gateway)](roadmap/phase10_b2b_observer_gateway.md)
**Goal:** Mimicking Eurocontrol NM's B2B interface. Deploying air-gapped gateway nodes to expose read-only REST APIs to external vendors and airlines without comprising the zero-trust architecture of the core SWIM mesh.

---

## [Exhaustive Testing & Simulation Roadmap](testing_roadmap.md)
**Goal:** To become a mission-critical rival to NM, DDFN must prove absolute safety and resilience. This roadmap outlines the rigorous, aviation-grade validation phases (Formal Verification, Chaos Engineering, Digital Twin Scale-out, and Payload Fuzzing) required to guarantee the swarm's algorithmic stability and security.

---

## [Operational & Deployment Roadmap (Day-2)](operational_roadmap.md)
**Goal:** Building the software is only half the battle. This roadmap outlines the enterprise requirements necessary to actually deploy and support DDFN in European airspace. It covers Distributed Tracing, Big Data Archiving (Data Lakes), Regulatory Compliance (DO-278AL), and the "Shadow Mode" live-traffic cutover strategy.

---

## [Visionary Expansions & Future Work](future_work.md)
**Goal:** Extending DDFN beyond the limitations of legacy ATFM. This covers Multi-Modal U-Space integration (scaling the CASA consensus to millions of UAM drones/air-taxis) and building direct Controller-Pilot Data Link Communications (CPDLC / FANS 1/A) for automated cockpit uplinks.
