"""Prevent automatic cloud routing of private or local-only request content."""

from __future__ import annotations

import re
from typing import Any

from backend.app.security.web_security import contains_secret


_PRIVATE_REQUEST = re.compile(
    r"(?i)\b(?:private|confidential|sensitive|personal|medical|health|"
    r"password|passwd|secret|credential|token|api[_ -]?key|"
    r"camera|microphone|recording|audio|photo|picture|image|screenshot|"
    r"attachment|document|file|workspace|local path|source code|"
    r"address|ssn|social security|credit card|bank account|appointment|"
    r"calendar|schedule|financial|tax|legal|my|mine|our|ours)\b|"
    r"\.env\b|[A-Z]:\\|\\\\[^\\/\s]+\\|"
    r"(?:^|\s)/(?:Users|home|private|etc|var|workspace)/"
)


class CloudPrivacyError(ValueError):
    """Raised when a request is not safe to send to a cloud provider."""


def is_safe_public_cloud_text(text: str) -> bool:
    return bool(
        isinstance(text, str)
        and text.strip()
        and not contains_secret(text)
        and not _PRIVATE_REQUEST.search(text)
    )


def public_cloud_input(messages: list[dict[str, Any]]) -> str:
    """Return only the latest direct user text after applying the privacy gate."""
    latest_user_text = next(
        (
            item.get("content")
            for item in reversed(messages)
            if isinstance(item, dict) and item.get("role") == "user"
        ),
        None,
    )
    if not is_safe_public_cloud_text(latest_user_text):
        raise CloudPrivacyError(
            "Cloud routing is blocked for private, sensitive, or non-text requests."
        )
    return latest_user_text.strip()
