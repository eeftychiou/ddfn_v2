"""
airport_service.py — DDFN V2 Airport Edge Node
================================================
An airport is a DDFN Edge Node. Rather than managing *en-route sectors*
it manages:
  - AAR (Arrival Acceptance Rate): max arriving flights/hr
  - ADR (Airport Departure Rate): max departing flights/hr

Capabilities
------------
1. Monitors inbound traffic demand against the AAR.
   When demand > AAR → emits a CONSTRAINT_WARNING_TRIGGER to the
   adjacent en-route node (ATFM calls this a GDP trigger).

2. When an upstream en-route node issues a warning for a sector the
   airport feeds into → responds with a GDP (Ground Delay Program) offer:
   delays its own departures so fewer flights enter the affected airspace.

3. Issues CTOT (Calculated Take-Off Time) equivalents as ActionDetails.

Race Condition Protection
-------------------------
- asyncio.Lock() on all state mutations
- processed_proposal_ids: Set[str] — skip re-delivered proposals
- processed_consensus_ids: Set[str] — skip replayed consensus
"""

import asyncio
import logging
import uuid
import random
import json
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field, asdict

from fastapi import FastAPI, Security
from fastapi.responses import JSONResponse
import uvicorn

from ddfn_v2.core.node import DDFN_Node
from ddfn_v2.core.auth import verify_api_key
from ddfn_v2.core.network import NetworkClient
from ddfn_v2.core.config import config
from ddfn_v2.eng.airspace import AIRPORT_DEFAULTS
from ddfn_v2.services import schedule
from ddfn_v2.services.rad_validator import VALIDATOR as RAD_VALIDATOR
from ddfn_v2.core.models import (
    TimeWindow, FlowReduction,
    FlowNegotiationProposal, DistributedFlowConsensus,
    ProposedAction, ActionDetails, CapacityConstraintWarning, from_dict, FlightPlanFiled
)
from ddfn_v2.eng.trajectories import FlightTrajectory, FlightDataProcessingSystem


@dataclass
class AirportStatus:
    icao: str
    aar: int                        # Current Arrival Acceptance Rate (flights/hr)
    adr: int                        # Current Airport Departure Rate (flights/hr)
    inbound_demand: int = 0         # Flights/hr currently inbound
    outbound_demand: int = 0        # Flights/hr currently departing
    ground_delay_slots: int = 0     # How many ground-delay slots allocated so far
    status: str = "GREEN"

    @property
    def aar_breach(self) -> bool:
        return self.inbound_demand > self.aar

    @property
    def adr_breach(self) -> bool:
        return self.outbound_demand > self.adr

    @property
    def aar_excess(self) -> int:
        return max(0, self.inbound_demand - self.aar)

    @property
    def adr_excess(self) -> int:
        return max(0, self.outbound_demand - self.adr)


