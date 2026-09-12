"""Consensus — قرار مشترك COS + تقرير لـ Cursor حول قبول نتيجة الاستراتيجية."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from cos import config
from cos.brain import llm


@dataclass
class ConsensusResult:
    cos_vote: str  # accept | reject | revise
    confidence: float
    reasons: str
    next_action: str
    cursor_brief: str
    agreed: bool


SYSTEM_CONSENSUS = """أنت محكّم استراتيجيات تداول لوكيل COS.
اقرأ ملخص الفحص وقرر بصرامة.
أرجع JSON فقط:
{"cos_vote":"accept|reject|revise","confidence":0.0-1.0,"reasons":"...","next_action":"...","cursor_brief":"تعليمات قصيرة لـ Cursor لتعديل الكود إن لزم"}
accept = النتيجة جيدة بما يكفي للتوقف.
revise = تحتاج تعديلاً ثم إعادة فحص.
reject = فاشلة بوضوح.
بالعربية في الحقول النصية."""


def judge_result(
    *,
    goal: str,
    platform: str,
    report_text: str,
    success_criteria: str = "",
) -> ConsensusResult:
    user = (
        f"الهدف: {goal}\n"
        f"المنصة: {platform}\n"
        f"معيار النجاح: {success_criteria or 'تحسين منطقي ومستقر يقبله فريق التطوير'}\n"
        f"تقرير الفحص:\n{report_text[:3500]}\n"
    )
    reply = llm.chat(SYSTEM_CONSENSUS, user)
    raw = (reply.text or "").strip()
    data = {}
    if raw:
        import re

        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = {}
    vote = str(data.get("cos_vote") or "revise").lower()
    if vote not in ("accept", "reject", "revise"):
        vote = "revise"
    conf = float(data.get("confidence") or 0.55)
    reasons = str(data.get("reasons") or raw[:400] or "لا تفاصيل من العقل")
    nxt = str(data.get("next_action") or "راجع التقرير مع Cursor")
    brief = str(data.get("cursor_brief") or reasons)
    agreed = vote == "accept" and conf >= 0.6
    return ConsensusResult(
        cos_vote=vote,
        confidence=min(1.0, max(0.0, conf)),
        reasons=reasons,
        next_action=nxt,
        cursor_brief=brief,
        agreed=agreed,
    )


def write_consensus_report(result: ConsensusResult, goal: str, round_i: int) -> Path:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = config.REPORTS_DIR / f"CONSENSUS_R{round_i}_{stamp}.md"
    body = (
        f"# توافق COS ↔ Cursor — الجولة {round_i}\n\n"
        f"**الوقت:** {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        f"**الهدف:** {goal}\n"
        f"**تصويت COS:** `{result.cos_vote}` (ثقة {result.confidence:.0%})\n"
        f"**متفق على القبول؟** {'نعم' if result.agreed else 'لا بعد'}\n\n"
        f"## الأسباب\n{result.reasons}\n\n"
        f"## الخطوة التالية\n{result.next_action}\n\n"
        f"## Brief لـ Cursor\n{result.cursor_brief}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
