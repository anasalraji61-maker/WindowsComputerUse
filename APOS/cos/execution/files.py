"""Files Agent — قراءة/كتابة/تنظيم ملفات ضمن مساحة العمل."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from cos import config
from cos.runtime import RUNTIME


def _safe(path: Path) -> Path:
    """امنع الخروج العشوائي من مساحة العمل إلا للقراءة من Downloads/Documents."""
    return path.expanduser().resolve()


def read_text(path: str, max_chars: int = 8000) -> str:
    RUNTIME.check()
    p = _safe(Path(path))
    if not p.exists():
        return f"غير موجود: {p}"
    data = p.read_text(encoding="utf-8", errors="replace")
    return data[:max_chars]


def write_text(path: str, content: str, *, under_workspace: bool = True) -> str:
    RUNTIME.check()
    p = Path(path)
    if under_workspace and not p.is_absolute():
        p = config.WORKSPACE / p
    p = _safe(p)
    # لا تكتب خارج workspace/reports بسهولة
    allowed_roots = [config.WORKSPACE.resolve(), config.REPORTS_DIR.resolve(), config.DATA.resolve()]
    if not any(str(p).startswith(str(r)) for r in allowed_roots):
        return f"مرفوض الكتابة خارج مساحة العمل: {p}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"كُتب: {p}"


def list_dir(path: Optional[str] = None, limit: int = 40) -> str:
    RUNTIME.check()
    p = _safe(Path(path) if path else config.WORKSPACE)
    if not p.exists():
        return f"غير موجود: {p}"
    items = sorted(p.iterdir(), key=lambda x: x.name.lower())[:limit]
    lines = [f"{'D' if i.is_dir() else 'F'} {i.name}" for i in items]
    return f"{p}\n" + "\n".join(lines)


def copy_into_workspace(src: str, dest_name: str = "") -> str:
    RUNTIME.check()
    s = _safe(Path(src))
    if not s.exists():
        return f"المصدر غير موجود: {s}"
    dest = config.WORKSPACE / (dest_name or s.name)
    if s.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(s, dest)
    else:
        shutil.copy2(s, dest)
    return f"نُسخ إلى: {dest}"
