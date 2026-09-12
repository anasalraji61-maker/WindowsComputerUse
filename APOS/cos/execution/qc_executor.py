"""منفّذ QuantConnect المتخصص — رفع كود → Compile → Backtest → تقرير رقمي.

بدون ماوس وبدون متصفح. يحتاج QC_USER_ID + QC_API_TOKEN مرة واحدة.
"""
from __future__ import annotations

import json
import time
from base64 import b64encode
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cos import config

BASE_URL = "https://www.quantconnect.com/api/v2"
DEFAULT_PROJECT = "MatrixRobotQC"
DEFAULT_ROBOT = (
    Path.home()
    / "Downloads"
    / "MatrixRobot_Handoff_Clean-3"
    / "MatrixRobot"
    / "artifacts"
    / "python-agents"
    / "quantconnect"
    / "MatrixRobotQC"
    / "main.py"
)


@dataclass
class QcResult:
    ok: bool
    summary: str
    report_path: Optional[Path] = None
    stats: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    project_id: Optional[int] = None
    backtest_id: str = ""
    url: str = ""


def credentials() -> tuple[str, str]:
    uid = (getattr(config, "QC_USER_ID", "") or "").strip()
    tok = (getattr(config, "QC_API_TOKEN", "") or "").strip()
    return uid, tok


def has_credentials() -> bool:
    uid, tok = credentials()
    return bool(uid and tok and len(tok) > 8)


def credentials_help() -> str:
    return (
        "منفّذ QC جاهز، لكن ينقصه مفتاحان مرة واحدة:\n\n"
        "1) افتح: https://www.quantconnect.com/settings/\n"
        "2) انسخ User ID و API Token من Security\n"
        "3) ضعهما في ملف APOS\\.env:\n"
        "   QC_USER_ID=...\n"
        "   QC_API_TOKEN=...\n\n"
        "ثم شغّل: RUN_QC_BACKTEST.bat\n"
        "أو من COS قل: افحص روبوت ماتريكس"
    )


def find_robot_main() -> Optional[Path]:
    """أفضل مسار معروف لملف الخوارزمية."""
    candidates: list[Path] = []
    preferred = [
        DEFAULT_ROBOT,
        Path(config.WORKSPACE)
        / "MatrixRobot"
        / "artifacts"
        / "python-agents"
        / "quantconnect"
        / "MatrixRobotQC"
        / "main.py",
        Path.home()
        / "Downloads"
        / "MatrixRobot_Handoff_Clean"
        / "MatrixRobot"
        / "artifacts"
        / "python-agents"
        / "quantconnect"
        / "MatrixRobotQC"
        / "main.py",
        Path.home()
        / "Downloads"
        / "MATRIX--ROBOT-"
        / "MatrixRobot"
        / "artifacts"
        / "python-agents"
        / "quantconnect"
        / "MatrixRobotQC"
        / "main.py",
    ]
    for p in preferred:
        try:
            if p.exists() and p.is_file():
                candidates.append(p.resolve())
        except Exception:
            continue
    if candidates:
        return candidates[0]
    try:
        from cos.execution.apps import find_robot_candidates

        for p in find_robot_candidates(8):
            if p.name.lower() == "main.py" and "matrixrobotqc" in str(p).lower():
                return p
        for p in find_robot_candidates(8):
            if p.name.lower() == "main.py":
                return p
    except Exception:
        pass
    return None


def _headers() -> dict[str, str]:
    uid, tok = credentials()
    timestamp = str(int(time.time()))
    hashed = sha256(f"{tok}:{timestamp}".encode("utf-8")).hexdigest()
    auth = b64encode(f"{uid}:{hashed}".encode("utf-8")).decode("ascii")
    return {
        "Authorization": f"Basic {auth}",
        "Timestamp": timestamp,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "COS-QC-Executor/1.0",
    }


def _post(path: str, payload: Optional[dict] = None, timeout: float = 60.0) -> dict[str, Any]:
    data = json.dumps(payload or {}).encode("utf-8")
    req = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=_headers(),
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"QC HTTP {e.code}: {body[:400]}") from e
    except URLError as e:
        raise RuntimeError(f"تعذّر الاتصال بـ QuantConnect: {e}") from e
    try:
        return json.loads(raw) if raw else {}
    except Exception as e:
        raise RuntimeError(f"رد QC غير JSON: {raw[:200]}") from e


def authenticate() -> dict[str, Any]:
    return _post("/authenticate", {})


def list_projects() -> list[dict[str, Any]]:
    data = _post("/projects/read", {})
    projects = data.get("projects") or data.get("project") or []
    if isinstance(projects, dict):
        return [projects]
    return list(projects)


