import sys
import os
import asyncio
import json

# Set up PYTHONPATH
sys.path.append(os.path.join(os.getcwd(), "src"))

async def test_api_setup():
    try:
        # We don't need to run the whole server, just import the function and try to call it
        # or mock the necessary parts.
        # However, the failure was at the 'from airspace import ...' line inside the function.
        
        from ddfn_v2.services.fmp_service import api_setup_configure
        
        # We need to mock 'req' (Request) and 'node'
        class MockNode:
            def __init__(self):
                self.logger = type('MockLogger', (), {'info': print, 'error': print, 'warning': print})
                self.sectors = []
                self._state_lock = asyncio.Lock()
                self.is_configured = False
            def save_local_config(self):
                pass

        class MockRequest:
            def __init__(self, data):
                self._data = data
            async def json(self):
                return self._data
        
        # We need to set the global 'node' in fmp_service module context
        import ddfn_v2.services.fmp_service as fmp_mod
        fmp_mod.node = MockNode()

        mock_data = {
            "file_path": "AIXM/BD_2025-09-30_400005921419525.xml",
            "fir_id": "LCCC",
            "window_size": 60
        }
        mock_req = MockRequest(mock_data)

        print("Calling api_setup_configure...")
        result = await fmp_mod.api_setup_configure(mock_req)
        print(f"Result: {result}")
        
        if result.get("status") == "success":
            print("SUCCESS: api_setup_configure worked!")
        else:
            print(f"FAILURE: api_setup_configure returned error: {result.get('message')}")

    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_setup())
