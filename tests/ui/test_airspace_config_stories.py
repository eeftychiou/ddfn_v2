import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json
from playwright.sync_api import sync_playwright, expect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(BASE_DIR, "src")

def start_process(cmd_path, name, args=None, env_vars=None):
    print(f"Starting {name}...")
    os.makedirs(os.path.join(BASE_DIR, "test_output"), exist_ok=True)
    log_file = open(os.path.join(BASE_DIR, "test_output", f"ui_test_{name.replace('/', '_').lower()}.log"), "w")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    if env_vars:
        env.update(env_vars)
    
    full_cmd = [sys.executable, "-m", cmd_path]
    if args:
        full_cmd.extend(args)
        
    p = subprocess.Popen(full_cmd, stdout=log_file, stderr=log_file, cwd=BASE_DIR, env=env)
    return p, log_file

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

def test_airspace_config_stories():
    print("Starting Airspace Configuration Stories UI Verification...")
    os.makedirs(os.path.join(BASE_DIR, "test_output"), exist_ok=True)
    processes = []
    logs = []
    
    api_key = "ui-story-test-key"
    env_vars = {"DDFN_API_KEY": api_key}
    
    # Cleanup previous runs
    cfg_dir = os.path.join(BASE_DIR, "data", "node_configs")
    for f in ["FMP_STORY_TEST_DDFN_NODE.json", "FMP_STORY_TEST_DDFN_NODE_saved.json", "STORY_VERIFY_CONFIG.json"]:
        p = os.path.join(cfg_dir, f)
        if os.path.exists(p):
            print(f"Cleaning up {f}...")
            os.remove(p)

    try:
        # Start Broker
        p, log = start_process("ddfn_v2.core.broker", "Broker", env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        time.sleep(2)
        
        # Start FMP Service on a test port
        port = "8097"
        p, log = start_process("ddfn_v2.services.fmp_service", "FMP_STORY_TEST", ["--port", port, "--node_id", "FMP_STORY_TEST"], env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        
        if not wait_for_server(f"http://127.0.0.1:{port}/health"):
            print(f"ERROR: FMP Service failed to start on port {port}")
            return False

        with sync_playwright() as p_play:
            browser = p_play.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            
            # Capture console logs
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: print(f"BROWSER ERROR: {err.message}"))
            
            print("Step 1: Navigating to Airspace Config...")
            page.goto(f"http://127.0.0.1:{port}")
            page.evaluate(f"k => window.localStorage.setItem('ddfn_api_key', k)", api_key)
            page.reload()
            
            # Bypass setup
            page.evaluate("""() => { 
                const wizard = document.getElementById('setup-wizard-modal'); 
                if(wizard) wizard.remove();
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
            }""")
            
            page.click("button[data-target='tab-config']", force=True)
            
            print("Step 2: Loading AIXM file...")
            aixm_path = os.path.join(BASE_DIR, "AIXM", "BD_2025-09-30_400005921419525.xml")
            page.fill("#config-aixm-path", aixm_path)
            page.click("#btn-load-aixm", force=True)
            
            print("  >> Selecting LCCC FIR...")
            page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=15000)
            page.select_option("#config-fir-select", "LCCC")
            
            print("  >> Waiting for sectors and airports...")
            page.wait_for_selector(".sector-config-item", timeout=10000)
            page.wait_for_selector("#config-airport-list .config-item", timeout=10000)
            
            print("Step 3: Configuring partial FIR and airport...")
            # Use the new "Select / Unselect All" functionality
            page.uncheck("#check-all-sectors")
            page.wait_for_timeout(500)
            
            # Check exactly one sector (the first one of LCCC)
            # The first check is now index 0 if we ignore the header checkbox
            page.locator(".sector-config-check").nth(0).check()
            
            # Uncheck all airports using the new header checkbox
            page.uncheck("#check-all-airports")
            page.wait_for_timeout(500)
            
            # Check exactly one airport
            page.locator(".airport-config-check").nth(0).check()
            
            baseline_cap = 55
            page.fill("#config-baseline-capacity", str(baseline_cap))
            config_name = "STORY_VERIFY_CONFIG"
            page.fill("#config-node-name", config_name)
            
            print("Step 4: Saving and Applying...")
            time.sleep(1) # Small buffer
            page.click("#btn-save-airspace-config", force=True)
            
            # Wait for reload
            print("  >> Waiting for page reload...")
            time.sleep(3) 
            page.wait_for_selector("#tab-overview.active", timeout=15000)
            
            print("Step 5: Verifying User Stories...")
            
            # Story 1: Verify saved config in list
            page.click("button[data-target='tab-config']", force=True)
            page.wait_for_selector(f"#config-saved-list option:has-text('{config_name}')", state="attached", timeout=10000)
            print("  [OK] Story 1: Saved configuration appears in dropdown.")
            
            # Verification via backend /metadata API for Story 2, 3, 4
            import urllib.request
            req = urllib.request.Request(f"http://127.0.0.1:{port}/metadata")
            with urllib.request.urlopen(req) as response:
                meta = json.loads(response.read())
            
            sectors = meta.get("sectors", [])
            print(f"  >> Metadata sectors count: {len(sectors)}")
            
            # Should have 2: 1 physical sector + 1 virtual airport sector
            assert len(sectors) == 2, f"Expected 2 sectors in responsibility, got {len(sectors)}"
            print("  [OK] Story 2 & 3: Partial FIR and Airport responsibility confirmed.")
            
            for s in sectors:
                assert s["declared_capacity_per_hour"] == baseline_cap, f"Expected capacity {baseline_cap}, got {s['declared_capacity_per_hour']}"
            print(f"  [OK] Story 4: Baseline capacity {baseline_cap} applied to all areas.")
            
            # Story 5: FMP Graph display
            page.click("button[data-target='tab-flow']", force=True)
            page.wait_for_selector("#tab-flow.active", timeout=10000)
            
            # Check chart capacity data (the green dashed line) via wait_for_function
            print("  >> Waiting for capacity 55 to appear in FMP state...")
            page.wait_for_function("window.currentSectorCapacity === 55", timeout=20000)
            print("  [OK] FMP state updated with capacity 55.")
            
            print("  >> Waiting for capacity 55 to appear on FMP Graph...")
            page.wait_for_function("""() => {
                if(!window.demandChart || !window.demandChart.data || !window.demandChart.data.datasets) return false;
                const capDataset = window.demandChart.data.datasets.find(d => d.label === 'Sector Capacity');
                return capDataset && capDataset.data && capDataset.data.length > 0 && capDataset.data.some(v => v === 55);
            }""", timeout=20000)
            print("  [OK] Story 5: FMP Graph correctly displays capacity.")
            
            print("\nSUCCESS: All 5 Airspace Configuration User Stories Verified.")
            browser.close()
            return True

    except Exception as e:
        print(f"ERROR: UI Test failed: {e}")
        # Capture screenshot on failure
        try:
            page.screenshot(path=os.path.join(BASE_DIR, "test_output", "story_test_error.png"))
        except: pass
        return False
    finally:
        print("Cleaning up...")
        for p in processes: p.terminate()
        for l in logs: l.close()

if __name__ == "__main__":
    success = test_airspace_config_stories()
    sys.exit(0 if success else 1)
