"""
generate_real_schedule.py — Generate a large-scale flight schedule from AIXM data.
"""
import json
import random
import os
from aixm_tool import AIXMParser

def generate_schedule(aixm_path: str, output_path: str, num_flights: int = 200):
    if not os.path.exists(aixm_path):
        print(f"AIXM file not found: {aixm_path}")
        return

    parser = AIXMParser(aixm_path)
    airports = parser.extract_airports()
    
    if len(airports) < 2:
        print("Not enough airports found in AIXM to generate a schedule.")
        return

    # Filter for major airports (e.g. 4-letter codes starting with E, L)
    major_airports = [a for a in airports if a.ident.startswith(('E', 'L')) and len(a.ident) == 4]
    
    if len(major_airports) < 2:
        major_airports = airports # Fallback

    airlines = ["DLH", "BAW", "AFR", "RYR", "EZY", "IBE", "KLM", "SAS"]
    
    schedule = []
    for i in range(num_flights):
        airline = random.choice(airlines)
        f_num = random.randint(100, 9999)
        flight_id = f"{airline}{f_num}"
        
        origin = random.choice(major_airports)
        destination = random.choice(major_airports)
        while destination.ident == origin.ident:
            destination = random.choice(major_airports)
            
        # Mock route string (DCT between waypoints)
        # In a real system, we'd use a router, but for this prototype DCT is fine
        route_string = f"{origin.ident} DCT {destination.ident}"
        
        cruise_fl = random.choice([320, 340, 360, 380, 400])
        departure_offset = random.randint(-60, 180) # Spread relative to sim start
        
        schedule.append({
            "flight_id": flight_id,
            "origin": origin.ident,
            "destination": destination.ident,
            "route_string": route_string,
            "cruise_fl": cruise_fl,
            "departure_offset": departure_offset
        })

    with open(output_path, "w") as f:
        json.dump(schedule, f, indent=4)
    
    print(f"Generated {len(schedule)} flights and saved to {output_path}")

if __name__ == "__main__":
    AIXM_FILE = r"c:\Users\eftyc\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml"
    OUTPUT_FILE = r"c:\Users\eftyc\Antigravity\ddfn_v2\real_schedule.json"
    generate_schedule(AIXM_FILE, OUTPUT_FILE)
