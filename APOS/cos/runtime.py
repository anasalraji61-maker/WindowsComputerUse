"""حالة تشغيل مشتركة: إيقاف طارئ، تعليقات للمستخدم."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Runtime:
    killed: bool = False
    busy: bool = False
    last_message: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    on_log: Optional[Callable[[str], None]] = None

    def kill(self) -> None:
        with self._lock:
            self.killed = True
            self.busy = False
        self.log("[KILL] توقف فوري")

    def reset_kill(self) -> None:
        with self._lock:
            self.killed = False

    def check(self) -> None:
        if self.killed:
            raise RuntimeError("تم الإيقاف الطارئ (Kill Switch)")

    def log(self, msg: str) -> None:
        self.last_message = msg
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass


RUNTIME = Runtime()
