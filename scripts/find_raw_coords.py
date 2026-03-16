import xml.etree.ElementTree as ET
import sys
from aixm_tool import AIXMParser

def find_raw_coords(file_path):
    parser = AIXMParser(file_path)
    root = parser.root
    
    print("Checking all Abd tags for LCCC related airspaces...")
    
    for abd in root.iter('Abd'):
        uid = abd.find('AbdUid')
        if uid is not None:
            ase_uid = uid.find('AseUid')
            if ase_uid is not None:
                mid = ase_uid.get('mid')
                code = ase_uid.findtext('codeId')
                
                if code == 'LCCC' or mid in ['4479462', '400003522489064']:
                    print(f"\n--- Found Abd for Code={code} MID={mid} ---")
                    for avx in abd.findall('Avx'):
                        lat_str = avx.findtext('geoLat')
                        lon_str = avx.findtext('geoLong')
                        lat = parser.parse_dms(lat_str) if lat_str else 0
                        lon = parser.parse_dms(lon_str) if lon_str else 0
                        if abs(lat) < 1.0:
                             print(f"  !!! MALFORMED Point Found: Raw {lat_str}/{lon_str} -> Parsed {lat}/{lon}")
                        else:
                             # Just print first 2
                             pass
                    print(f"  First point: {parser.parse_dms(abd.find('Avx').findtext('geoLat'))}, {parser.parse_dms(abd.find('Avx').findtext('geoLong'))}")

if __name__ == "__main__":
    find_raw_coords(sys.argv[1])
