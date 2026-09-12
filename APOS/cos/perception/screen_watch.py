"""مراقبة شاشة خفيفة: لقطة مصغّرة + هاش — فهم عميق لاحقاً عند التغيّر فقط."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Tuple

from cos import config
from cos.runtime import RUNTIME

_last_hash: str = ""


def _grab_thumb_bytes() -> bytes:
    import io

    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img = img.resize((320, 180))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=35)
        return buf.getvalue()


def screen_fingerprint() -> str:
    data = _grab_thumb_bytes()
    return hashlib.md5(data).hexdigest()


def watch_once() -> Tuple[bool, str]:
    """يرجع (تغيّر؟، الهاش). مراقبة رخيصة كل لحظة تقريباً."""
    global _last_hash
    RUNTIME.check()
    h = screen_fingerprint()
    changed = bool(_last_hash) and h != _last_hash
    if not _last_hash:
        changed = False
    _last_hash = h
    return changed, h


def save_snapshot(name: str = "shot") -> Path:
    RUNTIME.check()
    data = _grab_thumb_bytes()
    # احفظ أيضاً لقطة أوضح قليلاً للتحقق
    import io

    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        img = img.resize((960, 540))
        path = config.SCREENSHOTS_DIR / f"{name}.jpg"
        img.save(path, format="JPEG", quality=50)
    return path
