"""Terminal Agent — أوامر طرفية محلية بحذر."""
from __future__ import annotations

import subprocess
from typing import Optional

from cos.runtime import RUNTIME

# أوامر ممنوعة دائماً
_BLOCK = (
    "format ",
    "rm -rf /",
    "del /s /q c:\\",
    "shutdown",
    "reg delete",
    "Remove-Item -Recurse -Force C:\\",
)


def run_command(cmd: str, timeout: float = 30.0, shell: bool = True) -> str:
    RUNTIME.check()
    low = (cmd or "").lower()
    for b in _BLOCK:
        if b.lower() in low:
            return f"مرفوض: أمر خطير ({b.strip()})"
    try:
        proc = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=min(max(timeout, 1.0), 120.0),
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "")[-2000:]
        err = (proc.stderr or "")[-1000:]
        code = proc.returncode
        return f"exit={code}\n{out}" + (f"\nERR:\n{err}" if err else "")
    except subprocess.TimeoutExpired:
        return "انتهت مهلة الأمر"
    except Exception as e:
        return f"فشل الأمر: {e}"


def open_powershell(command: Optional[str] = None) -> str:
    RUNTIME.check()
    try:
        if command:
            subprocess.Popen(["powershell", "-NoExit", "-Command", command])
            return f"PowerShell: {command[:80]}"
        subprocess.Popen(["powershell"])
        return "فُتح PowerShell"
    except Exception as e:
        return str(e)
