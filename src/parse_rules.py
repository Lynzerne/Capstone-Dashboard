import re

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
