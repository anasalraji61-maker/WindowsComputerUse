"""Decision Engine — Reason → Act → Verify → (Recovery) → Learn."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from cos.core.planner import Plan
from cos.core.recovery import AutoRecovery
from cos.core.verify import VerifyResult, verify_after_action
from cos.execution.hand import Action, Supervisor, execute
from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch
from cos.perception.world_state import WorldState
from cos.runtime import RUNTIME

Dbg = Callable[[str], None]


@dataclass
class StepOutcome:
    action: Action
    executed: bool
    verify: Optional[VerifyResult] = None
    detail: str = ""
    blocked: bool = False
    recovered: bool = False


@dataclass
class DecisionResult:
    ok: bool
    reply: str
    outcomes: list[StepOutcome] = field(default_factory=list)
    learned: int = 0
    researched: int = 0


class DecisionEngine:
    """ينفّذ خطة مع تحقق، وتعافٍ تلقائي عبر الإنترنت عند الفشل."""

    def __init__(
        self,
        supervisor: Optional[Supervisor] = None,
        store: Optional[ExperienceStore] = None,
    ):
        self.supervisor = supervisor or Supervisor()
        self.store = store or ExperienceStore()
        self.recovery = AutoRecovery(self.supervisor, self.store)

    def reason_boost(self, action: Action, hint: str) -> Action:
        best = self.store.best_action(hint)
        if best and best == action.kind:
            action.confidence = min(0.98, max(action.confidence, 0.88))
            action.reason = (action.reason + " | خبرة سابقة").strip(" |")
        fails = self.store.recent_failures(hint, action.kind, limit=5)
        if fails >= 3:
            action.confidence = min(action.confidence, 0.5)
            action.reason = (action.reason + " | فشل متكرر").strip(" |")
        return action

    def _try_recover(
        self,
        *,
        goal: str,
        platform: str,
        action: Action,
        error: str,
        log: Dbg,
    ) -> tuple[bool, str]:
        rr = self.recovery.recover_action(
            goal=goal,
            platform=platform,
            action=action,
            error=error,
            dbg=log,
        )
        return rr.recovered, rr.detail

    def run_plan(
        self,
        plan: Plan,
        state: WorldState,
        *,
        confirm_risky: bool = False,
        dbg: Optional[Dbg] = None,
    ) -> DecisionResult:
        log = dbg or (lambda _m: None)
        hint = state.active_title or "desktop"
        outcomes: list[StepOutcome] = []
        learned = 0
        researched = 0
        ok_count = 0

        for i, raw in enumerate(plan.steps, 1):
            RUNTIME.check()
            action = self.reason_boost(raw, hint)
            log(f"decide {i}: {action.kind} conf={action.confidence:.2f} {action.params}")

            approved, why = self.supervisor.approve(action)
            if not approved:
                if action.risky and confirm_risky:
                    log("confirm_risky override")
                else:
                    log(f"blocked: {why}")
                    self.store.record(hint, action.kind, "blocked", why, False)
                    # حتى الحظر قد يُبحث عنه إن كان بسبب ثقة منخفضة
                    if "ثقة" in why or "confidence" in why.lower():
                        researched += 1
                        ok_r, detail_r = self._try_recover(
                            goal=plan.goal,
                            platform=hint,
                            action=action,
                            error=why,
                            log=log,
                        )
                        if ok_r:
                            ok_count += 1
                            learned += 1
                            outcomes.append(
                                StepOutcome(
                                    action=action,
                                    executed=True,
                                    detail=detail_r,
                                    recovered=True,
                                )
                            )
                            continue
                    outcomes.append(
                        StepOutcome(action=action, executed=False, detail=why, blocked=True)
                    )
                    continue

            before_hash = ""
            try:
                before_hash = screen_watch.screen_fingerprint()
            except Exception:
                pass

            try:
                result = execute(action)
                log(result)
            except Exception as e:
                log(f"fail: {e}")
                self.store.record(hint, action.kind, "fail", str(e), False)
                learned += 1
                researched += 1
                ok_r, detail_r = self._try_recover(
                    goal=plan.goal,
                    platform=hint,
                    action=action,
                    error=str(e),
                    log=log,
                )
                if ok_r:
                    ok_count += 1
                    outcomes.append(
                        StepOutcome(
                            action=action,
                            executed=True,
                            detail=detail_r,
                            recovered=True,
                        )
                    )
                else:
                    outcomes.append(
                        StepOutcome(action=action, executed=False, detail=detail_r or str(e))
                    )
                continue

            v = verify_after_action(action, before_hash=before_hash)
            log(f"verify: ok={v.ok} conf={v.confidence:.2f} — {v.reason}")
            success = bool(v.ok and v.confidence >= 0.55)
            self.store.record(
                hint if not v.active_title else v.active_title,
                action.kind,
                "ok" if success else "weak",
                v.reason,
                success,
            )
            learned += 1

            if success:
                ok_count += 1
                if v.active_title:
                    hint = v.active_title
                outcomes.append(
                    StepOutcome(action=action, executed=True, verify=v, detail=result)
                )
                continue

            # Verify فشل → انفتاح على العالم
            researched += 1
            ok_r, detail_r = self._try_recover(
                goal=plan.goal,
                platform=v.active_title or hint,
                action=action,
                error=v.reason,
                log=log,
            )
            if ok_r:
                ok_count += 1
                outcomes.append(
                    StepOutcome(
                        action=action,
                        executed=True,
                        verify=v,
                        detail=detail_r,
                        recovered=True,
                    )
                )
            else:
                outcomes.append(
                    StepOutcome(
                        action=action,
                        executed=True,
                        verify=v,
                        detail=detail_r or result,
                    )
                )

        if ok_count:
            extra = f" (تعافٍ بحثي×{researched})" if researched else ""
            lines = [plan.reply or "تم التنفيذ."]
            for i, o in enumerate(outcomes, 1):
                if o.executed:
                    lines.append(f"{i}. {o.action.kind}: {o.detail or 'ok'}")
                elif o.blocked:
                    lines.append(f"{i}. {o.action.kind}: محظور — {o.detail}")
                else:
                    lines.append(f"{i}. {o.action.kind}: فشل — {o.detail}")
            reply = "\n".join(lines) + extra
            return DecisionResult(
                ok=True,
                reply=reply,
                outcomes=outcomes,
                learned=learned,
                researched=researched,
            )

        if outcomes and all(o.blocked for o in outcomes):
            return DecisionResult(
                ok=False,
                reply="الإجراء محظور (ثقة منخفضة أو يحتاج تأكيداً).",
                outcomes=outcomes,
                learned=learned,
                researched=researched,
            )

        research_note = ""
        if researched:
            research_note = (
                "\nبحثت تلقائياً على الإنترنت/الذاكرة عند الفشل "
                "وصعّدت عند الحاجة."
            )
        return DecisionResult(
            ok=False,
            reply=(
                "لم أتمكّن من التنفيذ بثقة كافية بعد البحث الذاتي."
                + research_note
                + "\nيمكنك إعادة الصياغة أو فتح النافذة يدوياً ثم المحاولة."
            ),
            outcomes=outcomes,
            learned=learned,
            researched=researched,
        )
