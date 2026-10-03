"""Fail-closed guards around untrusted web input and outbound requests."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit


class WebSecurityError(ValueError):
    """A request cannot safely be sent to the public web."""


_CREDENTIAL_LABEL = (
    r"[A-Z0-9_.-]*(?:api[_ -]?key|access[_ -]?key|client[_ -]?secret|"
    r"secret|password|passwd|passphrase|token|authorization|credential|"
    r"private[_ -]?key|refresh[_ -]?token)[A-Z0-9_.-]*"
)
_PRIVATE_KEY_LABEL = (
    r"(?:(?:RSA|EC|OPENSSH|DSA|ENCRYPTED|PGP) )?PRIVATE KEY(?: BLOCK)?"
)

SECRET_PATTERNS = (
    re.compile(
        r"(?im)(?P<prefix>\b[A-Z0-9_.-]*(?:password|passwd|passphrase)"
        r"[A-Z0-9_.-]*\s*(?:[:=]|\bis\b)\s*)(?:\"(?P<quoted_double>[^\r\n\"]+)\"|"
        r"'(?P<quoted_single>[^\r\n']+)'|(?P<secret>[^\r\n]+))"
    ),
    re.compile(
        r"(?i)(?P<prefix>\b(?:authorization\s*[:=]\s*(?:Bearer|Basic)\s+|"
        + _CREDENTIAL_LABEL
        + r"\s*[:=]\s*)(?:\")(?P<quoted_double>[^\r\n\"]+)(?:\"|$)|"
        r"\b(?:authorization\s*[:=]\s*(?:Bearer|Basic)\s+|"
        + _CREDENTIAL_LABEL
        + r"\s*[:=]\s*)(?:')(?P<quoted_single>[^\r\n']+)(?:'|$)|"
        r"\b(?:authorization\s*[:=]\s*(?:Bearer|Basic)\s+|"
        + _CREDENTIAL_LABEL
        + r"\s*[:=]\s*)(?P<secret>[^\s,;]+))"
    ),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|bearer[_ -]?token|"
        r"password|passwd|secret|credential|private[_ -]?key)\s+is\s+"
        r"(?P<secret>[^\s,;]+)"
    ),
    re.compile(r"(?i)\b(?:Bearer|Basic)\s+(?P<secret>[A-Za-z0-9._~+/=-]{8,})"),
    re.compile(
        r"\b(?P<secret>eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
        r"[A-Za-z0-9_-]{8,})\b"
    ),
    re.compile(
        rf"(?is)(?P<prefix>-----BEGIN {_PRIVATE_KEY_LABEL}-----\s*)"
        rf"(?P<secret>.*?)(?P<suffix>-----END {_PRIVATE_KEY_LABEL}-----)"
    ),
    re.compile(
        rf"(?is)(?P<prefix>-----BEGIN {_PRIVATE_KEY_LABEL}-----\s*)"
        rf"(?![\s\S]*?-----END {_PRIVATE_KEY_LABEL}-----)"
        r"(?P<secret>.+)$"
    ),
    re.compile(
        r"(?i)\b(?P<secret>(?:sk-(?:proj-|live_|test_)?[A-Za-z0-9_-]{16,}|"
        r"AIza[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|"
        r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
        r"ASIA[0-9A-Z]{16}|ya29\.[A-Za-z0-9._-]{20,}|"
        r"sk_(?:live|test)_[A-Za-z0-9]{16,}))\b"
    ),
    re.compile(
        r"(?i)(?P<prefix>\bhttps?://[^:/@\s]+:)(?P<secret>[^@/\s]+)(?P<suffix>@)"
    ),
)

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(?:all|any|the)\s+previous\s+instructions"),
    re.compile(r"(?i)(?:system|developer)\s+message\s*[:=]"),
    re.compile(r"(?i)read\s+.*(?:\.env|api[_ -]?key|password|secret)"),
    re.compile(r"(?i)(?:run|execute)\s+(?:powershell|cmd|bash|shell)"),
)


def _secret_group(match: re.Match[str]) -> tuple[int, int] | None:
    for name in ("secret", "quoted_double", "quoted_single"):
        span = match.span(name)
        if span != (-1, -1):
            return span
    return None


def redact_secrets(value: str) -> tuple[str, bool]:
    """Redact detected credential values while preserving their surrounding text."""
    detected = False
    text = value

    for pattern in SECRET_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            nonlocal detected
            span = _secret_group(match)
            if span is None:
                return match.group(0)
            detected = True
            start, end = span
            return match.group(0)[:start - match.start()] + "[REDACTED]" + match.group(0)[end - match.start():]

        text = pattern.sub(replace, text)

    return text, detected


def redact_task_text(value: str | None) -> str:
    """Normalize task-related strings before persisting them."""
    if value is None:
        return ""
    text, _ = redact_secrets(str(value))
    return text


def contains_secret(value: object) -> bool:
    text = value if isinstance(value, str) else repr(value)
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def assert_safe_outbound_text(value: str, category: str = "request") -> str:
    if contains_secret(value):
        raise WebSecurityError(f"SECRET_DETECTED: blocked outbound {category}")
    return value


def _blocked_ip(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_unspecified or address.is_reserved or address.is_multicast
    )


def validate_public_url(url: str, *, resolve_dns: bool = True) -> str:
    if not isinstance(url, str) or not url.strip():
        raise WebSecurityError("INVALID_URL: URL must be a non-empty string")
    value = url.strip()
    if any(character.isspace() for character in value) or "\\" in value or "\x00" in value:
        raise WebSecurityError("INVALID_URL: URL contains invalid characters")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise WebSecurityError("INVALID_URL: only HTTP(S) URLs are allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise WebSecurityError("INVALID_URL: invalid port") from exc
    if port is not None and not 0 < port < 65536:
        raise WebSecurityError("INVALID_URL: invalid port")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(".localhost"):
        raise WebSecurityError("SSRF_BLOCKED: internal hostname")
    if _blocked_ip(host):
        raise WebSecurityError("SSRF_BLOCKED: private or local address")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise WebSecurityError("SOURCE_UNAVAILABLE: hostname could not be resolved") from exc
        if any(_blocked_ip(address) for address in addresses):
            raise WebSecurityError("SSRF_BLOCKED: hostname resolves to a private or local address")
    return value


def inspect_untrusted_content(text: str) -> dict[str, object]:
    """Classify page text; never turn its instructions into executable input."""
    matches = [pattern.pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern.search(text)]
    return {"untrusted": True, "prompt_injection_detected": bool(matches), "signals": matches}
