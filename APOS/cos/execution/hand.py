"""Execution: ماوس مرئي واضح + لوحة مفاتيح + مشرف."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Optional

import pyautogui

from cos import config
from cos.runtime import RUNTIME

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

# حركة واضحة أمام المستخدم (قابلة للضبط من .env)
_MOUSE_MIN_DUR = float((__import__("os").getenv("COS_MOUSE_MIN_DURATION") or "0.85"))
_MOUSE_SWEEP_DUR = float((__import__("os").getenv("COS_MOUSE_SWEEP_DURATION") or "1.15"))
_MOUSE_PAUSE = float((__import__("os").getenv("COS_MOUSE_PAUSE") or "0.22"))
_MOUSE_VISIBLE = (__import__("os").getenv("COS_MOUSE_VISIBLE") or "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


@dataclass
class Action:
    kind: str  # mouse_move | click | type | hotkey | wait | focus | show_desktop
    params: dict[str, Any]
    confidence: float = 0.7
    risky: bool = False
    reason: str = ""


class Supervisor:
    def __init__(self, min_confidence: Optional[float] = None):
        self.min_confidence = (
            min_confidence if min_confidence is not None else config.CONFIDENCE_MIN
        )

    def approve(self, action: Action) -> tuple[bool, str]:
        RUNTIME.check()
        if action.confidence < self.min_confidence:
            return False, f"ثقة منخفضة ({action.confidence:.2f}) — تحتاج موافقتك"
        if action.risky and config.REQUIRE_CONFIRM_RISKY:
            return False, "إجراء خطر — يحتاج تأكيداً من الواجهة"
        return True, "موافق"


def _ease_duration(duration: float) -> float:
    floor = _MOUSE_MIN_DUR if _MOUSE_VISIBLE else 0.35
    return max(floor, float(duration))


def move_to(x: int, y: int, duration: float = 1.0) -> str:
    RUNTIME.check()
    sw, sh = pyautogui.size()
    x = max(0, min(int(x), sw - 1))
    y = max(0, min(int(y), sh - 1))
    duration = _ease_duration(duration)
    # tween أوضح بصرياً من الحركة الخطية
    try:
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    except Exception:
        pyautogui.moveTo(x, y, duration=duration)
    if _MOUSE_VISIBLE:
        time.sleep(min(0.12, _MOUSE_PAUSE * 0.5))
    return f"الماوس → ({x},{y})"


def click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> str:
    RUNTIME.check()
    if x is not None and y is not None:
        move_to(x, y, duration=max(0.7, _MOUSE_MIN_DUR * 0.85))
        RUNTIME.check()
        time.sleep(0.12)
        pyautogui.click(x, y, button=button)
        return f"نقرة {button} عند ({x},{y})"
    pyautogui.click(button=button)
    return f"نقرة {button}"


def type_text(text: str) -> str:
    RUNTIME.check()
    if any(ord(c) > 127 for c in text) or len(text) > 40:
        try:
            import pyperclip

            old = None
            try:
                old = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
            if old is not None:
                try:
                    pyperclip.copy(old)
                except Exception:
                    pass
            return f"لصق {len(text)} حرفاً"
        except Exception:
            pass
    pyautogui.write(text, interval=0.01)
    return f"كتب {len(text)} حرفاً"


def hotkey(*keys: str) -> str:
    RUNTIME.check()
    pyautogui.hotkey(*keys)
    return "اختصار: " + "+".join(keys)


def show_desktop() -> str:
    RUNTIME.check()
    pyautogui.hotkey("win", "d")
    return "عرض سطح المكتب (Win+D)"


def mouse_sweep() -> str:
    """عرض تحكم واضح: إطار الشاشة + ضربات + مركز."""
    RUNTIME.check()
    w, h = pyautogui.size()
    dur = _MOUSE_SWEEP_DUR if _MOUSE_VISIBLE else 0.55
    pause = _MOUSE_PAUSE if _MOUSE_VISIBLE else 0.08

    # مسار كبير يُرى من بعيد
    path = [
        (int(w * 0.08), int(h * 0.12)),
        (int(w * 0.92), int(h * 0.12)),
        (int(w * 0.92), int(h * 0.88)),
        (int(w * 0.08), int(h * 0.88)),
        (int(w * 0.08), int(h * 0.12)),
        (int(w * 0.50), int(h * 0.50)),
        (int(w * 0.20), int(h * 0.50)),
        (int(w * 0.80), int(h * 0.50)),
        (int(w * 0.50), int(h * 0.20)),
        (int(w * 0.50), int(h * 0.80)),
        (int(w * 0.50), int(h * 0.50)),
    ]
    # دائرة تقريبية حول المركز لإثبات حيوية المؤشر
    cx, cy = w // 2, h // 2
    rad = int(min(w, h) * 0.18)
    for i in range(8):
        ang = (2 * math.pi * i) / 8
        path.append((int(cx + rad * math.cos(ang)), int(cy + rad * math.sin(ang))))
    path.append((cx, cy))

    for x, y in path:
        move_to(x, y, duration=dur)
        RUNTIME.check()
        time.sleep(pause)
    return (
        f"عرض ماوس مرئي: {len(path)} نقطة على شاشة {w}×{h} "
        f"(مدة النقلة ≈{dur:.1f}ث)"
    )


def execute(action: Action) -> str:
    RUNTIME.check()
    k = action.kind
    p = action.params or {}
    if k == "mouse_move":
        return move_to(int(p["x"]), int(p["y"]), float(p.get("duration", 1.0)))
    if k == "mouse_sweep":
        return mouse_sweep()
    if k == "click":
        return click(p.get("x"), p.get("y"), p.get("button", "left"))
    if k == "type":
        return type_text(str(p.get("text", "")))
    if k == "hotkey":
        keys = p.get("keys") or []
        return hotkey(*[str(x) for x in keys])
    if k == "show_desktop":
        return show_desktop()
    if k == "wait":
        time.sleep(min(float(p.get("seconds", 0.3)), 5.0))
        return "انتظار قصير"
    if k == "focus":
        from cos.perception.windows import focus_window

        ok, msg = focus_window(str(p.get("title", "")))
        if not ok:
            raise RuntimeError(msg)
        return msg
    if k == "open_url":
        from cos.execution import apps

        return apps.human_open_url(str(p.get("url", "")), float(p.get("wait", 2.5)))
    if k == "human_open_url":
        from cos.execution import apps

        return apps.human_open_url(str(p.get("url", "")), float(p.get("wait", 2.5)))
    if k == "open_qc":
        from cos.execution import apps

        return apps.human_open_url(apps.QC_URL, wait=2.8)
    if k == "open_platform":
        from cos.execution import platforms

        return platforms.open_plugin(str(p.get("plugin") or p.get("id") or ""))
    if k == "browser_search":
        from cos.execution import browser

        return browser.search_web(str(p.get("query", "")))
    if k == "terminal":
        from cos.execution import terminal

        return terminal.run_command(str(p.get("cmd", "")), float(p.get("timeout", 30)))
    if k == "read_file":
        from cos.execution import files

        return files.read_text(str(p.get("path", "")))
    if k == "write_file":
        from cos.execution import files

        return files.write_text(str(p.get("path", "")), str(p.get("content", "")))
    if k == "list_dir":
        from cos.execution import files

        return files.list_dir(p.get("path"))
    raise ValueError(f"إجراء غير معروف: {k}")
