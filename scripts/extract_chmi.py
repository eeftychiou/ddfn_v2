import PyPDF2
import os

pdf_dir = r"g:\My Drive\Antigravity\ddfn_v2\Documentation"
pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]

keywords = ["workspace", "airspace", "traffic volume", "sector", "multiple", "environment", "fmp"]

for file in pdf_files:
    print(f"\n--- Scanning {file} ---")
    try:
        with open(os.path.join(pdf_dir, file), 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            # Just read the first 50 pages to look at the Table of Contents or introductory definitions
            for i in range(min(50, len(reader.pages))):
                text = reader.pages[i].extract_text()
                if not text:
                    continue
                
                text_lower = text.lower()
                lines = text.split('\n')
                for idx, line in enumerate(lines):
                    if any(kw in line.lower() for kw in keywords):
                        # Print context
                        if "traffic volume" in line.lower() or "workspace" in line.lower() or "airspace" in line.lower():
                            print(f"Page {i+1}: {line.strip()}")
    except Exception as e:
        print(f"Error reading {file}: {e}")
