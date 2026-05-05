"""
trajectories.py — DDFN V2 4D Trajectory Engine
================================================
Replaces the PoC's hardcoded ETO values with real geometric computation:

  1.  FlightPlan  —  parses an ICAO-format route string into an ordered
                     sequence of waypoints (lat/lon).
  2.  TrajectorySolver  —  walks the waypoint sequence using haversine
                           great-circle distance + TAS to accumulate time,
                           then tests each sector polygon for intersection
                           using a ray-casting algorithm to produce ETOs.
  3.  FlightTrajectory  —  enriched result object with sector ETOs.
  4.  FlightDataProcessingSystem  —  the per-node FDPS query engine (same
                                     interface as PoC but now backed by real
                                     geometry).
"""

from __future__ import annotations
import math
from typing import List, Dict, Optional, Tuple
import ddfn_v2.eng.airspace as airspace_mod
from ddfn_v2.eng.airspace import WAYPOINTS, SECTORS, AIRWAYS, Waypoint, SectorGeometry
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("trajectories")

# ---------------------------------------------------------------------------
# 1. Data structures
# ---------------------------------------------------------------------------

class SectorEntry(BaseModel):
    """A flight crossing a sector at a computed ETO."""
    sector_id: str
    estimated_time_over: datetime
    entry_lat: float = 0.0                  # Approximate entry lat
    entry_lon: float = 0.0                  # Approximate entry lon
    exit_lat:  float = 0.0
    exit_lon:  float = 0.0

class FlightTrajectory(BaseModel):
    """
    A 4D flight trajectory resolved from a flight plan.
    The 'route' list contains all sector ETOs in order of crossing.
    """
    flight_id: str
    origin: str
    destination: str
    departure_time: datetime
    cruise_fl: int                          # Filed cruise flight level (e.g. 350)
    tas_kt: float                           # True Airspeed (knots). Derived from FL.
    route_string: str = ""                  # Original ICAO route string
    waypoints: List[Tuple[float, float]] = Field(default_factory=list) # resolved (lat, lon)
    route: List[SectorEntry] = Field(default_factory=list)             # sector crossings
    entry_fix: Optional[str] = None
    exit_fix: Optional[str] = None
    exit_time: Optional[datetime] = None
    remaining_route: str = "" # The rest of the ICAO string for handover
    rad_violation: Optional[str] = None

    @classmethod
    def from_flight_plan(
        cls,
        flight_id: str,
        origin: str,
        destination: str,
        departure_time: datetime,
        cruise_fl: int,
        route_string: str,
        waypoint_db: Optional[Dict[str, Waypoint]] = None,
        sector_db: Optional[Dict[str, SectorGeometry]] = None
    ) -> "FlightTrajectory":
        """
        Factory — parse a simplified ICAO route string and compute the full 4D trajectory.
        route_string: space-separated waypoints/airways (e.g. "DCT PODIP UL607 LAMSO DCT LFPG")
        """
        tas = _fl_to_tas(cruise_fl)
        flt = cls(
            flight_id=flight_id,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            cruise_fl=cruise_fl,
            tas_kt=tas,
            route_string=route_string
        )
        db = waypoint_db if waypoint_db is not None else WAYPOINTS
        wpts, exit_idx, rem_route = _parse_route(origin, route_string, destination, db)
        flt.waypoints = [(wp.lat, wp.lon) for wp in wpts]
        flt.remaining_route = rem_route
        if wpts:
            flt.entry_fix = wpts[0].ident
        
        # Default altitude profile is just cruise_fl for all waypoints
        alts = [cruise_fl] * len(flt.waypoints)
        
        crossings, exit_time = TrajectorySolver.compute_sector_etos(flt.waypoints, departure_time, tas, sector_db=sector_db, altitudes=alts)
        flt.route = crossings
        flt.exit_time = exit_time
        if exit_idx is not None and 0 <= exit_idx < len(wpts):
            flt.exit_fix = wpts[exit_idx].ident
        return flt


# ---------------------------------------------------------------------------
# 2. Physics helpers
# ---------------------------------------------------------------------------

def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    R = 3440.065  # Earth radius in nm
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    return 2 * R * math.asin(math.sqrt(a))

