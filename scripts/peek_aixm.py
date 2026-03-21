import xml.etree.ElementTree as ET

def peek_xml(file_path, num_elements=10):
    try:
        # Use iterparse to avoid loading the whole 5.6MB file at once if it's huge, 
        # but 5.6MB is actually small enough for memory.
        context = ET.iterparse(file_path, events=('start', 'end'))
        count = 0
        for event, elem in context:
            if event == 'start':
                print(f"Tag: {elem.tag}")
                print(f"Attrib: {elem.attrib}")
                count += 1
                if count >= num_elements:
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    peek_xml(os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml"))
