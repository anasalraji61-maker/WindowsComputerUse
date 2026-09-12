"""Business Agent — مهام إدارية خفيفة (ملفات/تقارير/تذكير)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cos import config
from cos.agents.memory_agent import MemoryAgent
from cos.data import get_data_layer
from cos.runtime import RUNTIME


class BusinessAgent:
    def __init__(self):
        self.memory = MemoryAgent()
        self.layer = get_data_layer()

    def run(self, goal: str) -> str:
        RUNTIME.check()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.REPORTS_DIR / f"BUSINESS_{stamp}.md"
        body = (
            f"# تقرير أعمال\n\n**الوقت:** {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
            f"**الطلب:** {goal}\n\n"
            "## ملاحظات\n- أنشأه Business Agent\n"
            f"- مساحة العمل: `{config.WORKSPACE}`\n"
        )
        path.write_text(body, encoding="utf-8")
        self.memory.learn_from_outcome("business", "report", "ok", True, str(path))
        self.layer.sql.record_goal(goal, "business", "ok", str(path))
        return f"[Business Agent]\nأُنشئ تقرير:\n{path}\n\n{self.memory.advise(goal, 'business')}"
