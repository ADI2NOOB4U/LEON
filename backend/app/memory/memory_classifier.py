import re


def classify_candidate(text: str) -> dict:
    explicit = bool(re.search(r"\b(?:remember|don't forget|my .* is)\b", text, re.I))
    return {"candidate": text.strip(), "explicit": explicit, "relevance": 1.0 if explicit else 0.0}

