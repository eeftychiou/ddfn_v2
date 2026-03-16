import subprocess
import time
import os
import signal
import sys
import argparse

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

def run_service(name, cmd, cwd=None):
    log_file = open(f"logs/{name}.log", "w")
    print(f"Starting {name}...")
    return subprocess.Popen(cmd, stdout=log_file, stderr=log_file, cwd=cwd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DDFN FIR Test Startup")
    parser.add_argument("--aixm", type=str, required=True, help="Path to AIXM 4.5 XML file")
    args = parser.parse_args()
    
    aixm_path = os.path.abspath(args.aixm)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    processes = []
    
    try:
        # 1. Start Broker
        processes.append(run_service("broker", ["uvicorn", "ddfn_v2.core.broker:app", "--host", "127.0.0.1", "--port", "8001"], cwd=os.path.join(script_dir, "src")))
        time.sleep(3)
        
        # 2. Start FMP Nodes for the 3 FIRs
        # LCCC: 8020, LGGG: 8021, LTAA: 8022
        fmp_nodes = [
            ("LCCC", "8020"),
            ("LGGG", "8021"),
            ("LTAA", "8022")
        ]
        
        for fir, port in fmp_nodes:
            cmd = ["python", "-m", "ddfn_v2.services.fmp_service", fir, "--port", port, "--aixm", aixm_path]
            processes.append(run_service(f"fmp_{fir}", cmd, cwd=os.path.join(script_dir, "src")))
            time.sleep(1)

        # 3. Start Airports relevant to these FIRs
        # LCLK (LCCC), LGAV (LGGG), LTBA (LTAA)
        for apt in ["LCLK", "LGAV", "LTBA"]:
            cmd = ["python", "-m", "ddfn_v2.services.airport_service", apt, "--aixm", aixm_path]
            processes.append(run_service(f"airport_{apt}", cmd, cwd=os.path.join(script_dir, "src")))
            
        # 4. Start AOCs
        for aoc in ["DLH", "AFR", "BAW"]:
            cmd = ["python", "-m", "ddfn_v2.services.aoc_service", aoc, "--aixm", aixm_path]
            processes.append(run_service(f"aoc_{aoc}", cmd, cwd=os.path.join(script_dir, "src")))
            
        # 5. Start Sim Manager
        processes.append(run_service("sim_manager", ["python", "-m", "ddfn_v2.services.sim_manager"], cwd=os.path.join(script_dir, "src")))

        print("\n" + "="*50)
        print("ALL FIR TEST SERVICES STARTED")
        print("="*50)
        print(f"Nicosia FIR (LCCC): http://127.0.0.1:8020")
        print(f"Athens FIR (LGGG):  http://127.0.0.1:8021")
        print(f"Ankara FIR (LTAA):  http://127.0.0.1:8022")
        print(f"Sim Manager:        http://127.0.0.1:8050")
        print("="*50)
        print("Logs are in the 'logs/' directory.")
        print("Press CTRL+C to stop all services.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down services...")
        for p in processes:
            p.terminate()
        print("Done.")
    except Exception as e:
        print(f"Error during startup: {e}")
        for p in processes:
            p.terminate()
        sys.exit(1)
