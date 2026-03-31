import re


def extract_no_diversion_rules(text):
    results = []

    if not text:
        return results

    text_lower = text.lower()

    pattern = r'(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'

    for match in re.finditer(pattern, text, re.IGNORECASE):
        value = float(match.group(1))

        river = None

        if "blindman river" in text_lower:
            river = "Blindman River"
        elif "red deer river" in text_lower:
            river = "Red Deer River"

        results.append({
            "rule_type": "flow_rule_candidate",
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
        results.append({
            "rule_type": "station_reference",
            "station_id": match.group(0),
            "source_text": text[:1500]
        })

    return results
