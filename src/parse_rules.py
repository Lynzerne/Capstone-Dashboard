import re


STATION_LOOKUP = {
    "05CC001": {
        "river": "Blindman",
        "station_name": "Blindman River near Blackfalds"
    },
    "05CC002": {
        "river": "Red Deer",
        "station_name": "Red Deer River at Red Deer"
    },
    "05CB007": {
        "river": "Red Deer",
        "station_name": "Dickson Dam Tunnel Outlet"
    }
}


STATION_PATTERNS = {
    "05CC001": [
        r"\b05CC001\b",
        r"\bblindman river near blackfalds\b",
        r"\bblindman near blackfalds\b"
    ],
    "05CC002": [
        r"\b05CC002\b",
        r"\bred deer river at red deer\b",
        r"\bred deer at red deer\b"
    ],
    "05CB007": [
        r"\b05CB007\b",
        r"\bdickson dam tunnel outlet\b",
        r"\bdickson dam\b",
        r"\btunnel outlet\b"
    ]
}


RIVER_PATTERNS = {
    "Blindman": [
        r"\bblindman\b",
        r"\bblindman river\b"
    ],
    "Red Deer": [
        r"\bred deer\b",
        r"\bred deer river\b",
        r"\bdickson dam\b",
        r"\btunnel outlet\b"
    ]
}


MONTH_PATTERN = (
    r"(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)"
)


def split_into_sections(text):
    """
    Split PDF text into paragraph-like sections.
    """
    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    sections = [s.strip() for s in re.split(r"\n\s*\n+", text) if s.strip()]

    if len(sections) <= 1:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        buffer = []
        sections = []

        for line in lines:
            buffer.append(line)

            if re.search(r"[.;:]$", line) or len(" ".join(buffer)) > 500:
                sections.append(" ".join(buffer).strip())
                buffer = []

        if buffer:
            sections.append(" ".join(buffer).strip())

    return sections


def find_station_ids(text):
    """
    Find station IDs from either:
    1. explicit station codes like 05CC002
    2. station name phrases like 'Dickson Dam Tunnel Outlet'
    """
    if not text:
        return []

    found_ids = set()

    explicit_ids = re.findall(r"\b05[A-Z0-9]{5}\b", text, re.IGNORECASE)
    for station_id in explicit_ids:
        station_id = station_id.upper()
        if station_id in STATION_LOOKUP:
            found_ids.add(station_id)

    text_lower = text.lower()
    for station_id, patterns in STATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                found_ids.add(station_id)
                break

    return sorted(found_ids)


def infer_river_from_text(text):
    """
    Determine river from station IDs or river name words inside the same section.
    """
    if not text:
        return None

    station_ids = find_station_ids(text)
    for station_id in station_ids:
        station_info = STATION_LOOKUP.get(station_id)
        if station_info and station_info.get("river"):
            return station_info["river"]

    text_lower = text.lower()
    for river, patterns in RIVER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return river

    return None


def infer_river_with_context(sections, idx):
    """
    Try current section first, then previous section if needed.
    """
    river = infer_river_from_text(sections[idx])
    if river:
        return river

    if idx > 0:
        river = infer_river_from_text(sections[idx - 1])
        if river:
            return river

    return None


def classify_flow_rule(section_text, value):
    """
    Decide rule type from wording, not just from the number.
    """
    s = section_text.lower()

    if "water conservation objective" in s or "wco" in s:
        return "water_conservation_objective"

    if "instream objective" in s or "instream flow objective" in s or re.search(r"\bio\b", s):
        return "instream_objective"

    if "no diversion" in s or "shall not divert" in s or "not divert" in s:
        return "no_diversion"

    if "when the flow is less than" in s or "if the flow is less than" in s:
        return "flow_threshold"

    return "unknown"


def extract_no_diversion_rules(text):
    results = []

    if not text:
        return results

    trigger_phrases = [
        "no diversion",
        "not divert",
        "shall not divert",
        "instream objective",
        "water conservation objective",
        "diversion table",
        "flow is less than"
    ]

    sections = split_into_sections(text)

    for i, section in enumerate(sections):
        section_lower = section.lower()

        if not any(phrase in section_lower for phrase in trigger_phrases):
            continue

        river = infer_river_with_context(sections, i)

        pattern = r'(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'

        for match in re.finditer(pattern, section, re.IGNORECASE):
            value = float(match.group(1))
            rule_type = classify_flow_rule(section, value)

            results.append({
                "rule_type": rule_type,
                "threshold_value": value,
                "units": "m3/s",
                "river": river,
                "station_ids_found": find_station_ids(section),
                "source_text": section[:1500]
            })

    return results


def extract_station_references(text):
    """
    Build station reference rows used later for joining extracted rules
    to station_id and station_name.
    """
    results = []

    if not text:
        return results

    sections = split_into_sections(text)

    for section in sections:
        station_ids = find_station_ids(section)

        for station_id in station_ids:
            station_info = STATION_LOOKUP.get(
                station_id,
                {"river": None, "station_name": None}
            )

            results.append({
                "rule_type": "station_reference",
                "station_id": station_id,
                "station_name": station_info["station_name"],
                "river": station_info["river"],
                "source_text": section[:1500]
            })

    return results


