import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import extract_no_diversion_rules, extract_station_references

PDF_FOLDER = "data/raw_pdfs"
OUTPUT_FILE = "data/outputs/extracted_rules.xlsx"

results = []

# Step 1: extract raw pieces
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

# Step 2: join flow rules to station references
combined_rows = []

flow_rule_types = {
    "no_diversion",
    "instream_objective",
    "flow_threshold",
    "water_conservation_objective"
}

flow_rows = [r for r in results if r.get("rule_type") in flow_rule_types]
station_rows = [r for r in results if r.get("rule_type") == "station_reference"]

for flow in flow_rows:
    for station in station_rows:
        if flow.get("source_pdf") != station.get("source_pdf"):
            continue

        # allow matching within same PDF + same river
        if flow.get("source_pdf") != station.get("source_pdf"):
            continue
        
        if flow.get("river") != station.get("river"):
            continue

        if flow.get("river") != station.get("river"):
            continue

        combined_rows.append({
            "rule_type": "combined_rule",
            "river": flow.get("river"),
            "threshold_value": flow.get("threshold_value"),
            "units": flow.get("units"),
            "station_id": station.get("station_id"),
            "station_name": station.get("station_name"),
            "source_text": flow.get("source_text"),
            "source_pdf": flow.get("source_pdf"),
            "page_no": flow.get("page_no")
        })

# Step 3: save
df = pd.DataFrame(combined_rows)

if not df.empty:
    df = df.drop_duplicates()

if df.empty:
    df = pd.DataFrame(columns=[
        "rule_type",
        "river",
        "threshold_value",
        "units",
        "station_id",
        "station_name",
        "source_text",
        "source_pdf",
        "page_no"
    ])

df.to_excel(OUTPUT_FILE, index=False)
print(f"Final output saved to {OUTPUT_FILE} with {len(df)} row(s)")
