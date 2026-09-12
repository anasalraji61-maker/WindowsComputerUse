"""Quant Agent — فتح منصات الفحص، جمع مرشّحات، تقارير، تعلّم."""
from __future__ import annotations

from cos.agents.memory_agent import MemoryAgent
from cos.data import get_data_layer
from cos.execution import apps
from cos.execution.hand import Action, execute
from cos.plugins import REGISTRY
from cos.perception import vision
from cos.runtime import RUNTIME

_QC_MATRIX_KEYS = (
    "كوانت كونكت",
    "كوانتكونكت",
    "quantconnect",
    "quant connect",
    "كوانت",
    "quant",
    "matrix",
    "ماتريكس",
    "الروبوت",
    "روبوت",
    "ملف الروبوت",
    "اطلب ملف",
    "افحص الروبوت",
    "فحص الروبوت",
    "backtest",
    "باك تست",
)

_TRADE_IDEAS_KEYS = (
    "trade ideas",
    "tradeideas",
    "holly",
    "هولي",
)


def _goal_wants_qc_matrix(goal: str) -> bool:
    g = (goal or "").lower()
    return any(k in goal or k in g for k in _QC_MATRIX_KEYS)


def _goal_wants_trade_ideas(goal: str) -> bool:
    g = (goal or "").lower()
    return any(k in goal or k in g for k in _TRADE_IDEAS_KEYS)


class QuantAgent:
    def __init__(self):
        self.memory = MemoryAgent()
        self.layer = get_data_layer()

    def _open_plugin(self, plugin_id: str) -> str:
        plug = REGISTRY.get(plugin_id)
        if not plug:
            return f"plugin غير معروف: {plugin_id}"
        notes = []
        if plug.window_hints:
            act = Action(
                kind="focus",
                params={"title": plug.window_hints[0]},
                confidence=0.85,
                reason="quant",
            )
            try:
                notes.append(execute(act))
            except Exception as e:
                notes.append(str(e))
        if plug.url:
            notes.append(
                apps.focus_or_open_url(
                    plug.window_hints[0] if plug.window_hints else plug.name, plug.url
                )
            )
        fr = vision.capture_event(f"quant_{plugin_id}", force=True)
        notes.append(f"لقطة:{fr.path.name}")
        self.memory.learn_from_outcome(plugin_id, "open", "ok", True, "; ".join(notes))
        return " | ".join(notes)

    def run(self, goal: str) -> str:
        RUNTIME.check()
        REGISTRY.load_all()

        # مسار Matrix/QuantConnect: لا تفتح Trade Ideas أبداً لهذا النوع من الطلبات
        if _goal_wants_qc_matrix(goal) and not _goal_wants_trade_ideas(goal):
            from cos.core.workflow import run_matrix_brief

            report = run_matrix_brief(goal)
            self.layer.sql.record_goal(goal, "quant", "ok", report[:500])
            return "[Quant Agent]\n" + report

        plug = REGISTRY.detect_from_goal(goal)
        advice = self.memory.advice(goal, plug.id if plug else "quant")
        robots = apps.find_robot_candidates(limit=3)
        lines = ["[Quant Agent]", advice, ""]

        if _goal_wants_trade_ideas(goal):
            lines.append(self._open_plugin("tradeideas"))
        elif plug and plug.category in ("trading_test", "llm_eval") and plug.id != "matrix":
            if plug.id == "tradeideas" and _goal_wants_qc_matrix(goal):
                lines.append(self._open_plugin("quantconnect"))
            else:
                lines.append(f"منصة مكتشفة: {plug.name} ({plug.id})")
                lines.append(self._open_plugin(plug.id))
        else:
            mentioned = [
                p
                for p in REGISTRY.by_category("trading_test")
                if p.matches_goal(goal) and p.id != "tradeideas"
            ]
            # الافتراضي دائماً QuantConnect — ليس Trade Ideas
            targets = [p.id for p in mentioned] or ["quantconnect"]
            for tid in targets[:2]:
                lines.append(self._open_plugin(tid))

        if robots:
            lines.append(f"ملف مرشّح: {robots[0]}")
            apps.copy_path_to_clipboard(robots[0])
        self.layer.sql.record_goal(goal, "quant", "ok", "\n".join(lines)[:500])
        lines.append("\nبعد ظهور النتائج قل: «احفظ نتيجة» أو «ارجع لـ Cursor».")
        return "\n".join(lines)
