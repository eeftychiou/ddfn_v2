import asyncio
import json
import logging
import subprocess
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
import websockets
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("MasterSuite")

BROKER_URL = "ws://127.0.0.1:8001/ws"
HTTP_BASE = "http://127.0.0.1:8001"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Root directory
SRC_DIR = os.path.join(BASE_DIR, "src")

# Global process registry for cleanup
processes: List[subprocess.Popen] = []
LOG_DIR = os.path.join(BASE_DIR, "logs")
AIXM_FILE = os.path.join(BASE_DIR, "AIXM", "BD_2025-09-30_400005921419525.xml")

def start_process(cmd_args: List[str], name: str, use_aixm: bool = False):
    logger.info(f"  » Starting {name}...")
    log_file_base = name.replace("/", "_").replace(".", "_").lower()
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"{log_file_base}.log")
    
    try:
        log_file = open(log_path, "w")
        env = os.environ.copy()
        env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
        
        final_cmd = [sys.executable, "-m"] + cmd_args
        if use_aixm and os.path.exists(AIXM_FILE):
            final_cmd.extend(["--aixm", AIXM_FILE])
            
        log_file.write(f"Executing: {' '.join(final_cmd)}\n")
        log_file.write(f"CWD: {SRC_DIR}\n")
        log_file.write(f"PYTHONPATH: {env['PYTHONPATH']}\n")
        log_file.write("-" * 40 + "\n")
        log_file.flush()

        p = subprocess.Popen(final_cmd, stdout=log_file, stderr=log_file, cwd=SRC_DIR, env=env)
        processes.append(p)
        logger.info(f"  » Started {name} (PID: {p.pid}) -> {log_path}")
        return p
    except Exception as e:
        logger.error(f"  » Failed to start {name}: {e}")
        return None

def cleanup():
    logger.info("  » Cleaning up simulation cluster...")
    for p in processes:
        try:
            p.terminate()
        except:
            pass
    for p in processes:
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except:
                pass
    logger.info("  » Cleanup complete.")

async def http_get(url: str) -> Dict[str, Any]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        logger.debug(f"HTTP GET failed: {url} -> {e}")
        return {}

