"""Priority Manager + Project Manager — ترتيب الأهداف والمشاريع."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from cos import config
from cos.core.goals import GoalManager, ManagedGoal


class PriorityManager:
    """يحسب أولوية الهدف من كلمات مفتاحية + طلب صريح."""

    URGENT = ("عاجل", "فوري", "الآن", "urgent", "asap", "حرج")
    HIGH = ("مهم", "أولوية", "high", "ضروري", "backtest", "افحص")
    LOW = ("لاحقاً", "لاحقا", "منخفض", "low", "متى ما تفرغ")

    def score(self, text: str, base: int = 50) -> int:
        t = (text or "").lower()
        score = base
        if any(k in text or k in t for k in self.URGENT):
            score += 35
        if any(k in text or k in t for k in self.HIGH):
            score += 20
        if any(k in text or k in t for k in self.LOW):
            score -= 25
        # طول المهمة العملية يرفع قليلاً
        if len(text) > 80:
            score += 5
        return max(0, min(100, score))

    def order(self, goals: list[ManagedGoal]) -> list[ManagedGoal]:
        return sorted(goals, key=lambda g: (-g.priority, g.created_at))


@dataclass
class Project:
    id: str
    name: str
    platforms: list[str] = field(default_factory=list)
    notes: str = ""
    updated_at: str = ""


class ProjectManager:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (config.DATA / "projects.json")
        self.projects: dict[str, Project] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            # مشاريع افتراضية من مخططك
            self.projects = {
                "matrix_robot": Project(
                    id="matrix_robot",
                    name="Matrix Robot Validation",
                    platforms=["quantconnect", "strategyquant", "metatrader5", "tradingview"],
                ),
                "llm_eval": Project(
                    id="llm_eval",
                    name="LLM Evaluation Stack",
                    platforms=["langsmith", "phoenix", "deepeval", "promptfoo", "sonarqube"],
                ),
            }
            self._save()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.projects = {
                k: Project(**v) for k, v in (raw.get("projects") or {}).items()
            }
        except Exception:
            self.projects = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"projects": {k: asdict(v) for k, v in self.projects.items()}}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure(self, project_id: str, name: str = "", platforms: Optional[list[str]] = None) -> Project:
        if project_id not in self.projects:
            self.projects[project_id] = Project(
                id=project_id,
                name=name or project_id,
                platforms=platforms or [],
                updated_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._save()
        return self.projects[project_id]

    def detect_project(self, goal: str) -> str:
        g = goal.lower()
        if any(x in g or x in goal for x in ("langsmith", "deepeval", "promptfoo", "phoenix", "sonar")):
            return "llm_eval"
        if any(
            x in g or x in goal
            for x in ("matrix", "quant", "mt5", "tradingview", "strategy", "روبوت", "backtest")
        ):
            return "matrix_robot"
        return "default"

    def summary(self) -> str:
        lines = ["[Project Manager]"]
        for p in self.projects.values():
            lines.append(f"  • {p.name} ({p.id}): {', '.join(p.platforms) or '—'}")
        return "\n".join(lines)


def enqueue_goal(text: str, goals: Optional[GoalManager] = None) -> ManagedGoal:
    gm = goals or GoalManager()
    pm = PriorityManager()
    proj = ProjectManager()
    project_id = proj.detect_project(text)
    proj.ensure(project_id)
    return gm.add(text, priority=pm.score(text), project=project_id)
