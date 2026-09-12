"""Experience Memory — JSON + طبقة البيانات (SQL/Vector/Redis)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cos import config


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", text.strip().lower())
    return (s[:80] or "unknown").strip("_")


class ExperienceStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or config.EXPERIENCE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, platform_hint: str) -> Path:
        return self.root / f"{_slug(platform_hint)}.json"

    def load(self, platform_hint: str) -> dict[str, Any]:
        p = self.path_for(platform_hint)
        if not p.exists():
            return {
                "platform_hint": platform_hint,
                "tried": [],
                "best": None,
                "skills_used": [],
                "updated_at": None,
            }
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"platform_hint": platform_hint, "tried": [], "best": None}

    def record(
        self,
        platform_hint: str,
        action: str,
        result: str,
        note: str = "",
        success: bool = False,
    ) -> dict[str, Any]:
        data = self.load(platform_hint)
        entry = {
            "action": action,
            "result": result,
            "note": note,
            "success": success,
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        data.setdefault("tried", []).append(entry)
        data["tried"] = data["tried"][-50:]
        if success:
            data["best"] = {
                "action": action,
                "confidence": 0.8,
                "note": note,
            }
        data["updated_at"] = entry["at"]
        data["platform_hint"] = platform_hint
        self.path_for(platform_hint).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            from cos.data import get_data_layer

            get_data_layer().remember_experience(
                platform_hint, action, result, note, success
            )
        except Exception:
            pass
        return data

    def best_action(self, platform_hint: str) -> Optional[str]:
        data = self.load(platform_hint)
        best = data.get("best") or {}
        return best.get("action")

    def recent_failures(self, platform_hint: str, action: str, limit: int = 5) -> int:
        data = self.load(platform_hint)
        tried = list(data.get("tried") or [])[-limit:]
        return sum(1 for e in tried if e.get("action") == action and not e.get("success"))

    def summarize(self, platform_hint: str) -> str:
        data = self.load(platform_hint)
        tried = data.get("tried") or []
        best = data.get("best") or {}
        ok = sum(1 for e in tried if e.get("success"))
        return f"خبرات={len(tried)} نجاح={ok} أفضل={best.get('action') or '—'}"
