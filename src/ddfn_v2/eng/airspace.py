"""
airspace.py — DDFN V2 Airspace Structure Definitions
=====================================================
Defines simplified airspace geometry for the prototype:
  - Waypoint database: real ICAO published lat/lon for key European fixes.
  - ATS route segments linking waypoints to simulate airways (DCT / named airways).
  - Sector polygon boundaries at simplified 2D lat/lon (ignoring FL bands for this prototype).
    In production these would be loaded from EUROCONTROL AIXM 5.1 XML files.

All coordinates are (lat, lon) in decimal degrees. WGS-84.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger("airspace")

# ---------------------------------------------------------------------------
# 1. Waypoint Database (ICAO published positions)
# ---------------------------------------------------------------------------

class Waypoint(BaseModel):
    ident: str              # ICAO 5-letter fix or 4-letter VOR/NDB
    lat: float              # decimal degrees N
    lon: float              # decimal degrees E (negative = W)
    name: str = ""
    type: str = "ENRT"      # ENRT, TERMINAL, APPROACH, etc.

# Key European en-route fixes — "real" published positions from EUROCONTROL AIRAC
WAYPOINTS: Dict[str, Waypoint] = {}

# ---------------------------------------------------------------------------
# 2. Airspace Sector Geometry
# ---------------------------------------------------------------------------

SECTORS: Dict[str, 'SectorGeometry'] = {}

# ---------------------------------------------------------------------------
# 3. Airways / Routes
# ---------------------------------------------------------------------------

AIRWAYS: Dict[str, List[str]] = {}

class SectorGeometry(BaseModel):
    """
    A simplified ATC sector defined as a 2D convex lat/lon polygon.
    In production: loaded from EUROCONTROL AIXM 5.1 as GML 3D volumes.
    FL bands are stored but not enforced in this prototype.
    """
    model_config = ConfigDict(populate_by_name=True)

    sector_id: str
    fir: str                        # Parent FIR (e.g. LFFF, EDDD)
    fl_lower: int                   # Lower flight level (e.g. 245)
    fl_upper: int                   # Upper flight level (e.g. 660)
    polygon: List[Tuple[float, float]]  # list of (lat, lon) vertices, CCW

# Key sector definitions — populated from AIXM
SECTORS: Dict[str, SectorGeometry] = {}


# ---------------------------------------------------------------------------
# 3. ATS route segments (Populated from AIXM)
# ---------------------------------------------------------------------------

AIRWAYS: Dict[str, List[str]] = {}

# ---------------------------------------------------------------------------
# 4. Airport -> sector entry mapping (Dynamically derived)
# ---------------------------------------------------------------------------
AIRPORT_SECTOR_ENTRY: Dict[str, str] = {}

# ---------------------------------------------------------------------------
# 5. Airport capacity defaults (AAR / ADR)
# ---------------------------------------------------------------------------
AIRPORT_DEFAULTS: Dict[str, Dict[str, int]] = {}

def derive_airport_sector_mapping():
    """
    Dynamically assign each airport to its containing sector using point-in-polygon logic.
    """
    global AIRPORT_SECTOR_ENTRY
    for ident, wpt in WAYPOINTS.items():
        if wpt.type == "AIRPORT":
            for s_id, sector in SECTORS.items():
                if is_point_in_polygon(wpt.lat, wpt.lon, sector.polygon):
                    AIRPORT_SECTOR_ENTRY[ident] = s_id
                    break

def is_point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if lat > min(p1x, p2x):
            if lat <= max(p1x, p2x):
                if lon <= max(p1y, p2y):
                    if p1x != p2x:
                        xints = (lat - p1x) * (p2y - p1y) / (p2x - p1x) + p1y
                    if p1y == p2y or lon <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def load_from_aixm(file_path: str):
    """Loads sectors, waypoints, and airports from an AIXM file and updates the global registries."""
    from ddfn_v2.util.aixm_tool import AIXMParser
    parser = AIXMParser(file_path)
    
    # 1. Load Sectors
    aixm_sectors = parser.extract_sectors()
    for s in aixm_sectors:
        SECTORS[s.sector_id] = SectorGeometry(
            sector_id=s.sector_id,
            fir=s.parent_fir,
            fl_lower=s.fl_lower,
            fl_upper=s.fl_upper,
            polygon=s.polygon
        )
    
    # 2. Load Waypoints
    aixm_waypoints = parser.extract_waypoints()
    for w in aixm_waypoints:
        WAYPOINTS[w.ident] = Waypoint(
            ident=w.ident,
            lat=w.lat,
            lon=w.lon,
            type=w.type
        )

    # 3. Load Airports
    aixm_airports = parser.extract_airports()
    for a in aixm_airports:
        # Register airport as a waypoint too
        WAYPOINTS[a.ident] = Waypoint(
            ident=a.ident,
            lat=a.lat,
            lon=a.lon,
            name=a.name,
            type="AIRPORT"
        )
        
    # 4. Load Airways
    aixm_routes = parser.extract_routes()
    for r in aixm_routes:
        r_name = r["route_name"]
        if r_name not in AIRWAYS:
            AIRWAYS[r_name] = []
        # Construct path if not present (simple segment-based approach)
        if r["start_id"] not in AIRWAYS[r_name]:
            AIRWAYS[r_name].append(r["start_id"])
        if r["end_id"] not in AIRWAYS[r_name]:
            AIRWAYS[r_name].append(r["end_id"])

    # 5. Finalize setup
    derive_airport_sector_mapping()
    
    if WAYPOINTS:
        first_wpt = next(iter(WAYPOINTS.values()))
        logger.info(f"Loaded {len(WAYPOINTS)} waypoints. Sample: {first_wpt.ident} {first_wpt.type}")
    if SECTORS:
        first_sec = next(iter(SECTORS.values()))
        logger.info(f"Loaded {len(SECTORS)} sectors. Sample: {first_sec.sector_id} in FIR {first_sec.fir}")
        
    logger.info(f"Loaded {len(aixm_sectors)} sectors, {len(aixm_waypoints)} waypoints, {len(aixm_airports)} airports, and {len(aixm_routes)} route segments from {file_path}")

def get_fir_sectors(fir_id: str) -> List[dict]:
    """Helper to return only sectors belonging to a specific FIR."""
    return [s.model_dump() for s in SECTORS.values() if s.fir == fir_id]

def get_sector_by_id(sector_id: str) -> Optional[dict]:
    """Helper to return a single sector by its ID."""
    s = SECTORS.get(sector_id)
    return s.model_dump() if s else None
