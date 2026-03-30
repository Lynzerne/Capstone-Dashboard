import re

def extract_no_diversion_rules(text):
    results = []

    if not text:
        return results

    pattern = r'(\d+\.\d+)\s*cubic meters per second'

    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        value = float(match.group(1))
        window = text[max(0, match.start()-120):match.end()+120].lower()

        if "not divert" in window or "no diversion" in window:
            results.append({
                "rule_type": "no diversion",
                "threshold_value": value,
                "units": "m3/s",
                "source_text": window
            })

    return results
