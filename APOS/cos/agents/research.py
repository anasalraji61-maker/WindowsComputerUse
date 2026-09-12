"""Research Agent — بحث إنترنت + تلميحات قابلة للتنفيذ عند الفشل."""
from __future__ import annotations

import json
import os
import re
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote_plus

from cos.agents.memory_agent import MemoryAgent
from cos.data import get_data_layer
from cos.execution.hand import Action
from cos.perception import vision
from cos.runtime import RUNTIME


@dataclass
class ResearchBrief:
    query: str
    urls: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    alt_actions: list[Action] = field(default_factory=list)
    memory_hits: list[dict] = field(default_factory=list)
    ai_advice: str = ""
    escalate_vision: bool = False
    summary: str = ""


class ResearchAgent:
    def __init__(self):
        self.memory = MemoryAgent()
        self.layer = get_data_layer()

    def _strip_goal(self, goal: str) -> str:
        q = goal
        for prefix in ("ابحث عن", "ابحث", "research", "وثّق", "وثق"):
            if q.lower().startswith(prefix) or q.startswith(prefix):
                q = q[len(prefix) :].strip(" ::-")
                break
        return q or goal

    def _search_urls(self, query: str, platform: str = "") -> list[str]:
        q = query
        if platform:
            q = f"{platform} {query}"
        return [
            f"https://www.google.com/search?q={quote_plus(q)}",
            f"https://duckduckgo.com/?q={quote_plus(q)}",
            f"https://www.google.com/search?q={quote_plus(q + ' site:docs OR site:github.com OR how to')}",
        ]

    def _ai_recovery_advice(
        self, *, goal: str, platform: str, action: str, error: str
    ) -> str:
        """عقل محلي أولاً (Ollama) ثم OpenRouter/Anthropic عبر Brain الموحّد."""
        try:
            from cos.brain import recovery_advice

            advice = recovery_advice(goal, platform, action, error)
            if advice:
                return advice
        except Exception as e:
            pass
        # تراجع مباشر Anthropic إن لزم
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return ""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
            prompt = (
                "You help a Windows desktop automation agent recover from a failed UI step.\n"
                "Reply in Arabic, max 8 short lines.\n"
                "Give concrete next UI steps (focus window, open URL, hotkey, wait, click idea).\n"
                f"Goal: {goal}\nPlatform: {platform}\nFailed action: {action}\nError: {error}\n"
            )
            msg = client.messages.create(
                model=model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = []
            for block in msg.content:
                t = getattr(block, "text", None)
                if t:
                    parts.append(t)
            return "\n".join(parts).strip()
        except Exception as e:
            return f"(تعذّر AI نصي: {e})"

    def _hints_to_actions(self, platform: str, advice: str) -> list[Action]:
        """حوّل نصائح بسيطة إلى إجراءات آمنة قابلة لإعادة المحاولة."""
        acts: list[Action] = []
        low = (advice or "").lower()
        title = platform or ""
        if any(x in low or x in (advice or "") for x in ("focus", "ركّز", "ركز", "افتح النافذة")):
            if title:
                acts.append(
                    Action(
                        kind="focus",
                        params={"title": title.split()[0] if title else title},
                        confidence=0.8,
                        reason="recovery:focus",
                    )
                )
        if any(x in low for x in ("wait", "انتظر", "انتظار")):
            acts.append(
                Action(
                    kind="wait",
                    params={"seconds": 1.2},
                    confidence=0.95,
                    reason="recovery:wait",
                )
            )
        if any(x in low for x in ("escape", "esc", "ألغ", "الغ")):
            acts.append(
                Action(
                    kind="hotkey",
                    params={"keys": ["esc"]},
                    confidence=0.85,
                    reason="recovery:esc",
                )
            )
        if any(x in low for x in ("refresh", "f5", "حدّث", "حدث الصفحة")):
            acts.append(
                Action(
                    kind="hotkey",
                    params={"keys": ["f5"]},
                    confidence=0.8,
                    reason="recovery:refresh",
                )
            )
        # دائماً انتظار قصير ثم إعادة تركيز إن وُجد عنوان
        if not acts and title:
            acts = [
                Action(kind="wait", params={"seconds": 0.8}, confidence=0.95, reason="recovery:pause"),
                Action(
                    kind="focus",
                    params={"title": title[:40]},
                    confidence=0.75,
                    reason="recovery:refocus",
                ),
            ]
        return acts[:4]

    def investigate(
        self,
        *,
        goal: str,
        platform: str = "",
        action: str = "",
        error: str = "",
        open_browser: bool = True,
    ) -> ResearchBrief:
        """بحث عند الفشل: ذاكرة + إنترنت + AI نصي → تلميحات وإجراءات بديلة."""
        RUNTIME.check()
        query = f"{platform} {action} failed: {error} | goal: {goal}".strip()
        query = re.sub(r"\s+", " ", query)[:240]
        urls = self._search_urls(
            f"{platform} {action} {error} how to fix OR documentation",
            platform=platform,
        )
        if open_browser and urls:
            try:
                webbrowser.open(urls[0], new=0, autoraise=True)
            except Exception:
                pass
        try:
            vision.capture_event("research_recovery", force=True)
        except Exception:
            pass

        memory_hits = self.memory.long.recall(query, limit=5)
        hints: list[str] = []
        for h in memory_hits:
            p = h.get("payload") or {}
            if p.get("success"):
                hints.append(
                    f"خبرة ناجحة سابقة: {p.get('platform')}/{p.get('action')} — {p.get('note') or p.get('text','')[:80]}"
                )
            else:
                hints.append(
                    f"فشل سابق للتعلّم: {p.get('platform')}/{p.get('action')} — {p.get('note') or ''}"
                )

        ai_advice = self._ai_recovery_advice(
            goal=goal, platform=platform, action=action, error=error
        )
        alt = self._hints_to_actions(platform, ai_advice + "\n" + "\n".join(hints))
        escalate = any(
            x in (ai_advice + error).lower()
            for x in ("vision", "screenshot", "انقر", "زر", "ui changed", "غير واضح")
        ) or (not alt and bool(error))

        brief = ResearchBrief(
            query=query,
            urls=urls,
            hints=hints,
            alt_actions=alt,
            memory_hits=memory_hits,
            ai_advice=ai_advice,
            escalate_vision=escalate,
            summary="",
        )
        brief.summary = self._format_brief(brief)
        self.memory.learn_from_outcome(
            "research",
            "investigate",
            "ok",
            True,
            note=brief.query[:180],
        )
        self.layer.sql.log_activity(
            "auto_research",
            query,
            {"urls": urls[:2], "escalate": escalate, "alts": len(alt)},
        )
        self.layer.vectors.upsert(
            f"recovery:{platform}:{action}:{error}",
            {"type": "recovery", "platform": platform, "action": action, "error": error},
        )
        return brief

    def _format_brief(self, brief: ResearchBrief) -> str:
        lines = [
            "[Auto Research]",
            f"استعلام: {brief.query}",
            f"روابط: {brief.urls[0] if brief.urls else '—'}",
        ]
        if brief.hints:
            lines.append("من الذاكرة:")
            lines.extend(f"- {h}" for h in brief.hints[:4])
        if brief.ai_advice:
            lines.append("نصيحة AI:")
            lines.append(brief.ai_advice)
        if brief.alt_actions:
            lines.append(
                "إجراءات بديلة: "
                + ", ".join(a.kind for a in brief.alt_actions)
            )
        if brief.escalate_vision:
            lines.append("ترشيح: تصعيد لرؤية Claude Computer Use")
        return "\n".join(lines)

    def run(self, goal: str) -> str:
        RUNTIME.check()
        q = self._strip_goal(goal)
        # إن كان الطلب صريح بحث — افتح وارجع ملخصاً
        if any(x in goal for x in ("ابحث", "research", "وثّق", "وثق")):
            brief = self.investigate(
                goal=q, platform="", action="manual_search", error="", open_browser=True
            )
            return brief.summary
        brief = self.investigate(
            goal=goal, platform="", action="research", error="", open_browser=True
        )
        return brief.summary
