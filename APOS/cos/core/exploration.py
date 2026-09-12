"""Exploration Mode — أول لقاء مع بيئة: راقب، سجّل، لا تكسر شيئاً خطراً."""
from __future__ import annotations

from cos.memory.experience import ExperienceStore
from cos.perception import screen_watch, windows as winmod
from cos.runtime import RUNTIME


def explore(goal: str = "") -> str:
    RUNTIME.check()
    store = ExperienceStore()
    changed, shash = screen_watch.watch_once()
    state = winmod.refresh_world(goal=goal, screen_hash=shash, screen_changed=changed)
    hint = state.active_title or "desktop"
    shot = screen_watch.save_snapshot("explore")

    store.record(
        platform_hint=hint,
        action="observe_windows",
        result="ok",
        note=f"windows={len(state.windows)}; shot={shot.name}",
        success=True,
    )

    lines = [
        "[استكشاف]",
        state.summary(),
        f"لقطة محفوظة: {shot}",
        "حُفظت خبرة أولية في Experience Store.",
    ]
    return "\n".join(lines)