class AirportNode(DDFN_Node):
    def __init__(
        self,
        icao: str,
        network: NetworkClient,
        fdps: FlightDataProcessingSystem, # FDPS is now passed in
        adjacent_sector: str,          # The en-route sector directly above this airport
        upstream_sector: Optional[str] = None,  # Sector feeding arrivals
    ):
        node_id = f"{icao}_AIRPORT"
        super().__init__(node_id, network)
        self.icao = icao
        self.adjacent_sector = adjacent_sector
        self.upstream_sector = upstream_sector

        defaults = AIRPORT_DEFAULTS.get(icao, {"aar": config.AIRPORT_DEFAULT_AAR, "adr": config.AIRPORT_DEFAULT_ADR})
        self.status = AirportStatus(
            icao=icao,
            aar=defaults["aar"],
            adr=defaults["adr"],
            inbound_demand=int(defaults["aar"] * config.AIRPORT_INBOUND_LOAD_FACTOR),   # Configurable load initially
            outbound_demand=int(defaults["adr"] * config.AIRPORT_OUTBOUND_LOAD_FACTOR),
        )

        self.fdps = fdps # Use the passed-in FDPS

        # Race-condition protection
        self._state_lock = asyncio.Lock()
        self.pending_warnings: Dict[str, dict] = {}
        self.processed_proposal_ids: Set[str] = set()
        self.processed_consensus_ids: Set[str] = set()

    async def start(self):
        await super().start()
        self.register_handler("CONSTRAINT_WARNING_TRIGGER", self.handle_en_route_warning)
        self.register_handler("FLOW_NEGOTIATION_PROPOSAL",  self.handle_proposal)
        self.register_handler("DISTRIBUTED_FLOW_CONSENSUS", self.handle_consensus)
        self.register_handler("MANUAL_AAR_OVERRIDE",        self.handle_aar_override)
        self.register_handler("AOCC_READY_TO_FLY",          self.handle_aoc_message)
        self.register_handler("FLIGHT_PLAN_FILED",          self.handle_flight_plan_filed)
        
        await self.network.subscribe("ddfn.flight.plan", self.subscription_queue)
        await self.network.subscribe("ddfn.aoc.messages", self.subscription_queue)
        
        self.local_slots = {} # Track active slots affecting this airport (warn_id -> slots)
        
        asyncio.create_task(self._sync_status())
        asyncio.create_task(self._monitor_aar())

    # -----------------------------------------------------------------------
    # Status broadcast
    # -----------------------------------------------------------------------
    async def handle_flight_plan_filed(self, message: dict):
        fp = from_dict(FlightPlanFiled, message)
        
        # Only care about this flight if it involves our ICAO
        if fp.origin == self.icao or fp.destination == self.icao:
            try:
                dept_time = datetime.fromisoformat(fp.departure_time)
                
                # Use TrajectorySolver to build the 4D geometry
                traj = FlightTrajectory.from_flight_plan(
                    flight_id=fp.flight_id,
                    origin=fp.origin,
                    destination=fp.destination,
                    departure_time=dept_time,
                    cruise_fl=fp.cruise_fl,
                    route_string=fp.route_string
                )
                
                async with self._state_lock:
                    self.fdps.add_flight(traj)
                    
                if fp.origin == self.icao:
                    self.logger.info(f"Accepted dynamic flight plan for departure: {fp.flight_id}")
                else:
                    self.logger.info(f"Accepted dynamic flight plan for arrival: {fp.flight_id}")
            except Exception as e:
                self.logger.error(f"Failed to process flight plan {fp.flight_id}: {e}")

    async def _sync_status(self):
        while True:
            msg = {
                "message_type": "AIRPORT_STATUS_BROADCAST",
                "node_id": self.node_id,
                "icao": self.icao,
                "aar": self.status.aar,
                "adr": self.status.adr,
                "inbound_demand": self.status.inbound_demand,
                "outbound_demand": self.status.outbound_demand,
                "status": "RED" if (self.status.aar_breach or self.status.adr_breach) else "GREEN",
            }
            await self.network.publish("ddfn.airport.state", msg)
            await asyncio.sleep(3.0)

    # -----------------------------------------------------------------------
    # AAR monitoring — triggers warning to upstream sector if breached
    # -----------------------------------------------------------------------
    async def _monitor_aar(self):
        while True:
            async with self._state_lock:
                if self.status.aar_breach and self.status.status != "RED":
                    self.status.status = "RED"
                    excess = self.status.aar_excess
                    self.logger.error(
                        f"AAR BREACH at {self.icao}: "
                        f"Demand={self.status.inbound_demand}, AAR={self.status.aar}, Excess={excess}"
                    )
                    await self._emit_gdp_warning(excess)
            await asyncio.sleep(2.0)

    async def _emit_gdp_warning(self, excess: int):
        """Emit a constraint warning upstream — requesting upstream nodes
        hold/delay flights bound for this airport."""
        warn = CapacityConstraintWarning(
            warning_id=f"WARN_{self.node_id}_{uuid.uuid4().hex[:6]}",
            originating_node=self.node_id,
            target_nodes=[],  # broadcast
            constrained_sector_id=self.adjacent_sector,
            affected_time_window=TimeWindow(
                start=(datetime.now(timezone.utc)).isoformat(),
                end=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            ),
            required_flow_reduction=FlowReduction(
                metric="FLIGHTS_PER_HOUR", amount_to_reduce=excess
            ),
            affected_flights_pool=[],
        )
        async with self._state_lock:
            self.pending_warnings[warn.warning_id] = {
                "remaining_reduction": excess,
                "received_proposals": [],
                "participating_nodes": {self.node_id},
                "status": "AUCTION_OPEN",
                "timer_started": False,
            }
        await self.emit("ddfn.warning.trigger", warn)
        self.logger.info(f"GDP Warning {warn.warning_id} emitted ({excess} flights)")

    # -----------------------------------------------------------------------
    # Handle warning from upstream en-route sector (airport offers GDP slots)
    # -----------------------------------------------------------------------
    async def handle_en_route_warning(self, msg: dict):
        originating_node = msg.get("originating_node", "")
        if originating_node == self.node_id:
            return

        constrained_sector = msg.get("constrained_sector_id", "")
        # Only respond if this sector is one we feed into
        if constrained_sector not in {self.adjacent_sector, self.upstream_sector}:
            return

        required = msg.get("required_flow_reduction", {}).get("amount_to_reduce", 0)
        warning_id = msg.get("warning_id")

        self.logger.info(
            f"Received en-route warning from {originating_node} "
            f"for sector {constrained_sector}: need to absorb {required} flights"
        )

        # How many departures can we delay?  Limit to ADR slack or required
        max_gdp = min(required, max(0, self.status.adr - 5))  # leave 5/hr slack
        if max_gdp == 0:
            self.logger.info("No GDP capacity available to offer.")
            return

        # Simulate calculating which departures to delay
        actual_offer = random.randint(max(1, max_gdp // 2), max_gdp)
        await asyncio.sleep(config.AIRPORT_CLEARINGHOUSE_WAIT)  # Clearinghouse wait time

        actions = []
        for i in range(actual_offer):
            ctot_delay = random.randint(10, 25)
            actions.append(ProposedAction(
                action_type="GDP_CTOT",
                flight_id=f"{self.icao}_DEP{uuid.uuid4().hex[:4].upper()}",
                details=ActionDetails(estimated_delay_minutes=ctot_delay,
                                      speed_mach=0.0)
            ))

        import dataclasses
        prop = FlowNegotiationProposal(
            proposal_id=f"PROP_{self.node_id}_{uuid.uuid4().hex[:6]}",
            referencing_warning_id=warning_id,
            proposing_node=self.node_id,
            proposed_actions=actions,
            contribution_to_reduction=actual_offer,
        )
        await self.emit("ddfn.negotiation.proposal", prop)
        self.logger.info(
            f"GDP offer sent: {actual_offer} departures delayed for warning {warning_id}"
        )

    # -----------------------------------------------------------------------
    # Clearinghouse (airport as originator)
    # -----------------------------------------------------------------------
    async def handle_proposal(self, msg: dict):
        proposal_id = msg.get("proposal_id", "")
        # Idempotency: skip if already seen
        async with self._state_lock:
            if proposal_id in self.processed_proposal_ids:
                self.logger.debug(f"Duplicate proposal {proposal_id} ignored.")
                return
            self.processed_proposal_ids.add(proposal_id)

        warn_id = msg.get("referencing_warning_id", "")
        async with self._state_lock:
            if warn_id not in self.pending_warnings:
                return
            wd = self.pending_warnings[warn_id]
            if wd["status"] != "AUCTION_OPEN":
                return

            wd["received_proposals"].append({
                "id": proposal_id,
                "node": msg.get("proposing_node"),
                "contribution": msg.get("contribution_to_reduction", 0),
                "cost": random.randint(1, 100),
                "raw_proposal": msg,
            })
            if not wd["timer_started"]:
                wd["timer_started"] = True
                asyncio.create_task(self._run_clearinghouse(warn_id))

    async def _run_clearinghouse(self, warn_id: str):
        self.logger.info(f"Airport clearinghouse opened for {warn_id}, waiting 4s...")
        await asyncio.sleep(4.0)

        async with self._state_lock:
            if warn_id not in self.pending_warnings:
                return
            wd = self.pending_warnings[warn_id]
            required = wd["remaining_reduction"]
            proposals = sorted(wd["received_proposals"], key=lambda x: x["cost"])

        accepted, nodes, absorbed, raw = [], {self.node_id}, 0, []
        for p in proposals:
            if absorbed < required:
                accepted.append(p["id"])
                nodes.add(p["node"])
                absorbed += p["contribution"]
                raw.append(p["raw_proposal"])
                self.logger.info(f" -> ACCEPTED {p['id']} from {p['node']} (+{p['contribution']})")

        async with self._state_lock:
            wd["status"] = "PENDING_HITL" if absorbed >= required else "CASCADING"
            wd["accepted"] = accepted
            wd["participating_nodes"] = nodes

        if absorbed >= required:
            cons = DistributedFlowConsensus(
                consensus_id=f"CONS_{self.node_id}_{uuid.uuid4().hex[:6]}",
                referencing_warning_id=warn_id,
                participating_nodes=list(nodes),
                final_action_plan=accepted,
            )
            await self.emit("ddfn.flow.consensus", cons)
            self.logger.info(f"Consensus emitted for {warn_id}.")
        else:
            residual = required - absorbed
            self.logger.warning(
                f"Cascade: could only absorb {absorbed}/{required}. "
                f"Residual={residual} propagating upstream."
            )
            await self._cascade_warning(warn_id, residual)

        async with self._state_lock:
            self.pending_warnings.pop(warn_id, None)

    async def _cascade_warning(self, original_warn_id: str, residual: int):
        """If airport cannot resolve fully, escalate upstream."""
        warn = CapacityConstraintWarning(
            warning_id=f"WARN_{self.node_id}_{uuid.uuid4().hex[:6]}",
            originating_node=self.node_id,
            target_nodes=[],
            constrained_sector_id=self.upstream_sector or self.adjacent_sector,
            affected_time_window=TimeWindow(
                start=datetime.now(timezone.utc).isoformat(),
                end=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            ),
            required_flow_reduction=FlowReduction(
                metric="FLIGHTS_PER_HOUR", amount_to_reduce=residual
            ),
            affected_flights_pool=[],
        )
        await self.emit("ddfn.warning.trigger", warn)
        self.logger.warning(f"Cascade warning {warn.warning_id} emitted (residual={residual})")

    # -----------------------------------------------------------------------
    # AAR manual override (from UI)
    # -----------------------------------------------------------------------
    async def handle_aar_override(self, msg: dict):
        if msg.get("target_node") != self.node_id:
            return
        new_aar = int(msg.get("aar", self.status.aar))
        async with self._state_lock:
            self.status.aar = new_aar
        self.logger.info(f"FMP AAR override: {self.icao} AAR set to {new_aar}")

    async def handle_consensus(self, msg: dict):
        cid = msg.get("consensus_id", "")
        async with self._state_lock:
            if cid in self.processed_consensus_ids:
                return
            self.processed_consensus_ids.add(cid)
            
        warn_id = msg.get("referencing_warning_id")
        slot_data = msg.get("slot_table", [])
        
        if slot_data:
            from ddfn_v2.core.models import SlotDetails
            slots = [SlotDetails(**s) if isinstance(s, dict) else s for s in slot_data]
            # Keep only slots originating here
            my_slots = [s for s in slots if s.origin == self.icao]
            if my_slots:
                self.local_slots[warn_id] = my_slots

        if self.node_id in msg.get("participating_nodes", []):
            self.logger.info(f"Consensus {cid} received. Issuing CTOTs to A-CDM.")

    async def handle_aoc_message(self, msg: dict):
        """Handle Ready-to-Fly (REA) from airlines to perform scavenging."""
        if msg.get("origin_node") != self.icao:
            return
            
        flight_id = msg.get("flight_id")
        self.logger.info(f"Received READY_TO_FLY (REA) for {flight_id}. Starting scavenging...")
        
        # Scavenge: find another flight originating here that is delayed, and swap them.
        for warn_id, slots in self.local_slots.items():
            rea_slot = next((s for s in slots if s.flight_id == flight_id), None)
            if not rea_slot or rea_slot.status == "MANUALLY_SWAPPED":
                continue
                
            # Find a flight with a worse delay that we can swap with
            # In a real scenario, we'd check if the swap violates ADR, but here we just swap delays
            worse_slots = [s for s in slots if s.delay > rea_slot.delay and s.status != "MANUALLY_SWAPPED"]
            if worse_slots:
                # Pick the one with the most delay to give it to the REA flight? No, REA wants LESS delay.
                # If REA flight is delayed (e.g., 20m), it wants a smaller delay (e.g., 5m).
                better_slots = [s for s in slots if s.delay < rea_slot.delay and s.status != "MANUALLY_SWAPPED"]
                if better_slots:
                    # Swap with the best available
                    best_swap = min(better_slots, key=lambda x: x.delay)
                    
                    # --- PHASE 21: RAD VALIDATION BEFORE PROPOSING SWAP ---
                    fl1 = self.fdps.flights.get(flight_id)
                    fl2 = self.fdps.flights.get(best_swap.flight_id)
                    
                    if fl1 and fl2:
                        valid1, err1 = RAD_VALIDATOR.is_valid(fl1)
                        valid2, err2 = RAD_VALIDATOR.is_valid(fl2)
                        
                        if not valid1 or not valid2:
                            err_msg = err1 or err2
                            self.logger.warning(f"SCAVENGING BLOCKED by RAD: {err_msg}")
                            return

                    self.logger.info(f"SCAVENGING SUCCESS: Autonomously proposing swap {flight_id} <-> {best_swap.flight_id}")
                    
                    swap_req = {
                        "message_type": "FMP_SLOT_SWAP_REQUEST",
                        "warning_id": warn_id,
                        "flight_id_1": flight_id,
                        "flight_id_2": best_swap.flight_id,
                        "target_node": ""
                    }
                    await self.network.publish("ddfn.flow.negotiation", swap_req)
                    return
                    
        self.logger.info(f"Scavenging failed for {flight_id}: No better slots available.")


# ============================================================================
# Standalone entry point
# ============================================================================
async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("icao", help="Airport ICAO (e.g. EDDF, EGLL, LFPG, LEMD)")
    parser.add_argument("--adjacent-sector", default=None)
    parser.add_argument("--upstream-sector", default=None)
    parser.add_argument("--broker", default="ws://127.0.0.1:8001/ws")
    parser.add_argument("--aar", type=int, default=None, help="Override AAR")
    parser.add_argument("--inbound-demand", type=int, default=None)
    parser.add_argument("--aixm", help="Path to AIXM 4.5 XML file")
    parser.add_argument("--port", type=int, default=8000, help="Port for the HTTP server (default: 8000)")
    args = parser.parse_args()

    if args.aixm:
        from ddfn_v2.eng.airspace import load_from_aixm
        load_from_aixm(args.aixm)

    from ddfn_v2.eng.airspace import AIRPORT_SECTOR_ENTRY
    adj = args.adjacent_sector or AIRPORT_SECTOR_ENTRY.get(args.icao, "LFFF1A")

    # -----------------------------------------------------------------------
    # Build FDPS from centralized schedule.py
    # -----------------------------------------------------------------------
    fdps = FlightDataProcessingSystem()
    now = datetime.now(timezone.utc)
    
    # Each airport only tracks flights originating from it
    my_flights = schedule.get_flights_for_origin(args.icao)
    for f_id, orig, dest, route, fl, dep_offset_min in my_flights:
        dep_time = now + timedelta(minutes=dep_offset_min)
        flt = FlightTrajectory.from_flight_plan(
            flight_id=f_id,
            origin=orig, destination=dest,
            departure_time=dep_time,
            cruise_fl=fl,
            route_string=route,
        )
        fdps.add_flight(flt)
        logging.getLogger(f"Node[{args.icao}_AIRPORT]").info(f"FPL {f_id} loaded into edge FDPS.")

    network = NetworkClient(args.broker)
    node = AirportNode(args.icao, network, fdps, adj, args.upstream_sector)

    if args.aar:
        node.status.aar = args.aar
    if args.inbound_demand:
        node.status.inbound_demand = args.inbound_demand

    # Create FastAPI app for health checks and API
    app = FastAPI(title=f"Airport Node - {args.icao}")

    @app.get("/health")
    async def health_check():
        """
        Health check endpoint for Airport node.
        """
        return {
            "status": "healthy",
            "service": "airport",
            "icao": node.icao,
            "aar": node.status.aar,
            "adr": node.status.adr,
            "flights_tracked": len(node.fdps.flights),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @app.post("/api/aar/override", dependencies=[Security(verify_api_key)])
    async def api_aar_override(data: dict):
        """Override AAR for this airport."""
        new_aar = data.get("aar", node.status.aar)
        async with node._state_lock:
            node.status.aar = int(new_aar)
        return {"status": "success", "aar": node.status.aar}

    # Start both the node and the web server
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        node.start(),
        server.serve()
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
