"""Memory interface — قصيرة + طويلة + متجهة + خبرة."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Optional

from cos.data import get_data_layer
from cos.memory.experience import ExperienceStore


@dataclass
class MemoryItem:
    role: str
    content: str
    at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    meta: dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    def __init__(self, maxlen: int = 40):
        self._items: Deque[MemoryItem] = deque(maxlen=maxlen)

    def add(self, role: str, content: str, **meta) -> None:
        self._items.append(MemoryItem(role=role, content=content, meta=meta))

    def recent(self, n: int = 10) -> list[MemoryItem]:
        return list(self._items)[-n:]

    def as_text(self, n: int = 8) -> str:
        return "\n".join(f"{m.role}: {m.content}" for m in self.recent(n))


class LongTermMemory:
    def __init__(self):
        self.layer = get_data_layer()
        self.experience = ExperienceStore()

    def store_fact(self, key: str, value: str) -> None:
        self.layer.cache.set(f"ltm:{key}", value, ttl=86400 * 30)
        self.layer.sql.log_activity("ltm", f"{key}={value}")
        self.layer.vectors.upsert(f"fact:{key}:{value}", {"type": "fact", "key": key})

    def get_fact(self, key: str) -> Any:
        return self.layer.cache.get(f"ltm:{key}")

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        return self.layer.similar_experiences(query, limit=limit)