def _fl_to_tas(fl: int) -> float:
    """
    Approximate True Airspeed (knots) from cruise flight level using ICAO
    standard atmosphere. Simple linear approximation valid 200-450 FL.
    At FL350 a typical narrowbody Mach 0.78 ≈ 450 KTAS.
    """
    # KTAS ≈ Mach * speed-of-sound-at-altitude
    # Speed of sound (kts) at standard ISA = 661.5 * sqrt(T/288.15)
    # ISA temperature at FL: T(K) = 288.15 - 6.5 * alt_km
    alt_m = fl * 30.48  # ft to metres
    temp_k = max(216.65, 288.15 - 0.0065 * alt_m)  # ISA lapse, tropopause floor
    sos = 661.5 * math.sqrt(temp_k / 288.15)
    # Assume Mach 0.78 for jets above FL280, Mach 0.68 below
    mach = 0.78 if fl >= 280 else 0.68
    return round(mach * sos, 1)

def _interpolate(p1: Tuple[float,float], p2: Tuple[float,float], t: float) -> Tuple[float,float]:
    """Linear interpolation between two (lat,lon) points, t in [0,1]."""
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def _parse_route(origin: str, route_string: str, destination: str, db: Dict[str, Waypoint]) -> List[Waypoint]:
    """
    Resolves an ICAO route string to an ordered list of Waypoints.
    """
    result: List[Waypoint] = []
    # Add destination airport
    exit_idx: Optional[int] = None
    rem_route: str = ""

    tokens = route_string.upper().split()
    
    # Departure
    logger.debug(f"_parse_route - origin={repr(origin)} count={len(db)}")
    if origin in db:
        result.append(db[origin])
    else:
        logger.debug(f"_parse_route - origin {repr(origin)} NOT in db! Keys sample: {list(db.keys())[:5]}")

    for i, token in enumerate(tokens):
        if token in ("DCT", "N/A", ""):
            continue
        logger.debug(f"_parse_route checking token={repr(token)} in_db={token in db}")
        if token in db:
            if not result or result[-1].ident != token:
                result.append(db[token])
        else:
            logger.debug(f"_parse_route - token {repr(token)} NOT in db! Keys sample: {list(db.keys())[:5]}")
            # First unknown token = EXIT POINT of this FIR's knowledge
            exit_idx = len(result) - 1
            rem_route = " ".join(tokens[i:])
            break

    if exit_idx is None:
        if destination in db:
            if not result or result[-1].ident != destination:
                result.append(db[destination])
        else:
            # Destination not in local database = Relay required
            exit_idx = len(result) - 1
            rem_route = " ".join(tokens) # simplified

    # Fallback: if only origin+destination resolved, add a midpoint from AIRWAYS lookup
    if len(result) <= 2:
        mid = _find_waypoints_between(origin, destination, db)
        if mid:
            result = [result[0]] + mid + (result[1:] if len(result) > 1 else [])

    return result, exit_idx, rem_route

def _find_waypoints_between(origin: str, destination: str, db: Dict[str, Waypoint]) -> List[Waypoint]:
    """Scan AIRWAYS for a route that passes through both endpoints."""
    for route_wpts in AIRWAYS.values():
        if origin in route_wpts and destination in route_wpts:
            i = route_wpts.index(origin)
            j = route_wpts.index(destination)
            if i < j:
                return [db[w] for w in route_wpts[i+1:j] if w in db]
    return []


# ---------------------------------------------------------------------------
# 4. Sector Intersection: Ray-Casting Point-in-Polygon
# ---------------------------------------------------------------------------

