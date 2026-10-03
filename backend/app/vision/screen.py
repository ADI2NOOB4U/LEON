from __future__ import annotations

import io

from PIL import ImageGrab


class ScreenCaptureError(RuntimeError):
    pass


def capture_screen() -> tuple[bytes, str, int, int]:
    """Capture one screen on demand; never polls or uploads it automatically."""
    try:
        image = ImageGrab.grab(all_screens=True)
    except Exception as exc:
        raise ScreenCaptureError("SCREEN_CAPTURE_FAILED") from exc
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue(), "image/png", image.width, image.height
