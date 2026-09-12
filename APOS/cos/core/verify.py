"""Verify — تحقق بعد التنفيذ (حلقة V في Observe→…→Verify→Learn)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cos.execution.hand import Action
from cos.perception import screen_watch, windows as winmod
from cos.perception.world_state import WorldState
from cos.runtime import RUNTIME


@dataclass
class VerifyResult:
    ok: bool
    confidence: float
    reason: str
    screen_changed: bool = False
    active_title: str = ""
    screen_hash: str = ""
    ocr_hit: Optional[bool] = None


def verify_after_action(
    action: Action,
    *,
    before_hash: str = "",
    expect_focus: Optional[str] = None,
    expect_text: Optional[str] = None,
) -> VerifyResult:
    """تحقق عملي: شاشة / نوافذ / OCR اختياري عند توفره."""
    RUNTIME.check()
    changed, shash = screen_watch.watch_once()
    state: WorldState = winmod.refresh_world(screen_hash=shash, screen_changed=changed)
    title = state.active_title or ""

    ocr_hit: Optional[bool] = None
    ocr_note = ""
    if expect_text:
        try:
            from cos.perception.ocr import screen_contains

            ocr_hit, ores = screen_contains(expect_text)
            ocr_note = f" | OCR:{ores.engine}" + (f" hit={ocr_hit}" if ores.ok else f" {ores.note}")
        except Exception as e:
            ocr_note = f" | OCR err:{e}"

    # إجراءات التركيز: يجب ظهور العنوان المستهدف
    if action.kind == "focus" or expect_focus:
        needle = (expect_focus or str(action.params.get("title", ""))).lower()
        hit = bool(needle) and any(needle in (w.title or "").lower() for w in state.windows)
        focused = bool(needle) and needle in title.lower()
        if focused or hit:
            conf = 0.85 if focused else 0.7
            if ocr_hit is True:
                conf = min(0.95, conf + 0.1)
            return VerifyResult(
                ok=True,
                confidence=conf,
                reason=f"النافذة موجودة/مركّزة: {title or needle}{ocr_note}",
                screen_changed=changed,
                active_title=title,
                screen_hash=shash,
                ocr_hit=ocr_hit,
            )
        return VerifyResult(
            ok=False,
            confidence=0.35,
            reason=f"لم أجد نافذة تطابق «{needle}»{ocr_note}",
            screen_changed=changed,
            active_title=title,
            screen_hash=shash,
            ocr_hit=ocr_hit,
        )

    # حركة ماوس / نقر / كتابة: يكفي أن التنفيذ تم؛ التغيّر البصري يدعم الثقة
    if action.kind in ("mouse_move", "click", "type", "hotkey", "show_desktop", "wait"):
        conf = 0.9 if action.kind == "mouse_move" else (0.8 if changed or not before_hash else 0.65)
        if ocr_hit is True:
            conf = min(0.95, conf + 0.1)
        elif ocr_hit is False and expect_text:
            conf = min(conf, 0.45)
        ok = True if ocr_hit is not False else False
        if action.kind in ("mouse_move", "wait", "show_desktop"):
            ok = True
        return VerifyResult(
            ok=ok,
            confidence=conf,
            reason="التنفيذ تم"
            + (" + تغيّر مرئي" if changed else "")
            + ocr_note,
            screen_changed=changed,
            active_title=title,
            screen_hash=shash,
            ocr_hit=ocr_hit,
        )

    if action.kind in ("open_url", "open_qc"):
        # انتظر ظهور متصفح أو QC في العناوين
        keys = ("chrome", "edge", "firefox", "quantconnect", "algorithm")
        hit = any(any(k in (w.title or "").lower() for k in keys) for w in state.windows)
        return VerifyResult(
            ok=hit or changed,
            confidence=0.75 if hit else 0.45,
            reason="فُتح الرابط/المنصة" if hit else "فُتح الرابط لكن النافذة غير مؤكدة بعد",
            screen_changed=changed,
            active_title=title,
            screen_hash=shash,
            ocr_hit=ocr_hit,
        )

    return VerifyResult(
        ok=True,
        confidence=0.6,
        reason="تحقق عام — لا معيار خاص لهذا الإجراء" + ocr_note,
        screen_changed=changed,
        active_title=title,
        screen_hash=shash,
        ocr_hit=ocr_hit,
    )
