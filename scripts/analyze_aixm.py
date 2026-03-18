import xml.etree.ElementTree as ET
import json
import os
import sys

# Add current dir to path to import aixm_tool
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from aixm_tool import AIXMParser

def analyze_full_aixm(file_path):
    parser = AIXMParser(file_path)
    
    sectors = parser.extract_sectors()
    print(f"Found {len(sectors)} Sector elements.")
    firs = sorted(list(set(s.parent_fir for s in sectors)))
    print(f"Unique FIRs: {firs}")
    
    for s in sectors[:5]:
        print(f"  Sector: {s.sector_id} (FIR: {s.parent_fir})")
        
    airports = parser.extract_airports()
    print(f"Found {len(airports)} Airport elements.")
    for a in airports[:3]:
        print(f"  Airport: {a.ident} ({a.name})")

    waypoints = parser.extract_waypoints()
    print(f"Found {len(waypoints)} Waypoint elements.")

    routes = parser.extract_routes()
    print(f"Found {len(routes)} Route segments.")

if __name__ == "__main__":
    path = os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml")
    if not os.path.exists(path):
        print(f"File not found: {path}")
    else:
        analyze_full_aixm(path)
