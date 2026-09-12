"""وضع استقلال — فحص → تقرير → نقاش Cursor → قرار توافق → تعديل/إعادة حتى الاقتناع."""
from __future__ import annotations

import re
import time
from typing import Optional

from cos.agents.coding import CodingAgent
from cos.brain.chat import smart_chat
from cos.core.consensus import judge_result, write_consensus_report
from cos.core.workflow import return_to_cursor, run_matrix_brief
from cos.execution.hand import Action, execute
from cos.execution import platforms
from cos.memory.experience import ExperienceStore
from cos.perception.world_model import get_world_model
from cos.plugins import REGISTRY
from cos.runtime import RUNTIME


def _parse_rounds(goal: str, default: int = 3) -> int:
    m = re.search(r"(\d+)\s*(جولة|مرات|محاولات|rounds?)", goal)
    if m:
        return max(1, min(8, int(m.group(1))))
    return default


def _detect_platform(goal: str) -> str:
    REGISTRY.load_all()
    plug = REGISTRY.detect_from_goal(goal)
    if plug:
        return plug.id
    return "quantconnect"


def _success_criteria(goal: str) -> str:
    m = re.search(r"حتى\s+(.+)$", goal.strip())
    if m:
        return m.group(1).strip()
    if "ربح" in goal or "موجب" in goal:
        return "نتيجة backtest مقبولة/موجبة ومستقرة بما يكفي لقبول الفريق"
    return "نتيجة فحص جيدة يقتنع بها COS وCursor معاً دون أخطاء واضحة"


def run_autonomous_cycle(goal: str, orch=None) -> str:
    """
    حلقة مستقلة:
    فحص منصة → توافق COS → فتح Cursor بالتقرير → تجهيز تعديل → إعادة إن لزم.
    """
    RUNTIME.check()
    store = ExperienceStore()
    wm = get_world_model()
    rounds = _parse_rounds(goal, 3)
    platform = _detect_platform(goal)
    criteria = _success_criteria(goal)
    lines = [
        "[وضع استقلال]",
        f"منصة={platform} | جولات أقصى={rounds}",
        f"معيار الاقتناع: {criteria}",
        "",
    ]

    # رسالة تفكير أولية
    try:
        lines.append(
            smart_chat(
                f"سأبدأ دورة مستقلة على {platform} بهدف: {goal}. لخّص خطتي بجملتين.",
                context="وضع استقلال COS↔Cursor",
            )
        )
    except Exception:
        lines.append("أبدأ الدورة المستقلة الآن.")

    last_consensus = None
    for i in range(1, rounds + 1):
        RUNTIME.check()
        lines.append(f"—— الجولة {i}/{rounds} ——")
        wm.note_event("auto_round", f"{i}/{rounds}", platform=platform)

        # 1) فحص
        try:
            if platform in ("quantconnect", "matrix") or "quant" in platform:
                report = run_matrix_brief(goal)
            else:
                report = platforms.open_plugin(platform)
                report += "\n(التقطت المنصة — أكمل القياس يدوياً إن لزم ثم سأحكم على التقرير)"
        except Exception as e:
            report = f"فشل الفحص: {e}"
        lines.append(report[:800])

        # 2) حكم COS
        consensus = judge_result(
            goal=goal,
            platform=platform,
            report_text=report,
            success_criteria=criteria,
        )
        last_consensus = consensus
        cpath = write_consensus_report(consensus, goal, i)
        lines.append(
            f"تصويت COS: {consensus.cos_vote} ({consensus.confidence:.0%}) — متفق؟ {consensus.agreed}"
        )
        lines.append(f"تقرير توافق: {cpath}")

        store.record(
            platform,
            f"consensus_r{i}",
            consensus.cos_vote,
            consensus.reasons[:180],
            consensus.agreed,
        )

        # 3) رجوع لـ Cursor بالنتيجة للنقاش/التعديل
        try:
            back = return_to_cursor(goal)
            lines.append(back[:300])
        except Exception as e:
            lines.append(f"Cursor: {e}")

        # افتح تقرير التوافق أيضاً
        try:
            import os

            os.startfile(str(cpath))  # type: ignore[attr-defined]
        except Exception:
            pass

        try:
            execute(
                Action(kind="focus", params={"title": "Cursor"}, confidence=0.9, reason="discuss")
            )
        except Exception:
            pass

        if consensus.agreed:
            lines.append(
                "اقتنعت بالنتيجة (تصويت accept بثقة كافية). أتوقف وأترك التقرير لـ Cursor للمراجعة النهائية."
            )
            break

        # 4) إن لم نقتنع → تجهيز تعديل عبر Coding Agent (بدون ادعاء أن Cursor وافق تلقائياً)
        lines.append("لم نصل لاتفاق قبول بعد — أجهّز تعديلاً عبر Coding/Cursor ثم أعيد الفحص.")
        try:
            coding_goal = (
                f"عدّل كود الروبوت حسب brief التوافق التالي ثم جهّز لإعادة الفحص:\n"
                f"{consensus.cursor_brief}\n\nالأسباب: {consensus.reasons}"
            )
            code_out = CodingAgent(orch).run(coding_goal)
            lines.append(code_out[:500])
        except Exception as e:
            lines.append(f"تعديل: {e}")

        time.sleep(0.8)

    # خاتمة تفكير
    if last_consensus and last_consensus.agreed:
        closing = "انتهت الدورة باقتناع COS. راجع مع Cursor التقرير الأخير وأكّد إن وافقت."
    else:
        closing = (
            "انتهت الجولات دون قبول نهائي تلقائي. "
            "التقارير جاهزة في Cursor — ناقشها هناك أو قل: كمل جولة إضافية."
        )
    try:
        closing = smart_chat(closing + f"\nآخر تصويت: {getattr(last_consensus, 'cos_vote', None)}")
    except Exception:
        pass
    lines.append(closing)
    return "\n".join(lines)
