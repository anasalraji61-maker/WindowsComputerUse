"""OCR Engine — استخراج نص من الشاشة عند الحاجة (اختياري التثبيت)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cos.runtime import RUNTIME

_engine_note = "none"


@dataclass
class OcrResult:
    text: str
    engine: str
    ok: bool
    note: str = ""


def available_engine() -> str:
    """pytesseract | windows_ocr | none"""
    global _engine_note
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        _engine_note = "pytesseract"
        return _engine_note
    except Exception:
        pass
    try:
        # Windows 10+ OCR عبر winocr إن وُجد لاحقاً — حالياً نتحقّق بلطف
        import importlib.util

        if importlib.util.find_spec("winocr"):
            _engine_note = "winocr"
            return _engine_note
    except Exception:
        pass
    _engine_note = "none"
    return _engine_note


def _capture_pil(max_w: int = 1280):
    import mss
    from PIL import Image

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    if img.width > max_w:
        ratio = max_w / float(img.width)
        img = img.resize((max_w, max(1, int(img.height * ratio))))
    return img


def read_screen(lang: str = "ara+eng") -> OcrResult:
    """اقرأ نص الشاشة إن توفّر محرك OCR؛ وإلا أرجع فارغاً بأمان."""
    RUNTIME.check()
    eng = available_engine()
    if eng == "none":
        return OcrResult(
            text="",
            engine="none",
            ok=False,
            note="OCR غير مثبت — pip install pytesseract + Tesseract-OCR",
        )
    try:
        img = _capture_pil()
        if eng == "pytesseract":
            import pytesseract

            # ara قد لا يكون مثبتاً — جرّب eng ثم ara+eng
            try:
                text = pytesseract.image_to_string(img, lang=lang)
            except Exception:
                text = pytesseract.image_to_string(img, lang="eng")
            text = (text or "").strip()
            return OcrResult(text=text, engine=eng, ok=bool(text), note=f"chars={len(text)}")
        if eng == "winocr":
            import asyncio

            import winocr

            async def _run():
                return await winocr.recognize_pil(img)

            text = str(asyncio.run(_run()) or "").strip()
            return OcrResult(text=text, engine=eng, ok=bool(text))
    except Exception as e:
        return OcrResult(text="", engine=eng, ok=False, note=str(e))
    return OcrResult(text="", engine=eng, ok=False, note="no backend")


def screen_contains(needle: str, *, case_insensitive: bool = True) -> tuple[bool, OcrResult]:
    """هل يظهر نص معيّن على الشاشة؟"""
    res = read_screen()
    if not res.ok:
        return False, res
    hay = res.text.lower() if case_insensitive else res.text
    n = needle.lower() if case_insensitive else needle
    return (n in hay), res
