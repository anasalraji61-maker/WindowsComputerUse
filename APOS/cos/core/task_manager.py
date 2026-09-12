"""مدير المهام الحقيقي — حالة دائمة + مراحل قابلة للتحقق + تعاون Cursor عبر ملفات.

لا يعتمد على وكيل الشاشة كعقل. الماوس خيار أخير عبر مسارات أخرى فقط.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cos import config


COLLAB_DIRNAME = "collab"


def collab_root(project: Optional[Path] = None) -> Path:
    root = Path(project) if project else (config.ROOT.parent)
    path = root / COLLAB_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "history").mkdir(exist_ok=True)
    return path


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Stage:
    id: str
    title: str
    kind: str  # analyze | cursor_task | read_cursor | files | tests | git | report | human
    status: str = "pending"  # pending | running | ok | fail | skipped | blocked
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    id: str
    goal: str
    phase: str = "plan"
    stages: list[Stage] = field(default_factory=list)
    current: int = 0
    attempts: int = 0
    max_attempts: int = 3
    log: list[str] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    needs_human: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "phase": self.phase,
            "stages": [asdict(s) for s in self.stages],
            "current": self.current,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "log": self.log[-200:],
            "results": self.results,
            "needs_human": self.needs_human,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        stages = [Stage(**s) for s in (data.get("stages") or [])]
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            goal=str(data.get("goal") or ""),
            phase=str(data.get("phase") or "plan"),
            stages=stages,
            current=int(data.get("current") or 0),
            attempts=int(data.get("attempts") or 0),
            max_attempts=int(data.get("max_attempts") or 3),
            log=list(data.get("log") or []),
            results=dict(data.get("results") or {}),
            needs_human=str(data.get("needs_human") or ""),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
        )


class TaskStore:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = collab_root(root)
        self.status_path = self.root / "STATUS.json"
        self.task_md = self.root / "TASK.md"
        self.cursor_reply = self.root / "CURSOR_REPLY.md"
        self.report_md = self.root / "REPORT.md"

    def save(self, state: TaskState) -> None:
        state.updated_at = _now()
        self.status_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # archive snapshot
        snap = self.root / "history" / f"{state.id}_{int(time.time())}.json"
        try:
            snap.write_text(
                json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load(self) -> Optional[TaskState]:
        if not self.status_path.exists():
            return None
        try:
            data = json.loads(self.status_path.read_text(encoding="utf-8"))
            return TaskState.from_dict(data)
        except Exception:
            return None

    def append_log(self, state: TaskState, msg: str) -> None:
        state.log.append(f"{_now()} | {msg}")
        self.save(state)


def build_plan(goal: str) -> list[Stage]:
    """خطة ثابتة قابلة للفحص — بدون تخمين شاشة."""
    g = (goal or "").strip()
    low = g.lower()
    stages: list[Stage] = [
        Stage("analyze", "تحليل المشروع وجمع حقائق قابلة للقياس", "analyze"),
    ]

    wants_cursor = any(
        x in g or x in low
        for x in ("cursor", "كورسر", "كورسا", "ناقش", "عدّل", "عدل", "أصلح", "اصلح", "fix")
    )
    wants_test = any(
        x in g or x in low
        for x in ("اختبر", "test", "pytest", "فحص", "افحص", "تحقق")
    )
    wants_git = any(x in g or x in low for x in ("git", "diff", "تغييرات", "الكوميت", "commit"))
    wants_qc = any(
        x in g or x in low
        for x in ("quantconnect", "كوانت", "backtest", "باك تست", "matrixrobotqc")
    )

    if wants_cursor or len(g) > 40:
        stages.append(
            Stage(
                "cursor_task",
                "كتابة طلب منظم لـ Cursor في TASK.md",
                "cursor_task",
            )
        )
        stages.append(
            Stage(
                "read_cursor",
                "قراءة CURSOR_REPLY.md إن وُجد (وإلا انتظار/إبلاغ)",
                "read_cursor",
            )
        )

    stages.append(Stage("files", "فحص الملفات الأساسية ومسار التعاون", "files"))

    if wants_git or wants_cursor:
        stages.append(Stage("git", "مراجعة حالة Git وملخص diff", "git"))

    if wants_test or wants_cursor:
        stages.append(Stage("tests", "تشغيل اختبارات متاحة وتسجيل النتيجة", "tests"))

    if wants_qc:
        stages.append(Stage("qc_api", "محاولة Backtest عبر منفّذ QC API", "qc_api"))

    stages.append(Stage("report", "كتابة REPORT.md النهائي مع الأدلة", "report"))
    return stages


def _project_paths() -> dict[str, Path]:
    root = config.ROOT.parent  # WindowsComputerUse
    return {
        "root": root,
        "apos": config.ROOT,
        "workspace": Path(config.WORKSPACE),
        "collab": collab_root(root),
        "qc_robot": Path(config.WORKSPACE)
        / "MatrixRobot"
        / "artifacts"
        / "python-agents"
        / "quantconnect"
        / "MatrixRobotQC"
        / "main.py",
    }


def _run_analyze(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.task_tools import analyze_project

    paths = _project_paths()
    info = analyze_project(paths)
    state.results["analyze"] = info
    return True, "تم تحليل المشروع", info


def _run_cursor_task(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.cursor_channel import write_task_for_cursor

    path = write_task_for_cursor(
        store=store,
        goal=state.goal,
        context=state.results.get("analyze") or {},
    )
    return True, f"كُتب طلب Cursor: {path.name}", {"task_path": str(path)}


def _run_read_cursor(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.cursor_channel import read_cursor_reply

    reply = read_cursor_reply(store)
    if not reply:
        # لا نفشل المهمة كلها — نبلّغ ونكمل بتحليل محلي
        state.needs_human = (
            "بانتظار رد Cursor: افتح TASK.md في المشروع، نفّذ المطلوب، "
            "ثم اكتب النتيجة في collab/CURSOR_REPLY.md وأعد: أكمل المهمة"
        )
        state.results["cursor_reply"] = None
        return True, "لا يوجد CURSOR_REPLY.md بعد — سأكمل بتحليل محلي وأنتظر ردك/Cursor", {
            "waiting": True,
            "task_file": str(store.task_md),
            "reply_file": str(store.cursor_reply),
        }
    state.results["cursor_reply"] = reply[:4000]
    # إن وصل رد، امسح انتظار بشري عام لهذا السبب
    if "CURSOR_REPLY" in (state.needs_human or ""):
        state.needs_human = ""
    return True, f"قُرئ رد Cursor ({len(reply)} حرف)", {"chars": len(reply)}


def _run_files(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.task_tools import verify_key_files

    ev = verify_key_files(_project_paths())
    state.results["files"] = ev
    ok = bool(ev.get("ok"))
    return ok, ("الملفات الأساسية موجودة" if ok else "نواقص في الملفات"), ev


def _run_git(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.task_tools import git_snapshot

    snap = git_snapshot(_project_paths()["root"])
    state.results["git"] = snap
    return True, "تم التقاط حالة Git", snap


def _run_tests(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.task_tools import run_available_tests

    res = run_available_tests(_project_paths())
    state.results["tests"] = res
    # عدم وجود اختبارات ≠ فشل كارثي
    if res.get("skipped"):
        return True, "لا اختبارات جاهزة — تم التخطي مع توثيق", res
    return bool(res.get("ok")), res.get("summary") or "نتيجة الاختبارات", res


def _run_qc(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.qc_executor import has_credentials, run_backtest

    if not has_credentials():
        msg = "مفاتيح QC غير موجودة — تخطّيت Backtest ووثّقت النقص"
        state.results["qc"] = {"ok": False, "skipped": True, "reason": "missing_credentials"}
        if not state.needs_human:
            state.needs_human = "ضع QC_USER_ID و QC_API_TOKEN في APOS/.env ثم أعد: أكمل المهمة"
        return True, msg, state.results["qc"]
    result = run_backtest()
    state.results["qc"] = {
        "ok": result.ok,
        "summary": result.summary[:1500],
        "report": str(result.report_path) if result.report_path else "",
    }
    return result.ok, ("QC Backtest تم" if result.ok else "QC Backtest فشل"), state.results["qc"]


def _run_report(state: TaskState, store: TaskStore) -> tuple[bool, str, dict]:
    from cos.execution.cursor_channel import write_final_report

    path = write_final_report(store, state)
    state.results["report_path"] = str(path)
    return True, f"التقرير النهائي: {path}", {"report": str(path)}


_HANDLERS = {
    "analyze": _run_analyze,
    "cursor_task": _run_cursor_task,
    "read_cursor": _run_read_cursor,
    "files": _run_files,
    "git": _run_git,
    "tests": _run_tests,
    "qc_api": _run_qc,
    "report": _run_report,
}


def _format_status(state: TaskState, store: TaskStore) -> str:
    lines = [
        "مدير المهام — نتيجة الدورة",
        f"المهمة: {state.goal[:160]}",
        f"المعرّف: {state.id}",
        f"المرحلة العامة: {state.phase}",
        f"المحاولة: {state.attempts}/{state.max_attempts}",
        "",
        "المراحل:",
    ]
    for i, s in enumerate(state.stages):
        mark = {
            "ok": "✓",
            "fail": "✗",
            "running": "…",
            "pending": "·",
            "skipped": "~",
            "blocked": "!",
        }.get(s.status, "?")
        cur = " ←" if i == state.current and state.phase not in ("done", "failed") else ""
        lines.append(f"  {mark} {s.title} [{s.status}]{cur}")
        if s.detail:
            lines.append(f"      {s.detail[:180]}")
    if state.needs_human:
        lines.extend(["", "يحتاج تدخلاً:", state.needs_human])
    report = state.results.get("report_path") or str(store.report_md)
    lines.extend(
        [
            "",
            f"STATUS: {store.status_path}",
            f"TASK:   {store.task_md}",
            f"REPLY:  {store.cursor_reply}",
            f"REPORT: {report}",
        ]
    )
    return "\n".join(lines)


def run_goal(goal: str, *, resume: bool = False, project: Optional[Path] = None) -> str:
    """شغّل مهمة جديدة أو أكمل الحالية. يرجع تقريراً نصياً صادقاً."""
    store = TaskStore(project)
    g = (goal or "").strip()
    resume_keys = ("أكمل", "اكمل", "كمّل", "كمل", "تابع", "استمر", "resume", "continue")

    state: Optional[TaskState] = None
    if resume or any(k in g for k in resume_keys):
        state = store.load()
        if state and state.phase in ("done", "failed") and not any(k in g for k in resume_keys):
            state = None

    if state is None:
        if not g or any(k == g for k in resume_keys):
            existing = store.load()
            if existing:
                return _format_status(existing, store) + "\n\nلا هدف جديد — هذه آخر حالة محفوظة."
            return "لا توجد مهمة نشطة. اكتب هدفاً واضحاً ثم أرسل."
        # هدف جديد
        state = TaskState(
            id=uuid.uuid4().hex[:10],
            goal=g,
            stages=build_plan(g),
            phase="running",
        )
        store.append_log(state, f"بدأت مهمة جديدة: {g[:200]}")
    else:
        store.append_log(state, f"استئناف / تحديث: {g[:200]}")
        if g and not any(k in g for k in resume_keys):
            # هدف جديد أثناء مهمة قديمة → استبدل
            if g != state.goal and len(g) > 12:
                state = TaskState(
                    id=uuid.uuid4().hex[:10],
                    goal=g,
                    stages=build_plan(g),
                    phase="running",
                )
                store.append_log(state, f"بدأت مهمة جديدة بدل السابقة: {g[:200]}")

    # نفّذ المراحل بالترتيب
    while state.current < len(state.stages):
        stage = state.stages[state.current]
        if stage.status == "ok":
            state.current += 1
            continue

        handler = _HANDLERS.get(stage.kind)
        if not handler:
            stage.status = "skipped"
            stage.detail = f"لا منفّذ للنوع: {stage.kind}"
            state.current += 1
            store.save(state)
            continue

        stage.status = "running"
        state.phase = stage.id
        store.save(state)
        try:
            ok, detail, evidence = handler(state, store)
            stage.detail = detail
            stage.evidence = evidence or {}
            if ok:
                stage.status = "ok"
                store.append_log(state, f"OK [{stage.id}] {detail}")
                state.current += 1
            else:
                stage.status = "fail"
                state.attempts += 1
                store.append_log(state, f"FAIL [{stage.id}] {detail}")
                if state.attempts >= state.max_attempts:
                    state.phase = "failed"
                    store.save(state)
                    return _format_status(state, store)
                # إعادة محاولة محدودة لنفس المرحلة
                stage.status = "pending"
                store.save(state)
                continue
        except Exception as e:
            stage.status = "fail"
            stage.detail = f"استثناء: {e}"
            state.attempts += 1
            store.append_log(state, f"EXC [{stage.id}] {e}")
            if state.attempts >= state.max_attempts:
                state.phase = "failed"
                store.save(state)
                return _format_status(state, store)
            stage.status = "pending"
            store.save(state)

    state.phase = "done" if not state.needs_human else "blocked"
    if state.phase == "blocked":
        # أكملنا المراحل لكن نحتاج رد Cursor/مفاتيح
        pass
    store.save(state)
    return _format_status(state, store)


def looks_like_managed_task(text: str) -> bool:
    """هل الطلب يناسب مدير المهام (مركب/مشروعي) لا محادثة ولا ماوس فقط؟"""
    t = (text or "").strip()
    if len(t) < 12:
        return False
    low = t.lower()
    keys = (
        "حلّل",
        "حلل",
        "ناقش",
        "أصلح",
        "اصلح",
        "اختبر",
        "مهمة",
        "خطة",
        "مشروع",
        "cursor",
        "كورسر",
        "تقرير",
        "git",
        "pytest",
        "workflow",
        "أكمل المهمة",
        "اكمل المهمة",
        "مدير المهام",
        "افحص المشروع",
        "عدّل",
        "عدل الكود",
    )
    if any(k in t or k in low for k in keys):
        return True
    # أوامر طويلة عملية
    if len(t) >= 60 and any(x in t for x in ("ثم", "بعدها", "واكتب", "وشغّل", "وشغل")):
        return True
    return False
