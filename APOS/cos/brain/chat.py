"""تصنيف النية: محادثة فقط أم أمر تنفيذ على الجهاز."""
from __future__ import annotations

from cos.brain import llm

SYSTEM_CHAT = """أنت COS: مساعد أتمتة ذكي على Windows.
اسمك COS Personal.
تفهم العربية الفصحى واللهجة العراقية والخليجية والمصرية والشامية.
إذا قال المستخدم عراقياً (شلونك، شنو، هسه، دزلي، سوي، ماكو، اكو، وين، ليش) افهم المقصود بدقة.
تجيب باختصار (2–5 جمل) بفصحى واضحة أو لهجة خفيفة مفهومة.
لا تختلق نتائج backtest غير موجودة.
اقترح خطوة تالية مفيدة عندما يناسب."""

SYSTEM_VOICE = """محادثة صوتية سريعة. أجب بجملة عربية فصحى واحدة قصيرة فقط.
افهم الفصحى والعراقية والخليجية والمصرية.
ممنوع تماماً: رموز، أكواد، إنجليزي، Markdown، قوائم، أو حروف عشوائية.
إذا لم تفهم قل فقط: ما فهمت، أعد من فضلك."""


# أوامر تنفيذ — أي منها يمر عبر الموجّه (Router) لا الشات فقط
_ACTION_HINTS = (
    "افتح",
    "شغّل",
    "شغل",
    "اقفل",
    "أغلق",
    "اكتب",
    "انقر",
    "اضغط",
    "نفّذ",
    "نفذ",
    "ابدأ",
    "ابدا",
    "افحص",
    "فحص",
    "حرّك",
    "حرك",
    "حرّكي",
    "حركي",
    "ماوس",
    "mouse",
    "لوحة المفاتيح",
    "ابحث",
    "روح ل",
    "اذهب",
    "انتقل",
    "matrix",
    "ماتريكس",
    "روبوت",
    "الروبوت",
    "كوانت",
    "quant",
    "quantconnect",
    "كوانتكونكت",
    "tradingview",
    "متاتريدر",
    "mt5",
    "cursor",
    "كرسر",
    "كورسر",
    "كورسا",
    "وحدك",
    "اعمل لوحدك",
    "backtest",
    "باك تست",
    "اختبر",
    "شغّل الاستراتيجية",
    "شغل الاستراتيجية",
    "workflow",
    "سير العمل",
    "على الشاشة",
    "حرّك المؤشر",
    "حرك المؤشر",
    "اكتب في",
    "الصق",
    "انسخ",
    "كبّر",
    "صغّر",
    "سكرول",
    "مرر",
)

_PURE_CHAT = (
    "كيف حالك",
    "كيفك",
    "شلونك",
    "شلونچ",
    "شنو أخبارك",
    "ما أخبارك",
    "تسمعني",
    "هل تسمعني",
    "مرحبا",
    "أهلا",
    "اهلا",
    "السلام",
    "hello",
    "hi",
    "شكرا",
    "شكراً",
    "ما اسمك",
    "ما هو اسمك",
    "من أنت",
    "من انت",
    "ماذا تستطيع",
    "وش تقدر",
    "شتعررف تسوي",
    "شگدر",
)


def is_pure_chat(user_text: str) -> bool:
    """تحية/سؤال حواري قصير — بدون طلب تنفيذ."""
    try:
        from cos.voice.dialects import normalize_dialect

        t = normalize_dialect(user_text or "").strip()
    except Exception:
        t = (user_text or "").strip()
    if not t:
        return True
    try:
        from cos.brain.intent import looks_gibberish, parse_intent

        if looks_gibberish(t):
            return True
        intent = parse_intent(t, use_llm=False)
        if intent.kind == "chat" and intent.confidence >= 0.8:
            return True
        if intent.kind in ("qc_matrix", "trade_ideas", "mouse", "open_app"):
            return False
    except Exception:
        pass
    low = t.lower()
    if wants_computer_action(t):
        return False
    if len(t) > 90:
        return False
    return any(k in t or k in low for k in _PURE_CHAT)


