# DDFN v2 Protocol Message Dictionary

This document outlines the standard message data schemas exchanged across the DDFN v2 decentralized publish/subscribe (SWIM) network. The central Broker holds no business logic and simply routes these payloads between edge nodes.

All core models are strictly defined in `src/ddfn_v2/core/models.py` using Pydantic v2.

---

## 1. Capacity & Demand Broadcasts

### `CAPACITY_STATE_BROADCAST`
- **Topic**: `ddfn.capacity.state`
- **Publisher**: FMP Nodes, Airport Nodes
- **Subscriber**: FMP Dashboards (UI), Global Sim Manager
- **Context**: Emitted periodically (e.g., every 3 seconds) by every active node to broadcast its localized worldview (demand vs capacity in its specific Area of Responsibility).
- **Payload Schema**:
  ```json
  {
    "message_type": "CAPACITY_STATE_BROADCAST",
    "node_id": "string",
    "timestamp": "ISO8601",
    "sectors": [
      {
        "sector_id": "string",
        "configuration": "SINGLE | MERGED_VIRTUAL | AIRPORT",
        "declared_capacity_per_hour": "integer",
        "current_demand_per_hour": "integer",
        "status": "GREEN | RED",
        "active_capacity": "integer (optional)",
        "constraint_reason": "string"
      }
    ],
    "measure_window": "integer",
    "demand_profile": "array (binned time slices)"
  }
  ```

### `AIRSPACE_INVENTORY_UPDATE`
- **Topic**: `ddfn.airspace.inventory`
- **Publisher**: FMP Nodes
- **Subscriber**: Sim Manager (Global map tracking)
- **Context**: Broadcasts the current internal list of Flight Trajectories residing currently within the node's FDPS.
- **Payload Schema**:
  ```json
  {
    "message_type": "AIRSPACE_INVENTORY_UPDATE",
    "node_id": "string",
    "flights": [
      {
        "flight_id": "string",
        "origin": "string",
        "destination": "string",
        "status": "ACTIVE | SCHEDULED",
        "entry_point": "string",
        "exit_point": "string",
        "eta_entry": "ISO8601",
        "eta_exit": "ISO8601"
      }
    ]
  }
  ```

---

## 2. Dynamic Capacity Management (CASA / Ripple)

### `CONSTRAINT_WARNING_TRIGGER`
- **Topic**: `ddfn.warning.trigger`
- **Publisher**: Airport Nodes
- **Subscriber**: FMP Nodes (Upstream)
- **Context**: Emitted when an endpoint (Airport) exceeds its Arrival Acceptance Rate (AAR), requesting upstream nodes to initiate ground delays (GDP offers) or Airborne holding.
- **Payload Schema**:
  ```json
  {
    "message_type": "CONSTRAINT_WARNING_TRIGGER",
    "warning_id": "string (UUID)",
    "originating_node": "string",
    "target_nodes": ["string"],
    "constrained_sector_id": "string",
    "affected_time_window": {
      "start": "ISO8601",
      "end": "ISO8601"
    },
    "required_flow_reduction": {
      "metric": "FLIGHTS_PER_HOUR",
      "amount_to_reduce": "integer"
    },
    "affected_flights_pool": ["string"]
  }
  ```

### `CTOT_ASSIGNMENT_PROPOSAL`
- **Topic**: `ddfn.negotiation.proposal`
- **Publisher**: FMP Nodes
- **Subscriber**: Airport Nodes / Origin FMPs
- **Context**: Emitted when an FMP detects an en-route sector breach and autonomously calculates a CASA delay table. Sends standard CTOTs backwards to the nodes where flights originate.
- **Payload Schema**:
  ```json
  {
    "message_type": "CTOT_ASSIGNMENT_PROPOSAL",
    "proposal_id": "string",
    "referencing_warning_id": "string",
    "originating_node": "string",
    "target_nodes": ["string"],
    "total_delay_minutes": "integer",
    "slot_assignments": [
      {
        "flight_id": "string",
        "origin": "string",
        "etot": "ISO8601",
        "ctot": "ISO8601",
        "delay": "integer",
        "status": "REGULATED"
      }
    ]
  }
  ```

