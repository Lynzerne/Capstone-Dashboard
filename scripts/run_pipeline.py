import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import extract_no_diversion_rules, extract_station_references

PDF_FOLDER = "data/raw_pdfs"
OUTPUT_FILE = "data/outputs/extracted_rules.xlsx"

results = []

# Step 1: Extract raw pieces from each PDF
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

# Step 2: Join flow rules to station references by page number
combined_rows = []

flow_rows = [r for r in results if r.get("rule_type") == "flow_rule_candidate"]
station_rows = [r for r in results if r.get("rule_type") == "station_reference"]

for flow in flow_rows:
    for station in station_rows:
        if (
            flow.get("source_pdf") == station.get("source_pdf")
            and flow.get("page_no") == station.get("page_no")
        ):
            combined_rows.append({
                "rule_type": "combined_rule",
                "threshold_value": flow.get("threshold_value"),
                "units": flow.get("units"),
                "station_id": station.get("station_id"),
                "source_text": flow.get("source_text"),
                "source_pdf": flow.get("source_pdf"),
                "page_no": flow.get("page_no")
            })

# Step 3: Save output once, at the end
df = pd.DataFrame(combined_rows)

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
