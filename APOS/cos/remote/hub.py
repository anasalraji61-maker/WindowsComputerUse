"""حالة مشتركة للتحكم عن بُعد (هاتف/لوحة)."""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime
from typing import Any, Deque, Optional

from cos.core.router import BrainRouter
from cos.runtime import RUNTIME

_lock = threading.Lock()
_messages: Deque[dict[str, Any]] = deque(maxlen=80)
_seq = 0
_router: Optional[BrainRouter] = None


def get_router() -> BrainRouter:
    global _router
    if _router is None:
        _router = BrainRouter()
    return _router


def push(role: str, text: str, *, source: str = "ui") -> int:
    global _seq
    with _lock:
        _seq += 1
        mid = _seq
        _messages.append(
            {
                "id": mid,
                "role": role,
                "text": text,
                "source": source,
                "at": datetime.now().strftime("%H:%M:%S"),
            }
        )
        return mid


def snapshot() -> dict[str, Any]:
    with _lock:
        msgs = list(_messages)
    busy = RUNTIME.busy
    killed = RUNTIME.killed
    return {
        "busy": busy,
        "killed": killed,
        "status": "يعمل..." if busy else ("توقف" if killed else "جاهز"),
        "messages": msgs,
    }


def run_goal(goal: str) -> str:
    goal = (goal or "").strip()
    if not goal:
        return "أدخل أمراً."
    push("user", goal, source="phone")
    if RUNTIME.busy:
        msg = "ما زلت أنفّذ أمراً سابقاً."
        push("assistant", msg, source="phone")
        return msg
    try:
        out = get_router().run(goal)
        out = (out or "تم.").strip()
        push("assistant", out, source="phone")
        try:
            from cos.voice.speak import speak

            speak(out[:400])
        except Exception:
            pass
        return out
    except Exception as e:
        msg = f"خطأ: {e}"
        push("assistant", msg, source="phone")
        return msg


def kill() -> str:
    RUNTIME.kill()
    push("assistant", "إيقاف طارئ من الهاتف/اللوحة.", source="phone")
    return "تم الإيقاف"
