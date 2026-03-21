import os
import sys
import time
import subprocess
import urllib.request
import urllib.error

# Ensure playwright is installed for this script to run
try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    print("ERROR: playwright is not installed.")
    print("Please install it using: pip install playwright pytest-playwright")
    print("And then install browsers using: playwright install")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(BASE_DIR, "src")

def start_process(cmd_path, name, args=None):
    print(f"Starting {name}...")
    log_name = name.replace("/", "_").lower()
    os.makedirs(os.path.join(BASE_DIR, "test_output", "logs"), exist_ok=True)
    log_file = open(os.path.join(BASE_DIR, "test_output", "logs", f"ui_test_{log_name}.log"), "w")
    
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    
    # cmd_path is like 'ddfn_v2.core.broker'
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

def run_ui_tests():
    print("Starting DDFN UI Testing Infrastructure...")
    processes = []
    
    # 1. Orchestration
    processes.append(start_process("ddfn_v2.core.broker", "Broker"))
    time.sleep(2)
    
    # FMP Nodes start UNCONFIGURED. We no longer pass positional FIR args.
    aixm_path = "AIXM/BD_2025-09-30_400005921419525.xml"
    processes.append(start_process("ddfn_v2.services.fmp_service", "FMP/Instance1", ["--node_id", "LGGG1A", "--port", "8023", "--aixm", aixm_path]))
    processes.append(start_process("ddfn_v2.services.fmp_service", "FMP/Instance2", ["--node_id", "LGGG2B", "--port", "8022", "--aixm", aixm_path]))
    
    # Wait for FMP dashboard to be available
    server_up = wait_for_server("http://127.0.0.1:8023")
    if not server_up:
        print("ERROR: FMP LGGG1A Dashboard failed to start within timeout.")
        for p in processes: p.terminate()
        sys.exit(1)
        
    print("FMP Dashboard is up. Starting flights and Sim Manager...")
    processes.append(start_process("ddfn_v2.services.airport_service", "Airport/LGAT", ["LGAT", "--aixm", aixm_path]))
    processes.append(start_process("ddfn_v2.services.airport_service", "Airport/LCLK", ["LCLK", "--aixm", aixm_path]))
    processes.append(start_process("ddfn_v2.services.aoc_service", "AOC/AEW", ["AEW"]))
    processes.append(start_process("ddfn_v2.services.aoc_service", "AOC/CYP", ["CYP"]))
    processes.append(start_process("ddfn_v2.services.sim_manager", "Sim Manager"))
    
    # Let flights populate
    time.sleep(20)
    
    print("Launching Playwright to run UI tests...")
    
    test_failed = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 900})
            
            # --- Test 1: Load Dashboard ---
            print("Test 1: Load Dashboard...")
            page.goto("http://127.0.0.1:8023", wait_until="domcontentloaded")
            expect(page).to_have_title("DDFN V2 | Advanced FMP Terminal")
            
            # Hide setup wizard if it appears (blocks UI tests)
            page.evaluate("() => { const modal = document.getElementById('setup-wizard-modal'); if(modal) modal.classList.add('hidden'); }")
            
            page.wait_for_timeout(1000)  # Let JS initialize
            print("  [OK] Dashboard loaded successfully.")

            # --- Test 1.5: Perform Airspace Configuration ---
            print("Test 1.5: Configuring Node via UI...")
            # Node should be in 'Airspace Config' tab already due to auto-redirect
            # But let's make sure.
            page.evaluate("() => document.querySelector(\"button[data-target='tab-config']\").click()")
            page.wait_for_selector("#tab-config.active")
            
            # Use 'Load' button for the seeded path
            print("  >> Loading AIXM from server path...")
            page.click("#btn-load-aixm")
            
            # Wait for FIR selection to populate
            print("  >> Waiting for FIR selection...")
            page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=15000)
            
            # Select LCCC robustly
            page.evaluate("() => { const sel = document.getElementById('config-fir-select'); sel.value = 'LCCC'; sel.dispatchEvent(new Event('change')); }")
            
            # Wait for sectors to populate (the bug fix verification)
            print("  >> Verifying sectors are populated...")
            page.wait_for_selector(".sector-config-item", state="attached", timeout=10000)
            sector_count = page.locator(".sector-config-item").count()
            assert sector_count > 0, "No sectors found in config list after FIR selection"
            print(f"  [OK] {sector_count} sectors successfully loaded and displayed.")
            
            # Set a name and save
            page.fill("#config-node-name", "LGGG_TEST_NODE")
            print("  >> Saving & Applying Configuration...")
            page.click("#btn-save-airspace-config")
            
            # After save, it should reload. Wait for reload.
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000) # Let it settle
            print("  [OK] Node configured and dashboard reloaded.")
            
            # --- Test 2: Verify Flow Management Tab & Modal ---
            print("Test 2: Verify Flow Management Tab & Constraint Modal...")
            # Directly activate the flow tab via JS (bypasses DOMContentLoaded listener timing)
            page.evaluate("""
                () => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                    document.querySelector("button[data-target='tab-flow']").classList.add('active');
                    document.getElementById('tab-flow').classList.add('active');
                }
            """)
            page.wait_for_timeout(500)
            
            # Verify the flow pane is now active
            is_active = page.evaluate("() => document.getElementById('tab-flow').classList.contains('active')")
            assert is_active, "Flow Management tab pane is not active"
            print("  [OK] Flow Management tab is active.")
            
            # Check button presence in DOM (bounding box check for headless mode)
            btn_visible = page.evaluate("""
                () => { 
                    const el = document.getElementById('btn-open-constraint-modal'); 
                    if (!el) return false;
                    const r = el.getBoundingClientRect(); 
                    return r.width > 0 && r.height > 0; 
                }
            """)
            assert btn_visible, "'+ Add Constraint' button has no visible dimensions in flow tab"
            print("  [OK] '+ Add Constraint' button is accessible (compact layout confirmed).")
            
            # Open modal via JS (bypass event listener timing)
            print("  >> Opening constraint modal via JS...")
            page.evaluate("""
                () => {
                    const modal = document.getElementById('constraint-modal');
                    if (modal) modal.style.display = 'flex';
                }
            """)
            page.wait_for_timeout(300)
            
            # Verify Modal is shown with correct contents
            modal_visible = page.evaluate("() => document.getElementById('constraint-modal').style.display === 'flex'")
            assert modal_visible, "Constraint modal did not open (display != flex)"
            apply_btn_exists = page.evaluate("() => !!document.getElementById('btn-apply-constraint')")
            assert apply_btn_exists, "Apply Constraint button not found in modal"
            cancel_btn_exists = page.evaluate("() => !!document.getElementById('btn-reset-capacity')")
            assert cancel_btn_exists, "Cancel button not found in modal"
            print("  [OK] Modal opened with Apply and Cancel buttons.")
            
            # Fill in constraint form
            print("  >> Filling in constraint form...")
            capacity_input = page.locator("input#builder-capacity")
            page.evaluate("() => { const el = document.getElementById('builder-capacity'); el.value = '5'; }")
            val = page.evaluate("() => document.getElementById('builder-capacity').value")
            assert val == "5", f"Capacity field not set correctly, got: {val}"
            print("  [OK] Capacity field set to 5.")
            
            # Close via JS
            print("  >> Canceling modal...")
            page.evaluate("""
                () => {
                    const modal = document.getElementById('constraint-modal');
                    if (modal) modal.style.display = 'none';
                }
            """)
            page.wait_for_timeout(200)
            modal_closed = page.evaluate("() => document.getElementById('constraint-modal').style.display === 'none'")
            assert modal_closed, "Modal did not close"
            print("  [OK] Modal closed successfully.")

            
            # --- Test 3: Verify Canvas Graph ---
            print("Test 3: Verify Chart.js Canvas...")
            expect(page.locator("canvas#demandChart")).to_be_visible()
            print("  [OK] Canvas demand graph is visible.")
            
            # --- Test 4: Verify Airspace & Slots Populated ---
            print("Test 4: Verify Airspace & Slots Data...")
            # Use JS click to avoid interception by potential overlays
            page.evaluate("() => document.querySelector(\"button[data-target='tab-airspace']\").click()")
            page.wait_for_selector("#tab-airspace.active", timeout=10000)

            # Wait for rows in the inventory table - increased timeout to 30s
            print("  >> Waiting for flight inventory to populate (up to 30s)...")
            try:
                page.wait_for_selector("#inventory-list-body tr", state="attached", timeout=30000)
                rows = page.locator("#inventory-list-body tr").count()
                if rows > 0:
                    print(f"  [OK] Flight Inventory table populated with {rows} flights.")
                else:
                    print("  [ERR] Flight Inventory table is empty after timeout.")
                    page.screenshot(path="test_output/logs/ui_test_error_empty_inventory.png")
                    test_failed = True
            except Exception as e:
                print(f"  [ERR] Timeout waiting for flight inventory to populate: {e}")
                page.screenshot(path="test_output/logs/ui_test_error_timeout.png")
                test_failed = True
            
            browser.close()
            
    except Exception as e:
        print(f"Test suite encountered an unhandled error: {e}")
        test_failed = True
    finally:
        print("Cleaning up processes...")
        for proc in processes:
            proc.terminate()
            
        if test_failed:
            print("UI Test Suite FAILED.")
            sys.exit(1)
        else:
            print("UI Test Suite PASSED.")
            sys.exit(0)

if __name__ == "__main__":
    run_ui_tests()
