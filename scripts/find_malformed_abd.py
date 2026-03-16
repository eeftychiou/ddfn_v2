import xml.etree.ElementTree as ET
import sys
from aixm_tool import AIXMParser

def find_malformed_abd(file_path):
    parser = AIXMParser(file_path)
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    target_lat = 0.530556
    target_lon = 0.566389
    
    print(f"Searching for Abd with coords near ({target_lat}, {target_lon})...")
    
    for abd in root.iter('Abd'):
        for avx in abd.findall('Avx'):
            lat_str = avx.findtext('geoLat')
            lon_str = avx.findtext('geoLong')
            if lat_str and lon_str:
                lat = parser.parse_dms(lat_str)
                lon = parser.parse_dms(lon_str)
                if abs(lat - target_lat) < 0.001 and abs(lon - target_lon) < 0.001:
                    uid = abd.find('AbdUid')
                    ase_uid = uid.find('AseUid') if uid is not None else None
                    mid = ase_uid.get('mid') if ase_uid is not None else "N/A"
                    code = ase_uid.findtext('codeId') if ase_uid is not None else "N/A"
                    print(f"FOUND in Abd: MID={mid}, Code={code}")
                    print(f"  lat_str={lat_str} -> {lat}")
                    print(f"  lon_str={lon_str} -> {lon}")
                    # Print more context
                    print(ET.tostring(abd, encoding='unicode'))

if __name__ == "__main__":
    find_malformed_abd(sys.argv[1])
