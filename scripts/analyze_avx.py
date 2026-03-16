import xml.etree.ElementTree as ET

def analyze_avx(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Let's find an Avx inside an Abd
    abd = root.find('.//Abd')
    if abd is not None:
        print(f"--- Detail for Abd parent {abd.find('AbdUid/AseUid/codeId').text} ---")
        for avx in abd.findall('Avx'):
            print(f"Tag: {avx.tag}, Attrib: {avx.attrib}")
            for child in avx:
                print(f"  Child: {child.tag}, Text: {child.text.strip() if child.text else ''}")
                # Check for deeper children like geoLat, geoLong
                for gchild in child:
                    print(f"    GChild: {gchild.tag}, Text: {gchild.text.strip() if gchild.text else ''}")

if __name__ == "__main__":
    analyze_avx(r"g:\My Drive\Antigravity\ddfn_v2\AIXM\BD_2025-09-30_400005921419525.xml")
