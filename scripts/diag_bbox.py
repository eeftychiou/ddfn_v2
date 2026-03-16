from aixm_tool import AIXMParser

p = AIXMParser('AIXM/BD_2025-09-30_400005921419525.xml')
bbox = p.get_fir_bbox('LCCC')
print(f"BBOX for LCCC: {bbox}")

wpts = p.extract_waypoints('LCCC')
print(f"Extracted {len(wpts)} waypoints for LCCC.")
if wpts:
    print(f"Sample: {wpts[0]}")

# Check unfiltered count
all_wpts = p.extract_waypoints()
print(f"Total unfiltered waypoints: {len(all_wpts)}")
