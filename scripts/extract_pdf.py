import os
import PyPDF2

pdfs = [
    r"g:\My Drive\Antigravity\ddfn_v2\Documentation\eurocontrol-ifps-user-manual-maint-2-external.pdf",
    r"g:\My Drive\Antigravity\ddfn_v2\Documentation\eurocontrol-atfcm-operations-manual-wave-2-1-external.pdf",
    r"g:\My Drive\Antigravity\ddfn_v2\Documentation\eurocontrol-atfcm-users-manual-wave-2-1.pdf"
]

for pdf_path in pdfs:
    print(f"--- Processing {os.path.basename(pdf_path)} ---")
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            num_pages = len(reader.pages)
            print(f"Total pages: {num_pages}")
            
            # Extract first 5 pages for TOC
            text = ""
            for i in range(min(15, num_pages)):
                text += reader.pages[i].extract_text() + "\n"
                
            out_path = pdf_path + ".toc.txt"
            with open(out_path, "w", encoding="utf-8") as out_f:
                out_f.write(text)
            print(f"Saved TOC to {out_path}")
    except Exception as e:
        print(f"Error: {e}")
