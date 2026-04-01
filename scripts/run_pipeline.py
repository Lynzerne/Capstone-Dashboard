import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import *

PDF_FOLDER = "data/raw_pdfs"
OUTPUT_FILE = "data/outputs/extracted_rules.xlsx"

results = []

for file_name in os.listdir(PDF_FOLDER):
    if file_name.lower().endswith(".pdf"):
        file_path = os.path.join(PDF_FOLDER, file_name)
        pages = extract_pdf_text(file_path)

        for page in pages:
            txt = page.get("text")

            if not txt:
                continue

            extracted = (
                extract_no_diversion_rules(txt)
                + extract_station_references(txt)
                + extract_percent_rules(txt)
                + extract_seasonal_rules(txt)
                + extract_temperature_rules(txt)
            )

            for r in extracted:
                r["source_pdf"] = file_name
                r["page_no"] = page["page"]
                results.append(r)

flow_types = {
    "no_diversion",
    "instream_objective",
    "flow_threshold",
    "water_conservation_objective",
    "percent_diversion",
    "seasonal_window",
    "temperature_window",
    "temperature_rule"
}

flows = [r for r in results if r["rule_type"] in flow_types]
stations = [r for r in results if r["rule_type"] == "station_reference"]

combined = []

for f in flows:
    sids = f.get("station_ids_found") or []

    if f["rule_type"] in {"temperature_rule", "temperature_window"} and not sids:
        combined.append({**f, "station_id": None, "station_name": None})
        continue

    for s in stations:
        if f.get("source_pdf") != s.get("source_pdf"):
            continue

        if sids:
            if s["station_id"] not in sids:
                continue
        else:
            if f.get("river") != s.get("river"):
                continue

        combined.append({
            **f,
            "station_id": s["station_id"],
            "station_name": s["station_name"]
        })

df = pd.DataFrame(combined).drop_duplicates()
df.to_excel(OUTPUT_FILE, index=False)

print(f"Saved {len(df)} rows")
