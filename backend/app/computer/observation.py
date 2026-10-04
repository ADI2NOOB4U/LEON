from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import time
import uuid
from typing import Deque, Dict, List, Optional, Tuple

from backend.app.computer.schemas import (
    Observation,
    ScreenInfo,
    VisualTarget,
)
from backend.app.computer.safety import sanitize_visual_data
from backend.app.computer.targets import parse_targets_from_vision
from backend.app.computer.windows import get_active_window_info, list_running_applications
from backend.app.vision.screen import ScreenCaptureError, capture_screen
from backend.app.vision.service import VisionService, VisionError


class ObservationService:
    """Provides bounded, privacy-respecting local screen and OS observation."""

    def __init__(self, vision_service: Optional[VisionService] = None, max_history: int = 5):
        self._vision = vision_service or VisionService()
        self._history: Deque[Observation] = deque(maxlen=max_history)
        self._image_cache: Dict[str, bytes] = {}  # temporary memory cache, keyed by observation id

    def get_latest(self) -> Optional[Observation]:
        return self._history[-1] if self._history else None

    def get_by_id(self, obs_id: str) -> Optional[Observation]:
        for obs in self._history:
            if obs.id == obs_id:
                return obs
        return None

    def get_cached_image(self, obs_id: str) -> Optional[bytes]:
        return self._image_cache.get(obs_id)

    async def observe(
        self,
        include_vision: bool = True,
        prompt: str | None = None,
        mode: str = "screen",
    ) -> Observation:
        """Capture the current computer and screen state."""
        obs_id = f"obs_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        diagnostics: List[str] = []

        # 1. OS & Window observation
        win_info = get_active_window_info()
        running_apps = list_running_applications()
        active_app = win_info.get("display_name")
        active_win = win_info.get("title")

        # 2. Local screen capture
        screenshot_data = None
        screenshot_mime = "image/png"
        width = 1920
        height = 1080
        screenshot_available = False

        try:
            screenshot_data, screenshot_mime, width, height = capture_screen()
            screenshot_available = True
            diagnostics.append(f"Screen captured ({width}x{height})")
        except ScreenCaptureError as exc:
            diagnostics.append(f"Screen capture unavailable in current session: {exc}")
        except Exception as exc:
            diagnostics.append(f"Screen capture error: {exc}")

        screen_info = ScreenInfo(
            width=width,
            height=height,
            scale_factor=1.0,
            is_captured=screenshot_available,
        )

        # 3. Vision analysis & target extraction
        visible_text = None
        detected_targets: List[VisualTarget] = []
        error_summary = None

        if screenshot_available and screenshot_data and include_vision:
            try:
                # Store in bounded cache
                self._image_cache[obs_id] = screenshot_data
                # Trim cache to keep only history IDs
                cache_keys = list(self._image_cache.keys())
                if len(cache_keys) > 5:
                    for k in cache_keys[:-5]:
                        self._image_cache.pop(k, None)

                vision_result = await self._vision.analyze(
                    data=screenshot_data,
                    mime_type=screenshot_mime,
                    prompt=prompt or "Analyze this screen. List visible UI elements, text, buttons, and any visible errors.",
                    mode=mode,
                )
                raw_desc = vision_result.get("description", "")
                visible_text = sanitize_visual_data(raw_desc)
                detected_targets = parse_targets_from_vision(
                    vision_text=visible_text,
                    screen=screen_info,
                    app_context=active_app,
                )
                diagnostics.append(f"Vision identified {len(detected_targets)} target(s)")

                # Detect errors
                error_targets = [t for t in detected_targets if t.type == "error"]
                if error_targets:
                    error_summary = error_targets[0].label

            except VisionError as exc:
                diagnostics.append(f"Vision analysis unavailable ({exc.code}): {exc}")
            except Exception as exc:
                diagnostics.append(f"Vision error: {exc}")
        elif not include_vision:
            diagnostics.append("Vision model call skipped per request parameters")

        observation = Observation(
            id=obs_id,
            timestamp=now_iso,
            screen=screen_info,
            active_application=active_app,
            active_window=active_win,
            visible_text=visible_text,
            screenshot_available=screenshot_available,
            running_applications=running_apps,
            detected_targets=detected_targets,
            diagnostics=diagnostics,
            error_summary=error_summary,
        )

        self._history.append(observation)
        return observation

    def clear_history(self) -> None:
        self._history.clear()
        self._image_cache.clear()


observation_service = ObservationService()
