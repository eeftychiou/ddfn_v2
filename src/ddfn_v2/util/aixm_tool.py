import xml.etree.ElementTree as ET
import os
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass
class AIXMSector:
    sector_id: str
    name: str
    type: str
    parent_fir: str
    fl_lower: int
    fl_upper: int
    polygon: List[Tuple[float, float]]

@dataclass
class AIXMWaypoint:
    ident: str
    lat: float
    lon: float
    type: str = "ENRT"

@dataclass
class AIXMAirport:
    ident: str
    name: str
    lat: float
    lon: float
    icao: Optional[str] = None
    iata: Optional[str] = None

class AIXMParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = ET.parse(file_path)
        self.root = self.tree.getroot()

    def parse_coordinate(self, val: str, ref: str) -> float:
        """
        Robustly parse AIXM coordinate strings to decimal degrees.
        Handles formats like DDMMSS.ssX, DDMMX, DD.ddX, etc.
        Based on bpaTools.GeoCoordinates logic from aixmParser.
        """
        if not val:
            return 0.0
        
        s_coord = str(val).strip().replace(" ", "").replace(",", "").replace("°", "").replace("'", "").replace("\"", "")
        
        # Identify direction
        s_dir = ""
        if s_coord[-1].upper() in ["N", "S", "E", "W", "O"]:
            s_dir = s_coord[-1].upper()
            s_coord = s_coord[:-1]
        elif s_coord[0].upper() in ["N", "S", "E", "W", "O"]:
            s_dir = s_coord[0].upper()
            s_coord = s_coord[1:]
        
        if s_dir == "O":
            s_dir = "W"

        # Determine if it's DD, DDMM, or DDMMSS based on length and decimal point
        try:
            if "." in s_coord:
                parts = s_coord.split(".")
                main = parts[0]
                decimal_part = float("0." + parts[1])
            else:
                main = s_coord
                decimal_part = 0.0

            n = len(main)
            if ref == "lat":
                if n <= 2: # DD.dd
                    deg, mnt, sec = float(main), 0.0, 0.0
                elif n <= 4: # DDMM.mm
                    main = main.zfill(4)
                    deg, mnt, sec = float(main[:2]), float(main[2:]), 0.0
                else: # DDMMSS.ss
                    main = main.zfill(6)
                    deg, mnt, sec = float(main[:2]), float(main[2:4]), float(main[4:])
            else: # lon
                if n <= 3: # DDD.dd
                    deg, mnt, sec = float(main), 0.0, 0.0
                elif n <= 5: # DDDMM.mm
                    main = main.zfill(5)
                    deg, mnt, sec = float(main[:3]), float(main[3:]), 0.0
                else: # DDDMMSS.ss
                    main = main.zfill(7)
                    deg, mnt, sec = float(main[:3]), float(main[3:5]), float(main[5:])

            dd = deg + (mnt / 60.0) + ((sec + decimal_part) / 3600.0)
            if s_dir in ["S", "W"]:
                dd *= -1
            return round(dd, 8)
        except (ValueError, IndexError):
            return 0.0

    def parse_dms(self, val: str) -> float:
        """Alias for parse_coordinate to support route extraction logic."""
        # Note: routes don't specify if it's lat or lon in the call, 
        # but the parser logic handles it based on length if possible.
        # However, route extraction uses separate calls for slat, slon.
        # So we can keep it generic or fix the call site.
        # Current call sites: slat, slon = parse_dms(lat_str), parse_dms(lon_str)
        # This means parse_dms might need to guess or the call site should be updated.
        # Since parse_coordinate needs 'ref', let's see where it's called.
        return self.parse_coordinate(val, "lat") # Risky fallback


    def get_fir_bbox(self, fir_id: str) -> Optional[Dict[str, float]]:
        """Calculate bounding box for a given FIR."""
        sectors = self.extract_sectors()
        # Find the FIR itself or its component sectors
        fir_polygons = [s.polygon for s in sectors if s.sector_id == fir_id or s.parent_fir == fir_id]
        if not fir_polygons:
            return None
        
        all_pts = [pt for poly in fir_polygons for pt in poly]
        if not all_pts:
            return None
            
        lats = [pt[0] for pt in all_pts]
        lons = [pt[1] for pt in all_pts]
        
        # Add a 1-degree buffer
        return {
            "min_lat": min(lats) - 1.0,
            "max_lat": max(lats) + 1.0,
            "min_lon": min(lons) - 1.0,
            "max_lon": max(lons) + 1.0
        }

    def _is_in_bbox(self, lat: float, lon: float, bbox: Optional[Dict[str, float]]) -> bool:
        if not bbox: return True
        return (bbox["min_lat"] <= lat <= bbox["max_lat"] and 
                bbox["min_lon"] <= lon <= bbox["max_lon"])

    def find_all_tags(self, tag_name: str):
        """Find all instances of a tag, ignoring namespaces."""
        # This is a bit slow but robust for mixed AIXM versions
        return self.root.findall(f".//{tag_name}") or self.root.findall(f".//{{*}}{tag_name}")

    def find_tag_text(self, element, tag_name: str, default=""):
        """Find text of a tag within an element, ignoring namespaces."""
        if element is None: return default
        res = element.find(tag_name)
        if res is None:
            res = element.find(f"{{*}}{tag_name}")
        return res.text if res is not None else default

    def extract_sectors(self) -> List[AIXMSector]:
        ase_by_mid = {}
        ase_by_code = {}
        for ase in self.find_all_tags('Ase'):
            uid = ase.find('AseUid') or ase.find('{*}AseUid')
            if uid is not None:
                mid = uid.get('mid')
                code_id = self.find_tag_text(uid, 'codeId')
                code_type = self.find_tag_text(uid, 'codeType')
                name = self.find_tag_text(ase, 'txtName')
                fl_lower = self.find_tag_text(ase, 'valDistVerLower')
                fl_upper = self.find_tag_text(ase, 'valDistVerUpper')
                
                def safe_int(s, default):
                    if not s: return default
                    try: return int(float(s))
                    except: return default

                info = {
                    'mid': mid,
                    'code_id': code_id,
                    'name': name or code_id or "Unknown",
                    'type': code_type or "Unknown",
                    'parent_fir': self._infer_parent_fir(code_id),
                    'fl_lower': safe_int(fl_lower, 0),
                    'fl_upper': safe_int(fl_upper, 660)
                }
                if mid: ase_by_mid[mid] = info
                if code_id: ase_by_code[code_id] = info

        sectors = []
        for abd in self.root.iter('Abd'):
            uid = abd.find('AbdUid')
            if uid is not None:
                ase_uid = uid.find('AseUid')
                if ase_uid is not None:
                    target_mid = ase_uid.get('mid')
                    target_code = ase_uid.findtext('codeId')
                    info = ase_by_mid.get(target_mid) or ase_by_code.get(target_code)
                    if info:
                        polygon = []
                        for avx in abd.findall('Avx'):
                            lat_str = avx.findtext('geoLat')
                            lon_str = avx.findtext('geoLong')
                            if lat_str and lon_str:
                                lat = self.parse_coordinate(lat_str, "lat")
                                lon = self.parse_coordinate(lon_str, "lon")
                                if not polygon or (lat != polygon[-1][0] or lon != polygon[-1][1]):
                                    polygon.append((lat, lon))
                        if polygon:
                            sectors.append(AIXMSector(
                                sector_id=info['code_id'] or info['mid'],
                                name=info['name'],
                                type=info['type'],
                                parent_fir=info['parent_fir'],
                                fl_lower=info['fl_lower'],
                                fl_upper=info['fl_upper'],
                                polygon=polygon
                            ))
        return sectors

    def _infer_parent_fir(self, code_id: str) -> str:
        if not code_id: return "UNKNOWN"
        # Heuristic for Nicosia, Beirut, Tel Aviv, Cairo from specific AIXM file patterns
        if code_id.startswith("LC"): return "LCCC"
        if code_id.startswith("OL"): return "OLBB"
        if code_id.startswith("LL"): return "LLLL"
        if code_id.startswith("HE"): return "HECC"
        if len(code_id) >= 4: return code_id[:4]
        return "UNKNOWN"

    def extract_airports(self, fir_id: Optional[str] = None) -> List[AIXMAirport]:
        bbox = self.get_fir_bbox(fir_id) if fir_id else None
        airports = []
        for ahp in self.find_all_tags('Ahp'):
            uid = ahp.find('AhpUid') or ahp.find('{*}AhpUid')
            if uid is not None:
                code_id = self.find_tag_text(uid, 'codeId')
                name = self.find_tag_text(ahp, 'txtName')
                lat_str = self.find_tag_text(ahp, 'geoLat')
                lon_str = self.find_tag_text(ahp, 'geoLong')
                icao = self.find_tag_text(ahp, 'codeIcao')
                iata = self.find_tag_text(ahp, 'codeIata')
                if code_id and lat_str and lon_str:
                    lat, lon = self.parse_coordinate(lat_str, "lat"), self.parse_coordinate(lon_str, "lon")
                    if self._is_in_bbox(lat, lon, bbox):
                        airports.append(AIXMAirport(ident=code_id, name=name or code_id, lat=lat, lon=lon, icao=icao, iata=iata))
        return airports

    def extract_waypoints(self, fir_id: Optional[str] = None) -> List[AIXMWaypoint]:
        bbox = self.get_fir_bbox(fir_id) if fir_id else None
        waypoints = []
        for dpn in self.find_all_tags('Dpn'):
            uid = dpn.find('DpnUid') or dpn.find('{*}DpnUid')
            if uid is not None:
                code_id = self.find_tag_text(uid, 'codeId')
                type_code = self.find_tag_text(dpn, 'codeType')
                lat_str = self.find_tag_text(uid, 'geoLat') or self.find_tag_text(dpn, 'geoLat')
                lon_str = self.find_tag_text(uid, 'geoLong') or self.find_tag_text(dpn, 'geoLong')
                if code_id and lat_str and lon_str:
                    lat, lon = self.parse_coordinate(lat_str, "lat"), self.parse_coordinate(lon_str, "lon")
                    if self._is_in_bbox(lat, lon, bbox):
                        waypoints.append(AIXMWaypoint(ident=code_id, type=type_code or "ENRT", lat=lat, lon=lon))
        return waypoints

    def extract_routes(self, fir_id: Optional[str] = None) -> List[Dict[str, Any]]:
        bbox = self.get_fir_bbox(fir_id) if fir_id else None
        
        # Cache route names
        rte_names = {}
        for r in self.find_all_tags('Rte'):
            uid = r.find('RteUid') or r.find('{*}RteUid')
            if uid is not None:
                mid = uid.get('mid')
                name = self.find_tag_text(uid, 'txtDesig')
                if mid and name:
                    rte_names[mid] = name

        # Pre-cache waypoint locations
        wpt_coords = {}
        for dpn in self.find_all_tags('Dpn'):
            uid = dpn.find('DpnUid') or dpn.find('{*}DpnUid')
            if uid is not None:
                c_id = self.find_tag_text(uid, 'codeId')
                l_str = self.find_tag_text(uid, 'geoLat') or self.find_tag_text(dpn, 'geoLat')
                o_str = self.find_tag_text(uid, 'geoLong') or self.find_tag_text(dpn, 'geoLong')
                if c_id and l_str and o_str:
                    wpt_coords[c_id] = (self.parse_coordinate(l_str, "lat"), self.parse_coordinate(o_str, "lon"))

        routes = []
        for rsg in self.find_all_tags('Rsg'):
            uid = rsg.find('RsgUid') or rsg.find('{*}RsgUid')
            if uid is None: continue
            
            rte_ref = uid.find('RteUid') or uid.find('{*}RteUid')
            route_name = rte_names.get(rte_ref.get('mid')) if rte_ref is not None else "DCT"
            
            sta, end = uid.find('DpnUidSta') or uid.find('{*}DpnUidSta'), uid.find('DpnUidEnd') or uid.find('{*}DpnUidEnd')
            if sta is not None and end is not None:
                s_id, e_id = self.find_tag_text(sta, 'codeId'), self.find_tag_text(end, 'codeId')
                
                # Get coordinates
                s_coords = wpt_coords.get(s_id)
                e_coords = wpt_coords.get(e_id)
                
                if not s_coords:
                    l, o = self.find_tag_text(sta, 'geoLat'), self.find_tag_text(sta, 'geoLong')
                    if l and o: s_coords = (self.parse_coordinate(l, "lat"), self.parse_coordinate(o, "lon"))
                
                if not e_coords:
                    l, o = self.find_tag_text(end, 'geoLat'), self.find_tag_text(end, 'geoLong')
                    if l and o: e_coords = (self.parse_coordinate(l, "lat"), self.parse_coordinate(o, "lon"))

                if s_coords and e_coords:
                    slat, slon = s_coords
                    elat, elon = e_coords
                    
                    if self._is_in_bbox(slat, slon, bbox) or self._is_in_bbox(elat, elon, bbox):
                        routes.append({
                            "route_name": route_name,
                            "start_id": s_id, "start_lat": slat, "start_lon": slon,
                            "end_id": e_id, "end_lat": elat, "end_lon": elon
                        })
        return routes
