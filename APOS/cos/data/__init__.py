"""Data Layer موحّد — SQL + Redis + Qdrant/Vector + Timeseries."""
from __future__ import annotations

from typing import Any, Optional

from cos.data.redis_cache import RedisCache
from cos.data.sql_store import SqlStore
from cos.data.timeseries import TimeSeriesStore
from cos.data.vector_store import VectorStore


class DataLayer:
    def __init__(self):
        self.sql = SqlStore()
        self.cache = RedisCache()
        self.vectors = VectorStore()
        self.ts = TimeSeriesStore(self.sql)

    def remember_experience(
        self,
        platform: str,
        action: str,
        result: str,
        note: str = "",
        success: bool = False,
    ) -> None:
        self.sql.record_experience(platform, action, result, note, success)
        text = f"{platform} | {action} | {result} | {note} | success={success}"
        self.vectors.upsert(
            text,
            payload={
                "platform": platform,
                "action": action,
                "success": success,
                "note": note,
            },
        )
        self.cache.set(f"last:exp:{platform}", {"action": action, "success": success}, ttl=86400)

    def similar_experiences(self, query: str, limit: int = 5) -> list[dict]:
        return self.vectors.search(query, limit=limit)

    def status(self) -> dict[str, Any]:
        sys = self.ts.sample_system()
        return {
            "sql": self.sql.status(),
            "redis": self.cache.status(),
            "vector": self.vectors.status(),
            "system": sys,
        }


_LAYER: Optional[DataLayer] = None


def get_data_layer() -> DataLayer:
    global _LAYER
    if _LAYER is None:
        _LAYER = DataLayer()
    return _LAYER
