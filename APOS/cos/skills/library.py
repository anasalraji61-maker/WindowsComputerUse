"""مهارات ذرية عامة — تُركَّب للمهام؛ ليست ملفات أزرار لمنصة واحدة."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cos.execution.hand import Action


@dataclass
class Skill:
    id: str
    name_ar: str
    description: str
    build: Callable[[dict], Action]


def skill_show_desktop(_: dict) -> Action:
    return Action(kind="show_desktop", params={}, confidence=0.95, reason="مهارة: سطح المكتب")


def skill_move_center(_: dict) -> Action:
    import pyautogui

    w, h = pyautogui.size()
    return Action(
        kind="mouse_move",
        params={"x": w // 2, "y": h // 2, "duration": 0.4},
        confidence=0.9,
        reason="مهارة: حرّك الماوس لمركز الشاشة",
    )


def skill_focus(params: dict) -> Action:
    return Action(
        kind="focus",
        params={"title": params.get("title", "")},
        confidence=0.75,
        reason=f"مهارة: ركّز نافذة {params.get('title')}",
    )


def skill_click_xy(params: dict) -> Action:
    return Action(
        kind="click",
        params={"x": params["x"], "y": params["y"]},
        confidence=float(params.get("confidence", 0.7)),
        reason="مهارة: انقر إحداثيات",
    )


SKILLS: dict[str, Skill] = {
    "show_desktop": Skill("show_desktop", "سطح المكتب", "عرض سطح المكتب", skill_show_desktop),
    "move_center": Skill("move_center", "حرّك الماوس", "إلى المركز", skill_move_center),
    "focus_window": Skill("focus_window", "تركيز نافذة", "بالعنوان", skill_focus),
    "click_xy": Skill("click_xy", "نقرة", "على إحداثيات", skill_click_xy),
}
