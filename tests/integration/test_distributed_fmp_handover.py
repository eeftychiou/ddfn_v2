import asyncio
import json
import logging
import websockets
import datetime
import uuid
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("DistVerify")

BROKER_URL = "ws://127.0.0.1:8001/ws"

async def run_verification():
    logger.info("Starting Distributed FMP Verification...")
    
    try:
        async with websockets.connect(BROKER_URL) as ws:
            # 1. Subscribe to relevant topics
            topics = ["ddfn.relay.handover", "ddfn.airspace.inventory", "ddfn.flow.consensus", "ddfn.capacity.state"]
            for t in topics:
                await ws.send(json.dumps({"action": "subscribe", "topic": t}))
            
            logger.info("Subscribed to SWIM topics. Waiting for heartbeat...")
            
            # 2. Monitor Inventory
            # We expect to see inventory updates from LFFF1A, LFFF1B, etc.
            inventories = {}
            
            # 3. Inject a new flight plan that crosses LFFF and EDDD
            flight_id = f"TEST{uuid.uuid4().hex[:4].upper()}"
            dept_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)).isoformat()
            
            flight_plan = {
                "message_type": "FLIGHT_PLAN_FILED",
                "flight_id": flight_id,
                "origin": "LFPG",
                "destination": "EDDF",
                "route_string": "LFPG VESAN EDDF", # Crosses LFFF and EDDD
                "cruise_fl": 350,
                "departure_time": dept_time
            }
            
            logger.info(f"Injecting test flight: {flight_id}")
            await ws.send(json.dumps({
                "action": "publish",
                "topic": "ddfn.flight.plan",
                "message": flight_plan
            }))
            
            # 4. Wait for handovers and inventory updates
            handovers = []
            start_time = time.time()
            
            while time.time() - start_time < 30:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(raw)
                    msg = data.get("message", {})
                    mtype = msg.get("message_type")
                    
                    if mtype == "AIRSPACE_INVENTORY_UPDATE":
                        node_id = msg.get("node_id")
                        flights = [f["flight_id"] for f in msg.get("flights", [])]
                        inventories[node_id] = flights
                        if flight_id in flights:
                            logger.info(f"Flight {flight_id} detected in inventory of {node_id}")
                            
                    elif mtype == "FIR_HANDOVER_ADVISORY":
                        h_fid = msg.get("flight_id")
                        if h_fid == flight_id:
                            logger.info(f"Handover advisory detected for {flight_id} from {msg.get('originating_node')} via {msg.get('exit_fix')}")
                            handovers.append(msg)
                            
                except asyncio.TimeoutError:
                    continue

            # 5. Final Report
            logger.info("Verification Complete.")
            logger.info(f"Inventories tracking {flight_id}: {[k for k,v in inventories.items() if flight_id in v]}")
            logger.info(f"Handovers seen: {len(handovers)}")
            
            if len(handovers) > 0 and any(flight_id in v for v in inventories.values()):
                logger.info("RESULT: PASS - Distributed tracking and handover confirmed.")
            else:
                logger.error("RESULT: FAIL - Handover or tracking missing.")

    except Exception as e:
        logger.error(f"Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_verification())
