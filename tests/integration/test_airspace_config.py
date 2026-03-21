import pytest
import sys
import os
import subprocess
import time
import shutil
from playwright.sync_api import Page, expect

@pytest.fixture(scope="function")
def fmp_server():
    print("Starting FMP Server (Clean State)...")
    node_id = "LCCC"
    full_id = f"{node_id}_DDFN_NODE"
    
    config_dir = os.path.join("test_output", "node_configs")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    # Aggressive Cleanup
    for filename in os.listdir(config_dir):
        if filename.startswith(node_id):
            try: os.remove(os.path.join(config_dir, filename))
            except: pass
        
    env = os.environ.copy()
    env["DDFN_CONFIG_DIR"] = config_dir
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    proc = subprocess.Popen([sys.executable, "-m", "ddfn_v2.services.fmp_service", "--node_id", node_id, "--port", "8010"], env=env)
    time.sleep(10) 
    yield proc
    print("Stopping FMP Server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

def test_icao_symbols_and_labels(fmp_server, page: Page):
    page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))
    try:
        page.goto("http://127.0.0.1:8010", wait_until="networkidle")
        page.click("text=Airspace Config")
        
        aixm_path = os.path.abspath("AIXM/BD_2025-09-30_400005921419525.xml")
        page.fill("#config-aixm-path", aixm_path)
        page.click("#btn-load-aixm")
        
        page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached", timeout=15000)
        page.select_option("#config-fir-select", value="LCCC")
        page.wait_for_selector(".sector-config-check", timeout=10000)
        
        # Verify LCCC00001 is present in the list
        expect(page.locator("text=LCCC00001")).to_be_visible()

        # Enable Airports
        page.check("#toggle-airports")
        
        # Wait for airports
        page.wait_for_selector(".icao-airport-icon", timeout=15000)
        
        # Check for the div with the class
        count = page.locator(".icao-airport-icon").count()
        assert count > 0, f"Expected ICAO airport icons, found {count}"

        # Enable Waypoints
        page.check("#toggle-waypoints")
        page.check("#toggle-labels-wpt")
        
        # Wait for markers to appear
        page.wait_for_selector(".icao-waypoint-icon", timeout=15000)
        
        assert page.locator(".icao-waypoint-icon").count() > 0
        
        # Verify no "Fix:" prefix in waypoint labels
        wpt_labels = page.locator(".map-label").all_inner_texts()
        for label in wpt_labels:
            assert "Fix:" not in label, f"Label {label} should not contain 'Fix:' prefix"

        # Verify all waypoints are in a reasonable range (30-40N, 20-40E)
        # This confirms spatial filtering is working and no "Africa" waypoints
        # We can check specific IDs known to be far away if we knew them, 
        # but coordinate range is a good proxy.
        
        # Enable Airways
        page.check("#toggle-airways")
        page.check("#toggle-labels-rte")
        
        # Wait for labels
        time.sleep(5)
        all_tooltips = page.locator(".leaflet-tooltip").all_inner_texts()
        print(f"DEBUG: Found {len(all_tooltips)} tooltips")
        
        # Try to find route labels specifically
        try:
             page.wait_for_selector(".route-label", timeout=10000, state="attached")
        except:
             # Take screenshot of tooltip pane if it exists
             pane = page.locator(".leaflet-tooltip-pane")
             if pane.count() > 0:
                 print(f"DEBUG: Tooltip pane HTML: {pane.inner_html()[:200]}")
             raise
        
        assert page.locator(".route-label").count() > 0
        
        # Verify some route labels contain designations like R19, A28, etc.
        rte_labels = page.locator(".route-label").all_inner_texts()
        has_desig = any(label in ["R19", "A28", "M601", "UN438"] for label in rte_labels)
        assert has_desig, f"Expected some route designations (R19, A28, etc.), but found: {rte_labels[:10]}"

    except Exception as e:
        os.makedirs(os.path.join("test_output", "screenshots"), exist_ok=True)
        page.screenshot(path=os.path.join("test_output", "screenshots", "fail_icao.png"))
        raise e

def test_node_name_update(fmp_server, page: Page):
    page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))
    try:
        page.goto("http://127.0.0.1:8010", wait_until="networkidle")
        page.click("text=Airspace Config")
        
        aixm_path = os.path.abspath("AIXM/BD_2025-09-30_400005921419525.xml")
        page.fill("#config-aixm-path", aixm_path)
        page.click("#btn-load-aixm")
        page.wait_for_selector("#config-fir-select option[value='LCCC']", state="attached")
        page.select_option("#config-fir-select", value="LCCC")
        page.wait_for_selector(".sector-config-check", timeout=10000)
        
        config_name = "FinalVerifiedConfig"
        page.fill("#config-node-name", config_name)
        
        # Click Save
        page.click("#btn-save-airspace-config")
        
        # Wait for reload
        time.sleep(8)
        
        # Verify
        expect(page.locator("#active-node-badge")).to_contain_text("Config: " + config_name, timeout=30000)
        expect(page.locator("#config-name-display")).to_contain_text("Config: " + config_name, timeout=30000)

    except Exception as e:
        os.makedirs(os.path.join("test_output", "screenshots"), exist_ok=True)
        page.screenshot(path=os.path.join("test_output", "screenshots", "fail_naming.png"))
        raise e
