import unittest
import requests
import subprocess
import time
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(BASE_DIR, "src")
TEST_CONFIG_DIR = os.path.join(BASE_DIR, "test_output", "metadata_test_configs")

class TestFMPMetadataIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start the FMP service on a random high port
        cls.port = 8122
        cls.api_key = "integration-test-key"
        env = os.environ.copy()
        env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
        env["DDFN_API_KEY"] = cls.api_key
        import shutil
        if os.path.exists(TEST_CONFIG_DIR):
            shutil.rmtree(TEST_CONFIG_DIR)
        os.makedirs(TEST_CONFIG_DIR, exist_ok=True)
        env["DDFN_CONFIG_DIR"] = TEST_CONFIG_DIR
        
        cls.proc = subprocess.Popen(
            [sys.executable, "-m", "ddfn_v2.services.fmp_service", "--port", str(cls.port), "--node_id", "TEST_INT_NODE"],
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to start
        start = time.time()
        while time.time() - start < 15:
            try:
                resp = requests.get(f"http://127.0.0.1:{cls.port}/health")
                if resp.status_code == 200:
                    break
            except:
                pass
            time.sleep(1)
        else:
            cls.proc.terminate()
            raise RuntimeError("FMP Service failed to start for integration test")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        import shutil
        if os.path.exists(TEST_CONFIG_DIR):
            shutil.rmtree(TEST_CONFIG_DIR)

    def test_metadata_contains_geometry_after_config(self):
        # 1. Initially metadata should be empty or unconfigured
        headers = {"X-API-Key": self.api_key}
        resp = requests.get(f"http://127.0.0.1:{self.port}/metadata", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data.get("sectors", [])), 0)
        
        # 2. Apply a setup configuration
        aixm_path = os.path.join(BASE_DIR, "uploads", "BD_2025-09-30_400005921419525.xml")
        if not os.path.exists(aixm_path):
            aixm_path = os.path.join(BASE_DIR, "data", "BD_2025-09-30_400005921419525.xml")
            
        config_payload = {
            "file_path": aixm_path,
            "fir_id": "LCCC",
            "window_size": 60,
            "config_name": "TEST_NODE"
        }
        
        headers = {"X-API-Key": self.api_key}
        apply_resp = requests.post(
            f"http://127.0.0.1:{self.port}/api/setup/configure",
            json=config_payload,
            headers=headers
        )
        self.assertEqual(apply_resp.status_code, 200)
        
        # 3. Verify metadata now has the sectors and their polygons
        headers = {"X-API-Key": self.api_key}
        meta_resp = requests.get(f"http://127.0.0.1:{self.port}/metadata", headers=headers)
        self.assertEqual(meta_resp.status_code, 200)
        meta_data = meta_resp.json()
        
        sectors = meta_data.get("sectors", [])
        self.assertGreater(len(sectors), 0)
        
        # Check that polygons are present in sectors
        polygons_found = 0
        for sector in sectors:
            if "polygon" in sector and isinstance(sector["polygon"], list) and len(sector["polygon"]) > 0:
                polygons_found += 1
        
        self.assertGreater(polygons_found, 0, "No polygons found in metadata sectors")
        print(f"Integration Test: Found {polygons_found} sectors with polygon data.")

if __name__ == "__main__":
    unittest.main()
