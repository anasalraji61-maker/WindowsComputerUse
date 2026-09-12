"""أدوات منفّذ المهام — ملفات / Git / اختبارات (بدون ماوس)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def analyze_project(paths: dict[str, Path]) -> dict[str, Any]:
    root = paths["root"]
    apos = paths["apos"]
    facts: dict[str, Any] = {
        "root": str(root),
        "apos": str(apos),
        "workspace": str(paths.get("workspace") or ""),
        "exists": {},
        "counts": {},
        "notes": [],
    }
    important = {
        "open_system.bat": root / "open_system.bat",
        "chat_ui.py": root / "chat_ui.py",
        "agent.py": root / "agent.py",
        "APOS/ui/app.py": apos / "ui" / "app.py",
        "task_manager.py": apos / "cos" / "core" / "task_manager.py",
        "qc_executor.py": apos / "cos" / "execution" / "qc_executor.py",
        "qc_robot_main": paths.get("qc_robot") or Path("."),
    }
    for name, p in important.items():
        facts["exists"][name] = bool(p and Path(p).exists())

    try:
        py_count = sum(1 for _ in apos.rglob("*.py") if ".venv" not in _.parts and "__pycache__" not in _.parts)
        facts["counts"]["apos_py_files"] = py_count
    except Exception as e:
        facts["notes"].append(f"count_error: {e}")

    robot = paths.get("qc_robot")
    if robot and Path(robot).exists():
        facts["qc_robot_bytes"] = Path(robot).stat().st_size
        facts["notes"].append("MatrixRobotQC/main.py موجود")
    else:
        facts["notes"].append("MatrixRobotQC/main.py غير موجود بالمسار المتوقع")

    # كشف مسار الشاشة القديم
    try:
        chat_ui = (root / "chat_ui.py").read_text(encoding="utf-8", errors="replace")
        facts["chat_ui_uses_smart_mission"] = "run_smart_mission" in chat_ui
        facts["chat_ui_routes_to_task_manager"] = "run_managed_task" in chat_ui
        if facts["chat_ui_routes_to_task_manager"]:
            facts["notes"].append("chat_ui يوجّه المهام المركبة إلى مدير المهام")
        elif facts["chat_ui_uses_smart_mission"]:
            facts["notes"].append("تحذير: chat_ui ما زال يعتمد run_smart_mission كمسار أساسي")
    except Exception:
        pass

    facts["ok"] = True
    return {"ok": True, "facts": facts}


def verify_key_files(paths: dict[str, Path]) -> dict[str, Any]:
    required = [
        paths["root"] / "open_system.bat",
        paths["apos"] / "ui" / "app.py",
        paths["apos"] / "cos" / "core" / "task_manager.py",
        paths["apos"] / "cos" / "execution" / "qc_executor.py",
    ]
    missing = [str(p) for p in required if not p.exists()]
    collab = paths["collab"]
    return {
        "ok": not missing,
        "missing": missing,
        "collab_dir": str(collab),
        "collab_ready": collab.exists(),
    }


def git_snapshot(repo: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"repo": str(repo), "ok": False}
    if not (repo / ".git").exists():
        out["skipped"] = True
        out["summary"] = "لا يوجد مستودع Git هنا"
        out["ok"] = True
        return out

    def _run(args: list[str]) -> str:
        try:
            p = subprocess.run(
                args,
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
            )
            return ((p.stdout or "") + (p.stderr or "")).strip()
        except Exception as e:
            return f"error: {e}"

    status = _run(["git", "status", "-sb"])
    diff = _run(["git", "diff", "--stat"])
    out.update(
        {
            "ok": True,
            "status": status[:2000],
            "diff_stat": diff[:2000],
            "summary": (status.splitlines()[0] if status else "git ok"),
        }
    )
    return out


def run_available_tests(paths: dict[str, Path]) -> dict[str, Any]:
    """يشغّل اختباراً خفيفاً إن وُجد؛ وإلا يوثّق التخطي."""
    root = paths["root"]
    apos = paths["apos"]
    candidates = [
        apos / "tools" / "smoke_plan_upgrade.py",
        root / "run_test.bat",
    ]
    found = [p for p in candidates if p.exists()]
    if not found:
        return {
            "ok": True,
            "skipped": True,
            "summary": "لا ملف اختبار جاهز — تخطّيت",
            "candidates_checked": [str(p) for p in candidates],
        }

    target = found[0]
    if target.suffix == ".py":
        try:
            p = subprocess.run(
                ["python", str(target)],
                cwd=str(apos if "APOS" in str(target) else root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            text = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
            return {
                "ok": p.returncode == 0,
                "command": f"python {target.name}",
                "returncode": p.returncode,
                "output": text[:3000],
                "summary": "اختبار خفيف نجح" if p.returncode == 0 else "اختبار خفيف فشل",
            }
        except Exception as e:
            return {"ok": False, "summary": f"فشل تشغيل الاختبار: {e}"}

    return {
        "ok": True,
        "skipped": True,
        "summary": f"وُجد {target.name} لكن التشغيل التلقائي للـ bat مؤجّل",
        "path": str(target),
    }
