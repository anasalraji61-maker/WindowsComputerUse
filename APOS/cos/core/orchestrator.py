"""Orchestrator — Goal/Priority/World + قرار وتنفيذ."""
from __future__ import annotations

import re
from datetime import datetime

from cos import config
from cos.core.decision import DecisionEngine
from cos.core.exploration import explore
from cos.core.goals import GoalManager, GoalStatus
from cos.core.planner import plan_goal
from cos.core.priority import PriorityManager, ProjectManager, enqueue_goal
from cos.core.scheduler import Scheduler
from cos.execution.hand import Supervisor
from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch, windows as winmod
from cos.perception import processes
from cos.perception.world_model import get_world_model
from cos.plugins import REGISTRY
from cos.runtime import RUNTIME

_SCHEDULER: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = Scheduler()
    return _SCHEDULER


def _file_log(line: str) -> None:
    try:
        p = config.LOGS_DIR / "runtime.log"
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S} | {line}\n")
    except Exception:
        pass


class Orchestrator:
    def __init__(self):
        self.supervisor = Supervisor()
        self.store = ExperienceStore()
        self.decision = DecisionEngine(self.supervisor, self.store)
        self.goals = GoalManager()
        self.priority = PriorityManager()
        self.projects = ProjectManager()
        self.world = get_world_model()
        try:
            REGISTRY.load_all()
        except Exception as e:
            _file_log(f"plugins load skip: {e}")

    def _handle_goals(self, goal: str) -> str:
        if any(x in goal for x in ("أضف هدف", "هدف جديد", "اضف هدف")):
            text = goal
            for p in ("أضف هدف:", "أضف هدف", "هدف جديد:", "هدف جديد", "اضف هدف:"):
                if p in text:
                    text = text.split(p, 1)[-1].strip(" :")
                    break
            g = enqueue_goal(text or goal, self.goals)
            self.world.note_event("goal_added", g.text, id=g.id, priority=g.priority)
            return f"أُضيف الهدف #{g.id} أولوية={g.priority} مشروع={g.project}\n{g.text}"
        if "نفّذ الهدف التالي" in goal or "نفذ الهدف التالي" in goal or "next goal" in goal.lower():
            nxt = self.goals.next_goal()
            if not nxt:
                return "لا أهداف مفتوحة في الطابور."
            self.goals.mark(nxt.id, GoalStatus.ACTIVE.value)
            # نفّذ كنص هدف
            result = self.run(nxt.text)
            ok = "توقفت" not in result and "خطأ" not in result[:40]
            self.goals.mark(
                nxt.id,
                GoalStatus.DONE.value if ok else GoalStatus.FAILED.value,
                result,
            )
            return f"نُفّذ الهدف #{nxt.id}\n{result}"
        return self.goals.summary()

    def _handle_schedule(self, goal: str) -> str:
        sched = get_scheduler()
        m = re.search(r"كل\s+(\d+)\s*(دقيقة|دقائق|ساعة|ساعات|min|hour)", goal)
        minutes = 60
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            minutes = n * 60 if "ساعة" in unit or "hour" in unit else n
        if any(x in goal for x in ("شغّل المجدول", "شغل المجدول", "start scheduler")):
            # runner يستدعي نفس الـ orchestrator بحذر
            msg = sched.start_background(lambda g: Orchestrator().run(g), poll_seconds=15)
            return msg + "\n" + sched.summary()
        if "أوقف المجدول" in goal or "stop scheduler" in goal.lower():
            return sched.stop()
        if any(x in goal for x in ("جدول", "أضف مهمة", "schedule")):
            # استخرج الهدف بعد :
            task = goal
            for sep in ("جدول:", "جدول", "مهمة:", "schedule:"):
                if sep in task:
                    task = task.split(sep, 1)[-1].strip()
                    break
            # أزل جزء كل X
            task = re.sub(r"كل\s+\d+\s*(دقيقة|دقائق|ساعة|ساعات|min|hour).*", "", task).strip()
            job = sched.add(task or "استكشف الشاشة", every_minutes=minutes)
            return f"مهمة مجدولة #{job.id} كل {minutes} دقيقة:\n{job.goal}\n{sched.summary()}"
        return sched.summary()

    def run(self, goal: str, confirm_risky: bool = False) -> str:
        RUNTIME.reset_kill()
        RUNTIME.busy = True
        detail: list[str] = []

        def dbg(m: str) -> None:
            detail.append(m)
            _file_log(m)

        try:
            dbg(f"GOAL: {goal}")
            changed, shash = screen_watch.watch_once()
            state = winmod.refresh_world(goal=goal, screen_hash=shash, screen_changed=changed)
            dbg(state.summary().replace("\n", " | "))
            self.world.note_event("goal", goal[:160], plugin=state.plugin_id)

            plug = REGISTRY.detect_from_title(state.active_title or "") or REGISTRY.detect_from_goal(goal)
            if plug:
                dbg(
                    f"plugin: {plug.id} ({plug.category}/{plug.kind}) | "
                    f"{self.store.summarize(state.active_title or plug.id)}"
                )

            plan = plan_goal(goal)

            if plan.mode == "chat":
                return plan.reply
            if plan.mode == "smart_chat":
                from cos.brain.chat import smart_chat

                return smart_chat(goal, context=self.world.summary())
            if plan.mode == "autonomous":
                from cos.core.autonomous import run_autonomous_cycle

                return run_autonomous_cycle(goal, orch=self)
            if plan.mode == "goals":
                return self._handle_goals(goal)
            if plan.mode == "projects":
                return self.projects.summary()
            if plan.mode == "schedule":
                return self._handle_schedule(goal)
            if plan.mode == "world":
                return self.world.summary() + "\n" + processes.summary()
            if plan.mode == "platforms_list":
                from cos.execution.platforms import open_from_goal

                return open_from_goal("قائمة المنصات") or REGISTRY.catalog().__str__()

            if plan.mode == "brain":
                from cos.brain import status_text

                return status_text()

            if plan.mode == "explore":
                report = explore(goal)
                dbg(report)
                proc = processes.summary(8)
                return (
                    f"راقبت الشاشة.\n"
                    f"النافذة النشطة: {state.active_title or '—'}\n"
                    f"عدد النوافذ: {len(state.windows)}\n"
                    f"{proc}\n"
                    f"حُفظت لقطة وخبرة أولية."
                )

            if plan.mode == "task_manager":
                from cos.core.task_manager import run_goal

                dbg("task_manager")
                return run_goal(goal)

            if plan.mode == "qc_api":
                from cos.execution.qc_executor import run_backtest_text

                dbg("qc_api executor")
                return run_backtest_text(goal)

            if plan.mode == "workflow":
                from cos.core.workflow import run_matrix_brief

                return run_matrix_brief(goal)

            if plan.mode == "workflow_return":
                from cos.core.workflow import return_to_cursor

                return return_to_cursor(goal)

            result = self.decision.run_plan(
                plan, state, confirm_risky=confirm_risky, dbg=dbg
            )
            dbg(
                f"decision ok={result.ok} learned={result.learned} researched={getattr(result, 'researched', 0)}"
            )
            if result.ok and plug:
                self.world.remember_platform(plug.id, result.reply[:200])
            return result.reply

        except RuntimeError as e:
            dbg(str(e))
            return "توقفت."
        except Exception as e:
            dbg(f"ERROR: {e}")
            return f"حدث خطأ أثناء التنفيذ: {e}"
        finally:
            RUNTIME.busy = False
            try:
                (config.LOGS_DIR / "last_run.txt").write_text(
                    "\n".join(detail), encoding="utf-8"
                )
            except Exception:
                pass
