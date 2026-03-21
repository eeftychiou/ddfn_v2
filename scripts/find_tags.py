import xml.etree.ElementTree as ET
import os

def find_all_tags(file_path):
    tags = set()
    try:
        context = ET.iterparse(file_path, events=('start',))
        for event, elem in context:
            tags.add(elem.tag)
            # To avoid slow execution, stop after a reasonable number of tags or just let it run
            # since the file is only 5.6MB
        
        print(f"Total Unique Tags: {len(tags)}")
        for t in sorted(list(tags)):
            print(t)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_all_tags(os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml"))
