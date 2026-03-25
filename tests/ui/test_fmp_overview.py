import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import json
from playwright.sync_api import sync_playwright, expect

# Ensure playwright is installed
try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    print("ERROR: playwright is not installed.")
    sys.exit(1)

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

def run_fmp_overview_test():
    print("Starting FMP Overview UI Verification...")
    os.makedirs(os.path.join(BASE_DIR, "test_output"), exist_ok=True)
    processes = []
    logs = []
    
    # Set a fixed API key for testing
    api_key = "ui-test-key"
    env_vars = {"DDFN_API_KEY": api_key}
    
    try:
        # Start Broker
        p, log = start_process("ddfn_v2.core.broker", "Broker", env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        time.sleep(2)
        
        # Start FMP Service on a test port
        port = "8099"
        p, log = start_process("ddfn_v2.services.fmp_service", "FMP_TEST", ["--port", port, "--node_id", "FMP_UI_TEST"], env_vars=env_vars)
        processes.append(p)
        logs.append(log)
        
        if not wait_for_server(f"http://127.0.0.1:{port}/health"):
            print(f"ERROR: FMP Service failed to start on port {port}")
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            
            # 1. Inject API Key into LocalStorage
            page.goto(f"http://127.0.0.1:{port}")
            page.evaluate(f"k => window.localStorage.setItem('ddfn_api_key', k)", api_key)
            page.reload()
            
            # 1.5 Bypass Setup Wizard and any backdrop robustly
            page.evaluate("""() => { 
                const wizard = document.getElementById('setup-wizard-modal'); 
                if(wizard) wizard.remove();
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
            }""")
            
            print("Step 1: Navigating to Airspace Config...")
            page.click("button[data-target='tab-config']", force=True)
            
            print("Step 2: Loading AIXM file...")
            aixm_path = os.path.join(BASE_DIR, "uploads", "BD_2025-09-30_400005921419525.xml")
            if not os.path.exists(aixm_path):
                aixm_path = os.path.join(BASE_DIR, "data", "BD_2025-09-30_400005921419525.xml")
                
            page.fill("#config-aixm-path", aixm_path)
            page.click("#btn-load-aixm", force=True)
            
            # Wait for FIR dropdown to have LCCC option
            print("  >> Waiting for LCCC option...")
            page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=15000)
            
            # Select LCCC
            print("  >> Selecting LCCC FIR...")
            page.evaluate("() => { const sel = document.getElementById('config-fir-select'); sel.value = 'LCCC'; sel.dispatchEvent(new Event('change')); }")
            
            # Wait for sectors
            print("  >> Waiting for sectors to populate...")
            page.wait_for_selector(".sector-config-item", timeout=10000)
            
            # Select all sectors
            print("  >> Clicking 'Select All' sectors...")
            page.click("#btn-select-all-sectors", force=True)
            
            print("Step 3: Applying Configuration...")
            page.click("#btn-save-airspace-config", force=True)
            
            # Wait for redirection
            print("  >> Waiting for redirection to Overview...")
            page.wait_for_selector("#tab-overview.active", timeout=15000)
            print("  [OK] Successfully applied config and moved to Overview.")
            
            # 4. Verify Overview UI Components
            print("Step 4: Verifying Overview Components...")
            
            # Use ID for badge verification
            print("  >> Verifying sector count badge...")
            badge = page.locator("#sector-count-badge")
            expect(badge).to_contain_text("17 Sectors", timeout=10000)
            print("  [OK] Sector count badge is correct.")
            
            # Check for Leaflet map initialization
            print("  >> Verifying Leaflet map...")
            map_container = page.locator("#overview-map-container .leaflet-container")
            expect(map_container).to_be_visible(timeout=5000)
            print("  [OK] Leaflet map is initialized and visible.")
            
            # Check for sector cards
            print("  >> Verifying sector cards...")
            page.wait_for_selector(".sector-card", timeout=10000)
            count = page.locator(".sector-card").count()
            assert count > 0, "No sector cards found in Overview tab"
            print(f"  [OK] Found {count} sector cards in Overview.")
            
            # Capture verification screenshot
            screenshot_path = os.path.join(BASE_DIR, "test_output", "fmp_overview_verification_final.png")
            page.screenshot(path=screenshot_path)
            print(f"  [OK] Verification screenshot saved to {screenshot_path}.")
            
            browser.close()
            return True

    except Exception as e:
        print(f"UI Test encountered error: {e}")
        # Capture error screenshot
        try:
            error_path = os.path.join(BASE_DIR, "test_output", "ui_test_error_final.png")
            page.screenshot(path=error_path)
            print(f"  [OK] Error screenshot saved to {error_path}.")
        except:
            pass
        return False
    finally:
        print("Cleaning up processes...")
        for p in processes:
            p.terminate()
        for l in logs:
            l.close()

if __name__ == "__main__":
    success = run_fmp_overview_test()
    sys.exit(0 if success else 1)
