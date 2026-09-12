"""إدراك العمليات الجارية (Processes)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cos.runtime import RUNTIME


@dataclass
class ProcInfo:
    name: str
    pid: int
    cpu: float = 0.0
    mem_mb: float = 0.0


def list_processes(limit: int = 25, name_filter: str = "") -> list[ProcInfo]:
    RUNTIME.check()
    out: list[ProcInfo] = []
    try:
        import psutil
    except Exception:
        return out
    needle = (name_filter or "").lower()
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = p.info
            name = info.get("name") or ""
            if needle and needle not in name.lower():
                continue
            mem = info.get("memory_info")
            mb = (mem.rss / (1024 * 1024)) if mem else 0.0
            out.append(
                ProcInfo(
                    name=name,
                    pid=int(info.get("pid") or 0),
                    cpu=float(info.get("cpu_percent") or 0.0),
                    mem_mb=float(mb),
                )
            )
        except Exception:
            continue
    out.sort(key=lambda x: x.mem_mb, reverse=True)
    return out[:limit]


def summary(limit: int = 12) -> str:
    procs = list_processes(limit=limit)
    if not procs:
        return "لا بيانات عمليات (psutil؟)"
    lines = [f"عمليات ({len(procs)}):"]
    for p in procs:
        lines.append(f"  {p.name} pid={p.pid} mem={p.mem_mb:.0f}MB")
    return "\n".join(lines)
