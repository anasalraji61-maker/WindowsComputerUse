"""Timeseries metrics — جدول زمني (SQLite/Postgres) بأسلوب Timescale-ready."""
from __future__ import annotations

from typing import Optional

from cos.data.sql_store import SqlStore


class TimeSeriesStore:
    """يسجّل مقاييس زمنية؛ مع Postgres+Timescale يُفضّل تفعيل COS_TIMESCALE=1 يدوياً على الخادم."""

    def __init__(self, sql: Optional[SqlStore] = None):
        self.sql = sql or SqlStore()

    def write(self, name: str, value: float, **labels) -> None:
        self.sql.record_metric(name, value, labels)

    def cpu_snapshot(self) -> dict:
        try:
            import psutil

            return {
                "cpu": psutil.cpu_percent(interval=0.05),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage("C:\\").percent,
            }
        except Exception as e:
            return {"cpu": 0.0, "ram": 0.0, "disk": 0.0, "error": str(e)}

    def sample_system(self) -> dict:
        snap = self.cpu_snapshot()
        self.write("system.cpu", float(snap.get("cpu") or 0))
        self.write("system.ram", float(snap.get("ram") or 0))
        return snap
