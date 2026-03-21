import sys
import os

# Set up PYTHONPATH
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    print("Testing import: from ddfn_v2.eng.airspace import get_fir_sectors...")
    from ddfn_v2.eng.airspace import get_fir_sectors
    print("SUCCESS: Import worked!")
    
    print("Testing specific function that failed with 'No module named airspace'...")
    # The failed import was: from airspace import get_fir_sectors
    try:
        import airspace
        print("Wait, 'import airspace' worked? This shouldn't happen if it's not in path.")
    except ImportError:
        print("As expected, 'import airspace' failed (correctly).")

    print("\nVerifying the fix in fmp_service.py by checking the line content...")
    with open("src/ddfn_v2/services/fmp_service.py", "r") as f:
        content = f.read()
        if "from ddfn_v2.eng.airspace import get_fir_sectors as get_global_fir_sectors" in content:
            print("Verified: fmp_service.py has the correct import path.")
        else:
            print("FAILURE: fmp_service.py STILL HAS THE WRONG IMPORT!")

except Exception as e:
    print(f"CRASH: {e}")
