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

SEASON_PATTERNS = {
    "spring": r"\bspring\b",
    "summer": r"\bsummer\b",
    "fall": r"\bfall\b|\bautumn\b",
    "winter": r"\bwinter\b",
    "ice_free_season": r"\bice[- ]?free season\b",
    "open_water_season": r"\bopen water season\b",
    "winter_ice_cover_season": r"\bwinter ice cover season\b"
}


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


def classify_seasonal_condition(section_text):
    """
    Decide what the seasonal rule is actually saying.
    """
    s = section_text.lower()

    if "shall not divert" in s or "no diversion" in s or "not divert" in s:
        return "diversion_prohibited_in_season"

    if "may only divert" in s or "only divert" in s or "diversion may occur" in s:
        return "diversion_allowed_in_season"

    if "diversion is permitted" in s or "may divert" in s:
        return "diversion_allowed_in_season"

    if "monitor" in s or "measurement" in s or "record" in s:
        return "monitoring_required_in_season"

    return "seasonal_condition_unknown"


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
    pattern = r'(\d+)%\s+of the rate of flow'

    for i, section in enumerate(sections):
        for match in re.finditer(pattern, section, re.IGNORECASE):
            percent = int(match.group(1))
            river = infer_river_with_context(sections, i)

            results.append({
                "rule_type": "percent_diversion",
                "percent": percent,
                "river": river,
                "station_ids_found": find_station_ids(section),
                "source_text": section[:1500]
            })

    return results


def extract_seasonal_rules(text):
    """
    Extract true seasonal station applicability rules only.
    This is specifically for clauses like:
      (a) Station 05CC002 ... during the open water season; or
      (b) Station 05CB007 ... during the winter ice cover season;
    """
    results = []

    if not text:
        return results

    sections = split_into_sections(text)

    for i, section in enumerate(sections):
        section_lower = section.lower()

        if "season" not in section_lower:
            continue

        river = infer_river_with_context(sections, i)

        station_season_patterns = [
            (
                r"(?:station\s+)?05CC002\b.*?(?:red deer river at red deer)?.*?during the open water season",
                "05CC002",
                "open_water_season"
            ),
            (
                r"(?:station\s+)?05CB007\b.*?(?:dickson dam tunnel outlet)?.*?during the winter ice cover season",
                "05CB007",
                "winter_ice_cover_season"
            ),
            (
                r"(?:station\s+)?05CC001\b.*?(?:blindman river near blackfalds)?.*?during the open water season",
                "05CC001",
                "open_water_season"
            ),
        ]

        found_any = False

        for pattern, station_id, season_type in station_season_patterns:
            if re.search(pattern, section, re.IGNORECASE | re.DOTALL):
                results.append({
                    "rule_type": "seasonal_window",
                    "condition_type": "seasonal_station_applicability",
                    "season_type": season_type,
                    "river": STATION_LOOKUP.get(station_id, {}).get("river", river),
                    "station_ids_found": [station_id],
                    "source_text": section[:1500]
                })
                found_any = True

        if not found_any:
            if re.search(r"\bopen water season\b", section, re.IGNORECASE):
                results.append({
                    "rule_type": "seasonal_window",
                    "condition_type": "seasonal_station_applicability",
                    "season_type": "open_water_season",
                    "river": river,
                    "station_ids_found": find_station_ids(section),
                    "source_text": section[:1500]
                })
            elif re.search(r"\bwinter ice cover season\b", section, re.IGNORECASE):
                results.append({
                    "rule_type": "seasonal_window",
                    "condition_type": "seasonal_station_applicability",
                    "season_type": "winter_ice_cover_season",
                    "river": river,
                    "station_ids_found": find_station_ids(section),
                    "source_text": section[:1500]
                })

    return results


def extract_temperature_rules(text):
    """
    Extract temperature-related rules only from sections that explicitly mention temperature.
    Captures:
    - monitoring period (June 1 to October 1)
    - maximum temperature cutoff (22 C)
    - baseline trigger (19 C)
    - monitoring frequency (hourly / daily) only within temperature sections
    """
    results = []

    if not text:
        return results

    sections = split_into_sections(text)

    date_range_pattern = (
        rf"\b(?:between|from|during|for)?\s*"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})"
        rf"(?:st|nd|rd|th)?"
        rf"\s*(?:,)?\s*(?:and|to|through|-)\s*"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})"
        rf"(?:st|nd|rd|th)?\b"
    )

    celsius_pattern = r'(\d+(?:\.\d+)?)\s*(?:o\s*)?[cC]\b'

    for i, section in enumerate(sections):
        section_lower = section.lower()

        if "temperature" not in section_lower:
            continue

        river = infer_river_with_context(sections, i)
        station_ids = find_station_ids(section)

        for match in re.finditer(date_range_pattern, section, re.IGNORECASE):
            results.append({
                "rule_type": "temperature_window",
                "temperature_rule_type": "monitoring_period",
                "start_month": match.group(1).title(),
                "start_day": int(match.group(2)),
                "end_month": match.group(3).title(),
                "end_day": int(match.group(4)),
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })

        for match in re.finditer(celsius_pattern, section):
            value = float(match.group(1))

            if value == 22 or (
                "shall not divert" in section_lower and "exceeds" in section_lower and value >= 22
            ):
                temp_rule_type = "temperature_maximum"
            elif value == 19 or "baseline temperature" in section_lower:
                temp_rule_type = "baseline_temperature_trigger"
            else:
                temp_rule_type = "temperature_threshold"

            results.append({
                "rule_type": "temperature_rule",
                "temperature_rule_type": temp_rule_type,
                "temperature_c": value,
                "units": "C",
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })

        if re.search(r"\bhourly\b", section, re.IGNORECASE):
            results.append({
                "rule_type": "temperature_rule",
                "temperature_rule_type": "temperature_monitoring_frequency",
                "frequency": "hourly",
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })

        if re.search(r"\bdaily\b", section, re.IGNORECASE):
            results.append({
                "rule_type": "temperature_rule",
                "temperature_rule_type": "temperature_monitoring_frequency",
                "frequency": "daily",
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })

    return results