def wants_computer_action(user_text: str) -> bool:
    """True إن كان المطلوب تنفيذ على الجهاز/المنصات."""
    try:
        from cos.voice.dialects import normalize_dialect

        t = normalize_dialect(user_text or "").strip()
    except Exception:
        t = (user_text or "").strip()
    if not t:
        return False
    # استعجال التنفيذ قبل أي تصنيف محادثة
    if any(
        k in t
        for k in (
            "لماذا لا تبدأ",
            "لماذا لا تبدا",
            "ليش ما تبدا",
            "ليش ما تبدأ",
            "لماذا لا تتحرك",
            "ليش ما تتحرك",
            "لماذا لا تنفذ",
            "لماذا لا تنفّذ",
            "ليش ما تنفذ",
            "ليش ما تشتغل",
            "لماذا لا تشتغل",
        )
    ):
        return True
    try:
        from cos.brain.intent import looks_gibberish, parse_intent

        if looks_gibberish(t):
            return False
        intent = parse_intent(t, use_llm=False)
        if intent.kind in ("qc_matrix", "trade_ideas", "mouse", "open_app"):
            return True
        if intent.kind in ("chat", "stop"):
            return False
    except Exception:
        pass
    low = t.lower()
    # «لماذا لا تبدأ/تتحرك» = استعجال تنفيذ، ليس سؤالاً سلبياً
    if any(
        k in t
        for k in (
            "لماذا لا تبدأ",
            "لماذا لا تبدا",
            "ليش ما تبدا",
            "ليش ما تبدأ",
            "لماذا لا تتحرك",
            "ليش ما تتحرك",
            "لماذا لا تنفذ",
            "لماذا لا تنفّذ",
            "ليش ما تنفذ",
            "ليش ما تشتغل",
            "لماذا لا تشتغل",
        )
    ):
        return True
    if any(k in t for k in ("لماذا", "ليش", "لم أقل", "ما قلت", "لا تحرك", "لا تحرّك", "لا تفتح")):
        if len(t) < 70 and not any(
            x in t for x in ("افتح الآن", "حرّك الآن", "حرك الآن", "نفّذ الآن", "نفذ الآن", "لا تبدأ", "لا تتحرك", "لا تنفذ")
        ):
            return False
    if any(k in t or k in low for k in _ACTION_HINTS):
        return True
    if any(k in t for k in ("سويلي", "سوي لي", "دزلي", "افتحلي", "افحصلي", "شيك", "شيّك")):
        return True
    if len(t) >= 80 and any(
        x in t for x in ("أريد", "اريد", "بدي", "قم ب", "سوي", "اشتغل", "اعمل")
    ):
        return True
    return False


def should_execute(user_text: str) -> bool:
    """قاعدة الصوت/الشات: نفّذ إلا إن كانت محادثة صافية."""
    try:
        from cos.brain.intent import looks_gibberish

        if looks_gibberish(user_text or ""):
            return False
    except Exception:
        pass
    if is_pure_chat(user_text):
        return False
    if wants_computer_action(user_text):
        return True
    t = user_text or ""
    if len(t) >= 25 and any(x in t for x in ("الآن", "الان", "فوراً", "فورا", "من فضلك", "رجاء")):
        return True
    return False


def brief_result(full: str) -> str:
    """ملخص صوتي صادق من نتيجة التنفيذ — بلا اختلاق."""
    text = (full or "").strip()
    if not text:
        return "تم."
    # ملخص مدير المهام: جملة قصيرة فقط
    if "مدير المهام" in text or "STATUS:" in text:
        phase = ""
        need = ""
        for ln in text.splitlines():
            if ln.startswith("المرحلة العامة:"):
                phase = ln.split(":", 1)[-1].strip()
            if ln.startswith("يحتاج تدخلاً:") or ln.strip().startswith("بانتظار"):
                need = ln.strip()
        if "blocked" in phase or "بانتظار" in text:
            return "أنجزت الدورة. يوجد طلب في TASK.md بانتظار Cursor. بعد الرد قل: أكمل المهمة."
        if phase == "done":
            return "أنجزت المهمة. التقرير في مجلد collab."
        if phase == "failed":
            return "فشلت المهمة بعد عدة محاولات. راجع REPORT.md."
        return f"مدير المهام: الحالة {phase or 'جارية'}."
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "تم."
    for ln in lines[:6]:
        clean = ln.lstrip("#*- ").strip()
        if len(clean) >= 8 and not clean.startswith("STATUS") and "http" not in clean.lower():
            return ("تم: " + clean)[:140]
    return ("تم: " + lines[0])[:140]


def _session_context(extra: str = "") -> str:
    parts: list[str] = []
    try:
        from cos import config
        from cos.brain.session import SESSION

        if config.SESSION_MEMORY:
            block = SESSION.context_block(max_turns=6)
            if block:
                parts.append(block)
    except Exception:
        pass
    if extra:
        parts.append(extra)
    return "\n".join(parts).strip()


