import pytest
import os
import sys
import requests
import subprocess
import time
import shutil
import json
import socket

# Use a separate config dir for tests to avoid mess
TEST_CONFIG_DIR = os.path.join("test_output", "node_configs")

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    # Clear any stale node_configs that might interfere
    if os.path.exists("node_configs"):
        test_files = [f for f in os.listdir("node_configs") if f.startswith("TEST_FMP")]
        for f in test_files:
            try: os.remove(os.path.join("node_configs", f))
            except: pass
            
    if os.path.exists(TEST_CONFIG_DIR):
        shutil.rmtree(TEST_CONFIG_DIR)
    os.makedirs(TEST_CONFIG_DIR)
    yield
    # Cleanup after all tests in module
    if os.path.exists(TEST_CONFIG_DIR):
        shutil.rmtree(TEST_CONFIG_DIR)

@pytest.fixture(scope="module")
def broker_server():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    proc = subprocess.Popen(
        [sys.executable, "-m", "ddfn_v2.core.broker"],
        env=env,
        cwd=os.getcwd()
    )
    # Wait for broker
    time.sleep(3)
    yield proc
    proc.terminate()
    try: proc.wait(timeout=5)
    except: proc.kill()

@pytest.fixture(scope="function")
def fmp_server(broker_server):
    node_id = f"TEST_FMP_{int(time.time())}"
    port = get_free_port()
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    env["DDFN_CONFIG_DIR"] = TEST_CONFIG_DIR
    env["DDFN_API_KEY"] = "fmp-config-flow-test-key"
    
    os.makedirs(os.path.join("test_output", "logs"), exist_ok=True)
    log_path = os.path.join("test_output", "logs", f"server_{node_id}.log")
    log_file = open(log_path, "w", buffering=1)
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "ddfn_v2.services.fmp_service", "--node_id", node_id, "--port", str(port)],
        env=env,
        cwd=os.getcwd(),
        stdout=log_file,
        stderr=log_file,
        text=True
    )
    
    # Wait for startup
    max_retries = 30
    url = f"http://127.0.0.1:{port}/api/setup/status"
    for i in range(max_retries):
        try:
            resp = requests.get(url, timeout=1)
            if resp.status_code == 200:
                break
        except Exception as e:
            pass
        time.sleep(1)
    else:
        proc.terminate()
        log_file.close()
        with open(log_path, "r") as f:
            print(f"SERVER LOGS:\n{f.read()}")
        pytest.fail(f"FMP Server failed to start on port {port}")
        
    yield {"node_id": node_id, "port": port, "base_url": f"http://127.0.0.1:{port}", "proc": proc, "api_key": "fmp-config-flow-test-key"}
    
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_file.close()
    try:
        if os.path.exists(log_path):
            os.remove(log_path)
    except PermissionError:
        pass

def test_unconfigured_startup_and_flow(fmp_server):
    base_url = fmp_server["base_url"]
    node_id = fmp_server["node_id"]
    
    # 1. Assert node starts UNCONFIGURED
    resp = requests.get(f"{base_url}/api/setup/status")
    data = resp.json()
    assert data["is_configured"] == False, f"Expected node {node_id} to be unconfigured on first launch"
    
    # 2. Configure via API
    aixm_path = os.path.abspath("AIXM/BD_2025-09-30_400005921419525.xml")
    fir_id = "LCCC"
    window_size = 45
    config_name = "LCCC_TDD_TEST"
    
    setup_payload = {
        "file_path": aixm_path,
        "fir_id": fir_id,
        "window_size": window_size,
        "config_name": config_name
    }
    
    headers = {"X-API-Key": fmp_server["api_key"]}
    resp = requests.post(f"{base_url}/api/setup/configure", json=setup_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    
    # 3. Verify configuration state
    resp = requests.get(f"{base_url}/api/setup/status")
    assert resp.json()["is_configured"] == True
    
    # 4. Verify local persistence
    node_id_full = f"{node_id}_DDFN_NODE"
    config_file = os.path.join(TEST_CONFIG_DIR, f"{node_id_full}.json")
    assert os.path.exists(config_file)
    with open(config_file, "r") as f:
        saved_data = json.load(f)
        assert saved_data["is_configured"] == True
        assert saved_data["measure_window"] == window_size
        assert saved_data["config_name"] == config_name
