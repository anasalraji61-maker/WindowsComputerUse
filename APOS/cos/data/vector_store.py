"""Vector store — Qdrant (خادم أو مسار محلي) مع فهرس محلي احتياطي."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Optional

from cos import config


def _tokenize(text: str, dim: int = 384) -> list[float]:
    """تضمين محلي حتمي بدون نموذج ثقيل — كافٍ للتشابه الدلالي البسيط."""
    vec = [0.0] * dim
    tokens = re.findall(r"[\w\u0600-\u06FF]+", (text or "").lower())
    if not tokens:
        tokens = ["empty"]
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, min(len(h), 32)):
            idx = (h[i] + i * 17) % dim
            vec[idx] += 1.0
        # n-grams قصيرة
        for i in range(len(tok) - 1):
            bg = tok[i : i + 2]
            hb = hashlib.md5(bg.encode("utf-8")).digest()
            vec[hb[0] % dim] += 0.5
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorStore:
    def __init__(self):
        self.collection = config.QDRANT_COLLECTION
        self.dim = config.VECTOR_DIM
        self.backend = "local"
        self._local_path = config.QDRANT_PATH / "local_vectors.jsonl"
        self._client = None
        self._points: list[dict[str, Any]] = []
        self._load_local()
        self._try_qdrant()

    def _load_local(self) -> None:
        if not self._local_path.exists():
            return
        try:
            for line in self._local_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._points.append(json.loads(line))
        except Exception:
            self._points = []

    def _persist_local(self, point: dict) -> None:
        with self._local_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(point, ensure_ascii=False) + "\n")

    def _try_qdrant(self) -> None:
        # خادم Qdrant فقط عند تعيين URL — المسار المحلي يستخدم JSON لتفادي أعطال الإغلاق على Windows
        if not config.QDRANT_URL:
            self._client = None
            self.backend = "local"
            return
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qm

            client = QdrantClient(url=config.QDRANT_URL, timeout=2.0)
            names = [c.name for c in client.get_collections().collections]
            if self.collection not in names:
                client.create_collection(
                    collection_name=self.collection,
                    vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
                )
            self._client = client
            self._qm = qm
            self.backend = "qdrant"
        except Exception:
            self._client = None
            self.backend = "local"

    def upsert(self, text: str, payload: Optional[dict] = None, point_id: Optional[str] = None) -> str:
        vec = _tokenize(text, self.dim)
        pid = point_id or hashlib.md5(f"{text}:{json.dumps(payload or {}, sort_keys=True)}".encode()).hexdigest()
        meta = dict(payload or {})
        meta["text"] = text
        if self._client is not None:
            try:
                self._client.upsert(
                    collection_name=self.collection,
                    points=[
                        self._qm.PointStruct(id=pid if pid.isdigit() else abs(hash(pid)) % (10**12), vector=vec, payload=meta)
                    ],
                )
                return pid
            except Exception:
                self.backend = "local"
        point = {"id": pid, "vector": vec, "payload": meta}
        self._points.append(point)
        self._persist_local(point)
        return pid

    def search(self, query: str, limit: int = 5) -> list[dict]:
        qv = _tokenize(query, self.dim)
        if self._client is not None:
            try:
                hits = self._client.search(
                    collection_name=self.collection, query_vector=qv, limit=limit
                )
                return [
                    {"score": float(h.score), "payload": dict(h.payload or {}), "id": str(h.id)}
                    for h in hits
                ]
            except Exception:
                self.backend = "local"
        scored = []
        for p in self._points:
            scored.append(
                {
                    "score": _cos(qv, p.get("vector") or []),
                    "payload": p.get("payload") or {},
                    "id": p.get("id"),
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "collection": self.collection,
            "local_points": len(self._points),
            "qdrant_url": config.QDRANT_URL or "(local path)",
        }
