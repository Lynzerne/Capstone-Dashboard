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
    "open_water_season": r"\bopen water season\b"
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
    if not text:
        return []

    return re.findall(r"\b05[A-Z0-9]{5}\b", text)


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

    for i, section in enumerate(sections):
        pattern = r'(\d+)%\s+of the rate of flow'

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
    results = []

    if not text:
        return results

    sections = split_into_sections(text)

    date_range_pattern = (
        rf"\b(?:between|from|during|for)?\s*"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})"
        rf"\s*(?:,)?\s*(?:and|to|through|-)\s*"
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})\b"
    )

    seasonal_trigger_phrases = [
        "between",
        "from",
        "during",
        "season",
        "spring",
        "summer",
        "fall",
        "autumn",
        "winter",
        "ice-free",
        "ice free",
        "open water"
    ]

    for i, section in enumerate(sections):
        section_lower = section.lower()

        if not any(phrase in section_lower for phrase in seasonal_trigger_phrases):
            continue

        river = infer_river_with_context(sections, i)
        station_ids = find_station_ids(section)
        condition_type = classify_seasonal_condition(section)

        found_any = False

        for match in re.finditer(date_range_pattern, section, re.IGNORECASE):
            start_month = match.group(1)
            start_day = int(match.group(2))
            end_month = match.group(3)
            end_day = int(match.group(4))

            results.append({
                "rule_type": "seasonal_window",
                "condition_type": condition_type,
                "season_type": "date_range",
                "start_month": start_month.title(),
                "start_day": start_day,
                "end_month": end_month.title(),
                "end_day": end_day,
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })
            found_any = True

        for season_name, pattern in SEASON_PATTERNS.items():
            if re.search(pattern, section, re.IGNORECASE):
                results.append({
                    "rule_type": "seasonal_window",
                    "condition_type": condition_type,
                    "season_type": season_name,
                    "river": river,
                    "station_ids_found": station_ids,
                    "source_text": section[:1500]
                })
                found_any = True

        if found_any and re.search(r"\bshall\b|\bmust\b|\bonly\b|\bnot\b|\bprohibited\b", section, re.IGNORECASE):
            results.append({
                "rule_type": "seasonal_condition_text",
                "condition_type": condition_type,
                "river": river,
                "station_ids_found": station_ids,
                "source_text": section[:1500]
            })

    return results
