import re


STATION_LOOKUP = {
    "05CC001": {
        "river": "Blindman River",
        "station_name": "Blindman River near Blackfalds"
    },
    "05CC002": {
        "river": "Red Deer River",
        "station_name": "Red Deer River at Red Deer"
    },
    "05CB007": {
        "river": "Red Deer River",
        "station_name": "Dickson Dam Tunnel Outlet"
    }
}


def extract_no_diversion_rules(text):
    results = []

    if not text:
        return results

    text_lower = text.lower()

    trigger_phrases = [
        "no diversion",
        "not divert",
        "shall not divert",
        "instream objective",
        "water conservation objective",
        "diversion table"
    ]

    if not any(phrase in text_lower for phrase in trigger_phrases):
        return results

    pattern = r'(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'

    for match in re.finditer(pattern, text, re.IGNORECASE):
       value = float(match.group(1))

        # Assign river
        if value in [0, 0.16, 0.5]:
            river = "Blindman River"
        elif value == 16:
            river = "Red Deer River"
        else:
            river = None
        
        # Assign rule meaning
        if value == 0:
            rule_type = "no_diversion"
        elif value == 0.16:
            rule_type = "instream_objective"
        elif value == 0.5:
            rule_type = "flow_threshold"
        elif value == 16:
            rule_type = "water_conservation_objective"
        else:
            rule_type = "unknown"
        
        results.append({
            "rule_type": rule_type,
            "threshold_value": value,
            "units": "m3/s",
            "river": river,
            "source_text": text[:1500]
        })

    return results


def extract_station_references(text):
    results = []

    if not text:
        return results

    pattern = r'\b05[A-Z0-9]{5}\b'

    for match in re.finditer(pattern, text):
        station_id = match.group(0)
        station_info = STATION_LOOKUP.get(
            station_id,
            {"river": None, "station_name": None}
        )

        results.append({
            "rule_type": "station_reference",
            "station_id": station_id,
            "station_name": station_info["station_name"],
            "river": station_info["river"],
            "source_text": text[:1500]
        })

    return results
