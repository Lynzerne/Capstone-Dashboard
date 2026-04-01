import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.extract_text import extract_pdf_text
from src.parse_rules import (
    extract_no_diversion_rules,
    extract_station_references,
    extract_percent_rules,
    extract_seasonal_rules,
    extract_temperature_rules
)

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
            percent_rules = extract_percent_rules(page_text)
            seasonal_rules = extract_seasonal_rules(page_text)
            temperature_rules = extract_temperature_rules(page_text)

            print(
                f"Page {page['page']}: "
                f"{len(rules)} flow rule(s), "
                f"{len(stations)} station reference(s), "
                f"{len(percent_rules)} percent rule(s), "
                f"{len(seasonal_rules)} seasonal rule(s), "
                f"{len(temperature_rules)} temperature rule(s)"
            )

            for rule in rules:
                rule["source_pdf"] = file_name
                rule["page_no"] = page["page"]
                results.append(rule)

            for station in stations:
                station["source_pdf"] = file_name
                station["page_no"] = page["page"]
                results.append(station)

            for pr in percent_rules:
                pr["source_pdf"] = file_name
                pr["page_no"] = page["page"]
                results.append(pr)

            for sr in seasonal_rules:
                sr["source_pdf"] = file_name
                sr["page_no"] = page["page"]
                results.append(sr)

            for tr in temperature_rules:
                tr["source_pdf"] = file_name
                tr["page_no"] = page["page"]
                results.append(tr)

print(f"DEBUG total raw results: {len(results)}")

flow_rule_types = {
    "no_diversion",
    "instream_objective",
    "flow_threshold",
    "water_conservation_objective",
    "percent_diversion",
    "seasonal_window",
    "temperature_window",
    "temperature_rule"
}

flow_rows = [r for r in results if r.get("rule_type") in flow_rule_types]
station_rows = [r for r in results if r.get("rule_type") == "station_reference"]

print(f"DEBUG flow rows: {len(flow_rows)}")
print(f"DEBUG station rows: {len(station_rows)}")

if flow_rows:
    print("DEBUG first 10 flow rows:")
    for row in flow_rows[:10]:
        print(row)

if station_rows:
    print("DEBUG first 10 station rows:")
    for row in station_rows[:10]:
        print(row)

# Step 2: join extracted rules to station references
combined_rows = []

for flow in flow_rows:
    flow_station_ids = flow.get("station_ids_found") or []

    for station in station_rows:
        if flow.get("source_pdf") != station.get("source_pdf"):
            continue

        # Priority 1: exact station match if station IDs were found
        if flow_station_ids:
            if station.get("station_id") not in flow_station_ids:
                continue
        else:
            # Fallback: river match only when no station was found
            if flow.get("river") != station.get("river"):
                continue

            if flow.get("river") is None or station.get("river") is None:
                continue

        combined_rows.append({
            "rule_type": flow.get("rule_type"),
            "condition_type": flow.get("condition_type"),
            "season_type": flow.get("season_type"),
            "temperature_rule_type": flow.get("temperature_rule_type"),
            "start_month": flow.get("start_month"),
            "start_day": flow.get("start_day"),
            "end_month": flow.get("end_month"),
            "end_day": flow.get("end_day"),
            "river": flow.get("river"),
            "threshold_value": flow.get("threshold_value"),
            "temperature_c": flow.get("temperature_c"),
            "percent": flow.get("percent"),
            "frequency": flow.get("frequency"),
            "units": flow.get("units"),
            "station_id": station.get("station_id"),
            "station_name": station.get("station_name"),
            "source_text": flow.get("source_text"),
            "source_pdf": flow.get("source_pdf"),
            "page_no": flow.get("page_no")
        })

print(f"DEBUG combined rows before dedupe: {len(combined_rows)}")

# Step 3: save
df = pd.DataFrame(combined_rows)

if not df.empty:
    df = df.drop_duplicates(subset=[
        "rule_type",
        "condition_type",
        "season_type",
        "temperature_rule_type",
        "start_month",
        "start_day",
        "end_month",
        "end_day",
        "river",
        "threshold_value",
        "temperature_c",
        "percent",
        "frequency",
        "units",
        "station_id",
        "source_pdf",
        "page_no"
    ])

print(f"DEBUG final rows after dedupe: {len(df)}")

if df.empty:
    df = pd.DataFrame(columns=[
        "rule_type",
        "condition_type",
        "season_type",
        "temperature_rule_type",
        "start_month",
        "start_day",
        "end_month",
        "end_day",
        "river",
        "threshold_value",
        "temperature_c",
        "percent",
        "frequency",
        "units",
        "station_id",
        "station_name",
        "source_text",
        "source_pdf",
        "page_no"
    ])

df.to_excel(OUTPUT_FILE, index=False)
print(f"Final output saved to {OUTPUT_FILE} with {len(df)} row(s)")