def find_or_create_project(name: str = DEFAULT_PROJECT) -> int:
    for p in list_projects():
        if str(p.get("name") or "").strip() == name:
            return int(p["projectId"])
    created = _post("/projects/create", {"name": name, "language": "Py"})
    # response shapes vary
    pid = created.get("projectId")
    if pid is None and isinstance(created.get("projects"), list) and created["projects"]:
        pid = created["projects"][0].get("projectId")
    if pid is None and isinstance(created.get("project"), dict):
        pid = created["project"].get("projectId")
    if pid is None:
        # refresh list
        for p in list_projects():
            if str(p.get("name") or "").strip() == name:
                return int(p["projectId"])
        raise RuntimeError(f"فشل إنشاء المشروع: {json.dumps(created, ensure_ascii=False)[:400]}")
    return int(pid)


def upsert_main(project_id: int, content: str, filename: str = "main.py") -> str:
    # حاول تحديث؛ إن فشل أنشئ
    try:
        upd = _post(
            "/files/update",
            {"projectId": project_id, "name": filename, "content": content},
            timeout=120.0,
        )
        if upd.get("success", True) is not False and not upd.get("errors"):
            return "updated"
    except Exception:
        pass
    created = _post(
        "/files/create",
        {"projectId": project_id, "name": filename, "content": content},
        timeout=120.0,
    )
    if created.get("success") is False:
        raise RuntimeError(f"فشل رفع الملف: {created}")
    return "created"


def compile_project(project_id: int, timeout_sec: float = 180.0) -> str:
    started = _post("/compile/create", {"projectId": project_id})
    compile_id = started.get("compileId") or started.get("compileID")
    if not compile_id:
        raise RuntimeError(f"لم يُرجع compileId: {started}")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        st = _post("/compile/read", {"projectId": project_id, "compileId": compile_id})
        state = str(st.get("state") or st.get("status") or "").lower()
        if state in ("buildsuccess", "success", "ok"):
            return str(compile_id)
        if state in ("builderror", "error", "failed"):
            logs = st.get("logs") or st.get("errors") or st
            raise RuntimeError(f"فشل التجميع (compile): {logs}")
        time.sleep(2.0)
    raise RuntimeError("انتهت مهلة التجميع")


def create_backtest(project_id: int, compile_id: str, name: str) -> str:
    data = _post(
        "/backtests/create",
        {
            "projectId": project_id,
            "compileId": compile_id,
            "backtestName": name,
        },
        timeout=90.0,
    )
    bt = data.get("backtest") or data
    bid = bt.get("backtestId") or bt.get("backtestID") or data.get("backtestId")
    if not bid:
        raise RuntimeError(f"لم يُرجع backtestId: {data}")
    return str(bid)


def wait_backtest(
    project_id: int, backtest_id: str, timeout_sec: float = 900.0
) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _post(
            "/backtests/read",
            {"projectId": project_id, "backtestId": backtest_id},
            timeout=60.0,
        )
        bt = last.get("backtest") or last
        completed = bt.get("completed")
        progress = bt.get("progress")
        status = str(bt.get("status") or "").lower()
        if completed is True or status in ("completed", "complete.success", "success"):
            return last
        if status in ("runtime error", "error", "cancelled", "canceled"):
            raise RuntimeError(f"فشل الباك تست: {bt.get('error') or bt.get('stacktrace') or bt}")
        # progress can be 1.0 when done
        try:
            if float(progress) >= 0.999 and completed is not False:
                # still wait for completed flag unless clearly done
                if completed is True:
                    return last
        except Exception:
            pass
        time.sleep(4.0)
    raise RuntimeError(f"انتهت مهلة الباك تست. آخر رد: {json.dumps(last, ensure_ascii=False)[:500]}")


def _pick_stats(backtest_payload: dict[str, Any]) -> dict[str, Any]:
    bt = backtest_payload.get("backtest") or backtest_payload
    stats = bt.get("statistics") or {}
    runtime = bt.get("runtimeStatistics") or {}
    out: dict[str, Any] = {}
    if isinstance(stats, dict):
        out.update({str(k): v for k, v in stats.items()})
    if isinstance(runtime, dict):
        for k, v in runtime.items():
            out.setdefault(str(k), v)
    # useful extras
    for k in ("totalPerformance", "equity", "alpha", "beta", "sharpeRatio", "drawdown"):
        if k in bt and k not in out:
            out[k] = bt[k]
    out["_name"] = bt.get("name") or ""
    out["_url"] = bt.get("url") or ""
    out["_error"] = bt.get("error") or ""
    return out


