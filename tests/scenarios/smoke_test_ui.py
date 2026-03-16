
import asyncio
import subprocess
import time
import os
import signal
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Root directory
SRC_DIR = os.path.join(BASE_DIR, "src")

def start_process(cmd, log_file=None):
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    full_cmd = f"\"{sys.executable}\" -m {cmd}"
    if log_file:
        log_path = os.path.join(BASE_DIR, log_file)
        f = open(log_path, "w")
        return subprocess.Popen(full_cmd, shell=True, stdout=f, stderr=f, env=env, cwd=SRC_DIR)
    return subprocess.Popen(full_cmd, shell=True, env=env, cwd=SRC_DIR)

def main():
    print("Starting DDFN infrastructure for UI Smoke Test...")
    processes = []
    
    # Ensure logs dir exists
    logs_dir = os.path.join(BASE_DIR, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Start Broker
    processes.append(start_process("ddfn_v2.core.broker", "logs/broker.log"))
    time.sleep(2)

    # Start FMP nodes
    processes.append(start_process("ddfn_v2.services.fmp_service EGTT", "logs/fmp_egtt.log"))
    processes.append(start_process("ddfn_v2.services.fmp_service EDDD", "logs/fmp_eddd.log"))
    time.sleep(2)

    # Start Airport & AOC services to populate flights
    processes.append(start_process("ddfn_v2.services.airport_service EGLL", "logs/apt_egll.log"))
    processes.append(start_process("ddfn_v2.services.aoc_service BAW", "logs/aoc_baw.log"))
    time.sleep(2)

    # Start Sim Manager to coordinate
    processes.append(start_process("ddfn_v2.services.sim_manager", "logs/sim_manager.log"))

    print("Simulation running. EGTT Dashboard: http://127.0.0.1:8012")
    print("EDDD Dashboard: http://127.0.0.1:8011")
    print("Press Ctrl+C to terminate...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTerminating processes...")
        for p in processes:
            p.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
