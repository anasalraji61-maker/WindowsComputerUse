"""Workflow Engine — تشغيل YAML + معالجات خاصة (Matrix/QC…)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from cos import config
from cos.execution.hand import Action, Supervisor, execute
from cos.plugins import REGISTRY, PluginRegistry
from cos.runtime import RUNTIME

Dbg = Callable[[str], None]
Handler = Callable[["WorkflowStep", "WorkflowContext"], str]


@dataclass
class WorkflowStep:
    id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    plugin: str = ""
    note: str = ""
    optional: bool = False
    core: str = ""


@dataclass
class WorkflowDef:
    id: str
    name: str
    steps: list[WorkflowStep]
    path: Optional[Path] = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    goal: str
    notes: list[str] = field(default_factory=list)
    shots: list[Path] = field(default_factory=list)
    robot: Optional[Path] = None
    data: dict[str, Any] = field(default_factory=dict)


def _as_steps(raw_steps: list[Any]) -> list[WorkflowStep]:
    out: list[WorkflowStep] = []
    for i, s in enumerate(raw_steps or []):
        if not isinstance(s, dict):
            continue
        out.append(
            WorkflowStep(
                id=str(s.get("id") or f"step_{i+1}"),
                action=str(s.get("action") or s.get("kind") or ""),
                params=dict(s.get("params") or {}),
                plugin=str(s.get("plugin") or ""),
                note=str(s.get("note") or s.get("description") or ""),
                optional=bool(s.get("optional", False)),
                core=str(s.get("core") or ""),
            )
        )
    return out


def load_workflow(workflow_id: str, root: Optional[Path] = None) -> WorkflowDef:
    root = root or config.WORKFLOWS_DIR
    direct = root / f"{workflow_id}.yaml"
    path = direct if direct.exists() else None
    if path is None:
        for p in sorted(root.glob("*.yaml")):
            try:
                import yaml

                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                if str(data.get("id") or p.stem) == workflow_id:
                    path = p
                    break
            except Exception:
                continue
        if path is None:
            matches = list(root.glob("*.yaml"))
            path = matches[0] if matches else None
    if path is None:
        raise FileNotFoundError(f"لا يوجد workflow: {workflow_id}")

    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    wid = str(data.get("id") or path.stem)
    return WorkflowDef(
        id=wid,
        name=str(data.get("name") or wid),
        steps=_as_steps(list(data.get("steps") or [])),
        path=path,
        raw=dict(data),
    )


_GENERIC = {
    "focus_window",
    "mouse_move",
    "click",
    "type",
    "hotkey",
    "wait",
    "show_desktop",
    "open_url",
    "open_qc",
}


def step_to_action(step: WorkflowStep, registry: Optional[PluginRegistry] = None) -> Action:
    reg = registry or REGISTRY
    kind = step.action
    params = dict(step.params)
    if step.plugin and "title" not in params:
        plug = reg.get(step.plugin)
        if plug and plug.window_hints:
            params["title"] = plug.window_hints[0]
    if kind == "focus_window" or kind == "focus_workspace":
        if "title" not in params:
            params["title"] = "Cursor"
        return Action(kind="focus", params=params, confidence=0.85, reason=step.note or step.id)
    if kind in _GENERIC:
        return Action(kind=kind, params=params, confidence=0.8, reason=step.note or step.id)
    return Action(
        kind=kind,
        params=params,
        confidence=0.4,
        reason=f"خطوة خاصة: {kind}",
        risky=True,
    )


# —— معالجات خاصة ——
def _h_locate_robot(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution import apps
    from cos.memory.experience import ExperienceStore

    robots = apps.find_robot_candidates(limit=5)
    ctx.robot = robots[0] if robots else None
    store = ExperienceStore()
    if ctx.robot:
        msg = apps.copy_path_to_clipboard(ctx.robot)
        try:
            msg += " | " + apps.copy_file_content_to_clipboard(ctx.robot)
        except Exception as e:
            msg += f" | content:{e}"
        try:
            msg += " | " + apps.open_in_explorer(ctx.robot)
        except Exception as e:
            msg += f" | explorer: {e}"
        store.record("matrix", "locate_robot", "ok", str(ctx.robot), True)
        return msg
    store.record("matrix", "locate_robot", "miss", ctx.goal[:120], False)
    return "لم أجد ملف روبوت مرشّحاً"


def _h_ask_cursor_robot(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution import apps

    path = apps.write_cursor_robot_request(ctx.robot, ctx.goal)
    ctx.data["cursor_request"] = path
    try:
        from cos.perception.windows import focus_window

        focus_window("Cursor")
    except Exception:
        pass
    return f"طُلب من Cursor مراجعة الملف: {path.name}"


def _h_open_qc(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution import apps
    from cos.memory.experience import ExperienceStore

    msg = apps.human_open_url(apps.QC_URL, wait=2.8)
    ExperienceStore().record("quantconnect", "human_open_terminal", "ok", msg, True)
    return msg


def _h_detect_qc_login(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution import apps

    time.sleep(1.2)
    need = apps.qc_login_likely()
    ctx.data["qc_needs_login"] = need
    if need:
        return "يبدو أن QuantConnect يطلب تسجيل دخول — سجّل يدوياً ثم قل: أكمل"
    return "لم تُرصد شاشة دخول واضحة — متابعة"


def _h_qc_paste_backtest(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution import apps

    if ctx.data.get("qc_needs_login"):
        return "تم التخطي بانتظار تسجيل الدخول — بعد الدخول قل: أكمل الفحص في كوانت"
    if ctx.robot:
        try:
            apps.copy_file_content_to_clipboard(ctx.robot)
        except Exception:
            pass
    return apps.qc_paste_and_backtest()


def _h_mouse_sweep(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.execution.hand import mouse_sweep

    return mouse_sweep()


def _h_snapshot(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from cos.perception import screen_watch

    name = str(step.params.get("name") or f"wf_{step.id}")
    path = screen_watch.save_snapshot(name)
    ctx.shots.append(path)
    return f"لقطة: {path.name}"


def _h_mouse_work_area(step: WorkflowStep, ctx: WorkflowContext) -> str:
    import pyautogui

    w, h = pyautogui.size()
    execute(
        Action(
            kind="mouse_move",
            params={
                "x": int(w * float(step.params.get("rx", 0.55))),
                "y": int(h * float(step.params.get("ry", 0.35))),
                "duration": 0.55,
            },
            confidence=0.95,
        )
    )
    execute(
        Action(
            kind="mouse_move",
            params={
                "x": int(w * float(step.params.get("rx2", 0.45))),
                "y": int(h * float(step.params.get("ry2", 0.5))),
                "duration": 0.5,
            },
            confidence=0.95,
        )
    )
    return "حرّكت الماوس في منطقة العمل عدة مرات"


def _h_write_handoff(step: WorkflowStep, ctx: WorkflowContext) -> str:
    from datetime import datetime

    out = config.DATA / "reports"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"QC_HANDOFF_{stamp}.md"
    lines = [
        "# تقرير دورة Matrix / QuantConnect",
        "",
        f"**الوقت:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"**الطلب:** {ctx.goal}",
        "",
        "## ملف الروبوت المرشّح",
        f"- `{ctx.robot}`" if ctx.robot else "- لم يُعثر تلقائياً",
        "",
        "## اللقطات",
        *[f"- `{s}`" for s in ctx.shots],
        "",
        "## ملاحظات التنفيذ",
        *[f"- {n}" for n in ctx.notes[-24:]],
        "",
        "## المطلوب الآن",
        "1. إن ظهرت شاشة دخول: سجّل في QuantConnect ثم قل لـ COS: «أكمل».",
        "2. إن بدأ الـ Backtest: انتظر النتيجة ثم قل: «احفظ نتيجة QC» أو «ارجع لـ Cursor».",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    ctx.data["handoff"] = path
    return str(path)


def _h_user_gate(step: WorkflowStep, ctx: WorkflowContext) -> str:
    if ctx.data.get("qc_needs_login"):
        return "بوابة دخول: سجّل في QuantConnect ثم قل «أكمل» لإعادة اللصق والباك تست"
    return step.note or "إن لم يبدأ الباك تست تلقائياً أكمله يدوياً ثم قل: ارجع لـ Cursor"


def _h_open_handoff(step: WorkflowStep, ctx: WorkflowContext) -> str:
    import os

    reports = sorted((config.DATA / "reports").glob("QC_HANDOFF_*.md"), reverse=True)
    if not reports:
        return "لا يوجد تقرير بعد"
    latest = reports[0]
    try:
        os.startfile(str(latest))  # type: ignore[attr-defined]
    except Exception as e:
        return f"{latest} ({e})"
    return f"فُتح: {latest}"


def _h_analyze_optional(step: WorkflowStep, ctx: WorkflowContext) -> str:
    return "StrategyQuant معطّل في الدورة الافتراضية"


def _h_apply_patch_optional(step: WorkflowStep, ctx: WorkflowContext) -> str:
    return "تطبيق التعديلات اختياري — استخدم Coding Agent أو Claude"


HANDLERS: dict[str, Handler] = {
    "locate_robot_file": _h_locate_robot,
    "ask_cursor_robot": _h_ask_cursor_robot,
    "open_terminal_in_browser": _h_open_qc,
    "open_qc": _h_open_qc,
    "human_open_qc": _h_open_qc,
    "detect_qc_login": _h_detect_qc_login,
    "qc_paste_backtest": _h_qc_paste_backtest,
    "snapshot": _h_snapshot,
    "mouse_sweep": _h_mouse_sweep,
    "mouse_work_area": _h_mouse_work_area,
    "write_handoff": _h_write_handoff,
    "user_gate": _h_user_gate,
    "open_handoff_report": _h_open_handoff,
    "analyze_export_report": _h_analyze_optional,
    "apply_code_changes": _h_apply_patch_optional,
}


def run_workflow(
    workflow_id: str,
    goal: str = "",
    *,
    supervisor: Optional[Supervisor] = None,
    dbg: Optional[Dbg] = None,
) -> tuple[str, WorkflowContext]:
    """يشغّل workflow كاملاً عبر معالجات + إجراءات عامة."""
    log = dbg or (lambda _m: None)
    wf = load_workflow(workflow_id)
    REGISTRY.load_all()
    sup = supervisor or Supervisor()
    ctx = WorkflowContext(goal=goal or wf.name)

    from cos.perception import screen_watch, windows as winmod

    changed, shash = screen_watch.watch_once()
    state = winmod.refresh_world(goal=goal, screen_hash=shash, screen_changed=changed)
    ctx.notes.append(f"نافذة نشطة: {state.active_title or '—'}")

    for step in wf.steps:
        RUNTIME.check()
        log(f"wf:{wf.id}:{step.id}:{step.action}")

        if step.core == "decision" or step.action in ("user_gate", "decide_qc"):
            msg = _h_user_gate(step, ctx)
            ctx.notes.append(msg)
            continue

        if step.action in HANDLERS:
            try:
                msg = HANDLERS[step.action](step, ctx)
                ctx.notes.append(f"{step.id}: {msg}")
                log(msg)
            except Exception as e:
                ctx.notes.append(f"{step.id}:fail {e}")
                if not step.optional:
                    return "fail", ctx
            continue

        # focus_workspace وغيرها العامة
        action = step_to_action(step)
        if action.kind not in (
            "focus",
            "mouse_move",
            "click",
            "type",
            "hotkey",
            "wait",
            "show_desktop",
            "open_url",
            "open_qc",
        ):
            if step.optional:
                ctx.notes.append(f"{step.id}:skipped special")
                continue
            ctx.notes.append(f"{step.id}:unknown {step.action}")
            continue

        ok, why = sup.approve(action)
        if not ok:
            ctx.notes.append(f"{step.id}:blocked {why}")
            continue
        try:
            msg = execute(action)
            ctx.notes.append(f"{step.id}: {msg}")
        except Exception as e:
            ctx.notes.append(f"{step.id}:fail {e}")
            if not step.optional:
                return "fail", ctx

    return "ok", ctx


# توافق الاسم القديم
def run_generic_workflow(
    workflow_id: str,
    *,
    supervisor: Optional[Supervisor] = None,
    dbg: Optional[Dbg] = None,
    stop_on_special: bool = True,
) -> tuple[str, list[str]]:
    status, ctx = run_workflow(workflow_id, goal=workflow_id, supervisor=supervisor, dbg=dbg)
    return status, ctx.notes
