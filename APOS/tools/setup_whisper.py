"""تثبيت faster-whisper لـ COS (small افتراضي، medium اختياري)."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    model = (os.getenv("COS_WHISPER_MODEL") or "small").strip() or "small"
    print("Installing faster-whisper (+ deps)...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "faster-whisper"],
        check=False,
    )
    if r.returncode != 0:
        print("pip failed", file=sys.stderr)
        return 1
    try:
        from faster_whisper import WhisperModel

        print(f"Loading {model} model once (download if needed)...")
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(
            __import__("numpy").zeros(16000, dtype="float32"),
            language="ar",
            beam_size=1,
        )
        _ = list(segs)
        print(f"OK: faster-whisper ready (model={model})")
        print("Default STT is auto (Google first, Whisper when warm).")
        print("For higher accuracy: set COS_WHISPER_MODEL=medium then re-run.")
        print("Tip: use headphones to reduce echo/dialect noise.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
