import re


SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|pk)_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*\S+", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9._-]{10,}\b"),
)


def contains_secret(value: object) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def assert_safe_memory(value: object) -> None:
    if contains_secret(value):
        raise ValueError("Secrets, credentials, tokens, and API keys cannot be stored in memory")

