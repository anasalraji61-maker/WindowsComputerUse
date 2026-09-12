"""Goal Manager — أهداف متعددة، حالة، وأولوية."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from cos import config


class GoalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class ManagedGoal:
    id: str
    text: str
    priority: int = 50  # 0..100 أعلى = أهم
    status: str = GoalStatus.PENDING.value
    project: str = "default"
    created_at: str = ""
    updated_at: str = ""
    notes: list[str] = field(default_factory=list)
    result: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")


class GoalManager:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (config.DATA / "goals_queue.json")
        self.goals: list[ManagedGoal] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.goals = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.goals = [ManagedGoal(**g) for g in raw.get("goals", [])]
        except Exception:
            self.goals = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"goals": [asdict(g) for g in self.goals]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, text: str, priority: int = 50, project: str = "default") -> ManagedGoal:
        now = datetime.now().isoformat(timespec="seconds")
        g = ManagedGoal(
            id=uuid.uuid4().hex[:10],
            text=text.strip(),
            priority=max(0, min(100, int(priority))),
            project=project,
            created_at=now,
            updated_at=now,
            status=GoalStatus.PENDING.value,
        )
        self.goals.append(g)
        self._save()
        return g

    def next_goal(self) -> Optional[ManagedGoal]:
        pending = [g for g in self.goals if g.status in (GoalStatus.PENDING.value, GoalStatus.ACTIVE.value)]
        if not pending:
            return None
        pending.sort(key=lambda g: (-g.priority, g.created_at))
        return pending[0]

    def mark(self, goal_id: str, status: str, result: str = "") -> Optional[ManagedGoal]:
        for g in self.goals:
            if g.id == goal_id:
                g.status = status
                if result:
                    g.result = result[:2000]
                g.touch()
                self._save()
                return g
        return None

    def list_open(self) -> list[ManagedGoal]:
        return [g for g in self.goals if g.status in (GoalStatus.PENDING.value, GoalStatus.ACTIVE.value, GoalStatus.PAUSED.value)]

    def summary(self) -> str:
        open_g = self.list_open()
        done = sum(1 for g in self.goals if g.status == GoalStatus.DONE.value)
        fail = sum(1 for g in self.goals if g.status == GoalStatus.FAILED.value)
        lines = [
            f"[Goal Manager] مفتوحة={len(open_g)} منجزة={done} فاشلة={fail}",
        ]
        for g in sorted(open_g, key=lambda x: -x.priority)[:8]:
            lines.append(f"  #{g.id} p={g.priority} [{g.status}] {g.text[:80]}")
        return "\n".join(lines)
