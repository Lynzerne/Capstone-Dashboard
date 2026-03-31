import os
import sys
import pandas as pd

# Add the repo root to Python's import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import extract_no_diversion_rules

PDF_FOLDER = "data/raw_pdfs"
OUTPUT_FILE = "data/outputs/extracted_rules.xlsx"

results = []

for file_name in os.listdir(PDF_FOLDER):
    if file_name.lower().endswith(".pdf"):
        file_path = os.path.join(PDF_FOLDER, file_name)
        pages = extract_pdf_text(file_path)

        for page in pages:
            rules = extract_no_diversion_rules(page["text"])

            for rule in rules:
                rule["source_pdf"] = file_name
                rule["page_no"] = page["page"]
                results.append(rule)

df = pd.DataFrame(results)

if not df.empty:
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved {len(df)} extracted rule(s) to {OUTPUT_FILE}")
else:
    print("No rules found.")
