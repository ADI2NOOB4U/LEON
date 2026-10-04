from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.db.database import get_connection, now
from backend.app.security.permissions import PermissionLevel, PermissionManager
from backend.app.security.web_security import redact_secrets, validate_public_url

_INJECTION_PATTERNS = [
    re.compile(r"\b(?:ignore\s+(?:all\s+)?(?:previous\s+)?instructions|system\s+prompt|new\s+system\s+instruction)\b", re.IGNORECASE),
    re.compile(r"\b(?:you\s+must\s+now|override\s+all\s+rules|jailbreak|disregard\s+safety)\b", re.IGNORECASE),
    re.compile(r"\b(?:exfiltrate|send\s+tokens|reveal\s+passwords?|disable\s+security|bypass\s+permissions?)\b", re.IGNORECASE),
    re.compile(r"\b(?:execute|run)\s+(?:bash|shell|powershell)\b.*\brm\s+-rf\b", re.IGNORECASE),
]

_TOOL_RISK_MAP = {
    "get_datetime": "LOW",
    "system_stats": "LOW",
    "list_processes": "LOW",
    "open_app": "MEDIUM",
    "open_url": "LOW",
    "fs_read": "LOW",
    "fs_write": "MEDIUM",
    "fs_delete": "HIGH",
    "coding_execute": "HIGH",
    "git_status": "LOW",
    "git_commit": "MEDIUM",
    "email_send": "HIGH",
    "media_control": "LOW",
}


class SecurityKernel:
    """The central agent security kernel governing authorization, risk, prompt injection, and auditing."""

    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permissions = permission_manager or PermissionManager()

    def score_risk(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        base_risk = _TOOL_RISK_MAP.get(tool_name, "MEDIUM")
        args = arguments or {}

        # Inspect arguments for sensitive or risky indicators
        args_str = json.dumps(args, default=str).lower()
        if "delete" in args_str or "remove" in args_str or "drop" in args_str:
            return "HIGH" if base_risk != "BLOCKED" else "BLOCKED"
        if "password" in args_str or "token" in args_str or "secret" in args_str:
            return "HIGH"
        return base_risk

    def detect_prompt_injection(self, text: str) -> Tuple[bool, str]:
        """Detect prompt injection attempts in user input, visual text, or retrieved documents."""
        if not text:
            return False, "Clean"
        for pat in _INJECTION_PATTERNS:
            if pat.search(text):
                return True, "Potential prompt injection directive detected"
        return False, "Clean"

    def authorize(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        confirmed: bool = False,
    ) -> Tuple[bool, str, str]:
        """Evaluate whether a tool execution is authorized under the active policy."""
        risk = self.score_risk(tool_name, arguments)
        args_str = json.dumps(arguments or {}, default=str)

        # Check prompt injection in arguments
        is_inj, reason = self.detect_prompt_injection(args_str)
        if is_inj:
            self.record_audit(
                action="authorize",
                tool=tool_name,
                risk="BLOCKED",
                decision="REJECTED_PROMPT_INJECTION",
                authorized=False,
                verified=False,
                details={"reason": reason},
            )
            return False, "BLOCKED", f"Security violation: {reason}"

        if risk == "BLOCKED":
            self.record_audit(
                action="authorize",
                tool=tool_name,
                risk=risk,
                decision="BLOCKED",
                authorized=False,
                verified=False,
                details={"reason": "Action is permanently blocked"},
            )
            return False, risk, f"Action '{tool_name}' is blocked by security policy."

        if risk == "HIGH" and not confirmed:
            self.record_audit(
                action="authorize",
                tool=tool_name,
                risk=risk,
                decision="CONFIRMATION_REQUIRED",
                authorized=False,
                verified=False,
                details={"reason": "High-risk action requires confirmation"},
            )
            return False, risk, f"Action '{tool_name}' requires explicit confirmation."

        self.record_audit(
            action="authorize",
            tool=tool_name,
            risk=risk,
            decision="ALLOWED",
            authorized=True,
            verified=True,
            details={"confirmed": confirmed},
        )
        return True, risk, "Authorized"

    def record_audit(
        self,
        action: str,
        tool: Optional[str],
        risk: str,
        decision: str,
        authorized: bool = True,
        verified: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write an entry to the local security audit trail with redacted payloads."""
        ts = now()
        details_safe = {}
        if details:
            details_str = json.dumps(details, default=str)
            redacted_str, _ = redact_secrets(details_str)
            try:
                details_safe = json.loads(redacted_str)
            except Exception:
                details_safe = {"raw": redacted_str}

        try:
            conn = get_connection()
            conn.execute(
                """
                INSERT INTO security_audit(timestamp, action, tool, risk, decision, authorized, verified, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, action, tool, risk, decision, int(authorized), int(verified), json.dumps(details_safe)),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM security_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("details"):
                try:
                    d["details"] = json.loads(d["details"])
                except Exception:
                    pass
            results.append(d)
        return results


security_kernel = SecurityKernel()

