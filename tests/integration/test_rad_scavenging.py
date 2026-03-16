import asyncio
import json
import logging
import datetime
import uuid
from ddfn_v2.core.network import NetworkClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("TestRAD")

async def main():
    broker_url = "ws://127.0.0.1:8001/ws"
    network = NetworkClient(broker_url)
    await network.connect("TEST_RAD_CLIENT")
    
    logger.info("Connected to broker. Forcing capacity constraint on UMLAT...")
    
    # 1. Force Capacity Constraint on UMLAT (impacts EGLL outbound)
    # This will trigger CASA and generate slots.
    # 1. Force Capacity Constraint on EGTT1C
    # In distributed mode, we target the specific sector node.
    capacity_msg = {
        "message_type": "FMP_MANUAL_OVERRIDE",
        "target_node": "EGTT1C_DDFN_NODE",
        "sector_id": "EGTT1C",
        "capacity": 2 
    }
    await network.publish("ddfn.fmp.command", capacity_msg)
    
    logger.info("Waiting for consensus...")
    await asyncio.sleep(5) # Wait for FMP to process and broadcast consensus
    
    # 2. Broadcast REA for BAW201 (Valid Flight)
    # It wants to scavenge a slot from BAW210 (Invalid Flight)
    # In our scenario, BAW201 (FL360) and BAW210 (FL250) both use DVR.
    # BAW210 is restricted by RAD_EG_001 (DVR < FL280).
    
    rea_msg = {
        "message_type": "AOCC_READY_TO_FLY",
        "flight_id": "BAW201",
        "origin_node": "EGLL"
    }
    logger.info("Broadcasting READY_TO_FLY for BAW201...")
    await network.publish("ddfn.aoc.messages", rea_msg)
    
    logger.info("Verification: Check logs/airport_EGLL.log for 'SCAVENGING BLOCKED by RAD'")
    await asyncio.sleep(2)
    await network.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
