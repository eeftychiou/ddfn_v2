import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright, expect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(BASE_DIR, "src")

def start_process(cmd_path, name, args=None):
    print(f"Starting {name}...")
    log_name = name.replace("/", "_").lower()
    os.makedirs(os.path.join(BASE_DIR, "test_output", "logs"), exist_ok=True)
    log_file = open(os.path.join(BASE_DIR, "test_output", "logs", f"ui_test_{log_name}.log"), "w")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    env["DDFN_API_KEY"] = "TEST_API_KEY"
    env["PYTHONUNBUFFERED"] = "1"
    
    full_cmd = [sys.executable, "-m", cmd_path]
    if args:
        full_cmd.extend(args)
        
    p = subprocess.Popen(full_cmd, stdout=log_file, stderr=log_file, cwd=BASE_DIR, env=env)
    return p

def wait_for_server(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionResetError, ConnectionRefusedError):
            pass
        time.sleep(1)
    return False

def test_window_persistence():
    log_out = open("ui_test_script_output.log", "w", encoding="utf-8")
    def log_print(msg):
        print(msg)
        log_out.write(str(msg) + "\n")
        log_out.flush()

    log_print("Starting Window Persistence UI Test...")
    processes = []
    
    try:
        # 1. Start Infrastructure
        log_print("Starting Broker...")
        processes.append(start_process("ddfn_v2.core.broker", "Broker"))
        time.sleep(2)
        
        aixm_path = "AIXM/BD_2025-09-30_400005921419525.xml"
        
        # Cleanup previous run configs
        import os
        for f in ["node_configs/PERSIST_NODE.json", "node_configs/UI_TEST_PERSIST.json", "node_configs/PERSIST_NODE_DDFN_NODE.json"]:
            if os.path.exists(f):
                log_print(f"Cleaning up {f}...")
                os.remove(f)
                
        # Start FMP Node on port 8023
        log_print("Starting FMP/Instance1...")
        processes.append(start_process("ddfn_v2.services.fmp_service", "FMP/Instance1", ["--node_id", "PERSIST_NODE", "--port", "8023", "--aixm", aixm_path]))
        
        if not wait_for_server("http://127.0.0.1:8023"):
            raise Exception("FMP Dashboard failed to start")
            
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("console", lambda msg: log_print(f"  [BROWSER]: {msg.text}"))
            
            # --- Step 1: Initial Load & Configuration ---
            log_print("  >> Loading Dashboard...")
            page.goto("http://127.0.0.1:8023", wait_until="networkidle")
            
            # Forcibly hide setup wizard if it blocks (both class and style)
            page.evaluate("() => { const modal = document.getElementById('setup-wizard-modal'); if(modal) { modal.classList.add('hidden'); modal.style.display = 'none'; } }")
            
            log_print("  >> Navigating to Airspace Config...")
            page.click("button[data-target='tab-config']")
            page.wait_for_selector("#tab-config.active")
            
            # Wait for initial data fetches to settle (Persistence check)
            log_print("  >> Waiting for page settlement...")
            time.sleep(3)
            
            log_print("  >> Loading AIXM sectors...")
            page.click("#btn-load-aixm")
            # Wait for FIR selection to populate in DOM (even if hidden)
            page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=25000)
            
            # Select LCCC robustly via JS
            log_print("  >> Selecting FIR LCCC via JS...")
            page.evaluate("() => { const sel = document.getElementById('config-fir-select'); sel.value = 'LCCC'; sel.dispatchEvent(new Event('change')); }")
            
            # Ensure sectors populated
            log_print("  >> Waiting for sector list to populate...")
            page.wait_for_selector(".sector-config-item", timeout=12000)
            
            log_print("  >> Selecting at least one sector...")
            page.click(".sector-config-check >> nth=0")

            log_print("  >> Setting window to 5 Minutes via JS...")
            page.evaluate("() => { const sel = document.getElementById('config-window-size'); sel.value = '5'; sel.dispatchEvent(new Event('change')); }")
            page.fill("#config-node-name", "UI_TEST_PERSIST")
            
            # --- DEFENSIVE CHECK ---
            log_print("  >> Defensive Check for FIR/FilePath...")
            fir_val = page.evaluate("() => document.getElementById('config-fir-select').value")
            path_val = page.evaluate("() => document.getElementById('config-aixm-path').value")
            log_print(f"  >> Current FIR: '{fir_val}', Path: '{path_val}'")
            if not fir_val or not path_val:
                 log_print("  >> WARNING: FIR or Path empty, re-setting LCCC...")
                 page.evaluate("() => { document.getElementById('config-fir-select').value = 'LCCC'; document.getElementById('config-aixm-path').value = 'AIXM/BD_2025-09-30_400005921419525.xml'; }")

            log_print("  >> Saving Configuration...")
            page.click("#btn-save-airspace-config")
            
            # Wait for page reload
            log_print("  >> Waiting for page reload after save...")
            page.wait_for_load_state("networkidle")
            time.sleep(5) # Let it settle completely
            
            # --- Step 2: Verify Persistence in Config Tab ---
            log_print("  >> Verifying Persistence in Config Tab...")
            page.click("button[data-target='tab-config']")
            page.wait_for_selector("#tab-config.active")
            time.sleep(2) # Wait for fetches in tab
            
            # Get current value
            val = page.evaluate("() => document.getElementById('config-window-size').value")
            log_print(f"  >> Config Tab Window Size: {val}")
            if val != "5":
                page.screenshot(path="test_output/logs/ui_test_persist_fail_config.png")
            assert val == "5", f"Window size did not persist in Config tab, got: {val}"
            
            # --- Step 3: Verify Sync in Settings Modal ---
            log_print("  >> Verifying Sync in Settings Modal...")
            settings_val = page.evaluate("() => document.getElementById('measurement-window-select').value")
            log_print(f"  >> Settings Modal Window Size: {settings_val}")
            if settings_val != "5":
                page.screenshot(path="test_output/logs/ui_test_persist_fail_settings.png")
            assert settings_val == "5", f"Window size did not sync to Settings modal, got: {settings_val}"
            
            # --- Step 4: Verify Persistence after Manual Refresh ---
            log_print("  >> Verifying Persistence after manual page refresh...")
            page.reload(wait_until="networkidle")
            time.sleep(3)
            
            page.click("button[data-target='tab-config']")
            page.wait_for_selector("#tab-config.active")
            val_after_refresh = page.evaluate("() => document.getElementById('config-window-size').value")
            log_print(f"  >> Value after refresh: {val_after_refresh}")
            if val_after_refresh != "5":
                page.screenshot(path="test_output/logs/ui_test_persist_fail_refresh.png")
            assert val_after_refresh == "5", "Window size did not persist after manual refresh"
            
            log_print("  [SUCCESS] UI Persistence Test Passed!")
            browser.close()
            
    except Exception as e:
        log_print(f"Test failed with error: {e}")
        # Try to take a screenshot and save page source on any failure
        try:
            if 'page' in locals():
                os.makedirs(os.path.join(BASE_DIR, "test_output", "logs"), exist_ok=True)
                page.screenshot(path="test_output/logs/ui_test_failure_screenshot.png")
                with open("test_output/logs/ui_test_failure_source.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
        except:
            pass
        raise e
    finally:
        log_print("Cleaning up processes...")
        for proc in processes:
            proc.terminate()
        log_out.close()

if __name__ == "__main__":
    test_window_persistence()