def smart_chat(user_text: str, context: str = "") -> str:
    ctx = _session_context(context)
    prompt = user_text
    if ctx:
        prompt = f"سياق الجلسة:\n{ctx}\n\nرسالة المستخدم:\n{user_text}"
    reply = llm.chat_complex(SYSTEM_CHAT, prompt, max_tokens=220, temperature=0.3, timeout=45.0)
    if reply.ok and reply.text.strip():
        try:
            from cos.brain.intent import looks_gibberish

            if looks_gibberish(reply.text):
                return _fallback(user_text)
        except Exception:
            pass
        return reply.text.strip()
    return _fallback(user_text)


def _for_speech(text: str) -> str:
    t = (text or "").replace("**", "").replace("`", "").replace("#", "")
    # أزل أسطر/قطع الرموز العشوائية
    try:
        from cos.brain.intent import looks_gibberish

        if looks_gibberish(t):
            return "ما فهمت جيداً. أعد بجملة عربية واضحة."
    except Exception:
        pass
    # أبقِ عربي/لاتيني/ترقيم أساسي فقط
    cleaned: list[str] = []
    for ch in t:
        o = ord(ch)
        if (
            ch.isspace()
            or ch.isalnum()
            or ("\u0600" <= ch <= "\u06FF")
            or ch in ".,!?؟،:;ـ-_()[]«»\"'/\\"
        ):
            cleaned.append(ch)
        elif o > 127:
            cleaned.append(ch)
    t = "".join(cleaned)
    t = " ".join(t.split())
    # إن اختفى العربي بعد التنظيف → رد آمن
    ar = sum(1 for c in t if "\u0600" <= c <= "\u06FF")
    if ar < 2 and len(t) > 8:
        return "ما فهمت جيداً. أعد بجملة عربية واضحة."
    if len(t) > 180:
        t = t[:180].rsplit(" ", 1)[0] + "…"
    return t or "سمعتك."


def voice_chat(user_text: str, history: str = "", context: str = "") -> str:
    """رد قصير للشات فقط (ليس بديلاً عن التنفيذ)."""
    try:
        from cos.brain.intent import looks_gibberish

        if looks_gibberish(user_text or ""):
            return "ما التقطت كلاماً واضحاً. أعد الجملة بهدوء."
    except Exception:
        pass

    instant = _instant(user_text)
    if instant:
        return instant

    # لا تحقن سياق جلسة طويل في الصوت — يبطئ ويشوّش النموذج
    prompt = (user_text or "").strip()
    if history:
        lines = [ln for ln in history.splitlines() if ln.strip()][-2:]
        if lines:
            prompt = "\n".join(lines) + "\n" + prompt

    reply = llm.chat_complex(
        SYSTEM_VOICE,
        prompt,
        max_tokens=60,
        temperature=0.2,
        timeout=25.0,
    )
    if reply.ok and reply.text.strip():
        out = _for_speech(reply.text.strip())
        try:
            from cos.brain.intent import looks_gibberish

            if looks_gibberish(out):
                return _for_speech(_fallback(user_text))
        except Exception:
            pass
        return out
    return _for_speech(_fallback(user_text))


def _instant(user_text: str) -> str:
    if should_execute(user_text) or wants_computer_action(user_text):
        return ""
    t = (user_text or "").strip().lower()
    if not t:
        return ""
    if "كيف حال" in t and "تسمع" in t:
        return "بخير وأسمعك بوضوح."
    if any(x in t for x in ("كيف حالك", "كيفك", "شلونك", "how are you")):
        return "بخير، وأنت؟"
    if any(x in t for x in ("تسمعني", "هل تسمعني", "سمعني", "تسمعيني")):
        return "نعم أسمعك."
    if any(x in t for x in ("مرحبا", "أهلا", "اهلا", "السلام", "hello", "hi")):
        return "أهلاً."
    if any(x in t for x in ("اسمك", "ما اسمك")):
        return "أنا COS."
    if any(x in t for x in ("لم أقل", "ما قلت", "خطأ", "مو هذي", "مو هذا")):
        return "حسناً، وضّح الأمر وسأتنفذه كما تريد."
    if any(x in t for x in ("تأخر", "بطيء", "بطئ", "بطيء")):
        return "حسناً، سأرد أسرع. تكلم بجملة قصيرة واضحة."
    return ""


def _fallback(user_text: str) -> str:
    t = (user_text or "").strip()
    if any(x in t for x in ("كيف حالك", "كيفك", "شلونك", "how are you")):
        return "بخير، وأنت؟"
    if any(x in t for x in ("مرحبا", "أهلا", "اهلا", "السلام", "hello", "hi")):
        return "أهلاً."
    return "سمعتك. إن أردت تنفيذاً على الجهاز قل الأمر بوضوح مثل: حرّك الماوس أو افتح كوانت."
