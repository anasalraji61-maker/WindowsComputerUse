"""إطلاق لوحة المراقبة من الواجهة."""
from __future__ import annotations


def launch_dashboard() -> None:
    from ui.dashboard import Dashboard

    Dashboard().run()
