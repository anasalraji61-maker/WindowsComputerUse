"""Marketing Agent — مسودات محتوى + فتح قنوات عند الطلب."""
from __future__ import annotations

from datetime import datetime

from cos import config
from cos.agents.memory_agent import MemoryAgent
from cos.execution import apps
from cos.runtime import RUNTIME


class MarketingAgent:
    def __init__(self):
        self.memory = MemoryAgent()

    def run(self, goal: str) -> str:
        RUNTIME.check()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.REPORTS_DIR / f"MARKETING_{stamp}.md"
        draft = (
            f"# مسودة تسويق\n\n**الطلب:** {goal}\n\n"
            "## منشور مقترح\n"
            f"{goal}\n\n"
            "## قنوات\n- Telegram / Discord / X — افتح يدوياً أو اطلب «افتح Telegram»\n"
        )
        path.write_text(draft, encoding="utf-8")
        if any(x in goal.lower() or x in goal for x in ("telegram", "تيليجرام")):
            try:
                apps.focus_or_open_url("Telegram", "https://web.telegram.org")
            except Exception:
                pass
        self.memory.learn_from_outcome("marketing", "draft", "ok", True, str(path))
        return f"[Marketing Agent]\nمسودة محفوظة:\n{path}"
