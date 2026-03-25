"""
UI Test for API Key Authentication

This test verifies that:
1. The API key is properly injected into the HTML by the server
2. Authenticated requests to protected endpoints succeed with the API key
3. Requests without the API key are rejected

Prerequisites:
- Services should be running (use start_demo.ps1 to start them)
- DDFN_API_KEY environment variable should be set
"""

import os
import sys
import time
import urllib.request
import urllib.error
import json

# Ensure playwright is installed for this script to run
try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    print("ERROR: playwright is not installed.")
    print("Please install it using: pip install playwright pytest-playwright")
    print("And then install browsers using: playwright install")
    sys.exit(1)

# Configuration
FMP_URL = "http://127.0.0.1:8010"  # FMP node URL from start_demo.ps1
TEST_API_KEY = os.environ.get("DDFN_API_KEY", "demo-api-key-12345")


def wait_for_server(url, timeout=10):
    """Wait for a server to become available."""
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


def test_api_key_injection():
    """Test that API key is properly injected into the HTML."""
    print("=" * 60)
    print("TEST: API Key Authentication")
    print("=" * 60)

    # Check if FMP service is running
    print(f"\nChecking if FMP service is running at {FMP_URL}...")
    if not wait_for_server(FMP_URL, timeout=5):
        print(f"ERROR: FMP service is not running at {FMP_URL}")
        print(r"Please start the services using: .\start_demo.ps1")
        sys.exit(1)

    print("FMP Dashboard is up. Running API key tests...")

    test_failed = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 900})

            # --- Test 1: Verify API Key is Injected ---
            print("\nTest 1: Verify API Key Injection...")
            page.goto(FMP_URL, wait_until="domcontentloaded")
            expect(page).to_have_title("DDFN V2 | Advanced FMP Terminal")

            # Wait for JS to initialize
            page.wait_for_timeout(1000)

            # Check that API_KEY is defined and not null/empty
            api_key = page.evaluate("() => window.API_KEY")

            if api_key is None:
                print("  [FAIL] API_KEY is null - not injected by server")
                test_failed = True
            elif len(api_key) == 0:
                print("  [FAIL] API_KEY is empty string")
                test_failed = True
            else:
                print(f"  [PASS] API Key is injected (length: {len(api_key)})")

            # --- Test 2: Verify Authenticated Request Succeeds ---
            print("\nTest 2: Verify Authenticated Request Succeeds...")

            aixm_path = "AIXM/BD_2025-09-30_400005921419525.xml"
            test_payload = json.dumps({
                "file_path": aixm_path,
                "fir_id": "LCCC",
                "window_size": 60,
                "config_name": "API_KEY_TEST"
            }).encode('utf-8')

            # Request WITH API key should succeed
            req_with_key = urllib.request.Request(
                f"{FMP_URL}/api/setup/configure",
                data=test_payload,
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': api_key
                },
                method='POST'
            )

            try:
                with urllib.request.urlopen(req_with_key, timeout=10) as response:
                    response_data = json.loads(response.read().decode('utf-8'))
                    if response_data.get('status') == 'success':
                        print("  [PASS] Authenticated request succeeded")
                    else:
                        print(f"  [FAIL] Request returned unexpected status: {response_data}")
                        test_failed = True
            except urllib.error.HTTPError as e:
                print(f"  [FAIL] Authenticated request failed with HTTP {e.code}")
                test_failed = True
            except Exception as e:
                print(f"  [FAIL] Authenticated request failed: {e}")
                test_failed = True

            # --- Test 3: Verify Unauthenticated Request Fails ---
            print("\nTest 3: Verify Unauthenticated Request Fails...")

            # Request WITHOUT API key should fail with 401/403
            req_without_key = urllib.request.Request(
                f"{FMP_URL}/api/setup/configure",
                data=test_payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            auth_rejected = False
            try:
                with urllib.request.urlopen(req_without_key, timeout=10) as response:
                    print("  [FAIL] Unauthenticated request succeeded (should have been rejected)")
                    test_failed = True
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    print(f"  [PASS] Unauthenticated request correctly rejected (HTTP {e.code})")
                    auth_rejected = True
                else:
                    print(f"  [FAIL] Unexpected HTTP error: {e.code}")
                    test_failed = True
            except Exception as e:
                print(f"  [FAIL] Unexpected error: {e}")
                test_failed = True

            browser.close()

    except Exception as e:
        print(f"\nTest suite encountered an unhandled error: {e}")
        test_failed = True

    finally:
        print("\n" + "=" * 60)
        if test_failed:
            print("API Key Authentication Test: FAILED")
            sys.exit(1)
        else:
            print("API Key Authentication Test: PASSED")
            sys.exit(0)


if __name__ == "__main__":
    test_api_key_injection()
