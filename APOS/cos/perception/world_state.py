"""World State — صورة موحّدة بسيطة لحالة الجهاز الآن."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class WindowInfo:
    title: str
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    is_active: bool = False


@dataclass
class WorldState:
    timestamp: str = ""
    active_title: str = ""
    windows: list[WindowInfo] = field(default_factory=list)
    screen_changed: bool = False
    screen_hash: str = ""
    goal: str = ""
    step: str = ""
    notes: list[str] = field(default_factory=list)
    processes_top: list[str] = field(default_factory=list)
    plugin_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        titles = [w.title for w in self.windows[:12] if w.title]
        active = self.active_title or "(لا نافذة نشطة)"
        procs = " | ".join(self.processes_top[:5]) if self.processes_top else "—"
        return (
            f"النشطة: {active}\n"
            f"تغيّر الشاشة: {self.screen_changed}\n"
            f"نوافذ ({len(self.windows)}): " + " | ".join(titles[:8]) + "\n"
            f"عمليات: {procs}\n"
            f"plugin: {self.plugin_id or '—'}"
        )


def stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")
