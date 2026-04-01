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


def split_into_sections(text):
    """
    Split PDF text into paragraph-like sections.
    This uses blank lines first, then falls back to line groups if needed.
    """
    if not text:
        return []

    # Normalize line endings and spacing
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    # First try true paragraph breaks
    sections = [s.strip() for s in re.split(r"\n\s*\n+", text) if s.strip()]

    # Fallback if PDF text is flattened and has no blank lines
    if len(sections) <= 1:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        buffer = []
        sections = []

        for line in lines:
            buffer.append(line)

            # End a section when line ends with punctuation or gets long enough
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

    # 1. Strongest evidence: station IDs
    station_ids = find_station_ids(text)
    for station_id in station_ids:
        station_info = STATION_LOOKUP.get(station_id)
        if station_info and station_info.get("river"):
            return station_info["river"]

    # 2. Next best: river name keywords
    text_lower = text.lower()
    for river, patterns in RIVER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
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

    for section in sections:
        section_lower = section.lower()

        if not any(phrase in section_lower for phrase in trigger_phrases):
            continue

        river = infer_river_from_text(section)

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

    for section in sections:
        pattern = r'(\d+)%\s+of the rate of flow'

        for match in re.finditer(pattern, section, re.IGNORECASE):
            percent = int(match.group(1))
            river = infer_river_from_text(section)

            results.append({
                "rule_type": "percent_diversion",
                "percent": percent,
                "river": river,
                "station_ids_found": find_station_ids(section),
                "source_text": section[:1500]
            })

    return results
