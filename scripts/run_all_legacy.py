import argparse
import subprocess
import time
import os
import signal
import sys

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

def run_service(name, cmd, cwd=None):
    log_file = open(f"logs/{name}.log", "w")
    print(f"Starting {name}...")
    return subprocess.Popen(cmd, stdout=log_file, stderr=log_file, cwd=cwd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DDFN Network Bootstrap")
    parser.add_argument("--aixm", type=str, help="Path to AIXM 4.5 XML file for sector definition")
    args = parser.parse_args()
    
    aixm_path = os.path.abspath(args.aixm) if args.aixm else None

    processes = []
    
    # 1. Start Broker
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Updated to src/ddfn_v2/core/broker.py
    processes.append(run_service("broker", ["uvicorn", "ddfn_v2.core.broker:app", "--host", "127.0.0.1", "--port", "8001"], cwd=os.path.join(script_dir, "src")))
    time.sleep(3)
    
    # 2. Determine FMP Nodes
    fmp_configs = []
    if args.aixm:
        sys.path.append(os.path.join(script_dir, "src"))
        from ddfn_v2.eng import airspace
        airspace.load_from_aixm(args.aixm)
        # Load real flight schedule if available
        from ddfn_v2.services import schedule
        schedule_path = "data/real_schedule.json"
        if os.path.exists(schedule_path):
            schedule.load_schedule_from_file(schedule_path)
        
        all_sectors = list(airspace.SECTORS.keys())
        print(f"Detected {len(all_sectors)} sectors. Starting first 10 for demonstration.")
        base_port = 8020
        for i, sector_id in enumerate(all_sectors[:10]):
            cmd = ["python", "-m", "ddfn_v2.services.fmp_service", sector_id, "--port", str(base_port + i)]
            if aixm_path:
                cmd.extend(["--aixm", aixm_path])
            fmp_configs.append((f"fmp_{sector_id}", cmd))
    else:
        # Default mock sectors
        fmp_configs = [
            ("fmp_LFFF1A", ["python", "-m", "ddfn_v2.services.fmp_service", "LFFF1A", "--port", "8020"]),
            ("fmp_LFFF1B", ["python", "-m", "ddfn_v2.services.fmp_service", "LFFF1B", "--port", "8021"]),
            ("fmp_EDDD2B", ["python", "-m", "ddfn_v2.services.fmp_service", "EDDD2B", "--port", "8022"]),
            ("fmp_EGTT1C", ["python", "-m", "ddfn_v2.services.fmp_service", "EGTT1C", "--port", "8023"]),
        ]

    # 3. Start FMP Nodes
    for name, cmd in fmp_configs:
        processes.append(run_service(name, cmd, cwd=script_dir))
    
    # 4. Start Airports
    for apt in ["LFPG", "EDDF", "EGLL"]:
        cmd = ["python", "-m", "ddfn_v2.services.airport_service", apt]
        if aixm_path:
            cmd.extend(["--aixm", aixm_path])
        processes.append(run_service(f"airport_{apt}", cmd, cwd=os.path.join(script_dir, "src")))
        
    # 5. Start AOCs
    for aoc in ["DLH", "AFR", "BAW"]:
        cmd = ["python", "-m", "ddfn_v2.services.aoc_service", aoc]
        if aixm_path:
            cmd.extend(["--aixm", aixm_path])
        processes.append(run_service(f"aoc_{aoc}", cmd, cwd=os.path.join(script_dir, "src")))
        
    # 6. Start Sim Manager
    processes.append(run_service("sim_manager", ["python", "-m", "ddfn_v2.services.sim_manager"], cwd=os.path.join(script_dir, "src")))

    print("All services started. Logs are in the 'logs/' directory.")
    print("Sim Manager UI: http://127.0.0.1:8050")
    print("Press CTRL+C to stop all services.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down services...")
        for p in processes:
            p.terminate()
        print("Done.")
