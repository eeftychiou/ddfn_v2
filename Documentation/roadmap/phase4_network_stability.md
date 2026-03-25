# Phase 4: Network Stability & Leader Election (Anti Yo-Yo)

## 1. Architectural Objective
The current DDFN_v2 Ripple Propagation architecture relies on localized independence—each FMP protects its own Area of Responsibility (AoR) autonomously. While highly resilient, this paradigm struggles during massive macro-disruptions (e.g., a squall line crossing Germany into France). 

In such scenarios, dozens of FMPs independently calculate overlapping CASA delays for the same traffic flows, leading to "yo-yo" CTOT assignments as cascading delays continuously clash upstream. Phase 4 introduces dynamic, transient **Leader Election** to establish deterministic stability during regional crises.

## 2. Core Principles
*   **Transient Authority**: Centralization is strictly temporary and geographically confined to the "Crisis Zone."
*   **Distributed Consensus (Raft/Paxos)**: Uses established distributed systems algorithms to ensure the elected leader is mutually agreed upon transparently.
*   **Fail-Safe Regression**: If the local leader fails, the swarm immediately falls back to localized autonomous CASA balancing.

## 3. Implementation Plan

### 3.1. Crisis Zone Detection
1.  **Macro-Disruption Heuristics**: FMP nodes (`fmp_service.py`) must monitor regional `CAPACITY_STATE_BROADCAST`s.
2.  **Trigger Condition**: If a node observes that $> 50\%$ of adjacent sectors within a defined 3-hop radius are simultaneously operating at `capacity=0` or broadcasting RED status, it drops an internal `MACRO_DISRUPTION_FLAG`.

### 3.2. Dynamic Election Protocol (`core/consensus.py`)
1.  **Algorithm Selection**: Implement a lightweight variant of the **Bully Algorithm** or **Raft Leader Election**.
2.  **State Machine Upgrades**: 
    - When `MACRO_DISRUPTION_FLAG` is true, affected FMPs halt independent `CTOT_ASSIGNMENT_PROPOSAL` emissions.
    - FMPs broadcast a `LEADER_ELECTION_VOTE` containing their current computational load and the number of active flights residing in their local FDPS.
    - The FMP managing the highest volume of traffic in the Crisis Zone is deterministically and automatically elected as the **Regional Lead FMP**.

### 3.3. Coordinated Macro-CASA
1.  **Unified Delay Calculation**: The Lead FMP aggregates the capacity constraints of the entire Crisis Zone.
2.  **Macro-Ripple emission**: It calculates a single, unified CASA table across the multiple sectors and emits a unique `MACRO_CONSTRAINT_WARNING_TRIGGER` to the originating airports.
3.  **Auction Freezing**: Airport nodes receiving a Macro-Trigger execute their clearinghouse auctions and freeze the accepted CTOTs for a minimum threshold (e.g., 60 minutes) to prevent further oscillation.

## 4. Expected Outcomes
*   Elimination of cyclic slot-swapping and oscillating CTOTs during severe weather.
*   Demonstration of a "hybrid swarm" capable of dynamic, transient centralization while retaining total hardware decoupling.
