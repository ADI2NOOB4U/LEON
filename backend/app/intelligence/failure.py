from __future__ import annotations

from enum import StrEnum


class FailureType(StrEnum):
    TRANSIENT = "TRANSIENT"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY = "DEPENDENCY"
    LOGIC = "LOGIC"
    PERMISSION = "PERMISSION"
    AUTHENTICATION = "AUTHENTICATION"
    PROVIDER = "PROVIDER"
    TIMEOUT = "TIMEOUT"
    RESOURCE = "RESOURCE"
    UNKNOWN = "UNKNOWN"


def classify_failure(error: BaseException | str) -> FailureType:
    text = str(error).lower()
    if isinstance(error, PermissionError) or "permission" in text or "action_blocked" in text:
        return FailureType.PERMISSION
    if "auth" in text or "not authorized" in text or "token" in text:
        return FailureType.AUTHENTICATION
    if "timeout" in text or "timed out" in text:
        return FailureType.TIMEOUT
    if "depend" in text or "module not found" in text:
        return FailureType.DEPENDENCY
    if "provider" in text or "unavailable" in text:
        return FailureType.PROVIDER
    if "memory" in text or "resource" in text or "no space" in text:
        return FailureType.RESOURCE
    if "config" in text or "invalid" in text:
        return FailureType.CONFIGURATION
    if "assert" in text or "test" in text or "verification" in text:
        return FailureType.LOGIC
    if "network" in text or "connection" in text or "429" in text:
        return FailureType.TRANSIENT
    return FailureType.UNKNOWN
