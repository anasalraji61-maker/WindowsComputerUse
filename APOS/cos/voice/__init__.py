"""استماع أوامر صوتية + محادثة مستمرة."""
from __future__ import annotations

import sys
from pathlib import Path

from cos.voice.conversation import VoiceConversation, listen_until_silence
from cos.voice.speak import set_enabled, speak, stop_speaking


def _ensure_root() -> None:
    root = Path(__file__).resolve().parents[3]  # WindowsComputerUse
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def start_listening(max_seconds: float = 20.0) -> float:
    _ensure_root()
    from voice import voice_start

    return voice_start(max_seconds)


def stop_listening() -> str:
    _ensure_root()
    from voice import voice_stop_and_transcribe

    return voice_stop_and_transcribe()


def cancel_listening() -> None:
    _ensure_root()
    from voice import voice_cancel

    voice_cancel()


__all__ = [
    "VoiceConversation",
    "listen_until_silence",
    "start_listening",
    "stop_listening",
    "cancel_listening",
    "speak",
    "stop_speaking",
    "set_enabled",
]
