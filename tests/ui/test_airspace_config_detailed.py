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
    log_file = open(os.path.join(BASE_DIR, "test_output", f"ui_test_detailed_{name.replace('/', '_').lower()}.log"), "w")
    
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

def test_airspace_config_detailed():
    print("Starting Detailed Airspace Configuration UI Verification...")
    os.makedirs(os.path.join(BASE_DIR, "test_output"), exist_ok=True)
    processes = []
    logs = []
    
    api_key = "ui-detailed-test-key"
    env_vars = {"DDFN_API_KEY": api_key}
    
    # Cleanup
    cfg_dir = os.path.join(BASE_DIR, "data", "node_configs")
    for f in ["FMP_DETAILED_TEST_DDFN_NODE.json", "FMP_DETAILED_TEST_DDFN_NODE_saved.json", "DETAILED_VERIFY_CONFIG.json"]:
        p = os.path.join(cfg_dir, f)
        if os.path.exists(p): os.remove(p)

    try:
        # Start Broker
        p, log = start_process("ddfn_v2.core.broker", "Broker", env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        time.sleep(2)
        
        # Start FMP Service
        port = "8098"
        p, log = start_process("ddfn_v2.services.fmp_service", "FMP_DETAILED_TEST", ["--port", port, "--node_id", "FMP_DETAILED_TEST"], env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        
        if not wait_for_server(f"http://127.0.0.1:{port}/health"):
            print(f"ERROR: FMP Service failed to start on port {port}")
            return False

        with sync_playwright() as p_play:
            browser = p_play.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            
            print("Step 1: Setup and Navigation")
            page.goto(f"http://127.0.0.1:{port}")
            page.evaluate(f"k => window.localStorage.setItem('ddfn_api_key', k)", api_key)
            page.reload()
            
            # Remove wizard
            page.evaluate("() => { const w = document.getElementById('setup-wizard-modal'); if(w) w.remove(); document.querySelectorAll('.modal-backdrop').forEach(b => b.remove()); }")
            page.click("button[data-target='tab-config']", force=True)
            
            print("Step 2: AIXM Loading & FIR Selection")
            aixm_path = os.path.join(BASE_DIR, "AIXM", "BD_2025-09-30_400005921419525.xml")
            page.fill("#config-aixm-path", aixm_path)
            page.click("#btn-load-aixm")
            
            page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=15000)
            page.select_option("#config-fir-select", "LCCC")
            
            # Wait for content
            page.wait_for_selector(".sector-config-item", timeout=10000)
            page.wait_for_selector(".airport-config-check", timeout=10000)
            page.screenshot(path=os.path.join(BASE_DIR, "test_output", "success_1_aixm_loaded.png"))
            
            print("Step 3: Verification of 'Select All' UI Elements")
            # Verify Sectors Select All (might be unchecked initially depending on current responsibility)
            page.check("#check-all-sectors")
            sector_checks = page.locator(".sector-config-check")
            for i in range(sector_checks.count()):
                expect(sector_checks.nth(i)).to_be_checked()
            
            page.uncheck("#check-all-sectors")
            for i in range(sector_checks.count()):
                expect(sector_checks.nth(i)).not_to_be_checked()
            
            page.screenshot(path=os.path.join(BASE_DIR, "test_output", "success_2_unselect_all.png"))
            
            # Verify Airports Select All
            expect(page.locator("#check-all-airports")).not_to_be_checked()
            page.check("#check-all-airports")
            airport_checks = page.locator(".airport-config-check")
            for i in range(airport_checks.count()):
                expect(airport_checks.nth(i)).to_be_checked()
            page.uncheck("#check-all-airports")

            print("Step 4: Customizing Sector (FL Overrides)")
            # Sector 0: LCCC (assumed first)
            # Find the first physical sector
            page.locator(".sector-config-check").nth(0).check()
            first_item = page.locator(".sector-config-item").nth(1) # nth(0) is the header
            
            min_fl_input = first_item.locator(".fl-min-input")
            max_fl_input = first_item.locator(".fl-max-input")
            
            new_min = 150
            new_max = 450
            min_fl_input.fill(str(new_min))
            min_fl_input.press("Enter") # Trigger change event
            max_fl_input.fill(str(new_max))
            max_fl_input.press("Enter")
            
            # Verify the data attributes on the checkbox updated (it's how app.js tracks it before save)
            checkbox = first_item.locator(".sector-config-check")
            attr_min = checkbox.get_attribute("data-fl-lower")
            attr_max = checkbox.get_attribute("data-fl-upper")
            assert attr_min == str(new_min), f"Expected data-fl-lower {new_min}, got {attr_min}"
            assert attr_max == str(new_max), f"Expected data-fl-upper {new_max}, got {attr_max}"
            print(f"  [OK] FL Overrides updated: {new_min}-{new_max}")
            page.screenshot(path=os.path.join(BASE_DIR, "test_output", "success_3_fl_overrides.png"))

            print("Step 5: Baseline Capacity & Config Name")
            page.fill("#config-baseline-capacity", "88")
            page.fill("#config-node-name", "DETAILED_VERIFY_CONFIG")
            
            print("Step 6: Saving and Applying")
            page.click("#btn-save-airspace-config")
            time.sleep(3) # Wait for reload
            page.wait_for_selector("#tab-overview.active", timeout=15000)
            page.screenshot(path=os.path.join(BASE_DIR, "test_output", "success_4_flow_graph.png"))

            print("Step 7: Final Verification (Persistence)")
            # Check metadata
            req = urllib.request.Request(f"http://127.0.0.1:{port}/metadata")
            with urllib.request.urlopen(req) as response:
                meta = json.loads(response.read())
            
            sectors = meta.get("sectors", [])
            # We unchecked all, then checked 1 sector. Airports were unchecked.
            assert len(sectors) == 1, f"Expected 1 sector, got {len(sectors)}"
            s = sectors[0]
            assert s["declared_capacity_per_hour"] == 88, f"Expected capacity 88, got {s['declared_capacity_per_hour']}"
            assert s["fl_lower"] == new_min, f"Expected FL lower {new_min}, got {s['fl_lower']}"
            assert s["fl_upper"] == new_max, f"Expected FL upper {new_max}, got {s['fl_upper']}"
            
            print("  [OK] Backend metadata persisted correctly.")

            print("Step 8: UI Persistence Verification")
            page.click("button[data-target='tab-config']", force=True)
            
            # Verify fields are pre-filled
            expect(page.locator("#config-aixm-path")).to_have_value(aixm_path)
            expect(page.locator("#config-baseline-capacity")).to_have_value("88")
            
            # Wait for FIR selection and rendering
            page.wait_for_function("() => document.getElementById('config-fir-select').value === 'LCCC'", timeout=20000)
            page.wait_for_selector(".sector-config-check", timeout=15000)
            
            # Re-locate the first item
            persisted_item = page.locator(".sector-config-item").nth(1)
            persisted_check = persisted_item.locator(".sector-config-check")
            
            expect(persisted_check).to_be_checked()
            assert persisted_check.get_attribute("value") == s["sector_id"]
            
            # Verify FL overrides are restored in the inputs
            expect(persisted_item.locator(".fl-min-input")).to_have_value(str(new_min))
            expect(persisted_item.locator(".fl-max-input")).to_have_value(str(new_max))
            
            print("  [OK] UI state restored correctly from persistence.")
            print("\nSUCCESS: Detailed UI Verification Completed.")
            browser.close()
            return True

    except Exception as e:
        print(f"ERROR: Detailed UI Test failed: {e}")
        try: page.screenshot(path=os.path.join(BASE_DIR, "test_output", "detailed_verify_error.png"))
        except: pass
        return False
    finally:
        for p in processes: p.terminate()
        for l in logs: l.close()

if __name__ == "__main__":
    success = test_airspace_config_detailed()
    sys.exit(0 if success else 1)