def _point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float,float]]) -> bool:
    """
    Ray-casting algorithm to test whether (lat, lon) lies inside a polygon
    defined as a list of (lat, lon) vertices.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][1], polygon[i][0]  # lon, lat
        xj, yj = polygon[j][1], polygon[j][0]
        x, y = lon, lat
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def _segment_sector_crossings(
    p1: Tuple[float,float],
    p2: Tuple[float,float],
    sector: SectorGeometry,
    samples: int = 20,
    alt1: Optional[int] = None,
    alt2: Optional[int] = None
) -> Optional[Tuple[float, float, Tuple[float,float], Tuple[float,float]]]:
    """
    Walk a leg (p1→p2) in `samples` steps. Return (t_entry, t_exit, entry_pt, exit_pt)
    fractions [0,1] along the leg where the flight enters/exits the sector, or None.
    Also respects sector fl_lower and fl_upper if altitudes are provided.
    """
    def is_inside(pt: Tuple[float, float], t: float) -> bool:
        inside_poly = _point_in_polygon(pt[0], pt[1], sector.polygon)
        if not inside_poly:
            return False
            
        # Check altitude if available
        if alt1 is not None and alt2 is not None:
            curr_alt = alt1 + t * (alt2 - alt1)
            if sector.fl_lower is not None and curr_alt < sector.fl_lower:
                return False
            if sector.fl_upper is not None and curr_alt > sector.fl_upper:
                return False
        return True

    inside_prev = is_inside(p1, 0.0)
    t_entry: Optional[float] = 0.0 if inside_prev else None
    t_exit: Optional[float] = None
    entry_pt = p1
    exit_pt = p2

    for k in range(1, samples + 1):
        t = k / samples
        pt = _interpolate(p1, p2, t)
        inside = is_inside(pt, t)

        if not inside_prev and inside:
            t_entry = t
            entry_pt = pt
        if inside_prev and not inside:
            t_exit = t
            exit_pt = pt
            break
        inside_prev = inside

    if t_entry is None:
        return None

    # If we entered but never exited (stayed inside), exit at p2
    if t_exit is None and t_entry is not None:
        is_p2_in = is_inside(p2, 1.0)
        # print(f"DEBUG: Sector {sector.sector_id} - t_entry={t_entry}, t_exit=None, is_p2_in={is_p2_in}")
        if is_p2_in:
            t_exit = 1.0
            exit_pt = p2
        else:
            return None  # transient hit, discard

    if t_entry is not None and t_exit is not None:
        # print(f"DEBUG: Crossing found: {sector.sector_id} ({t_entry}, {t_exit})")
        return (t_entry, t_exit, entry_pt, exit_pt)
    return None

def _get_bbox(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Returns (min_lat, min_lon, max_lat, max_lon) for a set of points."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return min(lats), min(lons), max(lats), max(lons)

def _bbox_overlap(bbox1: Tuple[float, float, float, float], bbox2: Tuple[float, float, float, float], buffer: float = 0.5) -> bool:
    """Returns True if two bounding boxes overlap, with an optional buffer (degrees)."""
    c1 = (bbox1[2] + buffer < bbox2[0] - buffer)
    c2 = (bbox1[0] - buffer > bbox2[2] + buffer)
    c3 = (bbox1[3] + buffer < bbox2[1] - buffer)
    c4 = (bbox1[1] - buffer > bbox2[3] + buffer)
    return not (c1 or c2 or c3 or c4)


# ---------------------------------------------------------------------------
# 5. The Core Trajectory Solver
# ---------------------------------------------------------------------------

class TrajectorySolver:
    """
    Given a resolved (lat, lon) waypoint sequence and a departure time,
    walk the legs using haversine distance + TAS to accumulate elapsed
    time, continuously testing every known sector polygon for intersection.
    """

    @staticmethod
    def compute_sector_etos(
        waypoints: List[Tuple[float,float]],
        departure_time: datetime,
        tas_kt: float,
        sector_db: Optional[Dict[str, SectorGeometry]] = None,
        altitudes: Optional[List[int]] = None
    ) -> Tuple[List[SectorEntry], Optional[datetime]]:
        logger.debug(f"Entering compute_sector_etos with {len(waypoints)} waypoints.")
        if len(waypoints) < 2:
            logger.debug("compute_sector_etos - Not enough waypoints!")
            return [], None

        db = sector_db if sector_db is not None else SECTORS
        logger.debug(f"compute_sector_etos - total sectors in db: {len(db)}")
        entries: Dict[str, SectorEntry] = {}  # sector_id -> first crossing
        elapsed_seconds = 0.0
        
        # Performance: Spatial filtering
        traj_bbox = _get_bbox(waypoints)
        logger.debug(f"traj_bbox: {traj_bbox}")
        candidate_sectors = []
        for i, (sid, sgeo) in enumerate(db.items()):
            s_bbox = _get_bbox(sgeo.polygon)
            overlap = _bbox_overlap(traj_bbox, s_bbox)
            if i < 3:
                logger.debug(f"sector {sid} bbox: {s_bbox}, overlap: {overlap}")
            if overlap:
                candidate_sectors.append((sid, sgeo))
        
        # print(f"DEBUG: compute_sector_etos - candidate sectors: {len(candidate_sectors)}")

        # candidate_sectors matches logic

        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i + 1]
            dist_nm = _haversine_nm(p1[0], p1[1], p2[0], p2[1])
            leg_duration_s = (dist_nm / tas_kt) * 3600.0 if tas_kt > 0 else 0.0
            
            # leg processing

            alt1 = altitudes[i] if altitudes and i < len(altitudes) else None
            alt2 = altitudes[i+1] if altitudes and i+1 < len(altitudes) else None

            for sector_id, sector in candidate_sectors:
                crossing = _segment_sector_crossings(p1, p2, sector, alt1=alt1, alt2=alt2)
                if crossing is not None:
                    t_entry, t_exit, entry_pt, exit_pt = crossing
                    # Time from departure to sector entry on this leg
                    entry_seconds = elapsed_seconds + t_entry * leg_duration_s
                    # exit_seconds  = elapsed_seconds + t_exit  * leg_duration_s (unused)

                    eto = departure_time + timedelta(seconds=entry_seconds)

                    if sector_id not in entries:
                        entries[sector_id] = SectorEntry(
                            sector_id=sector_id,
                            estimated_time_over=eto,
                            entry_lat=entry_pt[0], entry_lon=entry_pt[1],
                            exit_lat=exit_pt[0],   exit_lon=exit_pt[1],
                        )

            elapsed_seconds += leg_duration_s

        exit_time = departure_time + timedelta(seconds=elapsed_seconds)
        return sorted(entries.values(), key=lambda e: e.estimated_time_over), exit_time


# ---------------------------------------------------------------------------
# 6. Flight Data Processing System (FDPS) — per-node query engine
# ---------------------------------------------------------------------------

class FlightDataProcessingSystem:
    """
    Simulates a local ANSP's FDPS.
    Stores FlightTrajectory objects for flights under this node's control
    and provides ETO-based sector queries.
    """

    def __init__(self):
        self.flights: Dict[str, FlightTrajectory] = {}

    def add_flight(self, flight: FlightTrajectory):
        self.flights[flight.flight_id] = flight

    def predict_flights_in_sector(
        self,
        sector_id: str,
        window_start: datetime,
        window_end: datetime,
        composite_sector_map: Optional[Dict[str, List[str]]] = None
    ) -> List[FlightTrajectory]:
        """
        Returns all flights whose computed ETO for `sector_id` falls within
        the given UTC time window. 
        If `sector_id` is a composite virtual sector, `composite_sector_map` 
        should map the virtual ID to a list of its base sector IDs.
        """
        affected = []
        target_sectors = [sector_id]
        if composite_sector_map and sector_id in composite_sector_map:
            target_sectors = composite_sector_map[sector_id]

        for flight in self.flights.values():
            for entry in flight.route:
                if entry.sector_id in target_sectors:
                    if window_start <= entry.estimated_time_over <= window_end:
                        affected.append(flight)
                        break
        return affected

    def calculate_demand_profile(
        self,
        sector_id: str,
        start_time: datetime,
        end_time: datetime,
        bin_size_minutes: int = 15,
        composite_sector_map: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict]:
        """
        Calculates a time-binned demand profile for a sector.
        """
        bins = []
        current = start_time
        target_sectors = [sector_id]
        if composite_sector_map and sector_id in composite_sector_map:
            target_sectors = composite_sector_map[sector_id]

        while current < end_time:
            bin_end = current + timedelta(minutes=bin_size_minutes)
            bin_flights = set()
            for flight in self.flights.values():
                for i, entry in enumerate(flight.route):
                    if entry.sector_id in target_sectors:
                        eta_entry = entry.estimated_time_over
                        if i + 1 < len(flight.route):
                            eta_exit = flight.route[i + 1].estimated_time_over
                        else:
                            eta_exit = flight.exit_time or (eta_entry + timedelta(minutes=15))
                        
                        if eta_entry < bin_end and eta_exit > current:
                            bin_flights.add(flight.flight_id)
            
            bins.append({
                "time_label": current.strftime("%H:%M"),
                "timestamp": current.isoformat(),
                "demand_count": len(bin_flights),
                "flights": list(bin_flights)
            })
            current = bin_end
            
        return bins
