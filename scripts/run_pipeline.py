import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import extract_no_diversion_rules, extract_station_references

PDF_FOLDER = "data/raw_pdfs"
OUTPUT_FILE = "data/outputs/extracted_rules.xlsx"

results = []

for file_name in os.listdir(PDF_FOLDER):
    if file_name.lower().endswith(".pdf"):
        file_path = os.path.join(PDF_FOLDER, file_name)
        print(f"Processing {file_name}")

        pages = extract_pdf_text(file_path)

        for page in pages:
            page_text = page.get("text")

            if not page_text:
                print(f"Page {page['page']}: no text extracted")
                continue

            rules = extract_no_diversion_rules(page_text)
            stations = extract_station_references(page_text)

            print(
                f"Page {page['page']}: "
                f"{len(rules)} flow candidate(s), "
                f"{len(stations)} station reference(s)"
            )

            for rule in rules:
                rule["source_pdf"] = file_name
                rule["page_no"] = page["page"]
                results.append(rule)

            for station in stations:
                station["source_pdf"] = file_name
                station["page_no"] = page["page"]
                results.append(station)

# Save only once, after all PDFs/pages are processed
df = pd.DataFrame(results)

if df.empty:
    df = pd.DataFrame(columns=[
        "rule_type",
        "threshold_value",
        "units",
        "station_id",
        "source_text",
        "source_pdf",
        "page_no"
    ])

df.to_excel(OUTPUT_FILE, index=False)
print(f"Final output saved to {OUTPUT_FILE} with {len(df)} row(s)")
