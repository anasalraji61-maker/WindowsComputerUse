"""Vision Engine — لقطات حدثية (عند تغيّر/طلب) وليس كل ثانية."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from cos import config
from cos.runtime import RUNTIME

_last_full_hash: str = ""


@dataclass
class Frame:
    path: Path
    hash: str
    width: int
    height: int
    changed: bool


def _grab_rgb(max_w: int = 1280) -> Tuple["Image.Image", bytes]:
    import io

    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    if img.width > max_w:
        ratio = max_w / float(img.width)
        img = img.resize((max_w, max(1, int(img.height * ratio))))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=55)
    return img, buf.getvalue()


def frame_hash(jpeg_bytes: bytes) -> str:
    return hashlib.md5(jpeg_bytes).hexdigest()


def capture_event(name: str = "vision", *, force: bool = False) -> Frame:
    """التقط إطاراً عند حدث. إن لم يتغيّر الهاش ولم يُفرض — يحدّث الملفات بنفس الاسم."""
    global _last_full_hash
    RUNTIME.check()
    img, data = _grab_rgb()
    h = frame_hash(data)
    changed = bool(_last_full_hash) and h != _last_full_hash
    if not _last_full_hash:
        changed = True
    _last_full_hash = h
    path = config.SCREENSHOTS_DIR / f"{name}.jpg"
    if changed or force or not path.exists():
        path.write_bytes(data)
    return Frame(path=path, hash=h, width=img.width, height=img.height, changed=changed)


def region_brightness(x: int, y: int, w: int = 80, h: int = 40) -> float:
    """متوسط سطوع منطقة — مفيد لتحقق بسيط بدون OCR."""
    RUNTIME.check()
    img, _ = _grab_rgb(max_w=960)
    # حوّل إحداثيات الشاشة لنسبة الإطار
    import pyautogui

    sw, sh = pyautogui.size()
    sx = int(x / sw * img.width)
    sy = int(y / sh * img.height)
    rw = max(4, int(w / sw * img.width))
    rh = max(4, int(h / sh * img.height))
    crop = img.crop((sx, sy, min(img.width, sx + rw), min(img.height, sy + rh)))
    gray = crop.convert("L")
    pixels = list(gray.getdata())
    if not pixels:
        return 0.0
    return sum(pixels) / (255.0 * len(pixels))


def describe_brief() -> str:
    """وصف قصير بدون نموذج رؤية ثقيل — يعتمد على الحجم والتغيّر."""
    fr = capture_event("vision_brief", force=True)
    return (
        f"إطار {fr.width}×{fr.height} | hash={fr.hash[:8]} | "
        f"تغيّر={fr.changed} | ملف={fr.path.name}"
    )
