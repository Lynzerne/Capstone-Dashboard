import re

def extract_no_diversion_rules(text):
    results = []

    if not text:
        return results

    text_lower = text.lower()

    # Trigger only on pages that look relevant
    trigger_phrases = [
        "no diversion",
        "not divert",
        "shall not divert",
        "instream objective",
        "diversion table"
    ]

    if any(phrase in text_lower for phrase in trigger_phrases):
        pattern = r'(\d+(?:\.\d+)?)\s*cubic\s*meters?\s*per\s*second'

        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = float(match.group(1))

            results.append({
                "rule_type": "flow_rule_candidate",
                "threshold_value": value,
                "units": "m3/s",
                "source_text": text[:1500]
            })

    return results
