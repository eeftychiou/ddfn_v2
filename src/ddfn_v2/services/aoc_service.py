import asyncio
import json
import logging
import argparse
from datetime import datetime, timedelta, timezone
import uuid
import dataclasses
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from typing import List, Dict, Set, Optional
from ddfn_v2.core.network import NetworkClient
from ddfn_v2.core.node import DDFN_Node
from ddfn_v2.core.models import FlightSummary, DistributedFlowConsensus, TimeWindow, from_dict, SlotDetails, FlightPlanFiled

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

class AOCNode(DDFN_Node):
    def __init__(self, node_id: str, network: NetworkClient):
        super().__init__(node_id, network)
        self.flights = [] # List of managed flights
        self.logger = logging.getLogger(f"AOC-{self.node_id}")
        
    async def start(self):
        await super().start()
        # AOC needs to listen to flow consensus to know if its flights are delayed
        self.register_handler("DISTRIBUTED_FLOW_CONSENSUS", self._handle_consensus)
        # Also airspace inventory to track its active flights
        self.register_handler("AIRSPACE_INVENTORY_UPDATE", self._handle_inventory)
        # Listen for new flight plans
        self.register_handler("FLIGHT_PLAN_FILED", self._handle_flight_plan_filed)
        await self.network.subscribe("ddfn.flight.plan", self.subscription_queue)
        
    async def _handle_consensus(self, message: dict):
        consensus = from_dict(DistributedFlowConsensus, message)
        
        # Check if any of our managed flights got a delay
        for slot in consensus.slot_table:
            if any(f["flight_id"] == slot.flight_id for f in self.flights):
                if slot.delay > 0:
                    self.logger.info(f"Flight {slot.flight_id} received CTOT delay: +{slot.delay} mins. CTOT: {slot.ctot}")

    async def _handle_inventory(self, message: dict):
         # In a real system, the AOC uses this to update its internal fleet tracking
         pass
         
    async def _handle_flight_plan_filed(self, message: dict):
        fp = from_dict(FlightPlanFiled, message)
        # If the flight belongs to us (e.g., node_id is DLH and flight is DLH123)
        if fp.flight_id.startswith(self.node_id):
            # Add to managed flights if not already there
            if not any(f.get("flight_id") == fp.flight_id for f in self.flights):
                self.flights.append({
                    "flight_id": fp.flight_id,
                    "origin": fp.origin,
                    "destination": fp.destination,
                    "route_string": fp.route_string,
                    "cruise_fl": fp.cruise_fl,
                    "departure_time": fp.departure_time
                })
                self.logger.info(f"Added new flight to fleet tracking: {fp.flight_id}")

    async def send_flight_plan(self, flight: any):
        """Files a flight plan to the network as a decentralized originator."""
        try:
            if isinstance(flight, dict):
                f_id = flight.get("flight_id")
                orig = flight.get("origin")
                dest = flight.get("destination", "LEMD")
                route = flight.get("route_string", "DCT")
                fl = flight.get("cruise_fl", 350)
                dep_offset = flight.get("departure_offset", 0)
            else:
                # flight is (f_id, orig, dest, route, fl, dep_offset)
                f_id, orig, dest, route, fl, dep_offset = flight
            
            dep_time = (datetime.now(timezone.utc) + timedelta(minutes=dep_offset)).isoformat()
            
            fp = FlightPlanFiled(
                flight_id=f_id,
                origin=orig,
                destination=dest,
                route_string=route,
                cruise_fl=fl,
                departure_time=dep_time
            )
            await self.emit("ddfn.flight.plan", fp)
            self.logger.info(f"Filed decentralized flight plan: {f_id} {orig}->{dest}")
        except Exception as e:
            self.logger.error(f"Failed to create/send flight plan for {flight}: {e}")
         
    async def send_ready_message(self, flight_id: str):
        """
        Broadcasts an AOCC_READY_TO_FLY message, indicating the aircraft is boarded 
        and ready to accept a better slot (scavenging).
        """
        # We need to find the flight to know its origin
        flight = next((f for f in self.flights if f["flight_id"] == flight_id), None)
        if not flight:
            self.logger.warning(f"Cannot send REA for unknown flight {flight_id}")
            return
            
        msg = {
            "message_type": "AOCC_READY_TO_FLY",
            "flight_id": flight_id,
            "origin_node": flight["origin"]
        }
        await self.network.publish("ddfn.aoc.messages", msg)
        self.logger.info(f"Broadcasted READY_TO_FLY (REA) for flight {flight_id}")

app = FastAPI()
node = None

@app.get("/metrics")
async def get_metrics():
    return {"node_id": node.node_id, "flights_managed": len(node.flights)}
    
@app.post("/api/ready/{flight_id}")
async def api_ready(flight_id: str):
    await node.send_ready_message(flight_id)
    return {"status": "success", "message": f"REA sent for {flight_id}"}
    

async def run_aoc_async(node_id: str, broker_url: str, port: int, aixm_path: Optional[str] = None):
    global node
    
    if aixm_path:
        from ddfn_v2.eng.airspace import load_from_aixm
        load_from_aixm(aixm_path)
        
    network = NetworkClient(broker_url)
    node = AOCNode(node_id, network)
    
    # Pre-populate some mock flights for this AOC
    from ddfn_v2.services import schedule
    import os
    # Adjusted path for data/real_schedule.json
    schedule_path = "data/real_schedule.json"
    if os.path.exists(schedule_path):
        schedule.load_schedule_from_file(schedule_path)
        
    raw_flights = schedule.get_flights_for_airline(node_id)
    node.flights = []
    for f in raw_flights:
        # Convert tuple (f_id, orig, dest, route, fl, dep_offset) to dict
        node.flights.append({
            "flight_id": f[0],
            "origin": f[1],
            "destination": f[2],
            "route_string": f[3],
            "cruise_fl": f[4],
            "departure_offset": f[5]
        })
    node.logger.info(f"AOC {node_id} loaded {len(node.flights)} flights from schedule.")
    
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    
    node.logger.info(f"AOC Node {node_id} started. Serving API on http://127.0.0.1:{port}")
    async def file_plans():
        try:
            await asyncio.sleep(10) # Wait for registration
            for flt in node.flights:
                await node.send_flight_plan(flt)
            node.logger.info(f"AOC {node_id} filed {len(node.flights)} initial flight plans.")
        except Exception as e:
            node.logger.error(f"Error filing plans for {node_id}: {e}")

    await asyncio.gather(
        node.start(),
        server.serve(),
        file_plans()
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DDFN AOC Node")
    parser.add_argument("node_id", help="Airline ICAO code (e.g., DLH, AFR, BAW)")
    parser.add_argument("--broker", default="ws://127.0.0.1:8001/ws", help="Broker WebSocket URL")
    parser.add_argument("--aixm", help="Path to AIXM 4.5 XML file")
    parser.add_argument("--port", type=int, help="Optional port for the local UI/API")
    args = parser.parse_args()
    
    port_map = {"DLH": 8030, "AFR": 8031, "BAW": 8032, "AEW": 8033, "CYP": 8034}
    port = args.port or port_map.get(args.node_id, 8030)
    
    asyncio.run(run_aoc_async(args.node_id, args.broker, port, args.aixm))
