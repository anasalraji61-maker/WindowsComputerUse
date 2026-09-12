"""Browser Agent — فتح روابط وتركيز المتصفح."""
from __future__ import annotations

import time
import webbrowser

from cos.execution.apps import focus_or_open_url
from cos.runtime import RUNTIME


def open_url(url: str, wait: float = 2.0) -> str:
    RUNTIME.check()
    webbrowser.open(url, new=0, autoraise=True)
    time.sleep(min(max(wait, 0.3), 5.0))
    return f"متصفح ← {url}"


def open_or_focus(title_hint: str, url: str) -> str:
    RUNTIME.check()
    return focus_or_open_url(title_hint, url)


def search_web(query: str) -> str:
    from urllib.parse import quote_plus

    return open_url(f"https://www.google.com/search?q={quote_plus(query)}", wait=1.5)
