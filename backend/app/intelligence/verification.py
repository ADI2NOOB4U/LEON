from __future__ import annotations

from typing import Any


def verify_result(result: Any, strategy: str = "result") -> bool:
    """Conservative generic verifier used by adapters until tool-specific checks run."""
    if strategy == "playback_state":
        return bool(isinstance(result, dict) and result.get("success") and result.get("state") == "PLAYING")
    if isinstance(result, dict) and "success" in result:
        return bool(result["success"])
    return result is not None