def _format_summary(
    *,
    robot: Path,
    project_id: int,
    backtest_id: str,
    stats: dict[str, Any],
    report_path: Path,
) -> str:
    keys_pref = [
        "Net Profit",
        "Compounding Annual Return",
        "Sharpe Ratio",
        "Drawdown",
        "Total Orders",
        "Win Rate",
        "Loss Rate",
        "Profit-Loss Ratio",
        "Average Win",
        "Average Loss",
        "Equity",
        "Return",
    ]
    lines = [
        "نتيجة Backtest QuantConnect (منفّذ مباشر — بلا ماوس)",
        f"الملف: {robot}",
        f"Project ID: {project_id}",
        f"Backtest ID: {backtest_id}",
        "",
        "إحصائيات:",
    ]
    shown = set()
    for k in keys_pref:
        if k in stats:
            lines.append(f"  - {k}: {stats[k]}")
            shown.add(k)
    # أضف بضع مفاتيح إضافية
    extra = 0
    for k, v in stats.items():
        if k.startswith("_") or k in shown:
            continue
        lines.append(f"  - {k}: {v}")
        extra += 1
        if extra >= 8:
            break
    if stats.get("_error"):
        lines.append(f"خطأ معلن: {stats['_error']}")
    if stats.get("_url"):
        lines.append(f"رابط: {stats['_url']}")
    lines.append(f"التقرير: {report_path}")
    return "\n".join(lines)


def run_backtest(
    *,
    robot_path: Optional[Path] = None,
    project_name: str = DEFAULT_PROJECT,
    poll_timeout: float = 900.0,
) -> QcResult:
    """المسار الكامل: اعتماد → مشروع → رفع → تجميع → باك تست → تقرير."""
    if not has_credentials():
        return QcResult(ok=False, summary=credentials_help(), errors=["missing_credentials"])

    robot = Path(robot_path) if robot_path else find_robot_main()
    if robot is None or not robot.exists():
        return QcResult(
            ok=False,
            summary=(
                "لم أجد main.py لروبوت MatrixRobotQC.\n"
                f"المسار المتوقع:\n{DEFAULT_ROBOT}"
            ),
            errors=["robot_not_found"],
        )

    try:
        auth = authenticate()
        if auth.get("success") is False:
            return QcResult(
                ok=False,
                summary=f"فشل التحقق من مفاتيح QC:\n{auth}\n\n" + credentials_help(),
                errors=["auth_failed"],
            )

        content = robot.read_text(encoding="utf-8", errors="replace")
        if "class MatrixRobotQC" not in content and "QCAlgorithm" not in content:
            return QcResult(
                ok=False,
                summary=f"الملف لا يبدو خوارزمية QC صالحة:\n{robot}",
                errors=["invalid_algorithm"],
            )

        project_id = find_or_create_project(project_name)
        upsert_main(project_id, content, "main.py")
        compile_id = compile_project(project_id)
        bt_name = f"COS_{time.strftime('%Y%m%d_%H%M%S')}"
        backtest_id = create_backtest(project_id, compile_id, bt_name)
        payload = wait_backtest(project_id, backtest_id, timeout_sec=poll_timeout)
        stats = _pick_stats(payload)

        ts = time.strftime("%Y%m%d_%H%M%S")
        report_path = config.REPORTS_DIR / f"QC_API_{ts}.md"
        body = [
            "# QuantConnect Backtest Report (API Executor)",
            "",
            f"- robot: `{robot}`",
            f"- projectId: `{project_id}`",
            f"- backtestId: `{backtest_id}`",
            f"- name: `{bt_name}`",
            "",
            "## Statistics",
            "",
        ]
        for k, v in stats.items():
            if k.startswith("_"):
                continue
            body.append(f"- **{k}**: {v}")
        if stats.get("_url"):
            body.extend(["", f"URL: {stats['_url']}"])
        if stats.get("_error"):
            body.extend(["", f"Error: {stats['_error']}"])
        report_path.write_text("\n".join(body) + "\n", encoding="utf-8")

        summary = _format_summary(
            robot=robot,
            project_id=project_id,
            backtest_id=backtest_id,
            stats=stats,
            report_path=report_path,
        )
        ok = not bool(stats.get("_error"))
        return QcResult(
            ok=ok,
            summary=summary,
            report_path=report_path,
            stats=stats,
            project_id=project_id,
            backtest_id=backtest_id,
            url=str(stats.get("_url") or ""),
        )
    except Exception as e:
        return QcResult(
            ok=False,
            summary=f"فشل منفّذ QC:\n{e}",
            errors=[type(e).__name__, str(e)],
        )


def run_backtest_text(goal: str = "") -> str:
    """واجهة نصية لـ COS / السكربتات."""
    _ = goal
    result = run_backtest()
    return result.summary
