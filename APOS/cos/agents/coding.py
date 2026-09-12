"""Coding Agent — وكيل برمجة: Cursor + ملفات + خبرة، مع تصعيد لـ Claude عند الحاجة."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from cos.execution import apps
from cos.execution.hand import Action, Supervisor, execute
from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch, windows as winmod
from cos.perception import vision
from cos.runtime import RUNTIME

if TYPE_CHECKING:
    from cos.core.orchestrator import Orchestrator


class CodingAgent:
    def __init__(self, orch: Optional["Orchestrator"] = None):
        self.orch = orch
        self.store = ExperienceStore()
        self.sup = Supervisor()

    def _focus_cursor(self) -> str:
        act = Action(kind="focus", params={"title": "Cursor"}, confidence=0.9, reason="coding")
        ok, why = self.sup.approve(act)
        if not ok:
            return why
        try:
            return execute(act)
        except Exception as e:
            return str(e)

    def _find_code_targets(self, goal: str) -> list[Path]:
        keys = []
        low = goal.lower()
        for token in ("matrix", "robot", "main", "strategy", "agent", "workflow"):
            if token in low or token in goal:
                keys.append(token)
        found = apps.find_robot_candidates(limit=8)
        if keys:
            ranked = []
            for p in found:
                score = sum(1 for k in keys if k in p.name.lower() or k in str(p).lower())
                ranked.append((score, p))
            ranked.sort(key=lambda x: x[0], reverse=True)
            return [p for s, p in ranked if s > 0] or found
        return found

    def run(self, goal: str) -> str:
        RUNTIME.check()
        notes: list[str] = []
        changed, shash = screen_watch.watch_once()
        state = winmod.refresh_world(goal=goal, screen_hash=shash, screen_changed=changed)
        notes.append(f"نافذة: {state.active_title or '—'}")

        notes.append("Cursor: " + self._focus_cursor())
        fr = vision.capture_event("coding_agent", force=True)
        notes.append(f"لقطة: {fr.path.name}")

        targets = self._find_code_targets(goal)
        robot = targets[0] if targets else None
        if robot:
            notes.append(apps.copy_path_to_clipboard(robot))
            try:
                notes.append(apps.open_in_explorer(robot))
            except Exception as e:
                notes.append(str(e))
            self.store.record("coding", "locate_file", "ok", str(robot), True)
        else:
            notes.append("لم أجد ملفاً مرشّحاً في مساحة العمل.")
            self.store.record("coding", "locate_file", "miss", goal[:100], False)

        # مهام تحتاج رؤية عميقة داخل المحرر → تصعيد
        escalate = any(
            x in goal
            for x in (
                "أصلح",
                "اصلح",
                "اكتب",
                "عدّل داخل",
                "عدل داخل",
                "refactor",
                "bug",
                "خطأ في السطر",
            )
        )
        if escalate:
            try:
                from cos.core.router import run_claude_task

                brief = (
                    f"أنت وكيل برمجة على Windows داخل Cursor. المهمة:\n{goal}\n\n"
                    f"ملف مرشّح: {robot or 'غير محدد'}\n"
                    "افتح الملف إن لزم، نفّذ التعديل بحذر، لا تحذف ملفات."
                )
                out = run_claude_task(brief)
                self.store.record("coding", "claude_escalate", "ok", out[:200], True)
                return (
                    "Coding Agent → صعّدت لـ Claude Computer Use داخل Cursor.\n\n"
                    f"{out}\n\n"
                    + (f"ملف مرشّح: {robot}" if robot else "")
                )
            except Exception as e:
                notes.append(f"تصعيد Claude فشل: {e}")

        self.store.record("coding", "prep", "ok", "; ".join(notes)[:200], True)
        return (
            "Coding Agent جهّز بيئة البرمجة.\n\n"
            + (f"ملف مرشّح:\n{robot}\n(في الحافظة)\n\n" if robot else "")
            + "ركّزت Cursor وأخذت لقطة.\n"
            "للتعديل العميق بالرؤية اكتب مثلاً: «أصلح الخطأ في الكود بالرؤية».\n\n"
            "ملاحظات:\n- " + "\n- ".join(notes[:8])
        )
