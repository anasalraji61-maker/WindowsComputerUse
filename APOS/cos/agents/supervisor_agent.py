"""Supervisor Agent — أمان + صلاحيات + قائمة حظر + سجل نشاط + تأكيدات."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from cos import config
from cos.data import get_data_layer
from cos.execution.hand import Action, Supervisor
from cos.runtime import RUNTIME


DEFAULT_BLOCKLIST = [
    "chrome://settings",
    "ms-settings:",
    "passwd",
    "wallet",
    "seed phrase",
    "private key",
]


@dataclass
class GateResult:
    allowed: bool
    reason: str
    needs_confirm: bool = False


class SupervisorAgent:
    def __init__(self):
        self.inner = Supervisor()
        self.layer = get_data_layer()
        self.blocklist = self._load_blocklist()
        self.permissions = self._load_permissions()

    def _load_blocklist(self) -> list[str]:
        path = config.BLOCKLIST_PATH
        if not path.exists():
            path.write_text("\n".join(DEFAULT_BLOCKLIST) + "\n", encoding="utf-8")
        lines = [
            ln.strip().lower()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        return lines or list(DEFAULT_BLOCKLIST)

    def _load_permissions(self) -> dict:
        path = config.PERMISSIONS_PATH
        default = {
            "allow_delete_files": False,
            "allow_payments": False,
            "allow_credentials": False,
            "allow_install_software": False,
            "max_clicks_per_goal": 40,
        }
        if not path.exists():
            try:
                import yaml

                path.write_text(
                    yaml.safe_dump(default, allow_unicode=True), encoding="utf-8"
                )
            except Exception:
                path.write_text(json.dumps(default, indent=2), encoding="utf-8")
            return default
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            default.update(data)
        except Exception:
            pass
        return default

    def _blocked_text(self, text: str) -> Optional[str]:
        t = (text or "").lower()
        for b in self.blocklist:
            if b and b in t:
                return b
        return None

    def gate_goal(self, goal: str) -> GateResult:
        hit = self._blocked_text(goal)
        if hit:
            self.log("block_goal", f"blocklist:{hit}", {"goal": goal[:200]})
            return GateResult(False, f"محظور بسبب قائمة الحظر: {hit}")
        risky_keys = ("احذف", "delete", "format", "تحويل مالي", "password", "كلمة السر")
        if any(k in goal.lower() or k in goal for k in risky_keys):
            if not self.permissions.get("allow_delete_files") and (
                "احذف" in goal or "delete" in goal.lower()
            ):
                return GateResult(False, "حذف الملفات غير مسموح في الصلاحيات", True)
            return GateResult(True, "إجراء حسّاس — يحتاج تأكيداً", True)
        return GateResult(True, "مسموح")

    def gate_action(self, action: Action, confirm_risky: bool = False) -> GateResult:
        RUNTIME.check()
        blob = f"{action.kind} {action.params} {action.reason}"
        hit = self._blocked_text(blob)
        if hit:
            return GateResult(False, f"إجراء محظور: {hit}")
        ok, why = self.inner.approve(action)
        if not ok:
            if action.risky and confirm_risky:
                return GateResult(True, "تأكيد المستخدم تجاوز الحظر الجزئي")
            return GateResult(False, why, needs_confirm=action.risky)
        return GateResult(True, why)

    def log(self, kind: str, detail: str, meta: Optional[dict] = None) -> None:
        self.layer.sql.log_activity(kind, detail, meta)
        try:
            line = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "kind": kind,
                "detail": detail,
                "meta": meta or {},
            }
            with config.ACTIVITY_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def emergency_stop(self) -> str:
        RUNTIME.kill()
        self.log("kill", "emergency_stop")
        return "إيقاف طارئ مفعّل"

    def run(self, goal: str) -> str:
        g = self.gate_goal(goal)
        status = self.layer.status()
        brain = ""
        try:
            from cos.brain import status_text

            brain = "\n" + status_text()
        except Exception:
            pass
        return (
            f"[Supervisor Agent]\n"
            f"الهدف: {'مسموح' if g.allowed else 'مرفوض'} — {g.reason}\n"
            f"تأكيد مطلوب: {g.needs_confirm}\n"
            f"صلاحيات: {self.permissions}\n"
            f"حظر: {len(self.blocklist)} بنداً\n"
            f"SQL={status['sql']['backend']} Redis={status['redis']['backend']} Vector={status['vector']['backend']}"
            f"{brain}"
        )
