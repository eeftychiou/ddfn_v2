
import os
import sys

# Add current directory to path
sys.path.append(os.path.abspath("ddfn_v2"))

from airspace import load_from_aixm, WAYPOINTS, SECTORS

def main():
    aixm_file = "ddfn_v2/AIXM/BD_2025-09-30_400005921419525.xml"
    if not os.path.exists(aixm_file):
        print(f"Error: AIXM file not found at {aixm_file}")
        return

    print(f"Loading AIXM file: {aixm_file}")
    load_from_aixm(aixm_file)

    print("\n--- Verification Results ---")
    print(f"Total Sectors: {len(SECTORS)}")
    print(f"Total Waypoints/Airports: {len(WAYPOINTS)}")

    # Check for some expected content
    # In Nicosia FIR (LCCC), we expect some waypoints like GIKAS, LCA, etc.
    found_gikas = "GIKAS" in WAYPOINTS
    found_lclk = "LCLK" in WAYPOINTS # Airport
    
    if found_gikas:
        wp = WAYPOINTS["GIKAS"]
        print(f"Found GIKAS: Lat={wp.lat}, Lon={wp.lon}, Type={wp.type}")
    else:
        print("GIKAS not found in WAYPOINTS")

    if found_lclk:
        ap = WAYPOINTS["LCLK"]
        print(f"Found LCLK (Airport): Lat={ap.lat}, Lon={ap.lon}, Type={ap.type}")
    else:
        print("LCLK (Airport) not found in WAYPOINTS")

    # Check for sector integration
    found_lccc = any(sid.startswith("LCCC") for sid in SECTORS)
    print(f"LCCC Sectors Found: {found_lccc}")

    if found_gikas and found_lclk and found_lccc:
        print("\nSUCCESS: AIXM data integration verified!")
    else:
        print("\nFAILURE: Some expected data was missing.")

if __name__ == "__main__":
    main()
