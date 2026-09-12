"""Window Manager — قائمة النوافذ وتركيزها بدون رؤية ثقيلة."""
from __future__ import annotations

from typing import Optional

from cos.perception.world_state import WindowInfo, WorldState, stamp
from cos.runtime import RUNTIME


def list_windows() -> list[WindowInfo]:
    try:
        import pygetwindow as gw
    except Exception:
        return []

    out: list[WindowInfo] = []
    active_title = ""
    try:
        aw = gw.getActiveWindow()
        active_title = (aw.title or "").strip() if aw else ""
    except Exception:
        pass

    try:
        windows = gw.getAllWindows()
    except Exception:
        return out

    for w in windows:
        title = (w.title or "").strip()
        if not title:
            continue
        try:
            out.append(
                WindowInfo(
                    title=title,
                    left=int(getattr(w, "left", 0) or 0),
                    top=int(getattr(w, "top", 0) or 0),
                    width=int(getattr(w, "width", 0) or 0),
                    height=int(getattr(w, "height", 0) or 0),
                    is_active=title == active_title,
                )
            )
        except Exception:
            continue
    return out


def focus_window(title_substr: str) -> tuple[bool, str]:
    """ركّز أول نافذة يحتوي عنوانها النص (بدون اعتماد على أزرار محفوظة)."""
    RUNTIME.check()
    try:
        import pygetwindow as gw
    except Exception as e:
        return False, f"pygetwindow غير متاح: {e}"

    needle = title_substr.strip().lower()
    if not needle:
        return False, "عنوان فارغ"

    matches = []
    for w in gw.getAllWindows():
        title = (w.title or "").strip()
        if needle in title.lower():
            matches.append(w)
    if not matches:
        return False, f"لا نافذة تطابق: {title_substr}"

    w = matches[0]
    try:
        if w.isMinimized:
            w.restore()
        w.activate()
        return True, f"ركزت: {w.title}"
    except Exception as e:
        return False, f"فشل التركيز: {e}"


def refresh_world(goal: str = "", screen_hash: str = "", screen_changed: bool = False) -> WorldState:
    wins = list_windows()
    active = next((w.title for w in wins if w.is_active), "")
    if not active and wins:
        try:
            import pygetwindow as gw

            aw = gw.getActiveWindow()
            active = (aw.title or "") if aw else ""
        except Exception:
            active = ""
    procs_top: list[str] = []
    try:
        from cos.perception import processes

        procs_top = [f"{p.name}" for p in processes.list_processes(limit=8)]
    except Exception:
        pass
    plugin_id = ""
    try:
        from cos.plugins import REGISTRY

        plug = REGISTRY.detect_from_title(active) or (
            REGISTRY.detect_from_goal(goal) if goal else None
        )
        plugin_id = plug.id if plug else ""
    except Exception:
        pass
    return WorldState(
        timestamp=stamp(),
        active_title=active,
        windows=wins,
        screen_hash=screen_hash,
        screen_changed=screen_changed,
        goal=goal,
        processes_top=procs_top,
        plugin_id=plugin_id,
    )
