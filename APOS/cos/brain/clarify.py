"""حلقة توضيح: تلخيص القصد + خطة مكتوبة + تأكيد قبل التنفيذ."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from cos.brain import llm
from cos.brain.session import PendingPlan, SessionMemory

_CONFIRM = re.compile(
    r"^(نعم|اي|أي|أجل|اجل|تمام|صح|صحيح|اوكي|أوكي|ok|okay|yes|y|نفّذ|نفذ|"
    r"أكمل|اكمل|كمّل|كمل|موافق|امشِ|امشي|يلا|يلا نفذ|نفذها|نفّذها|"
    r"هذا المطلوب|هذي|هذا|صح نفذ|صح نفّذ|ابدأ|ابدا|امشي عليها|كملي|كمّلي)\b",
    re.I,
)
_DENY = re.compile(
    r"^(لا|لأ|لاء|مو|غلط|خطأ|خطا|الغي|ألغي|cancel|stop|وقف|"
    r"مو هذي|مو هذا|مو هيك|غير|بدّل|بدل)\b",
    re.I,
)
_SKIP_CLARIFY = (
    "بدون تأكيد",
    "بدون تاكيد",
    "نفّذ فورا",
    "نفذ فورا",
    "نفّذ فوراً",
    "نفذ فوراً",
    "فوراً بدون",
    "مباشرة بدون تأكيد",
    "مباشرة",
    "الحين",
    "هسه",
    "فورا",
    "فوراً",
)
# شكاوى «ليش ما تشتغل» = تأكيد تنفيذ وليس طلب توضيح جديد
_URGENCY_CONFIRM = (
    "لماذا لا تبدأ",
    "ليش ما تبدا",
    "ليش ما تبدأ",
    "لماذا لا تبدا",
    "لماذا لا تنفذ",
    "لماذا لا تنفّذ",
    "ليش ما تنفذ",
    "ليش ما تشتغل",
    "لماذا لا تشتغل",
    "ابدأ الآن",
    "ابدا الان",
    "نفذ الآن",
    "نفّذ الآن",
    "يلا ابدأ",
    "يلا ابدا",
    "كمل التنفيذ",
    "كمّل التنفيذ",
    "روح نفذ",
    "روح نفّذ",
)
_MOUSE_URGENCY = (
    "لماذا لا تتحرك",
    "ليش ما تتحرك",
    "لماذا لا يتحرك",
    "حرّك الماوس",
    "حرك الماوس",
    "حرك ماوس",
    "مسح الماوس",
    "move mouse",
    "حرّك المؤشر",
    "حرك المؤشر",
)
_DEFAULT_QC_GOAL = "افحص روبوت ماتريكس في QuantConnect وافتح المنصة للصق والكود والباك تست"


@dataclass
class ClarifyDecision:
    action: str  # clarify | execute | chat | ask
    message: str = ""
    goal: str = ""
    plan: PendingPlan | None = None


def is_confirm(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 80:
        return False
    return bool(_CONFIRM.search(t))


def is_deny(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 80:
        return False
    return bool(_DENY.search(t))


def wants_skip_clarify(text: str) -> bool:
    t = (text or "").strip()
    return any(k in t for k in _SKIP_CLARIFY)


def is_mouse_urgency(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # نفي صريح فقط في بداية الجملة — لا تلمس «لماذا لا تتحرك»
    if re.match(r"^\s*(من فضلك\s+)?(لا|مو)\s*(ت|ي)?تحر[كّ]", t):
        return False
    return any(k in t for k in _MOUSE_URGENCY)


def is_urgency_confirm(text: str) -> bool:
    """«لماذا لا تبدأ؟» ونحوها = نفّذ الآن، لا تعِد كتابة الخطة."""
    t = (text or "").strip()
    if not t:
        return False
    return any(k in t for k in _URGENCY_CONFIRM)


def _rule_plan(user_text: str, kind: str) -> PendingPlan:
    t = (user_text or "").strip()
    if kind == "qc_matrix":
        steps = [
            "طلب/نسخ ملف الروبوت",
            "فتح QuantConnect",
            "لصق الكود ومحاولة Backtest",
            "تقرير النتيجة أو طلب تسجيل الدخول",
        ]
        summary = "فحص روبوت Matrix في QuantConnect (نسخ → فتح QC → Backtest)"
    elif kind == "trade_ideas":
        steps = ["فتح Trade Ideas", "تشغيل المسح المطلوب", "تلخيص النتائج"]
        summary = "تشغيل مسار Trade Ideas"
    elif kind == "mouse":
        steps = ["تحريك المؤشر على الشاشة حسب الطلب"]
        summary = "تحريك الماوس على الشاشة"
    elif kind == "open_app":
        steps = ["فتح التطبيق المطلوب"]
        summary = f"فتح تطبيق/نافذة: {t[:80]}"
    else:
        steps = ["فهم الطلب", "تنفيذ على الجهاز", "إبلاغ النتيجة"]
        summary = t[:160] or "تنفيذ أمر على الجهاز"
    return PendingPlan(goal=t, summary=summary, steps=steps, kind=kind or "other")


def build_plan(user_text: str, *, session: SessionMemory, kind: str = "") -> PendingPlan:
    """ابنِ خطة مكتوبة؛ الأنواع المعروفة بقواعد ثابتة، والباقي بعقل أقوى إن أمكن."""
    k = (kind or "").strip()
    if k in ("qc_matrix", "trade_ideas", "mouse", "open_app"):
        return _rule_plan(user_text, k)

    ctx = session.context_block(max_turns=6)
    system = (
        "أنت مخطّط أوامر لنظام أتمتة Windows اسمه COS.\n"
        "أخرج JSON فقط بالمفاتيح: summary (جملة عربية واضحة لما فهمت)، "
        "steps (مصفوفة 2-5 خطوات قصيرة)، kind "
        "(qc_matrix|trade_ideas|mouse|open_app|other).\n"
        "لا تختلق تفاصيل غير موجودة في الطلب."
    )
    user = (
        f"سياق الجلسة:\n{ctx}\n\n"
        f"طلب المستخدم:\n{user_text}\n"
        f"تصنيف أولي: {k or 'unknown'}"
    )
    reply = llm.chat_complex(
        system,
        user,
        max_tokens=350,
        temperature=0.1,
        timeout=45.0,
    )
    if reply.ok and reply.text:
        raw = reply.text.strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                data = json.loads(m.group(0))
                steps = data.get("steps") or []
                if isinstance(steps, str):
                    steps = [steps]
                steps = [str(s).strip() for s in steps if str(s).strip()][:6]
                summary = str(data.get("summary") or "").strip()
                kk = str(data.get("kind") or k or "other").strip()
                if kk in ("qc_matrix", "trade_ideas", "mouse", "open_app"):
                    return _rule_plan(user_text, kk)
                if summary:
                    return PendingPlan(
                        goal=(user_text or "").strip(),
                        summary=summary,
                        steps=steps or _rule_plan(user_text, kk).steps,
                        kind=kk,
                    )
            except Exception:
                pass
    return _rule_plan(user_text, k or "other")


def format_clarify(plan: PendingPlan) -> str:
    # قصير جداً — النطق الطويل كان يسبب تأخيراً ووهماً أنه «تقرير فقط»
    return f"هل أنفّذ: {plan.summary}؟ قل نعم أو لا."


def decide(
    user_text: str,
    *,
    session: SessionMemory,
    needs_execute: bool,
    kind: str = "",
    clarify_enabled: bool = True,
) -> ClarifyDecision:
    """
    قرّر: توضيح / تنفيذ / سؤال / محادثة.
    يحترم pending في الجلسة (نعم/لا بعد التوضيح).
    """
    text = (user_text or "").strip()
    session.add_turn("user", text)

    # ماوس فقط عند طلب ماوس صريح — لا تحوّل كل شيء لعرض ماوس
    if is_mouse_urgency(text) or (kind == "mouse" and is_mouse_urgency(text)):
        session.clear_pending()
        plan = _rule_plan("حرّك الماوس على الشاشة الآن", "mouse")
        return ClarifyDecision(
            action="execute",
            goal=plan.goal,
            plan=plan,
            message="أنفّذ حركة الماوس الآن.",
        )

    pending = session.get_pending()
    if pending is not None:
        if is_confirm(text) or is_urgency_confirm(text):
            session.clear_pending()
            return ClarifyDecision(
                action="execute",
                goal=pending.goal,
                plan=pending,
                message=f"حسناً، أنفّذ: {pending.summary}",
            )
        if is_deny(text):
            session.clear_pending()
            session.mark_idle()
            return ClarifyDecision(
                action="ask",
                message="حسناً، وضّح لي المطلوب بجملة واحدة واضحة.",
            )
        # طلب تنفيذي جديد أثناء الانتظار → نفّذ مباشرة بدل إعادة التقرير
        if needs_execute:
            session.clear_pending()
            plan = build_plan(text, session=session, kind=kind)
            return ClarifyDecision(
                action="execute",
                goal=plan.goal or text,
                plan=plan,
                message=f"أنفّذ: {plan.summary}",
            )
        return ClarifyDecision(
            action="ask",
            message=(
                f"ما زلت أنتظر تأكيدك على: «{pending.summary}». "
                "قل نعم لأنفّذ أو لا للإلغاء."
            ),
        )

    if not needs_execute:
        return ClarifyDecision(action="chat")

    if (not clarify_enabled) or wants_skip_clarify(text) or is_urgency_confirm(text):
        # استعجال «ابدأ» → آخر هدف حقيقي، وإلا دورة Matrix/QC (ليس ماوس)
        if is_urgency_confirm(text):
            last_goal = (session.state.goal or "").strip()
            if (
                last_goal
                and last_goal != text
                and "ماوس" not in last_goal
                and "mouse" not in last_goal.lower()
            ):
                plan = build_plan(last_goal, session=session, kind=kind or "qc_matrix")
                return ClarifyDecision(
                    action="execute",
                    goal=plan.goal or last_goal,
                    plan=plan,
                    message=f"أنفّذ الآن: {plan.summary}",
                )
            plan = _rule_plan(_DEFAULT_QC_GOAL, "qc_matrix")
            return ClarifyDecision(
                action="execute",
                goal=plan.goal,
                plan=plan,
                message="أنفّذ دورة Matrix / QuantConnect الآن.",
            )
        plan = build_plan(text, session=session, kind=kind)
        return ClarifyDecision(
            action="execute",
            goal=plan.goal or text,
            plan=plan,
            message=f"أنفّذ مباشرة: {plan.summary}",
        )

    plan = build_plan(text, session=session, kind=kind)
    session.set_pending(plan)
    msg = format_clarify(plan)
    session.add_turn("assistant", msg)
    return ClarifyDecision(action="clarify", message=msg, plan=plan, goal=plan.goal)
