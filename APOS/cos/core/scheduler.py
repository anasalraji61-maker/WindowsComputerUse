"""Scheduler — مهام مجدولة + حلقة خلفية خفيفة."""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from cos import config
from cos.runtime import RUNTIME


@dataclass
class ScheduledJob:
    id: str
    goal: str
    every_minutes: int = 60
    next_run: str = ""
    enabled: bool = True
    last_result: str = ""
    runs: int = 0


class Scheduler:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or (config.DATA / "schedule.json")
        self.jobs: list[ScheduledJob] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._runner: Optional[Callable[[str], str]] = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.jobs = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.jobs = [ScheduledJob(**j) for j in raw.get("jobs", [])]
        except Exception:
            self.jobs = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"jobs": [asdict(j) for j in self.jobs]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, goal: str, every_minutes: int = 60) -> ScheduledJob:
        now = datetime.now()
        job = ScheduledJob(
            id=uuid.uuid4().hex[:8],
            goal=goal.strip(),
            every_minutes=max(1, int(every_minutes)),
            next_run=(now + timedelta(minutes=max(1, int(every_minutes)))).isoformat(timespec="seconds"),
            enabled=True,
        )
        self.jobs.append(job)
        self._save()
        return job

    def due_jobs(self) -> list[ScheduledJob]:
        now = datetime.now()
        due = []
        for j in self.jobs:
            if not j.enabled:
                continue
            try:
                nxt = datetime.fromisoformat(j.next_run) if j.next_run else now
            except Exception:
                nxt = now
            if nxt <= now:
                due.append(j)
        return due

    def mark_ran(self, job: ScheduledJob, result: str) -> None:
        job.runs += 1
        job.last_result = (result or "")[:500]
        job.next_run = (
            datetime.now() + timedelta(minutes=job.every_minutes)
        ).isoformat(timespec="seconds")
        self._save()

    def summary(self) -> str:
        lines = [f"[Scheduler] مهام={len(self.jobs)} شغّال={self._thread is not None and self._thread.is_alive()}"]
        for j in self.jobs[:10]:
            lines.append(
                f"  #{j.id} every={j.every_minutes}m enabled={j.enabled} next={j.next_run} | {j.goal[:60]}"
            )
        return "\n".join(lines)

    def start_background(self, runner: Callable[[str], str], poll_seconds: int = 20) -> str:
        if self._thread and self._thread.is_alive():
            return "المجدول يعمل مسبقاً"
        self._runner = runner
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                if RUNTIME.killed:
                    break
                if not RUNTIME.busy:
                    for job in self.due_jobs():
                        if RUNTIME.killed or RUNTIME.busy:
                            break
                        try:
                            RUNTIME.busy = True
                            result = self._runner(job.goal) if self._runner else ""
                            self.mark_ran(job, result)
                        except Exception as e:
                            self.mark_ran(job, f"error:{e}")
                        finally:
                            RUNTIME.busy = False
                time.sleep(max(5, poll_seconds))

        self._thread = threading.Thread(target=loop, daemon=True, name="cos-scheduler")
        self._thread.start()
        return "بدأ المجدول في الخلفية"

    def stop(self) -> str:
        self._stop.set()
        return "طُلب إيقاف المجدول"
