"""تصنيف نية الأوامر المعقّدة قبل الراوتر."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from cos.brain import llm

IntentKind = str  # qc_matrix | trade_ideas | mouse | chat | open_app | stop | other


@dataclass
class Intent:
    kind: IntentKind
    confidence: float
    platform: str = ""
    ask_cursor_for_robot: bool = False
    want_backtest: bool = False
    gibberish: bool = False
    reason: str = ""
    entities: dict[str, str] = field(default_factory=dict)


_QC_KEYS = (
    "كوانت كونكت",
    "كوانتكونكت",
    "quantconnect",
    "quant connect",
    "كوانت",
    "quant",
    "matrix",
    "ماتريكس",
    "الروبوت",
    "روبوت",
    "ملف الروبوت",
    "اطلب ملف",
    "افحص الروبوت",
    "فحص الروبوت",
    "backtest",
    "باك تست",
    "افتح كوانت",
)

_TI_KEYS = (
    "trade ideas",
    "tradeideas",
    "holly",
    "هولي",
    "ماسح السوق",
)

_MOUSE_KEYS = (
    "حرّك الماوس",
    "حرك الماوس",
    "حرك ماوس",
    "مسح الماوس",
    "move mouse",
    "حرّك المؤشر",
    "حرك المؤشر",
    "لماذا لا تتحرك",
    "ليش ما تتحرك",
    "تحرك الماوس",
    "تحرّك",
)

_STOP_KEYS = (
    "انهي المحادثة",
    "إيقاف المحادثة",
    "وقف المحادثة",
    "انهاء الجلسة",
    "إيقاف الجلسة",
    "باي",
    "مع السلامة",
)

_CHAT_KEYS = (
    "كيف حالك",
    "كيفك",
    "شلونك",
    "شلونچ",
    "مرحبا",
    "أهلا",
    "اهلا",
    "شكرا",
    "تسمعني",
    "ما اسمك",
    "شنو أخبارك",
)


def looks_gibberish(text: str) -> bool:
    """رفض نص STT/الرد المشوّه — خاصة حساء الرموز بدون عربي."""
    t = (text or "").strip()
    if not t:
        return True
    if len(t) < 2:
        return True

    ar = sum(1 for c in t if "\u0600" <= c <= "\u06FF")
    letters_lat = sum(1 for c in t if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    digits = sum(1 for c in t if c.isdigit())
    spaces = sum(1 for c in t if c.isspace())
    weird = sum(
        1
        for c in t
        if c in "'\"`~@$%^&*+=<>[]{}|\\/#_;:"
        or (ord(c) < 32)
    )
    # حساء رموز مثل: *09E25.412-E/$68<^A9G@...
    if ar == 0 and weird >= 4 and (weird + digits) >= max(8, len(t) // 3):
        return True
    if ar == 0 and spaces == 0 and len(t) >= 12 and letters_lat < 4:
        return True
    if ar == 0 and weird >= 6:
        return True
    # نسبة رموز عالية حتى مع بعض الأحرف
    if weird >= max(5, len(t) // 4) and ar < 3:
        return True

    if ar >= 2:
        return weird >= max(5, len(t) // 3)

    ok = sum(
        1
        for c in t
        if c.isalnum()
        or c.isspace()
        or ("\u0600" <= c <= "\u06FF")
        or c in ".,!?؟،:;-_/\\"
    )
    ratio = ok / max(1, len(t))
    if ratio < 0.55:
        return True
    if weird >= max(4, len(t) // 4):
        return True
    # لاتيني بلا مسافات طويلة غالباً ضوضاء STT
    if ar == 0 and spaces == 0 and len(t) >= 18:
        return True
    return False


def parse_intent(text: str, *, use_llm: bool = True) -> Intent:
    try:
        from cos.voice.dialects import normalize_dialect

        t = normalize_dialect(text or "").strip()
    except Exception:
        t = (text or "").strip()
    if looks_gibberish(t):
        return Intent(
            kind="chat",
            confidence=0.95,
            gibberish=True,
            reason="نص غير مفهوم ( gibberish )",
        )

    low = t.lower()
    ask_cursor = any(
        x in t or x in low
        for x in (
            "اطلب ملف",
            "من كورسر",
            "من كرسر",
            "من cursor",
            "اطلب منك",
            "ملف الروبوت",
        )
    )
    want_bt = any(x in t or x in low for x in ("backtest", "باك تست", "افحص", "فحص", "اختبر"))

    if any(k in t or k in low for k in _STOP_KEYS):
        return Intent("stop", 0.95, reason="إيقاف جلسة")

    if any(k in t or k in low for k in _TI_KEYS) and not any(
        k in t or k in low for k in ("كوانت", "quant", "روبوت", "matrix", "ماتريكس")
    ):
        return Intent("trade_ideas", 0.92, platform="tradeideas", reason="Trade Ideas صريح")

    if any(k in t or k in low for k in _QC_KEYS):
        return Intent(
            kind="qc_matrix",
            confidence=0.93,
            platform="quantconnect",
            ask_cursor_for_robot=ask_cursor,
            want_backtest=want_bt or True,
            reason="مسار Matrix/QuantConnect",
        )

    if any(k in t for k in _MOUSE_KEYS) or (
        ("ماوس" in t or "mouse" in low)
        and any(x in t for x in ("حرّك", "حرك", "حركة", "move", "مسح", "تحرك", "تحرّك"))
    ):
        return Intent("mouse", 0.9, reason="أمر ماوس")
    if any(x in t for x in ("لماذا لا تتحرك", "ليش ما تتحرك", "تحرك الآن", "تحرك الحين")):
        return Intent("mouse", 0.88, reason="استعجال حركة ماوس")

    if any(k in t or k in low for k in _CHAT_KEYS) and len(t) < 80:
        return Intent("chat", 0.85, reason="محادثة قصيرة")

    if any(x in t for x in ("افتح", "open", "شغّل", "شغل")):
        return Intent("open_app", 0.7, reason="فتح تطبيق/منصة")

    if use_llm and len(t) >= 20:
        llm_intent = _llm_classify(t)
        if llm_intent is not None:
            return llm_intent

    if len(t) >= 80 and any(x in t for x in ("أريد", "اريد", "بدي", "قم ب", "سوي", "اعمل")):
        # أوامر طويلة بدون تصنيف واضح → COS عامة
        return Intent("other", 0.55, reason="أمر طويل غير مصنّف")

    return Intent("chat", 0.5, reason="افتراضي محادثة")


def _llm_classify(text: str) -> Optional[Intent]:
    prompt = (
        "صنّف نية المستخدم إلى JSON فقط بهذا الشكل:\n"
        '{"kind":"qc_matrix|trade_ideas|mouse|chat|open_app|stop|other",'
        '"platform":"","ask_cursor_for_robot":false,"want_backtest":false}\n'
        "قواعد: روبوت/ماتريكس/كوانت كونكت/افحص الروبوت → qc_matrix. "
        "Trade Ideas/Holly فقط → trade_ideas. "
        "تحية قصيرة → chat.\n"
        f"النص:\n{text}\n"
    )
    try:
        reply = llm.chat(
            "أنت مصنّف نية فقط. أرجع JSON بدون Markdown.",
            prompt,
            max_tokens=80,
            temperature=0.1,
            timeout=8.0,
        )
    except Exception:
        return None
    if not reply.ok or not reply.text:
        return None
    m = re.search(r"\{[\s\S]*\}", reply.text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    kind = str(data.get("kind") or "other").strip()
    if kind not in {
        "qc_matrix",
        "trade_ideas",
        "mouse",
        "chat",
        "open_app",
        "stop",
        "other",
    }:
        return None
    return Intent(
        kind=kind,
        confidence=0.75,
        platform=str(data.get("platform") or ""),
        ask_cursor_for_robot=bool(data.get("ask_cursor_for_robot")),
        want_backtest=bool(data.get("want_backtest")),
        reason="LLM intent",
    )


def intent_overrides_force(intent: Intent) -> bool:
    """طلبات QC/الروبوت تفوز على وضع الواجهة المفروض."""
    return intent.kind in ("qc_matrix", "trade_ideas", "stop") and not intent.gibberish
