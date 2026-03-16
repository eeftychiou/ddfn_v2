"""
schedule.py — Centralized Flight Schedule for DDFN
==================================================
Provides a single source of truth for all flight plans in the simulation.
Used by FMPNodes, AirportNodes, and AOCNodes to ensure consistency.
"""

from typing import List, Tuple, Dict

# Flight Plan Format: (Flight ID, Origin, Destination, Route String, Cruise FL, Departure Offset Mins)
FLIGHT_SCHEDULE: List[Tuple[str, str, str, str, int, int]] = [
    # --- GERMANY (DLH) ---
    # Airborne / En-route
    ("DLH100", "EDDF", "LEMD", "PODIP KERAX LAMSO TRASN LUMEL OKRIB BRANE PAMPI SOSAL LEMD", 350, -30),
    ("DLH101", "EDDF", "LEMD", "ARPEG VESAN KORER NAKID OKRIB BRANE PAMPI LEMD", 350, -25),
    ("DLH102", "EDDF", "LEBL", "PODIP KERAX LAMSO BRALE DIJON KOVIN LEBL", 370, -20),
    ("DLH103", "EDDF", "LFMN", "ADMUT INBED NURMO KELIP AMENT LFMN", 390, -15),
    ("DLH104", "EDDF", "LFMN", "ROTAX ADMUT INBED AMENT LFMN", 370, -10),
    # Pre-departure
    ("DLH105", "EDDF", "LEMD", "PODIP KERAX LAMSO TRASN LUMEL LERGA PAMPI SOSAL LEMD", 350, +45),
    ("DLH106", "EDDF", "LEMD", "ARPEG VESAN KORER MOLUS DIJON BRANE PAMPI LEMD", 360, +55),
    ("DLH107", "EDDM", "LEMD", "OBK ADMUT INBED LUMEL LERGA PAMPI LEMD", 350, +60),
    ("DLH108", "EDDF", "LEBL", "PODIP LAMSO DIJON BRANE SOSAL LEBL", 370, +65),
    ("DLH109", "EDDB", "LEMD", "RASPU NOLGO ARPEG FFM VESAN MOLUS DIJON LEMD", 350, +70),
    ("DLH110", "EDDF", "LFPG", "PODIP KERAX VESAN RANUX LFPG", 280, +20),
    ("DLH111", "EDDM", "LFPG", "OBK WUR FFM PODIP KERAX VESAN LFPG", 310, +80),

    # --- UK (BAW) ---
    ("BAW200", "EGLL", "LEMD", "LAM DVR ZAGZO UMLAT KOTAP OKASI LERGA PAMPI SOSAL LEMD", 350, -15),
    ("BAW201", "EGLL", "LEMD", "LAM DVR VEDAM UMLAT BALAN OKASI LERGA LEMD", 360, -5),
    ("BAW202", "EGLL", "LEBL", "LAM BIG DVR ZAGZO UMLAT KOTAP LERGA LEBL", 370, +10),
    ("BAW203", "EGLL", "LFPG", "ADMAG MIMKU BALAN LFPG", 250, +15),
    ("BAW204", "EGCC", "LEMD", "ADMAG OCEAN LERGA PAMPI SOSAL LEMD", 350, +20),
    ("BAW205", "EGLL", "GCXO", "LAM DVR VEDAM UMLAT BALAN LERGA ERNAS GCXO", 370, +30),
    ("BAW206", "EGLL", "GCXO", "LAM DVR VEDAM ZAGZO KOTAP LERGA GCXO", 370, +40),
    ("BAW207", "EGLL", "LEMD", "BIG DVR VEDAM UMLAT OKASI LERGA LEMD", 360, +50),
    ("BAW208", "EGCC", "LEBL", "ADMAG OCEAN LERGA PAMPI LEBL", 340, +55),
    ("BAW209", "EGLL", "LFMN", "LAM BIG VEDAM ZAGZO UMLAT BALAN BRANE KOVIN LFMN", 380, +60),
    ("BAW210", "EGLL", "LEMD", "LAM DVR ZAGZO UMLAT KOTAP LERGA PAMPI LEMD", 250, +70), # RAD-INVALID (FL250 via DVR)

    # --- FRANCE (AFR) ---
    ("AFR300", "LFPG", "LEMD", "RANUX SBT MOLUS DIJON AMB LERGA PAMPI LEMD", 330, -10),
    ("AFR301", "LFPG", "LEBL", "RANUX SBT MOLUS DIJON AMB BRALE LEBL", 350, +10),
    ("AFR302", "LFMN", "EGLL", "AMENT KELIP NURMO INBED ROTAX FFM PODIP LAM DVR EGLL", 370, +20),
    ("AFR303", "LFPG", "EDDF", "RANUX VESAN KERAX PODIP FFM EDDF", 290, +30),
    ("AFR304", "LFMN", "EDDF", "AMENT KELIP NURMO INBED ROTAX FFM EDDF", 310, +45),
    ("AFR305", "LFPG", "LSZH", "RANUX SBT MOLUS DIJON LSZH", 250, +50),
    
    # --- GREECE (LGGG) ---
    ("AEW400", "LGAT", "LGRP", "KAVOS ROTAS LGRP", 330, -10),
    ("AEW401", "LGAT", "LGAV", "KAVOS LGAV", 280, +10),
    ("AEW402", "LGRP", "LGAT", "ROTAS KAVOS LGAT", 310, +20),

    # --- CYPRUS (LCCC) ---
    ("CYP400", "LCLK", "LGAV", "LCLK DCT LGAV", 340, -10),
    ("CYP401", "LCLK", "LGRP", "LCLK DCT LGRP", 320, +10),
    ("CYP402", "LCPH", "LGKR", "LCPH DCT LGKR", 360, +20),
    ("CYP403", "LCLK", "LLBG", "LCLK DCT LLBG", 280, +30),
    ("CYP404", "LCPH", "LTAI", "LCPH DCT LTAI", 300, +45),
]

def load_schedule_from_file(path: str):
    """Loads flight schedule from a JSON file."""
    global FLIGHT_SCHEDULE
    import json
    import os
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                # Convert list of dicts or list of tuples
                if data and isinstance(data[0], dict):
                    FLIGHT_SCHEDULE = [
                        (f["flight_id"], f["origin"], f["destination"], f["route_string"], f["cruise_fl"], f["departure_offset"])
                        for f in data
                    ]
                else:
                    FLIGHT_SCHEDULE = [tuple(f) for f in data]
                print(f"Loaded {len(FLIGHT_SCHEDULE)} flights from {path}")
        except Exception as e:
            print(f"Failed to load schedule from {path}: {e}")

def get_flights_for_origin(origin_icao: str) -> List[Tuple]:
    """Returns flights starting at the given airport."""
    return [f for f in FLIGHT_SCHEDULE if f[1] == origin_icao]

def get_flights_for_fir(fir_id: str) -> List[Tuple]:
    """
    Returns flights that should be managed by the given FIR node.
    In this prototype, we map origins to FIRs (ED=Germany, EG=UK, LF=France).
    """
    fir_prefix = fir_id[:2]
    return [f for f in FLIGHT_SCHEDULE if f[1].startswith(fir_prefix)]

def get_flights_for_airline(airline_code: str) -> List[Tuple]:
    """Returns flight metadata for a specific AOC."""
    return [f for f in FLIGHT_SCHEDULE if f[0].startswith(airline_code)]
