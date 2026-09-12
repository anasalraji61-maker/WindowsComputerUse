"""Auto Recovery — فشل → بحث عالمي/AI → إعادة تخطيط → تنفيذ → تعلّم."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from cos import config
from cos.agents.memory_agent import MemoryAgent
from cos.agents.research import ResearchAgent, ResearchBrief
from cos.execution.hand import Action, Supervisor, execute
from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch
from cos.core.verify import verify_after_action
from cos.runtime import RUNTIME

Dbg = Callable[[str], None]


@dataclass
class RecoveryResult:
    recovered: bool
    detail: str
    brief: Optional[ResearchBrief] = None
    tried: list[str] = field(default_factory=list)
    escalated_vision: bool = False


class AutoRecovery:
    """حلقة انفتاح على الإنترنت عند العجز المحلي."""

    def __init__(
        self,
        supervisor: Optional[Supervisor] = None,
        store: Optional[ExperienceStore] = None,
    ):
        self.supervisor = supervisor or Supervisor()
        self.store = store or ExperienceStore()
        self.research = ResearchAgent()
        self.memory = MemoryAgent()
        self.max_retries = int(getattr(config, "AUTO_RESEARCH_RETRIES", 2) or 2)

    def enabled(self) -> bool:
        return bool(getattr(config, "AUTO_RESEARCH", True))

    def recover_action(
        self,
        *,
        goal: str,
        platform: str,
        action: Action,
        error: str,
        dbg: Optional[Dbg] = None,
    ) -> RecoveryResult:
        log = dbg or (lambda _m: None)
        if not self.enabled():
            return RecoveryResult(False, "AUTO_RESEARCH معطّل")

        log(f"recovery:start platform={platform} action={action.kind} err={error}")
        brief = self.research.investigate(
            goal=goal,
            platform=platform,
            action=action.kind,
            error=error,
            open_browser=True,
        )
        log(brief.summary)
        self.memory.learn_from_outcome(
            platform or "desktop",
            f"fail:{action.kind}",
            error,
            False,
            note="trigger_auto_research",
        )

        tried: list[str] = []
        # 1) جرّب إجراءات بديلة من البحث/AI
        for alt in brief.alt_actions[: self.max_retries + 1]:
            RUNTIME.check()
            ok, why = self.supervisor.approve(alt)
            if not ok:
                tried.append(f"block:{alt.kind}:{why}")
                continue
            try:
                before = ""
                try:
                    before = screen_watch.screen_fingerprint()
                except Exception:
                    pass
                msg = execute(alt)
                v = verify_after_action(alt, before_hash=before)
                success = bool(v.ok and v.confidence >= 0.55)
                self.store.record(platform or "desktop", alt.kind, msg, v.reason, success)
                tried.append(f"{alt.kind}:{'ok' if success else 'weak'}")
                if success:
                    self.memory.learn_from_outcome(
                        platform or "desktop",
                        alt.kind,
                        msg,
                        True,
                        note="recovered_via_research",
                    )
                    return RecoveryResult(
                        True,
                        f"تعافيت بعد البحث: {msg}\n{brief.summary}",
                        brief=brief,
                        tried=tried,
                    )
            except Exception as e:
                tried.append(f"{alt.kind}:fail:{e}")
                self.store.record(platform or "desktop", alt.kind, "fail", str(e), False)

        # 2) أعد محاولة الإجراء الأصلي مرة بعد الانتظار/التركيز
        RUNTIME.check()
        try:
            execute(Action(kind="wait", params={"seconds": 0.7}, confidence=0.99))
            msg = execute(action)
            v = verify_after_action(action)
            success = bool(v.ok and v.confidence >= 0.55)
            tried.append(f"retry_original:{'ok' if success else 'weak'}")
            if success:
                self.memory.learn_from_outcome(
                    platform or "desktop", action.kind, msg, True, note="retry_after_research"
                )
                return RecoveryResult(
                    True,
                    f"نجحت إعادة المحاولة بعد البحث.\n{brief.summary}",
                    brief=brief,
                    tried=tried,
                )
        except Exception as e:
            tried.append(f"retry_original:fail:{e}")

        # 3) تصعيد رؤية Claude إن لزم
        if brief.escalate_vision and getattr(config, "AUTO_CLAUDE_ESCALATE", True):
            try:
                from cos.core.router import run_claude_task

                vision_goal = (
                    f"فشلت خطوة أتمتة على Windows. أصلِحها بالرؤية على الشاشة.\n"
                    f"الهدف: {goal}\nالمنصة: {platform}\nالإجراء: {action.kind} {action.params}\n"
                    f"الخطأ: {error}\n"
                    f"نصيحة البحث:\n{brief.ai_advice or brief.summary}\n"
                    "نفّذ الحد الأدنى الآمن لإكمال الخطوة."
                )
                log("recovery:escalate_claude_vision")
                out = run_claude_task(vision_goal)
                self.memory.learn_from_outcome(
                    platform or "desktop",
                    "claude_recovery",
                    out[:200],
                    True,
                    note="escalated_vision",
                )
                return RecoveryResult(
                    True,
                    f"صعّدت للرؤية بعد البحث:\n{out}\n\n{brief.summary}",
                    brief=brief,
                    tried=tried + ["claude_vision"],
                    escalated_vision=True,
                )
            except Exception as e:
                tried.append(f"claude:fail:{e}")
                log(f"recovery:claude_fail {e}")

        self.memory.learn_from_outcome(
            platform or "desktop",
            f"unrecovered:{action.kind}",
            error,
            False,
            note=";".join(tried)[:200],
        )
        return RecoveryResult(
            False,
            "بحثت في الإنترنت/الذاكرة ولم أستطع التعافي تلقائياً بعد.\n" + brief.summary,
            brief=brief,
            tried=tried,
        )
