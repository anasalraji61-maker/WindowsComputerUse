"""Trading Agent — مراقبة منصات التداول/الأفكار اليومية."""
from __future__ import annotations

from cos.agents.memory_agent import MemoryAgent
from cos.execution import apps
from cos.execution.hand import Action, execute
from cos.perception import vision
from cos.plugins import REGISTRY
from cos.runtime import RUNTIME


class TradingAgent:
    def __init__(self):
        self.memory = MemoryAgent()

    def run(self, goal: str) -> str:
        RUNTIME.check()
        REGISTRY.load_all()
        # منصات المتابعة اليومية حسب ورقتك
        daily = ["tradingview", "trendspider", "tradestation", "tradeideas"]
        plug = REGISTRY.detect_from_goal(goal)
        targets = [plug.id] if plug else []
        if not targets:
            for pid in daily:
                if pid in goal.lower() or (REGISTRY.get(pid) and REGISTRY.get(pid).matches_goal(goal)):
                    targets.append(pid)
        if not targets:
            targets = ["tradingview"]

        lines = ["[Trading Agent]", self.memory.advise(goal, targets[0]), ""]
        for tid in targets[:2]:
            p = REGISTRY.get(tid)
            if not p:
                continue
            if p.window_hints:
                try:
                    execute(
                        Action(
                            kind="focus",
                            params={"title": p.window_hints[0]},
                            confidence=0.8,
                        )
                    )
                except Exception:
                    pass
            if p.url:
                lines.append(apps.focus_or_open_url(p.window_hints[0] if p.window_hints else p.name, p.url))
            vision.capture_event(f"trade_{tid}", force=True)
            self.memory.learn_from_outcome(tid, "open_watch", "ok", True, goal[:80])
        lines.append("راقب الشارت/الماسح. للتقييم التلقائي استخدم Quant Agent أو اذكر MT5/Build Alpha.")
        return "\n".join(lines)
