import re


STATION_LOOKUP = {
    "05CC001": {"river": "Blindman", "station_name": "Blindman River near Blackfalds"},
    "05CC002": {"river": "Red Deer", "station_name": "Red Deer River at Red Deer"},
    "05CB007": {"river": "Red Deer", "station_name": "Dickson Dam Tunnel Outlet"}
}


STATION_PATTERNS = {
    "05CC001": [r"\b05CC001\b", r"blindman river near blackfalds"],
    "05CC002": [r"\b05CC002\b", r"red deer river at red deer"],
    "05CB007": [r"\b05CB007\b", r"dickson dam", r"tunnel outlet"]
}


MONTH_PATTERN = (
    r"(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)"
)


def split_into_sections(text):
    if not text:
        return []
    text = re.sub(r"\s+", " ", text)
    return re.split(r"\.\s+|\;\s+", text)


def find_station_ids(text):
    found = set()

    explicit = re.findall(r"\b05[A-Z0-9]{5}\b", text)
    for s in explicit:
        if s in STATION_LOOKUP:
            found.add(s)

    text_lower = text.lower()
    for sid, patterns in STATION_PATTERNS.items():
        for p in patterns:
            if re.search(p, text_lower):
                found.add(sid)

    return list(found)


def infer_river(section):
    stations = find_station_ids(section)
    if stations:
        return STATION_LOOKUP[stations[0]]["river"]

    if "blindman" in section.lower():
        return "Blindman"
    if "red deer" in section.lower():
        return "Red Deer"

    return None


# ---------------- FLOW RULES ---------------- #

def extract_no_diversion_rules(text):
    results = []
    sections = split_into_sections(text)

    for sec in sections:
        if "cubic meters per second" not in sec.lower():
            continue

        river = infer_river(sec)

        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*cubic meters per second', sec, re.I):
            value = float(m.group(1))

            if "instream" in sec.lower():
                rule_type = "instream_objective"
            elif "conservation" in sec.lower():
                rule_type = "water_conservation_objective"
            else:
                rule_type = "flow_threshold"

            results.append({
                "rule_type": rule_type,
                "threshold_value": value,
                "units": "m3/s",
                "river": river,
                "station_ids_found": find_station_ids(sec),
                "source_text": sec
            })

    return results


# ---------------- PERCENT RULES ---------------- #

def extract_percent_rules(text):
    results = []
    sections = split_into_sections(text)

    for sec in sections:
        if "% of the rate of flow" not in sec.lower():
            continue

        river = infer_river(sec)
        stations = find_station_ids(sec)

        # 10% band
        band = re.search(
            r'(\d+)%.*?greater than (\d+\.?\d*).*?less than or equal to (\d+\.?\d*)',
            sec, re.I
        )
        if band:
            results.append({
                "rule_type": "percent_diversion",
                "percent": int(band.group(1)),
                "flow_min_exclusive": float(band.group(2)),
                "flow_max_inclusive": float(band.group(3)),
                "max_diversion_rate": None,
                "units": "m3/s",
                "river": river,
                "station_ids_found": stations,
                "source_text": sec
            })
            continue

        # 15% band
        upper = re.search(
            r'(\d+)%.*?maximum diversion rate of (\d+\.?\d*).*?greater than (\d+\.?\d*)',
            sec, re.I
        )
        if upper:
            results.append({
                "rule_type": "percent_diversion",
                "percent": int(upper.group(1)),
                "flow_min_exclusive": float(upper.group(3)),
                "flow_max_inclusive": None,
                "max_diversion_rate": float(upper.group(2)),
                "units": "m3/s",
                "river": river,
                "station_ids_found": stations,
                "source_text": sec
            })

    return results


# ---------------- SEASONAL ---------------- #

def extract_seasonal_rules(text):
    results = []

    if "05cc002" in text.lower() and "open water season" in text.lower():
        results.append({
            "rule_type": "seasonal_window",
            "condition_type": "seasonal_station_applicability",
            "season_type": "open_water_season",
            "river": "Red Deer",
            "station_ids_found": ["05CC002"],
            "source_text": text
        })

    if "05cb007" in text.lower() and "winter ice cover" in text.lower():
        results.append({
            "rule_type": "seasonal_window",
            "condition_type": "seasonal_station_applicability",
            "season_type": "winter_ice_cover_season",
            "river": "Red Deer",
            "station_ids_found": ["05CB007"],
            "source_text": text
        })

    return results


# ---------------- TEMPERATURE ---------------- #

def extract_temperature_rules(text):
    results = []

    if "temperature" not in text.lower():
        return results

    # Window
    m = re.search(r'between (\w+) (\d+) and (\w+) (\d+)', text, re.I)
    if m:
        results.append({
            "rule_type": "temperature_window",
            "temperature_rule_type": "monitoring_period",
            "start_month": m.group(1).title(),
            "start_day": int(m.group(2)),
            "end_month": m.group(3).title(),
            "end_day": int(m.group(4)),
            "river": "Blindman",
            "station_ids_found": [],
            "source_text": text
        })

    # Temps
    for m in re.finditer(r'(\d+)\s*(?:°|o)?\s*C', text):
        val = float(m.group(1))

        if val == 22:
            t = "temperature_maximum"
        elif val == 19:
            t = "baseline_temperature_trigger"
        else:
            t = "temperature_threshold"

        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": t,
            "temperature_c": val,
            "units": "C",
            "river": "Blindman",
            "station_ids_found": [],
            "source_text": text
        })

    # Frequency
    if "hourly" in text.lower():
        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": "temperature_monitoring_frequency",
            "frequency": "hourly",
            "frequency_condition": "baseline temperature > 19 C",
            "river": "Blindman",
            "station_ids_found": [],
            "source_text": text
        })

    if "daily" in text.lower():
        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": "temperature_monitoring_frequency",
            "frequency": "daily",
            "frequency_condition": "previous temperature measurement < 19 C",
            "river": "Blindman",
            "station_ids_found": [],
            "source_text": text
        })

    return results
