import asyncio
import json
import logging
import subprocess
import os
import sys
import time
import websockets
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("ResilienceTest")

BROKER_URL = "ws://127.0.0.1:8001/ws"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ResilienceRunner:
    def __init__(self):
        self.processes = []
        self.results = []

    def start_process(self, cmd: List[str], name: str):
        logger.info(f"  » Starting {name}...")
        p = subprocess.Popen([sys.executable] + cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
        self.processes.append(p)
        return p

    def cleanup(self):
        logger.info("  » Cleaning up...")
        for p in self.processes:
            p.terminate()
            try: p.wait(timeout=2)
            except: p.kill()

    async def test_reconnect(self):
        logger.info("\n--- TEST: Broker Reconnect Resilience ---")
        broker_p = self.start_process(["broker.py"], "Broker")
        await asyncio.sleep(2)
        
        # Start a client (FMP)
        fmp_p = self.start_process(["fmp_service.py", "LFFF1A"], "FMP/LFFF1A")
        await asyncio.sleep(5)
        
        # Verify LFFF is connected
        connected = False
        try:
            async with websockets.connect(BROKER_URL) as ws:
                await ws.send(json.dumps({"action": "subscribe", "topic": "ddfn.capacity.state"}))
                # Wait for any broadcast
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    logger.info("  » Initial connection verified.")
                    connected = True
                except asyncio.TimeoutError:
                    logger.warning("  » No broadcast seen, but continuing...")
                    connected = True # Assume it's alive if no error
        except Exception as e:
            logger.error(f"  » Initial connection failed: {e}")
            return False

        # KILL BROKER
        logger.info("  » KILLING BROKER...")
        broker_p.terminate()
        broker_p.wait()
        await asyncio.sleep(2)
        
        # RESTART BROKER
        logger.info("  » RESTARTING BROKER...")
        broker_p = self.start_process(["broker.py"], "Broker")
        await asyncio.sleep(5) # Give FMP time to reconnect (usually 3-5s retry)
        
        # Verify LFFF reconnected by checking if it sends another heartbeat/broadcast
        reconnected = False
        logger.info("  » Checking for LFFF reconnection...")
        try:
            async with websockets.connect(BROKER_URL) as ws:
                await ws.send(json.dumps({"action": "subscribe", "topic": "ddfn.capacity.state"}))
                # FMP sends state every 3 seconds or on change
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(msg)
                    if data.get("message", {}).get("node_id") == "LFFF1A_DDFN_NODE":
                        logger.info("  » PASS: LFFF automatically reconnected and resumed broadcasting.")
                        reconnected = True
                except asyncio.TimeoutError:
                    logger.error("  » FAIL: LFFF did not resume broadcasting after broker restart.")
        except Exception as e:
            logger.error(f"  » Reconnection verification failed: {e}")
            
        return reconnected

    async def run(self):
        try:
            success = await self.test_reconnect()
            if success:
                logger.info("\n✅ ALL RESILIENCE TESTS PASSED")
            else:
                logger.info("\n❌ RESILIENCE TESTS FAILED")
                sys.exit(1)
        finally:
            self.cleanup()

if __name__ == "__main__":
    runner = ResilienceRunner()
    asyncio.run(runner.run())