class SwimMonitor:
    def __init__(self, broker_url: str):
        self.broker_url = broker_url
        self.messages: List[Dict[str, Any]] = []
        self._ws = None
        self._listen_task = None

    async def connect(self):
        for i in range(10):
            try:
                self._ws = await websockets.connect(self.broker_url, open_timeout=5)
                logger.info("  » Monitor connected to SWIM bus.")
                break
            except Exception as e:
                logger.warning(f"  » Monitor connection retry {i+1}/10... ({e})")
                await asyncio.sleep(2)
        else:
            raise ConnectionError("Could not connect to SWIM broker.")

        topics = ["ddfn.flow.consensus", "ddfn.capacity.state", "ddfn.warning.trigger", "ddfn.ui.inbox"]
        for t in topics:
            await self._ws.send(json.dumps({"action": "subscribe", "topic": t}))
        self._listen_task = asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "message" in msg:
                    self.messages.append(msg["message"])
                else:
                    self.messages.append(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Monitor listener stopped: {e}")

    async def publish(self, topic: str, payload: Dict[str, Any]):
        envelope = {"action": "publish", "topic": topic, "message": payload}
        if self._ws:
            await self._ws.send(json.dumps(envelope))

    async def disconnect(self):
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws:
            await self._ws.close()

class MasterTestRunner:
    def __init__(self):
        self.monitor = SwimMonitor(BROKER_URL)
        self.results = []

    def report(self, name: str, success: bool, detail: str = ""):
        self.results.append({"name": name, "success": success, "detail": detail})
        icon = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"  {icon} - {name} ({detail})")

    async def run(self):
        try:
            # --- 1. Orchestration ---
            if not start_process(["ddfn_v2.core.broker"], "Broker"):
                raise RuntimeError("Failed to start Broker")
            
            await asyncio.sleep(5)
            
            start_process(["ddfn_v2.services.fmp_service", "LCCC", "--port", "8020"], "FMP_LCCC", use_aixm=True)
            # start_process(["ddfn_v2.services.fmp_service", "LCCCS2", "--port", "8021"], "FMP_LCCCS2", use_aixm=True)
            # start_process(["ddfn_v2.services.fmp_service", "LCCCWL", "--port", "8022"], "FMP_LCCCWL", use_aixm=True)
            # start_process(["ddfn_v2.services.fmp_service", "LCCCWU", "--port", "8023"], "FMP_LCCCWU", use_aixm=True)

            for a in ["LCLK", "LCPH"]: 
                start_process(["ddfn_v2.services.airport_service", a], f"Airport_{a}", use_aixm=True)
            
            start_process(["ddfn_v2.services.aoc_service", "CYP", "--port", "8034"], "AOC_CYP", use_aixm=True)
            start_process(["ddfn_v2.services.aoc_service", "AEW", "--port", "8033"], "AOC_AEW", use_aixm=True)
            
            start_process(["ddfn_v2.services.sim_manager"], "Sim_Manager", use_aixm=False)
            
            logger.info("  » Giving services time to initialize...")
            await asyncio.sleep(40)
            
            await self.monitor.connect()
            
            # Verify Nodes Registration via API
            nodes_data = {"nodes": []}
            required_nodes = 6 # LCCC, 2 Airports, 2 AOCs, Sim Manager
            for i in range(30):
                nodes_data = await http_get(f"{HTTP_BASE}/api/nodes")
                current_nodes = len(nodes_data.get("nodes", []))
                if current_nodes >= required_nodes:
                    break
                logger.info(f"  » Waiting for nodes to register... (seen {current_nodes}/{required_nodes})")
                await asyncio.sleep(3)

            self.report("Orchestration", len(nodes_data.get("nodes", [])) >= required_nodes, f"Registered: {len(nodes_data.get('nodes', []))} nodes")

            # --- 3. Phase 22: Demand Profiles ---
            profile_ok = False
            for _ in range(20):
                await asyncio.sleep(2)
                caps = [m for m in self.monitor.messages if m.get("message_type") == "CAPACITY_STATE_BROADCAST"]
                if caps:
                    # Check if any message has a legitimate demand profile
                    for c in caps:
                        profile = c.get("demand_profile", [])
                        if len(profile) >= 288:
                            profile_ok = True
                            break
                if profile_ok: break
            
            self.report("Phase 22 (Demand Profiles)", profile_ok, "Profile bins found" if profile_ok else "No complete demand profile seen")

            # --- 4. Phase 23: Multi-Constraints ---
            logger.info("  » Injecting multiple constraints into LCCC00003...")
            
            # 4a. Inject overlapping flights to ensure demand > capacity
            now_base = time.strftime("%Y-%m-%dT22:15:00Z")
            for i in range(3):
                await self.monitor.publish("ddfn.flight.plan", {
                    "message_type": "FLIGHT_PLAN_FILED",
                    "flight_id": f"TEST{i}",
                    "origin": "LCLK",
                    "destination": "LGRP",
                    "route_string": "LCLK DCT LGRP",
                    "cruise_fl": 340,
                    "departure_time": now_base
                })
            await asyncio.sleep(5) # Let FMP process them

            # 4b. Set override
            await self.monitor.publish("ddfn.fmp.command", {
                "message_type": "MANUAL_CAPACITY_OVERRIDE",
                "target_node": "LCCC_DDFN_NODE",
                "sector": "LCCC00003",
                "capacity": 1, 
                "start_time": "22:00",
                "end_time": "23:00", 
                "reason": "WEATHER"
            })
            
            found_ovr = False
            for i in range(20):
                await asyncio.sleep(2)
                msgs = [m for m in self.monitor.messages if m.get("message_type") == "CAPACITY_STATE_BROADCAST" and m.get("sector", {}).get("sector_id") == "LCCC00003"]
                if msgs:
                    latest = msgs[-1]
                    ovrs = latest.get("active_overrides", [])
                    if len(ovrs) >= 1:
                        found_ovr = True
                        break
            
            self.report("Phase 23 (Multi-Constraints)", found_ovr, "Overrides detected" if found_ovr else "Overrides not found")

            # --- 5. Phase 24: CASA Flow Cycle ---
            logger.info("  » Waiting for approval request (HITL)...")
            found_req = None
            for _ in range(40):
                await asyncio.sleep(1)
                reqs = [m for m in self.monitor.messages if m.get("message_type") == "UI_INBOX_APPROVAL_REQUEST"]
                if reqs:
                    found_req = reqs[-1]
                    break
            
            found_consensus = False
            if found_req:
                target_fmp = found_req.get("target_node")
                await self.monitor.publish("ddfn.fmp.command", {
                    "message_type": "FMP_PROPOSAL_APPROVAL",
                    "target_node": target_fmp,
                    "warning_id": found_req.get("warning_id"),
                    "action": "APPROVE"
                })
                
                for _ in range(30):
                    await asyncio.sleep(1)
                    consensus_msgs = [m for m in self.monitor.messages if m.get("message_type") == "DISTRIBUTED_FLOW_CONSENSUS"]
                    if len(consensus_msgs) > 0:
                        found_consensus = True
                        break
            
            self.report("CASA Cycle", found_consensus, "Consensus reached" if found_consensus else "No consensus")

            # --- 6. Phase 25: AOC Scavenging ---
            logger.info("  » Phase 25: Triggering AOC REA scavenge for TEST1...")
            await self.monitor.publish("ddfn.aoc.messages", {
                "message_type": "AOCC_READY_TO_FLY",
                "flight_id": "TEST1"
            })
            
            await asyncio.sleep(15)
            all_cons = [m for m in self.monitor.messages if m.get("message_type") == "DISTRIBUTED_FLOW_CONSENSUS"]
            self.report("Phase 25 (AOC Scavenging)", len(all_cons) >= 2, f"Total consensus iterations: {len(all_cons)}")

            self.print_final()

        except Exception as e:
            logger.error(f"Master test execution failed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await self.monitor.disconnect()
            cleanup()

    def print_final(self):
        print("\n" + "="*60)
        print("  DDFN MASTER COMPREHENSIVE TEST SUITE - FINAL RESULTS")
        print("="*60)
        passed_count = sum(1 for r in self.results if r["success"])
        for r in self.results:
            status = "PASS" if r["success"] else "FAIL"
            print(f" {status} | {r['name']:.<35} | {r['detail']}")
        print("="*60)
        if passed_count == len(self.results):
            print(f"  OVERALL STATUS: SUCCESS ({passed_count}/{len(self.results)})")
        else:
            print(f"  OVERALL STATUS: FAILURE ({passed_count}/{len(self.results)})")
        print("="*60 + "\n")

if __name__ == "__main__":
    runner = MasterTestRunner()
    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        cleanup()