def extract_percent_rules(text):
    results = []

    if not text:
        return results

    sections = split_into_sections(text)

    for i, section in enumerate(sections):
        if "% of the rate of flow" not in section.lower():
            continue

        river = infer_river_with_context(sections, i)
        station_ids = find_station_ids(section)

        band_pattern = (
            r'(\d+)%\s+of the rate of flow.*?'
            r'greater than\s+(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second.*?'
            r'less than or equal to\s+(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'
        )

        upper_pattern = (
            r'(\d+)%\s+of the rate of flow.*?'
            r'(?:up to a maximum diversion rate of\s+(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second.*?)?'
            r'greater than\s+(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'
        )

        found_band = False

        for match in re.finditer(band_pattern, section, re.IGNORECASE | re.DOTALL):
            percent = int(match.group(1))
            flow_min_exclusive = float(match.group(2))
            flow_max_inclusive = float(match.group(3))

            results.append({
                "rule_type": "percent_diversion",
                "percent": percent,
                "flow_min_exclusive": flow_min_exclusive,
                "flow_max_inclusive": flow_max_inclusive,
                "max_diversion_rate": None,
                "units": "m3/s",
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })
            found_band = True

        if not found_band:
            for match in re.finditer(upper_pattern, section, re.IGNORECASE | re.DOTALL):
                percent = int(match.group(1))
                max_diversion_rate = float(match.group(2)) if match.group(2) else None
                flow_min_exclusive = float(match.group(3))

                results.append({
                    "rule_type": "percent_diversion",
                    "percent": percent,
                    "flow_min_exclusive": flow_min_exclusive,
                    "flow_max_inclusive": None,
                    "max_diversion_rate": max_diversion_rate,
                    "units": "m3/s",
                    "river": river,
                    "station_ids_found": station_ids,
                    "source_text": section[:1500]
                })

    return results


def extract_seasonal_rules(text):
    """
    Extract the Red Deer seasonal station applicability clause:
      (a) 05CC002 during open water season
      (b) 05CB007 during winter ice cover season
    """
    results = []

    if not text:
        return results

    text_norm = re.sub(r"\s+", " ", text)

    open_water_pattern = (
        r"05CC002\s*\(Red Deer River at Red Deer\)\s*;?\s*during the open water season"
    )
    winter_ice_pattern = (
        r"05CB007\s*\(Dickson Dam Tunnel Outlet\)\s*;?\s*during the winter ice cover season"
    )

    if re.search(open_water_pattern, text_norm, re.IGNORECASE):
        results.append({
            "rule_type": "seasonal_window",
            "condition_type": "seasonal_station_applicability",
            "season_type": "open_water_season",
            "river": "Red Deer",
            "station_ids_found": ["05CC002"],
            "source_text": text[:1500]
        })

    if re.search(winter_ice_pattern, text_norm, re.IGNORECASE):
        results.append({
            "rule_type": "seasonal_window",
            "condition_type": "seasonal_station_applicability",
            "season_type": "winter_ice_cover_season",
            "river": "Red Deer",
            "station_ids_found": ["05CB007"],
            "source_text": text[:1500]
        })

    return results


def extract_temperature_rules(text):
    """
    Extract temperature-related rules only from text that explicitly mentions temperature.
    Captures:
    - monitoring period (June 1 to October 1)
    - maximum temperature cutoff (22 C)
    - baseline trigger (19 C)
    - monitoring frequency (hourly / daily)
    """
    results = []

    if not text:
        return results

    text_lower = text.lower()
    text_norm = re.sub(r"\s+", " ", text)

    if "temperature" not in text_lower:
        return results

    river = "Blindman"

    date_range_pattern = (
        rf"\bbetween\s+"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})"
        rf"(?:st|nd|rd|th)?\s+"
        rf"and\s+"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})"
        rf"(?:st|nd|rd|th)?\b"
    )

    celsius_pattern = r'(\d+(?:\.\d+)?)\s*(?:°|o)?\s*[cC]\b'

    for match in re.finditer(date_range_pattern, text_norm, re.IGNORECASE):
        results.append({
            "rule_type": "temperature_window",
            "temperature_rule_type": "monitoring_period",
            "start_month": match.group(1).title(),
            "start_day": int(match.group(2)),
            "end_month": match.group(3).title(),
            "end_day": int(match.group(4)),
            "river": river,
            "station_ids_found": [],
            "source_text": text[:1500]
        })

    for match in re.finditer(celsius_pattern, text_norm):
        value = float(match.group(1))

        if value == 22 or (
            "shall not divert" in text_lower and "exceeds" in text_lower and value >= 22
        ):
            temp_rule_type = "temperature_maximum"
        elif value == 19 or "baseline temperature" in text_lower:
            temp_rule_type = "baseline_temperature_trigger"
        else:
            temp_rule_type = "temperature_threshold"

        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": temp_rule_type,
            "temperature_c": value,
            "units": "C",
            "river": river,
            "station_ids_found": [],
            "source_text": text[:1500]
        })

    if re.search(r"\bhourly\b", text_norm, re.IGNORECASE):
        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": "temperature_monitoring_frequency",
            "frequency": "hourly",
            "frequency_condition": "baseline temperature > 19 C",
            "river": river,
            "station_ids_found": [],
            "source_text": text[:1500]
        })

    if re.search(r"\bdaily\b", text_norm, re.IGNORECASE):
        results.append({
            "rule_type": "temperature_rule",
            "temperature_rule_type": "temperature_monitoring_frequency",
            "frequency": "daily",
            "frequency_condition": "previous temperature measurement < 19 C",
            "river": river,
            "station_ids_found": [],
            "source_text": text[:1500]
        })

    return results
