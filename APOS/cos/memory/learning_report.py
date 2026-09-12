"""تقرير التعلّم الدوري — ماذا تعلّم النظام من نجاحاته وأخطائه."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from cos import config
from cos.data import get_data_layer
from cos.memory.experience import ExperienceStore


@dataclass
class LearningReport:
    period_label: str
    since: str
    until: str
    total: int = 0
    successes: int = 0
    failures: int = 0
    success_rate: float = 0.0
    by_platform: dict[str, dict[str, int]] = field(default_factory=dict)
    top_wins: list[str] = field(default_factory=list)
    top_lessons: list[str] = field(default_factory=list)
    recovery_count: int = 0
    goals_count: int = 0
    path: Optional[Path] = None

    def as_text(self) -> str:
        lines = [
            f"[تقرير التعلّم — {self.period_label}]",
            f"الفترة: {self.since} → {self.until}",
            "",
            f"محاولات: {self.total}",
            f"نجاح: {self.successes} | فشل: {self.failures}",
            f"نسبة النجاح: {self.success_rate:.0%}",
            f"أهداف مسجّلة: {self.goals_count}",
            f"تعافٍ/بحث: {self.recovery_count}",
            "",
        ]
        if self.by_platform:
            lines.append("حسب المنصة:")
            for plat, st in sorted(
                self.by_platform.items(),
                key=lambda x: x[1].get("total", 0),
                reverse=True,
            )[:12]:
                ok = st.get("ok", 0)
                tot = st.get("total", 0) or 1
                lines.append(f"  • {plat}: {ok}/{tot} ({ok / tot:.0%})")
            lines.append("")
        if self.top_wins:
            lines.append("أهم النجاحات:")
            lines.extend(f"  ✓ {w}" for w in self.top_wins[:8])
            lines.append("")
        if self.top_lessons:
            lines.append("دروس من الأخطاء:")
            lines.extend(f"  ! {w}" for w in self.top_lessons[:8])
            lines.append("")
        if self.path:
            lines.append(f"حُفظ التقرير: {self.path}")
        if self.total == 0:
            lines.append("لا تجارب في هذه الفترة بعد — استخدم المنظومة وستتراكم هنا.")
        return "\n".join(lines)


def _parse_period(goal: str) -> tuple[str, timedelta]:
    g = (goal or "").lower()
    if any(x in goal or x in g for x in ("اليوم", "today", "يومي")):
        return "اليوم", timedelta(days=1)
    if any(x in goal or x in g for x in ("الشهر", "month", "شهري")):
        return "هذا الشهر", timedelta(days=30)
    if any(x in goal or x in g for x in ("أمس", "yesterday")):
        return "آخر 48 ساعة", timedelta(days=2)
    # افتراضي: أسبوع
    return "هذا الأسبوع", timedelta(days=7)


def _load_json_experiences(since: datetime) -> list[dict[str, Any]]:
    store = ExperienceStore()
    rows: list[dict[str, Any]] = []
    root = config.EXPERIENCE_DIR
    if not root.exists():
        return rows
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        platform = data.get("platform_hint") or path.stem
        for e in data.get("tried") or []:
            at = e.get("at") or ""
            try:
                ts = datetime.fromisoformat(at)
            except Exception:
                continue
            if ts < since:
                continue
            rows.append(
                {
                    "platform": platform,
                    "action": e.get("action") or "",
                    "result": e.get("result") or "",
                    "note": e.get("note") or "",
                    "success": bool(e.get("success")),
                    "created_at": at,
                }
            )
    return rows


def _load_sql_experiences(since: datetime) -> list[dict[str, Any]]:
    layer = get_data_layer()
    since_s = since.isoformat(timespec="seconds")
    out: list[dict[str, Any]] = []
    try:
        with layer.sql._connect() as conn:
            if layer.sql.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT platform,action,result,note,success,created_at FROM experiences WHERE created_at>=%s ORDER BY id DESC",
                        (since_s,),
                    )
                    for r in cur.fetchall():
                        out.append(
                            {
                                "platform": r[0] or "",
                                "action": r[1] or "",
                                "result": r[2] or "",
                                "note": r[3] or "",
                                "success": bool(r[4]),
                                "created_at": r[5] or "",
                            }
                        )
            else:
                cur = conn.execute(
                    "SELECT platform,action,result,note,success,created_at FROM experiences WHERE created_at>=? ORDER BY id DESC",
                    (since_s,),
                )
                for r in cur.fetchall():
                    out.append(
                        {
                            "platform": r["platform"] or "",
                            "action": r["action"] or "",
                            "result": r["result"] or "",
                            "note": r["note"] or "",
                            "success": bool(r["success"]),
                            "created_at": r["created_at"] or "",
                        }
                    )
    except Exception:
        pass
    return out


def build_learning_report(goal: str = "ماذا تعلمت هذا الأسبوع", save: bool = True) -> LearningReport:
    label, delta = _parse_period(goal)
    until = datetime.now()
    since = until - delta
    rows = _load_sql_experiences(since)
    # ادمج JSON إن كان أغنى
    seen = {(r["platform"], r["action"], r["created_at"]) for r in rows}
    for r in _load_json_experiences(since):
        key = (r["platform"], r["action"], r["created_at"])
        if key not in seen:
            rows.append(r)
            seen.add(key)

    by_plat: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0, "total": 0})
    wins: list[str] = []
    lessons: list[str] = []
    recovery = 0
    for r in rows:
        plat = r["platform"] or "unknown"
        by_plat[plat]["total"] += 1
        note = (r.get("note") or "") + " " + (r.get("result") or "")
        if "recover" in note.lower() or "بحث" in note or r.get("action", "").startswith("fail:"):
            if "recover" in note.lower() or "research" in note.lower() or "auto_research" in note.lower():
                recovery += 1
        if r.get("action", "").startswith("fail:") or "trigger_auto_research" in note:
            recovery += 1
        if r["success"]:
            by_plat[plat]["ok"] += 1
            wins.append(f"{plat}/{r['action']}: {(r.get('note') or r.get('result') or '')[:90]}")
        else:
            by_plat[plat]["fail"] += 1
            lessons.append(f"{plat}/{r['action']}: {(r.get('note') or r.get('result') or '')[:90]}")

    # إزالة تكرار الدروس/النجاحات مع الإبقاء على الأحدث
    def uniq(items: list[str], n: int) -> list[str]:
        out, seen_s = [], set()
        for it in items:
            if it in seen_s:
                continue
            seen_s.add(it)
            out.append(it)
            if len(out) >= n:
                break
        return out

    total = len(rows)
    ok = sum(1 for r in rows if r["success"])
    fail = total - ok
    layer = get_data_layer()
    goals = [
        g
        for g in layer.sql.recent_goals(80)
        if (g.get("created_at") or "") >= since.isoformat(timespec="seconds")
    ]

    report = LearningReport(
        period_label=label,
        since=since.strftime("%Y-%m-%d %H:%M"),
        until=until.strftime("%Y-%m-%d %H:%M"),
        total=total,
        successes=ok,
        failures=fail,
        success_rate=(ok / total) if total else 0.0,
        by_platform=dict(by_plat),
        top_wins=uniq(wins, 8),
        top_lessons=uniq(lessons, 8),
        recovery_count=recovery,
        goals_count=len(goals),
    )

    if save:
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = until.strftime("%Y%m%d_%H%M%S")
        path = config.REPORTS_DIR / f"LEARNING_{stamp}.md"
        md = (
            f"# تقرير التعلّم — {report.period_label}\n\n"
            f"{report.as_text()}\n"
        )
        path.write_text(md, encoding="utf-8")
        report.path = path
        try:
            layer.vectors.upsert(
                report.as_text()[:1500],
                {"type": "learning_report", "period": label},
            )
            layer.sql.log_activity("learning_report", label, {"path": str(path), "total": total})
        except Exception:
            pass
    return report
