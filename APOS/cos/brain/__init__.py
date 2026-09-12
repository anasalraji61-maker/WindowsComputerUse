"""Brain facade — تخطيط وقرار وتعافٍ عبر العقل المحلي أولاً."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from cos.brain import llm
from cos.execution.hand import Action


SYSTEM_PLAN = """أنت عقل تخطيط لمنظومة أتمتة Windows اسمها COS.
أجب بالعربية باختصار.
إن طُلب JSON فأرجع JSON فقط بدون Markdown.
الإجراءات المسموحة: focus, open_platform, open_url, mouse_move, click, type, hotkey, wait, show_desktop, browser_search, terminal, read_file, list_dir.
لا تقترح حذف ملفات أو أوامر خطرة."""

SYSTEM_RECOVER = """أنت تساعد وكيل أتمتة Windows على التعافي من خطوة فاشلة.
أجب بالعربية في أقل من 8 أسطر.
اقترح خطوات واجهة عملية: تركيز نافذة، فتح رابط، انتظار، ESC، F5، إعادة فتح المنصة."""


def think(prompt: str, system: str = "") -> llm.BrainReply:
    return llm.chat(system or SYSTEM_PLAN, prompt)


def plan_actions_from_goal(goal: str, context: str = "") -> tuple[list[Action], str, str]:
    """يرجع (خطوات, رد للمستخدم, اسم المزوّد)."""
    user = (
        "حوّل الهدف إلى خطة تنفيذ قصيرة.\n"
        "أرجع JSON بالشكل:\n"
        '{"mode":"execute|chat|explore","reply":"...","steps":[{"kind":"...","params":{},"confidence":0.8}]}\n'
        f"السياق:\n{context}\n\nالهدف:\n{goal}\n"
    )
    reply = llm.chat(SYSTEM_PLAN, user)
    if not reply.ok:
        return [], "", reply.provider
    text = reply.text.strip()
    # استخرج JSON
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return [], text[:500], reply.provider
    try:
        data = json.loads(m.group(0))
    except Exception:
        return [], text[:500], reply.provider
    steps: list[Action] = []
    for s in data.get("steps") or []:
        if not isinstance(s, dict):
            continue
        kind = str(s.get("kind") or s.get("action") or "").strip()
        if not kind:
            continue
        params = dict(s.get("params") or {})
        conf = float(s.get("confidence") or 0.75)
        steps.append(
            Action(
                kind=kind,
                params=params,
                confidence=min(0.95, max(0.4, conf)),
                reason="brain_plan",
            )
        )
    mode = str(data.get("mode") or ("execute" if steps else "chat"))
    user_reply = str(data.get("reply") or "")
    if mode == "chat" and not steps:
        return [], user_reply or text[:500], reply.provider
    if mode == "explore" and not steps:
        return [], user_reply or "أستكشف الشاشة.", reply.provider
    return steps[:8], user_reply or "أنفّذ وفق خطة العقل المحلي.", reply.provider


def recovery_advice(goal: str, platform: str, action: str, error: str) -> str:
    prompt = (
        f"Goal: {goal}\nPlatform: {platform}\nFailed action: {action}\nError: {error}\n"
    )
    reply = llm.chat(SYSTEM_RECOVER, prompt)
    if reply.ok:
        return f"[{reply.provider}/{reply.model}]\n{reply.text}"
    return ""


def status_text() -> str:
    st = llm.status()
    lines = [
        "[Brain]",
        f"تفضيل: {st['provider_pref']} → المستخدَم المتوقع: {st['resolved']}",
        f"llama.cpp: {'يعمل' if st['llamacpp_up'] else 'غير متصل'} @ {st['llamacpp_host']}",
        f"نموذج llama.cpp: {st['llamacpp_model']}",
    ]
    if st.get("llamacpp_models"):
        lines.append("نماذج الخادم: " + ", ".join(st["llamacpp_models"][:6]))
    lines.append(
        f"Ollama: {'يعمل' if st['ollama_up'] else 'غير متصل'} @ {st['ollama_host']} ({st['ollama_model']})"
    )
    if st["ollama_models"]:
        lines.append("نماذج Ollama: " + ", ".join(st["ollama_models"][:6]))
    lines.append(
        f"OpenRouter: {'مضبوط' if st['openrouter_configured'] else 'غير مضبوط'} ({st['openrouter_model']})"
    )
    lines.append(
        f"Anthropic: {'مضبوط' if st['anthropic_configured'] else 'غير مضبوط'} | تصعيد Claude={st['claude_escalate']}"
    )
    return "\n".join(lines)