### `FLOW_NEGOTIATION_PROPOSAL`
- **Topic**: `ddfn.negotiation.proposal`
- **Publisher**: Airport Nodes
- **Subscriber**: Originating FMP Nodes (Auction Clearinghouse)
- **Context**: Airport node's response to an en-route constraint warning, detailing exactly how many ground delay slots they are offering to fulfill the requested flow reduction.

### `DISTRIBUTED_FLOW_CONSENSUS`
- **Topic**: `ddfn.flow.consensus`
- **Publisher**: Any node acting as clearinghouse (e.g. Airport) or HITL UI (FMP)
- **Subscriber**: All affected Nodes natively
- **Context**: Final lock-in of CTOT slots. Nodes receiving this message immediately update their local FDPS to reflect the new delay profiles for affected flights.
- **Payload Schema**:
  ```json
  {
    "message_type": "DISTRIBUTED_FLOW_CONSENSUS",
    "consensus_id": "string",
    "referencing_warning_id": "string",
    "participating_nodes": ["string"],
    "final_action_plan": ["string (IDs of accepted proposals)"],
    "slot_table": ["array of SlotDetails"],
    "status": "AGREED_AND_LOCKED"
  }
  ```

---

## 3. Flight Injectors & Handover

### `FLIGHT_PLAN_FILED`
- **Topic**: `ddfn.flight.plan`
- **Publisher**: Global Sim Manager
- **Subscriber**: All Nodes
- **Context**: Injects a fresh flight plan into the global simulation. Edge nodes process this by utilizing generating 4D geometric ETOs.
- **Payload Schema**:
  ```json
  {
    "message_type": "FLIGHT_PLAN_FILED",
    "flight_id": "string",
    "origin": "string",
    "destination": "string",
    "route_string": "string (ICAO format)",
    "cruise_fl": "integer",
    "departure_time": "ISO8601 (ETOT)"
  }
  ```

### `FIR_HANDOVER_ADVISORY`
- **Topic**: `ddfn.relay.handover`
- **Publisher**: FMP Nodes
- **Subscriber**: Adjacent FMP Nodes
- **Context**: Emitted when a flight physically exits one FIR to inform the next downstream FIR. Facilitates node-to-node object migration without central tracking.

---

## 4. Edge Airline Operations (AOC)

### `AOCC_READY_TO_FLY`
- **Topic**: `ddfn.aoc.messages`
- **Publisher**: AOC Nodes (Airlines)
- **Subscriber**: Airport Nodes (Local FDPS)
- **Context**: "REA" message. Indicates an airline is boarded and ready earlier than their assigned CTOT, requesting the Airport node to autonomously scavenge and swap their slot for an earlier departure.

### `FMP_SLOT_SWAP_REQUEST`
- **Topic**: `ddfn.flow.negotiation`
- **Publisher**: Airport Nodes (post-scavenge) or FMP UI (manual drag-and-drop)
- **Subscriber**: Originating FMP Nodes / Broker validation
- **Context**: Formally swaps the CTOT of two flights utilizing the same constrained resource without negatively impacting the total sector flow limit.

---

## 5. UI Commands & Overrides

These messages govern human-in-the-loop actions via the React Dashboards.
- `MANUAL_CAPACITY_OVERRIDE` (Topic: `ddfn.fmp.command`, applies targeted capacity restriction map)
- `SET_MEASURE_WINDOW` (Topic: `ddfn.fmp.command`, alters predictive radar limits)
- `MERGE_SECTORS` (Topic: `ddfn.fmp.command`, dynamically combines discrete AIXM geometries into single operational virtual sectors)
- `RAD_RULE_UPDATE` (Topic: `ddfn.fmp.command`, globally toggles Route Availability Document validation limits)
