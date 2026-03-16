import xml.etree.ElementTree as ET
import sys
from aixm_tool import AIXMParser

def find_raw_lcc(file_path):
    parser = AIXMParser(file_path)
    root = parser.root
    
    found = False
    for abd in root.iter('Abd'):
        uid = abd.find('AbdUid')
        if uid is not None:
            ase_uid = uid.find('AseUid')
            if ase_uid is not None:
                code = ase_uid.findtext('codeId')
                mid = ase_uid.get('mid')
                if code == 'LCCC':
                    found = True
                    print(f"\n--- Found Abd for {code} UID={mid} ---")
                    for avx in abd.findall('Avx'):
                        lat_str = avx.findtext('geoLat')
                        lon_str = avx.findtext('geoLong')
                        lat = parser.parse_dms(lat_str) if lat_str else "N/A"
                        lon = parser.parse_dms(lon_str) if lon_str else "N/A"
                        print(f"  Raw: {lat_str} / {lon_str} -> Parsed: {lat}, {lon}")
    
    if not found:
        print("LCCC FIR not found in Abd tags.")

if __name__ == "__main__":
    find_raw_lcc(sys.argv[1])
