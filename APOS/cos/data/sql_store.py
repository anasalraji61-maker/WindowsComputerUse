"""SQL store — SQLite افتراضي + Postgres عند COS_DATABASE_URL."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from cos import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  platform TEXT, action TEXT, result TEXT, note TEXT,
  success INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  goal TEXT, route TEXT, status TEXT, reply TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, detail TEXT, meta TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, value REAL, labels TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exp_platform ON experiences(platform);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(created_at);
"""


class SqlStore:
    def __init__(self, url: str = "", sqlite_path: Optional[Path] = None):
        self.url = (url or config.DATABASE_URL or "").strip()
        self.sqlite_path = Path(sqlite_path or config.SQLITE_PATH)
        self.backend = "postgres" if self.url.startswith("postgres") else "sqlite"
        self._pg = None
        if self.backend == "postgres":
            self._init_postgres()
        else:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _init_postgres(self) -> None:
        try:
            import psycopg

            self._pg = psycopg
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS experiences (
                          id SERIAL PRIMARY KEY,
                          platform TEXT, action TEXT, result TEXT, note TEXT,
                          success INTEGER, created_at TEXT
                        );
                        CREATE TABLE IF NOT EXISTS goals (
                          id SERIAL PRIMARY KEY,
                          goal TEXT, route TEXT, status TEXT, reply TEXT, created_at TEXT
                        );
                        CREATE TABLE IF NOT EXISTS activity (
                          id SERIAL PRIMARY KEY,
                          kind TEXT, detail TEXT, meta TEXT, created_at TEXT
                        );
                        CREATE TABLE IF NOT EXISTS metrics (
                          id SERIAL PRIMARY KEY,
                          name TEXT, value DOUBLE PRECISION, labels TEXT, created_at TEXT
                        );
                        """
                    )
                conn.commit()
        except Exception:
            self.backend = "sqlite"
            self._pg = None
            self._init_sqlite()

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self.backend == "postgres" and self._pg is not None:
            conn = self._pg.connect(self.url)
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(str(self.sqlite_path))
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def record_experience(
        self, platform: str, action: str, result: str, note: str, success: bool
    ) -> None:
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO experiences(platform,action,result,note,success,created_at) VALUES(%s,%s,%s,%s,%s,%s)",
                        (platform, action, result, note, int(success), self._now()),
                    )
                conn.commit()
            else:
                conn.execute(
                    "INSERT INTO experiences(platform,action,result,note,success,created_at) VALUES(?,?,?,?,?,?)",
                    (platform, action, result, note, int(success), self._now()),
                )

    def record_goal(self, goal: str, route: str, status: str, reply: str) -> None:
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO goals(goal,route,status,reply,created_at) VALUES(%s,%s,%s,%s,%s)",
                        (goal, route, status, reply[:2000], self._now()),
                    )
                conn.commit()
            else:
                conn.execute(
                    "INSERT INTO goals(goal,route,status,reply,created_at) VALUES(?,?,?,?,?)",
                    (goal, route, status, reply[:2000], self._now()),
                )

    def log_activity(self, kind: str, detail: str, meta: Optional[dict] = None) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO activity(kind,detail,meta,created_at) VALUES(%s,%s,%s,%s)",
                        (kind, detail, payload, self._now()),
                    )
                conn.commit()
            else:
                conn.execute(
                    "INSERT INTO activity(kind,detail,meta,created_at) VALUES(?,?,?,?)",
                    (kind, detail, payload, self._now()),
                )

    def record_metric(self, name: str, value: float, labels: Optional[dict] = None) -> None:
        payload = json.dumps(labels or {}, ensure_ascii=False)
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO metrics(name,value,labels,created_at) VALUES(%s,%s,%s,%s)",
                        (name, float(value), payload, self._now()),
                    )
                conn.commit()
            else:
                conn.execute(
                    "INSERT INTO metrics(name,value,labels,created_at) VALUES(?,?,?,?)",
                    (name, float(value), payload, self._now()),
                )

    def recent_goals(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT goal,route,status,reply,created_at FROM goals ORDER BY id DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "goal": r[0],
                            "route": r[1],
                            "status": r[2],
                            "reply": r[3],
                            "created_at": r[4],
                        }
                        for r in rows
                    ]
            cur = conn.execute(
                "SELECT goal,route,status,reply,created_at FROM goals ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

    def success_rate(self, platform: str = "") -> float:
        with self._connect() as conn:
            if self.backend == "postgres":
                with conn.cursor() as cur:
                    if platform:
                        cur.execute(
                            "SELECT AVG(success) FROM experiences WHERE platform=%s",
                            (platform,),
                        )
                    else:
                        cur.execute("SELECT AVG(success) FROM experiences")
                    row = cur.fetchone()
                    return float(row[0] or 0.0)
            if platform:
                cur = conn.execute(
                    "SELECT AVG(success) FROM experiences WHERE platform=?", (platform,)
                )
            else:
                cur = conn.execute("SELECT AVG(success) FROM experiences")
            row = cur.fetchone()
            return float(row[0] or 0.0)

    def status(self) -> dict:
        return {
            "backend": self.backend,
            "sqlite": str(self.sqlite_path),
            "database_url_set": bool(self.url),
        }
