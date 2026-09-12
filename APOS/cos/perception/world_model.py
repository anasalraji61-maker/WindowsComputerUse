"""World Model — معرفة مستمرة عن البيئة: تطبيقات، تفضيلات، أحداث، مسارات."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cos import config
from cos.plugins import REGISTRY


@dataclass
class WorldModel:
    apps: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    known_paths: dict[str, str] = field(default_factory=dict)
    platform_notes: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""

    def touch(self) -> None:
        self.updated_at = datetime.now().isoformat(timespec="seconds")


class WorldModelStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (config.DATA / "world_model.json")
        self.model = WorldModel()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.bootstrap()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.model = WorldModel(
                apps=dict(raw.get("apps") or {}),
                preferences=dict(raw.get("preferences") or {}),
                events=list(raw.get("events") or [])[-200:],
                known_paths=dict(raw.get("known_paths") or {}),
                platform_notes=dict(raw.get("platform_notes") or {}),
                updated_at=str(raw.get("updated_at") or ""),
            )
        except Exception:
            self.bootstrap()

    def save(self) -> None:
        self.model.touch()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(asdict(self.model), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def bootstrap(self) -> None:
        REGISTRY.load_all()
        for p in REGISTRY.load_all().values():
            self.model.apps[p.id] = {
                "name": p.name,
                "kind": p.kind,
                "url": p.url,
                "hints": p.window_hints,
                "category": p.category,
            }
            if p.url:
                self.model.known_paths[p.id] = p.url
        self.model.preferences.setdefault("language", "ar")
        self.model.preferences.setdefault("auto_research", True)
        self.save()

    def note_event(self, kind: str, detail: str, **meta) -> None:
        self.model.events.append(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "kind": kind,
                "detail": detail,
                "meta": meta,
            }
        )
        self.model.events = self.model.events[-200:]
        self.save()

    def remember_platform(self, plugin_id: str, note: str) -> None:
        self.model.platform_notes[plugin_id] = note[:500]
        self.save()

    def summary(self) -> str:
        m = self.model
        lines = [
            f"[World Model] تطبيقات={len(m.apps)} أحداث={len(m.events)} ملاحظات منصات={len(m.platform_notes)}",
            f"تحديث: {m.updated_at or '—'}",
        ]
        for e in m.events[-5:]:
            lines.append(f"  - {e.get('at','')} {e.get('kind')}: {str(e.get('detail'))[:70]}")
        return "\n".join(lines)


_STORE: Optional[WorldModelStore] = None


def get_world_model() -> WorldModelStore:
    global _STORE
    if _STORE is None:
        _STORE = WorldModelStore()
    return _STORE
