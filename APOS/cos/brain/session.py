"""ذاكرة جلسة: هدف → خطوات → حالة عبر عدة جولات."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingPlan:
    goal: str
    summary: str
    steps: list[str] = field(default_factory=list)
    kind: str = "other"
    created_at: float = field(default_factory=time.time)


@dataclass
class SessionState:
    topic: str = ""
    goal: str = ""
    steps: list[str] = field(default_factory=list)
    status: str = "idle"  # idle | clarifying | executing | done | failed
    pending: PendingPlan | None = None
    history: list[tuple[str, str]] = field(default_factory=list)
    last_result: str = ""
    updated_at: float = field(default_factory=time.time)


class SessionMemory:
    """ذاكرة جلسة واحدة مشتركة (نص + صوت)."""

    def __init__(self, max_history: int = 24) -> None:
        self._lock = threading.Lock()
        self._max_history = max_history
        self.state = SessionState()

    def reset(self) -> None:
        with self._lock:
            self.state = SessionState()

    def add_turn(self, role: str, text: str) -> None:
        t = (text or "").strip()
        if not t:
            return
        with self._lock:
            self.state.history.append((role, t))
            if len(self.state.history) > self._max_history:
                self.state.history = self.state.history[-self._max_history :]
            self.state.updated_at = time.time()

    def set_topic(self, topic: str, goal: str = "") -> None:
        with self._lock:
            self.state.topic = (topic or "").strip()
            if goal:
                self.state.goal = goal.strip()
            self.state.updated_at = time.time()

    def set_pending(self, plan: PendingPlan) -> None:
        with self._lock:
            self.state.pending = plan
            self.state.goal = plan.goal
            self.state.topic = plan.summary or plan.goal
            self.state.steps = list(plan.steps)
            self.state.status = "clarifying"
            self.state.updated_at = time.time()

    def clear_pending(self) -> PendingPlan | None:
        with self._lock:
            p = self.state.pending
            self.state.pending = None
            return p

    def get_pending(self) -> PendingPlan | None:
        with self._lock:
            return self.state.pending

    def mark_executing(self, goal: str = "") -> None:
        with self._lock:
            if goal:
                self.state.goal = goal
            self.state.status = "executing"
            self.state.pending = None
            self.state.updated_at = time.time()

    def mark_done(self, result: str = "") -> None:
        with self._lock:
            self.state.status = "done"
            self.state.last_result = (result or "")[:2000]
            self.state.updated_at = time.time()

    def mark_failed(self, result: str = "") -> None:
        with self._lock:
            self.state.status = "failed"
            self.state.last_result = (result or "")[:2000]
            self.state.updated_at = time.time()

    def mark_idle(self) -> None:
        with self._lock:
            self.state.status = "idle"
            self.state.pending = None
            self.state.updated_at = time.time()

    def context_block(self, *, max_turns: int = 8) -> str:
        """نص قصير يُحقن في برومبت الفهم/التوضيح."""
        with self._lock:
            s = self.state
            lines: list[str] = []
            if s.topic:
                lines.append(f"موضوع الجلسة: {s.topic}")
            if s.goal:
                lines.append(f"الهدف الحالي: {s.goal}")
            if s.steps:
                lines.append("الخطوات: " + " → ".join(s.steps[:8]))
            lines.append(f"الحالة: {s.status}")
            if s.pending:
                lines.append(f"بانتظار التأكيد على: {s.pending.summary}")
            if s.last_result:
                lines.append(f"آخر نتيجة: {s.last_result[:240]}")
            hist = s.history[-max_turns:]
            if hist:
                lines.append("حوار أخير:")
                for role, text in hist:
                    lines.append(f"  {role}: {text[:180]}")
            return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = self.state
            return {
                "topic": s.topic,
                "goal": s.goal,
                "steps": list(s.steps),
                "status": s.status,
                "pending": None
                if not s.pending
                else {
                    "goal": s.pending.goal,
                    "summary": s.pending.summary,
                    "steps": list(s.pending.steps),
                    "kind": s.pending.kind,
                },
                "history_len": len(s.history),
            }


# جلسة عالمية للواجهة
SESSION = SessionMemory()
