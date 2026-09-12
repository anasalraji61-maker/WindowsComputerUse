"""Memory Agent — يدير الذاكرة والتعلّم من الأخطاء + تقرير دوري."""
from __future__ import annotations

from cos.data import get_data_layer
from cos.memory.experience import ExperienceStore
from cos.memory.interface import LongTermMemory, ShortTermMemory
from cos.memory.learning_report import build_learning_report


class MemoryAgent:
    def __init__(self):
        self.short = ShortTermMemory()
        self.long = LongTermMemory()
        self.experience = ExperienceStore()
        self.layer = get_data_layer()

    def observe_dialog(self, user: str, assistant: str) -> None:
        self.short.add("user", user)
        self.short.add("assistant", assistant)
        self.layer.sql.log_activity("dialog", user[:200], {"reply": assistant[:200]})

    def learn_from_outcome(
        self,
        platform: str,
        action: str,
        result: str,
        success: bool,
        note: str = "",
    ) -> str:
        self.experience.record(platform, action, result, note, success)
        self.layer.remember_experience(platform, action, result, note, success)
        if success:
            self.long.store_fact(f"best:{platform}:{action}", note or result)
            return f"تعلّمت نجاحاً على {platform}/{action}"
        lesson = f"فشل {action} على {platform}: {note or result}"
        self.long.store_fact(f"fail:{platform}:{action}", lesson)
        self.layer.ts.write("agent.errors", 1.0, platform=platform, action=action)
        return f"سجّلت الخطأ للتعلّم: {lesson}"

    def advise(self, goal: str, platform_hint: str = "") -> str:
        hits = self.long.recall(goal, limit=4)
        best = self.experience.best_action(platform_hint or "desktop")
        lines = ["[Memory Agent]"]
        if best:
            lines.append(f"أفضل إجراء سابق: {best}")
        if hits:
            lines.append("ذكريات مشابهة:")
            for h in hits:
                p = h.get("payload") or {}
                lines.append(
                    f"- score={h.get('score', 0):.2f} | {p.get('platform','?')}/{p.get('action','?')} success={p.get('success')}"
                )
        ctx = self.short.as_text(6)
        if ctx:
            lines.append("سياق قصير:\n" + ctx)
        return "\n".join(lines) if len(lines) > 1 else "[Memory Agent] لا ذكريات بعد."

    def wants_learning_report(self, goal: str) -> bool:
        g = (goal or "").lower()
        keys = (
            "ماذا تعلمت",
            "ماذا تعلّمت",
            "تقرير التعلم",
            "تقرير التعلّم",
            "تقرير الاسبوع",
            "تقرير الأسبوع",
            "هذا الاسبوع",
            "هذا الأسبوع",
            "دروس الاخطاء",
            "دروس الأخطاء",
            "learning report",
            "what did you learn",
            "ملخص التعلم",
            "ملخص التعلّم",
        )
        return any(k in goal or k in g for k in keys)

    def learning_report(self, goal: str = "ماذا تعلمت هذا الأسبوع") -> str:
        report = build_learning_report(goal, save=True)
        text = report.as_text()
        self.short.add("assistant", text[:500])
        return text

    def run(self, goal: str) -> str:
        self.short.add("user", goal)
        if goal.strip() in ("ذاكرة", "memory") or self.wants_learning_report(goal):
            out = self.learning_report(
                goal if self.wants_learning_report(goal) else "ماذا تعلمت هذا الأسبوع"
            )
            self.short.add("assistant", out[:400])
            return out
        advice = self.advise(goal)
        self.short.add("assistant", advice)
        return advice
