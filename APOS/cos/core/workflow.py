"""دورة Matrix → QuantConnect — تعتمد على Workflow Engine (v0.4)."""
from __future__ import annotations

from cos.core.workflow_engine import run_workflow
from cos.execution.hand import Action, Supervisor, execute
from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch
from cos.runtime import RUNTIME


def load_matrix_workflow() -> dict:
    from cos.core.workflow_engine import load_workflow

    try:
        return load_workflow("matrix_cycle").raw
    except Exception:
        return {}


def _safe_focus(title: str) -> str:
    sup = Supervisor()
    act = Action(kind="focus", params={"title": title}, confidence=0.85, reason="wf")
    ok, why = sup.approve(act)
    if not ok:
        return why
    try:
        return execute(act)
    except Exception as e:
        return str(e)


def run_matrix_brief(goal: str) -> str:
    """تنفيذ عبر محرك YAML + معالجات خاصة."""
    RUNTIME.check()
    store = ExperienceStore()

    def dbg(m: str) -> None:
        try:
            from cos import config
            from datetime import datetime

            with (config.LOGS_DIR / "runtime.log").open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%H:%M:%S} | WF | {m}\n")
        except Exception:
            pass

    status, ctx = run_workflow("matrix_cycle", goal=goal, dbg=dbg)
    handoff = ctx.data.get("handoff")
    step_ids = [s for s in (load_matrix_workflow().get("steps") or [])]
    ids = " → ".join(str(s.get("id", "?")) for s in step_ids)

    store.record(
        "workflow",
        "matrix_cycle_v04",
        status,
        str(handoff or ""),
        success=(status == "ok"),
    )

    robot_line = (
        f"ملف مرشّح:\n{ctx.robot}\n(مساره في الحافظة)"
        if ctx.robot
        else "لم يُحدد ملف روبوت تلقائياً."
    )
    handoff_line = f"التقرير:\n{handoff}\n\n" if handoff else ""
    return (
        "دورة Matrix / QuantConnect:\n\n"
        f"{robot_line}\n\n"
        "فُتحت QuantConnect (أو رُكّزت) وطُلب/نُسخ الكود حيث أمكن.\n\n"
        f"{handoff_line}"
        f"الحالة: {status}\n"
        f"الخطوات: {ids}\n\n"
        "إن ظهرت شاشة دخول سجّل يدوياً ثم قل: أكمل.\n"
        "بعد النتيجة: «احفظ نتيجة QC» أو «ارجع لـ Cursor»."
    )


def run_matrix_cycle(goal: str) -> str:
    return run_matrix_brief(goal)


def return_to_cursor(goal: str = "") -> str:
    RUNTIME.check()
    from pathlib import Path

    from cos import config

    reports = sorted((config.DATA / "reports").glob("QC_HANDOFF_*.md"), reverse=True)
    notes = [_safe_focus("Cursor")]
    if reports:
        latest = reports[0]
        try:
            import os

            os.startfile(str(latest))  # type: ignore[attr-defined]
            notes.append(f"فُتح التقرير: {latest}")
        except Exception as e:
            notes.append(f"التقرير موجود: {latest} ({e})")
        screen_watch.save_snapshot("wf_return_cursor")
        return (
            "رجعت إلى Cursor وفتحت آخر تقرير الدورة.\n\n"
            f"{latest}\n\n"
            "انسخ منه الملاحظات إلى نافذة Matrix إن لزم."
        )
    screen_watch.save_snapshot("wf_return_no_report")
    return (
        "ركّزت Cursor لكن لا يوجد تقرير QC بعد.\n"
        "قل أولاً: كمل   (ليبدأ فتح QuantConnect وحفظ التقرير)."
    )
