"""Small, deterministic verifiers used by mission steps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def verify_step(step: dict[str, Any], result: Any) -> tuple[bool, str]:
    method = str(step.get("verification_method") or "result").lower()
    expected = step.get("expected_result")
    if method in {"result", "command_result"}:
        passed = result is not None and (not isinstance(result, dict) or result.get("success", True) is not False)
    elif method == "file_exists":
        path = (step.get("arguments") or {}).get("path")
        passed = bool(path and Path(str(path)).is_file())
    elif method == "file_content":
        args = step.get("arguments") or {}
        path, needle = args.get("path"), expected or args.get("contains")
        passed = bool(path and needle and Path(str(path)).is_file() and str(needle) in Path(str(path)).read_text(encoding="utf-8"))
    elif method == "test_pass":
        passed = isinstance(result, dict) and result.get("exit_code") == 0 and not result.get("timed_out", False)
    elif method == "model_response_valid":
        try:
            json.loads(result if isinstance(result, str) else json.dumps(result))
            passed = True
        except (TypeError, ValueError, json.JSONDecodeError):
            passed = False
    elif method == "text_match":
        passed = expected is not None and str(expected).lower() in str(result).lower()
    else:
        passed = bool(result)
    return passed, ("verification passed" if passed else f"verification failed ({method})")
