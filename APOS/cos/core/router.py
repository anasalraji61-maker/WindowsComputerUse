"""Brain Router — توجيه لكل الوكلاء + COS + Claude (بدون تأجيل)."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from cos.agents.supervisor_agent import SupervisorAgent
from cos.core.orchestrator import Orchestrator
from cos.core.planner import plan_goal
from cos.data import get_data_layer


class Route(str, Enum):
    COS = "cos"
    CLAUDE = "claude"
    CODING = "coding"
    QUANT = "quant"
    TRADING = "trading"
    RESEARCH = "research"
    BUSINESS = "business"
    MARKETING = "marketing"
    MEMORY = "memory"
    SUPERVISOR = "supervisor"


@dataclass
class RouteDecision:
    route: Route
    reason: str


def _project_root() -> Path:
    from cos import config

    return config.ROOT.parent


def _has_any(goal: str, keys: tuple[str, ...]) -> bool:
    g = goal.lower()
    return any(k in goal or k in g for k in keys)


def decide_route(goal: str, force: Optional[Route] = None) -> RouteDecision:
    # طبقة النية: طلبات QC/الروبوت تفوز حتى على الوضع المفروض من الواجهة
    try:
        from cos.brain.intent import intent_overrides_force, parse_intent

        intent = parse_intent(goal, use_llm=False)
        if intent.gibberish:
            return RouteDecision(Route.COS, "نص غير مفهوم — تجاهل التنفيذ")
        if intent.kind == "qc_matrix":
            return RouteDecision(Route.COS, f"Intent qc_matrix ({intent.reason})")
        if intent.kind == "trade_ideas":
            return RouteDecision(Route.TRADING, f"Intent trade_ideas ({intent.reason})")
        if intent.kind == "stop":
            return RouteDecision(Route.COS, "Intent stop")
        # force لا يتجاوز نية QC فوق — إن وُجدت نية صريحة أخرى اترك force
        if force is not None and not intent_overrides_force(intent):
            return RouteDecision(force, "وضع مفروض من الواجهة")
    except Exception:
        if force is not None:
            return RouteDecision(force, "وضع مفروض من الواجهة")

    if force is not None:
        return RouteDecision(force, "وضع مفروض من الواجهة")

    if _has_any(
        goal,
        (
            "اعمل لوحدك",
            "اشتغل لوحدك",
            "دورة مستقلة",
            "حتى تقتنع",
            "حتى نتفق",
            "اتركك تعمل",
            "ناقش كورسر",
            "ناقش cursor",
            "كرر الفحص",
        ),
    ):
        return RouteDecision(Route.COS, "وضع استقلال عبر COS")

    if _has_any(
        goal,
        (
            "مشرف",
            "supervisor",
            "صلاحيات",
            "قائمة الحظر",
            "حالة النظام",
            "status system",
            "حالة العقل",
            "brain status",
        ),
    ):
        # حالة العقل لها مسار COS أيضاً؛ إن ذُكر العقل صراحة فضّل COS/brain
        if _has_any(goal, ("حالة العقل", "brain", "ollama", "عقل محلي")):
            return RouteDecision(Route.COS, "Brain status via COS")
        return RouteDecision(Route.SUPERVISOR, "Supervisor Agent")
    if _has_any(
        goal,
        (
            "ذاكرة",
            "تذكّر",
            "تذكر",
            "ماذا تعلمت",
            "ماذا تعلّمت",
            "تقرير التعلم",
            "تقرير التعلّم",
            "تقرير الأسبوع",
            "تقرير الاسبوع",
            "ملخص التعلم",
            "ملخص التعلّم",
            "learning report",
            "memory agent",
        ),
    ):
        return RouteDecision(Route.MEMORY, "Memory Agent / تقرير التعلّم")
    if _has_any(goal, ("ابحث", "research", "وثّق", "وثق", "google")):
        return RouteDecision(Route.RESEARCH, "Research Agent")
    if _has_any(goal, ("تسويق", "marketing", "منشور", "محتوى سوشيال")):
        return RouteDecision(Route.MARKETING, "Marketing Agent")
    if _has_any(goal, ("فاتورة", "crm", "أعمال", "business agent", "تقرير أعمال")):
        return RouteDecision(Route.BUSINESS, "Business Agent")
    if _has_any(
        goal,
        (
            "tradingview",
            "trendspider",
            "holly",
            "trade ideas",
            "tradeideas",
            "شارت",
            "ماسح السوق",
            "trading agent",
        ),
    ):
        return RouteDecision(Route.TRADING, "Trading Agent")

    # ملف الروبوت / ماتريكس / كوانت كونكت → مسار COS workflow (ليس Trade Ideas)
    if _has_any(
        goal,
        (
            "quantconnect",
            "كوانت كونكت",
            "كوانتكونكت",
            "matrix",
            "ماتريكس",
            "ملف الروبوت",
            "اطلب ملف",
            "افحص الروبوت",
            "فحص الروبوت",
            "افتح كوانت",
            "الروبوت",
        ),
    ) and not _has_any(goal, ("trade ideas", "tradeideas", "holly", "هولي")):
        return RouteDecision(Route.COS, "Matrix/QuantConnect workflow")

    if _has_any(
        goal,
        (
            "quant",
            "كوانت",
            "backtest",
            "باك تست",
            "strategyquant",
            "metatrader",
            "mt5",
            "build alpha",
            "ninjatrader",
            "tradestation",
            "composer",
            "forex strategy",
            "algotrader",
            "فحص الاستراتيجية",
            "quant agent",
        ),
    ):
        return RouteDecision(Route.QUANT, "Quant Agent")
    if _has_any(
        goal,
        (
            "عدّل الكود",
            "عدل الكود",
            "أصلح الخطأ",
            "اصلح الخطأ",
            "اكتب دالة",
            "وكيل البرمجة",
            "coding agent",
            "refactor",
        ),
    ):
        return RouteDecision(Route.CODING, "Coding Agent")
    if _has_any(
        goal,
        (
            "claude",
            "computer use",
            "برؤية",
            "بالرؤية",
            "رؤية عميقة",
            "انقر على الزر",
            "اقرأ الشاشة",
        ),
    ):
        return RouteDecision(Route.CLAUDE, "Claude Computer Use")

    plan = plan_goal(goal)
    if plan.mode in ("chat", "execute", "workflow", "workflow_return", "explore"):
        return RouteDecision(Route.COS, "COS محلي")
    if len(goal.strip()) > 80:
        return RouteDecision(Route.CLAUDE, "مهمة طويلة → Claude")
    return RouteDecision(Route.COS, "افتراضي COS")


def run_claude_task(goal: str) -> str:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except Exception:
        pass
    from agent import run_task

    steps = int(os.getenv("MAX_STEPS", "40"))
    out = run_task(goal, steps)
    return (out or "").strip() or "انتهى تنفيذ Claude Computer Use."


class BrainRouter:
    def __init__(self):
        self.orch = Orchestrator()
        self.supervisor = SupervisorAgent()
        self.force: Optional[Route] = None
        self.layer = get_data_layer()

    def set_force(self, route: Optional[Route]) -> None:
        self.force = route

    def run(self, goal: str, confirm_risky: bool = False) -> str:
        gate = self.supervisor.gate_goal(goal)
        if not gate.allowed and not (gate.needs_confirm and confirm_risky):
            self.supervisor.log("deny", gate.reason, {"goal": goal[:200]})
            return f"مرفوض بواسطة Supervisor: {gate.reason}"

        decision = decide_route(goal, self.force)
        route = decision.route
        out = ""

        try:
            if route == Route.COS:
                out = self.orch.run(goal, confirm_risky=confirm_risky or gate.needs_confirm)
            elif route == Route.CODING:
                from cos.agents.coding import CodingAgent

                out = CodingAgent(self.orch).run(goal)
            elif route == Route.QUANT:
                from cos.agents.quant import QuantAgent

                out = QuantAgent().run(goal)
            elif route == Route.TRADING:
                from cos.agents.trading import TradingAgent

                out = TradingAgent().run(goal)
            elif route == Route.RESEARCH:
                from cos.agents.research import ResearchAgent

                out = ResearchAgent().run(goal)
            elif route == Route.BUSINESS:
                from cos.agents.business import BusinessAgent

                out = BusinessAgent().run(goal)
            elif route == Route.MARKETING:
                from cos.agents.marketing import MarketingAgent

                out = MarketingAgent().run(goal)
            elif route == Route.MEMORY:
                from cos.agents.memory_agent import MemoryAgent

                out = MemoryAgent().run(goal)
            elif route == Route.SUPERVISOR:
                out = self.supervisor.run(goal)
            else:
                try:
                    out = run_claude_task(goal)
                    if not out.startswith("["):
                        out = f"[claude] {out}"
                except Exception as e:
                    fallback = self.orch.run(goal, confirm_risky=confirm_risky)
                    out = f"تعذّر Claude ({e}).\nCOS:\n{fallback}"

            # إن فشل المسار المحلي بوضوح → انفتاح عالمي على مستوى الهدف
            out = self._maybe_world_recover(goal, route, out)

        except Exception as e:
            out = self._recover_exception(goal, route, e)
        finally:
            self.layer.sql.record_goal(goal, route.value, "ok" if out else "empty", out or "")
            self.supervisor.log("route", f"{route.value}: {decision.reason}", {"goal": goal[:160]})
            try:
                from cos.agents.memory_agent import MemoryAgent

                MemoryAgent().observe_dialog(goal, out or "")
            except Exception:
                pass

        return out

    def _looks_failed(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return True
        markers = (
            "لم أتمكّن",
            "لم اتمكن",
            "تعذّر",
            "تعذر",
            "مرفوض بواسطة",
            "بعد البحث الذاتي",
            "plugin غير معروف",
            "لم أجد",
            "لم اجد",
        )
        return any(m in t for m in markers)

    def _maybe_world_recover(self, goal: str, route: Route, out: str) -> str:
        if route in (Route.RESEARCH, Route.SUPERVISOR, Route.MEMORY, Route.CLAUDE):
            return out
        if not self._looks_failed(out):
            return out
        try:
            from cos import config
            from cos.core.recovery import AutoRecovery
            from cos.execution.hand import Action

            if not getattr(config, "AUTO_RESEARCH", True):
                return out
            rr = AutoRecovery().recover_action(
                goal=goal,
                platform=route.value,
                action=Action(
                    kind="wait",
                    params={"seconds": 0.4},
                    confidence=0.99,
                    reason="goal_level_recovery",
                ),
                error=(out or "")[:300],
            )
            if rr.recovered:
                return (
                    f"{out}\n\n——\n[انفتاح عالمي] تعافيت بعد البحث/التصعيد:\n{rr.detail}"
                )
            return f"{out}\n\n——\n[انفتاح عالمي] بحثت ولم أُكمل بعد:\n{rr.detail}"
        except Exception as e:
            return f"{out}\n\n(تعذّر مسار التعافي العالمي: {e})"

    def _recover_exception(self, goal: str, route: Route, err: Exception) -> str:
        try:
            from cos.core.recovery import AutoRecovery
            from cos.execution.hand import Action

            rr = AutoRecovery().recover_action(
                goal=goal,
                platform=route.value,
                action=Action(kind="wait", params={"seconds": 0.3}, confidence=0.99),
                error=str(err),
            )
            if rr.recovered:
                return f"حدث خطأ ثم تعافيت عبر البحث العالمي:\n{rr.detail}"
            return f"خطأ: {err}\n\nبحث عالمي:\n{rr.detail}"
        except Exception as e2:
            return f"حدث خطأ أثناء التنفيذ: {err}\n(تعافي فشل: {e2})"
