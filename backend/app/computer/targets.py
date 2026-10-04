from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import uuid
from typing import Any, List, Optional

from backend.app.computer.schemas import (
    ScreenInfo,
    TargetBounds,
    TargetLocation,
    VisualTarget,
)


_ELEMENT_PATTERNS = [
    re.compile(r"(?:button|btn)[\s:\"\']+([A-Za-z0-9_\- ]+)[\s:\"\']*(?:at|coords?|loc)?[\s\(\[\{]*(\d+)[,\s]+(\d+)", re.IGNORECASE),
    re.compile(r"([A-Za-z0-9_\- ]+)\s+(?:button|tab|menu|icon)\s+(?:at|coords?|loc)?[\s\(\[\{]*(\d+)[,\s]+(\d+)", re.IGNORECASE),
    re.compile(r"error[\s:\"\']+([A-Za-z0-9_\-:\. ]+)", re.IGNORECASE),
]


def parse_targets_from_vision(
    vision_text: str,
    screen: ScreenInfo,
    app_context: str | None = None,
) -> List[VisualTarget]:
    """Extract structured VisualTarget objects from Vision model text or JSON."""
    targets: List[VisualTarget] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    if not vision_text or not vision_text.strip():
        return targets

    # Try extracting JSON array or object
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", vision_text)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            elements_data = []
            if isinstance(parsed, dict):
                elements_data = parsed.get("elements", parsed.get("targets", []))
            elif isinstance(parsed, list):
                elements_data = parsed

            for item in elements_data:
                if isinstance(item, dict):
                    label = str(item.get("label", item.get("name", item.get("text", "element")))).strip()
                    elem_type = str(item.get("type", item.get("category", "element"))).lower()
                    loc_data = item.get("location", item.get("coords", item.get("point", {})))
                    x = int(loc_data.get("x", 100)) if isinstance(loc_data, dict) else 100
                    y = int(loc_data.get("y", 100)) if isinstance(loc_data, dict) else 100
                    conf = float(item.get("confidence", 0.9))

                    bounds_data = item.get("bounds", item.get("box"))
                    bounds = None
                    if isinstance(bounds_data, dict):
                        bounds = TargetBounds(
                            left=int(bounds_data.get("left", bounds_data.get("x", x))),
                            top=int(bounds_data.get("top", bounds_data.get("y", y))),
                            width=int(bounds_data.get("width", bounds_data.get("w", 50))),
                            height=int(bounds_data.get("height", bounds_data.get("h", 20))),
                        )

                    targets.append(
                        VisualTarget(
                            id=f"target_{uuid.uuid4().hex[:8]}",
                            label=label,
                            type=elem_type,
                            location=TargetLocation(x=min(x, screen.width), y=min(y, screen.height)),
                            bounds=bounds,
                            confidence=max(0.1, min(1.0, conf)),
                            freshness_timestamp=now_iso,
                            app_context=app_context,
                            raw_text=str(item),
                        )
                    )
        except Exception:
            pass

    # Pattern-based extraction fallback if no JSON targets found
    if not targets:
        lines = vision_text.splitlines()
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            # Detect error lines
            if "error" in line_str.lower() or "traceback" in line_str.lower() or "failed" in line_str.lower():
                targets.append(
                    VisualTarget(
                        id=f"error_{idx}",
                        label=line_str[:120],
                        type="error",
                        location=TargetLocation(x=screen.width // 2, y=min(screen.height - 100, 200 + idx * 30)),
                        confidence=0.88,
                        freshness_timestamp=now_iso,
                        app_context=app_context,
                        raw_text=line_str,
                    )
                )
            # Detect UI buttons or common keywords
            elif any(kw in line_str.lower() for kw in ("button", "menu", "tab", "input", "file", "terminal", "run", "debug")):
                targets.append(
                    VisualTarget(
                        id=f"ui_{idx}",
                        label=line_str.strip("-*# ")[:80],
                        type="button" if "run" in line_str.lower() or "button" in line_str.lower() else "element",
                        location=TargetLocation(x=screen.width // 4, y=min(screen.height - 50, 100 + idx * 40)),
                        confidence=0.75,
                        freshness_timestamp=now_iso,
                        app_context=app_context,
                        raw_text=line_str,
                    )
                )

    return targets[:30]


def find_target_by_query(
    targets: List[VisualTarget],
    query: str,
    target_type: Optional[str] = None,
) -> Optional[VisualTarget]:
    """Find the best matching visual target for a given textual query or intention."""
    if not targets or not query:
        return None

    query_norm = query.strip().lower()
    best_target = None
    best_score = 0.0

    for target in targets:
        if target_type and target.type.lower() != target_type.lower():
            continue

        label_norm = target.label.lower()
        score = 0.0

        # Exact match
        if query_norm == label_norm:
            score = 1.0
        # Substring match
        elif query_norm in label_norm or label_norm in query_norm:
            score = 0.8
        # Token overlap
        else:
            q_tokens = set(re.findall(r"\w+", query_norm))
            t_tokens = set(re.findall(r"\w+", label_norm))
            if q_tokens and t_tokens:
                overlap = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
                score = overlap * 0.7

        score *= target.confidence

        if score > best_score and score >= 0.35:
            best_score = score
            best_target = target

    return best_target
