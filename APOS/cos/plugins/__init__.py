"""Plugin registry — تحميل إضافات خفيفة من YAML (هوية مسار لا أزرار ثابتة)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cos import config


@dataclass
class Plugin:
    id: str
    name: str
    window_hints: list[str] = field(default_factory=list)
    skills_preferred: list[str] = field(default_factory=list)
    category: str = "general"  # trading_test | llm_eval | ide | robot | general
    kind: str = "mixed"  # web | desktop | cli | mixed
    role: str = ""
    url: str = ""
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    path: Optional[Path] = None

    def matches_window(self, title: str) -> bool:
        t = (title or "").lower()
        return any(h.lower() in t for h in self.window_hints if h)

    def matches_goal(self, goal: str) -> bool:
        g = (goal or "").lower()
        needles = [self.id, self.name] + self.window_hints + self.tags
        return any(n and n.lower() in g for n in needles)


class PluginRegistry:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or (config.ROOT / "plugins")
        self._plugins: dict[str, Plugin] = {}

    def load_all(self, force: bool = False) -> dict[str, Plugin]:
        if self._plugins and not force:
            return self._plugins
        self._plugins = {}
        if not self.root.exists():
            return self._plugins
        try:
            import yaml
        except ImportError as e:
            raise RuntimeError("ثبّت PyYAML: pip install PyYAML") from e

        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or folder.name.startswith("_"):
                continue
            meta = folder / "plugin.yaml"
            if not meta.exists():
                continue
            try:
                data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            pid = folder.name
            plugin = Plugin(
                id=pid,
                name=str(data.get("name") or pid),
                window_hints=list(data.get("window_hints") or []),
                skills_preferred=list(data.get("skills_preferred") or []),
                category=str(data.get("category") or "general"),
                kind=str(data.get("kind") or "mixed"),
                role=str(data.get("role") or ""),
                url=str(data.get("url") or ""),
                tags=list(data.get("tags") or []),
                raw=dict(data),
                path=folder,
            )
            self._plugins[pid] = plugin
        return self._plugins

    def get(self, plugin_id: str) -> Optional[Plugin]:
        self.load_all()
        return self._plugins.get(plugin_id)

    def by_category(self, category: str) -> list[Plugin]:
        self.load_all()
        return [p for p in self._plugins.values() if p.category == category]

    def detect_from_title(self, title: str) -> Optional[Plugin]:
        self.load_all()
        for p in self._plugins.values():
            if p.matches_window(title):
                return p
        return None

    def detect_from_goal(self, goal: str) -> Optional[Plugin]:
        self.load_all()
        hits = [p for p in self._plugins.values() if p.matches_goal(goal)]
        if not hits:
            return None
        # فضّل تطابق الاسم الأطول / الأدق
        hits.sort(key=lambda p: max((len(h) for h in p.window_hints + [p.name, p.id]), default=0), reverse=True)
        return hits[0]

    def list_ids(self) -> list[str]:
        return list(self.load_all().keys())

    def catalog(self) -> dict[str, list[str]]:
        self.load_all()
        out: dict[str, list[str]] = {}
        for p in self._plugins.values():
            out.setdefault(p.category, []).append(p.id)
        for k in out:
            out[k].sort()
        return out


REGISTRY = PluginRegistry()
