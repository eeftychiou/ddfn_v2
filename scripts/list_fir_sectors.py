from aixm_tool import AIXMParser
import json

parser = AIXMParser(r"c:\Users\eftyc\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml")
sectors = parser.extract_sectors()

target_firs = ["LCCC", "LGGG", "LTAA"]
fir_sectors = {fir: [] for fir in target_firs}

for s in sectors:
    if s.parent_fir in target_firs:
        fir_sectors[s.parent_fir].append(s.sector_id)

for fir, s_list in fir_sectors.items():
    print(f"FIR {fir}: {len(s_list)} sectors found")
    print(f"Sample: {s_list[:10]}")

with open("fir_sectors_sample.json", "w") as f:
    json.dump(fir_sectors, f, indent=4)
