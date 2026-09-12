"""Redis cache — يتصل بـ Redis إن وُجد، وإلا ذاكرة محلية كاملة الميزات."""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Optional

from cos import config


class RedisCache:
    def __init__(self, url: str = ""):
        self.url = (url or config.REDIS_URL).strip()
        self.backend = "memory"
        self._mem: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._client = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis

            client = redis.Redis.from_url(self.url, decode_responses=True, socket_connect_timeout=0.4)
            client.ping()
            self._client = client
            self.backend = "redis"
        except Exception:
            self._client = None
            self.backend = "memory"

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        if self._client is not None:
            try:
                self._client.setex(key, ttl, payload)
                return
            except Exception:
                self.backend = "memory"
        with self._lock:
            self._mem[key] = (payload, time.time() + ttl)

    def get(self, key: str) -> Any:
        if self._client is not None:
            try:
                raw = self._client.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                self.backend = "memory"
        with self._lock:
            item = self._mem.get(key)
            if not item:
                return None
            payload, exp = item
            if time.time() > exp:
                del self._mem[key]
                return None
            return json.loads(payload)

    def delete(self, key: str) -> None:
        if self._client is not None:
            try:
                self._client.delete(key)
            except Exception:
                pass
        with self._lock:
            self._mem.pop(key, None)

    def status(self) -> dict:
        return {"backend": self.backend, "url": self.url}
