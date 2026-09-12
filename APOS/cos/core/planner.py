"""Planner محلي موسّع — بدون ضجيج؛ يفرّق السؤال عن الأمر."""
from __future__ import annotations

from dataclasses import dataclass

from cos.execution.hand import Action
from cos.skills.library import SKILLS


@dataclass
class Plan:
    goal: str
    steps: list[Action]
    mode: str  # execute | explore | chat | workflow
    reply: str = ""


def _is_meta_question(g: str) -> bool:
    """أسئلة عن النظام نفسه — ليست أمر تحريك."""
    # استعجال التنفيذ ليس سؤالًا ميتاً
    if any(
        x in g
        for x in (
            "لماذا لا تبدأ",
            "لماذا لا تبدا",
            "لماذا لا تتحرك",
            "لماذا لا تنفذ",
            "لماذا لا تنفّذ",
            "ليش ما تبدا",
            "ليش ما تبدأ",
            "ليش ما تتحرك",
            "ليش ما تنفذ",
            "ليش ما تشتغل",
        )
    ):
        return False
    keys = (
        "لماذا",
        "ليش",
        "ما المشكلة",
        "وين الخطأ",
        "هل يعمل",
        "كيف حالك",
        "ما رأيك",
        "ماذا تستطيع",
        "explain",
        "why ",
        "what happened",
    )
    return any(k in g for k in keys)


def _is_chatty(g: str) -> bool:
    """تحية أو سؤال حواري — يحتاج رد ذكي من العقل."""
    keys = (
        "كيف حالك",
        "كيفك",
        "شلونك",
        "ما أخبارك",
        "من أنت",
        "من انت",
        "ماذا تستطيع",
        "وش تقدر",
        "ما رأيك",
        "تسمعني",
        "هل انت معي",
        "هل أنت معي",
        "شكرا",
        "شكراً",
        "مرحبا",
        "اهلا",
        "أهلا",
        "السلام",
        "hello",
        "hi",
        "how are you",
        "what can you",
        "who are you",
    )
    return any(k in g for k in keys) or (_is_meta_question(g) and len(g) < 80)


def _wants_autonomous(g: str) -> bool:
    keys = (
        "اعمل لوحدك",
        "تعمل لوحدك",
        "يشتغل لوحده",
        "اشتغل لوحدك",
        "عمل مستقل",
        "دورة مستقلة",
        "حتى تقتنع",
        "حتى تقتنعوا",
        "حتى نتفق",
        "كرر الفحص",
        "auton",
        "independ",
        "بدون أوامري",
        "اتركك تعمل",
        "خلّيك تشتغل",
        "خليك تشتغل",
        "أمامي",
        "امامى",
        "ناقش cursor",
        "ناقش كورسر",
        "ناقش كورسا",
        "اتفق مع cursor",
        "اتفق مع كورسر",
        "لوحدك",
    )
    return any(k in g.lower() or k in g for k in keys)


def _wants_continue(g: str) -> bool:
    keys = (
        "ماذا بعد",
        "وش بعد",
        "كمّل",
        "كمل",
        "تابع",
        "continue",
        "ابدأ العمل",
        "ابدا العمل",
        "والمرحلة",
        "الخطوة التالية",
        "ماذا بعد ذلك",
    )
    return any(k in g for k in keys)


def _wants_return_to_cursor(g: str) -> bool:
    return any(
        x in g
        for x in (
            "ارجع",
            "رجوع",
            "ارجع لـ",
            "ارجع ل",
            " نتيجة QC",
            "احفظ نتيجة",
            "تقرير QC",
            "handoff",
        )
    )


def plan_goal(goal: str) -> Plan:
    g = (goal or "").strip()
    low = g.lower()

    if not g:
        return Plan(g, [], "chat", "اكتب طلبك.")

    if _wants_autonomous(g):
        return Plan(g, [], "autonomous", "")

    if _wants_return_to_cursor(g):
        return Plan(g, [], "workflow_return", "")

    # متابعة بعد نجاح الماوس / بناء QC
    if _wants_continue(g):
        return Plan(
            g,
            [],
            "workflow",
            "",
        )

    # حوار ذكي عبر Ollama (كيف حالك / تحية / ماذا تستطيع…)
    if _is_chatty(g) and not any(
        x in g
        for x in (
            "نفّذ",
            "نفذ",
            "الآن حرّك",
            "الآن حرك",
            "افتح",
            "افحص",
            "تحرك",
            "تحرّك",
            "ماوس",
            "mouse",
            "ابدأ",
            "ابدا",
        )
    ):
        return Plan(g, [], "smart_chat", "")

    steps: list[Action] = []

    # مدير المهام الحقيقي — مهام مركبة/مشاريع (قبل الماوس وQC)
    try:
        from cos.core.task_manager import looks_like_managed_task

        if looks_like_managed_task(g):
            return Plan(g, [], "task_manager", "")
    except Exception:
        pass

    # «لماذا لا تبدأ» = أكمل العمل الحقيقي (QC)، وليس عرض ماوس
    if any(
        x in g
        for x in (
            "لماذا لا تبدأ",
            "لماذا لا تبدا",
            "ليش ما تبدأ",
            "ليش ما تبدا",
            "لماذا لا تنفذ",
            "لماذا لا تنفّذ",
            "ليش ما تشتغل",
            "لماذا لا تشتغل",
        )
    ) and "ماوس" not in g and "mouse" not in low:
        return Plan(
            "افحص روبوت ماتريكس في QuantConnect",
            [],
            "qc_api",
            "",
        )

    # أمر ماوس صريح فقط (ليس سؤالاً) — أولوية قبل workflow
    mouse_cmd = any(
        x in g
        for x in (
            "حرّك الماوس",
            "حرك الماوس",
            "حرك ماوس",
            "move mouse",
            "حركة الماوس",
            "مسح الماوس",
            "لماذا لا تتحرك",
            "ليش ما تتحرك",
            "حرّك المؤشر",
            "حرك المؤشر",
        )
    )
    mouse_cmd = mouse_cmd or (
        any(x in g for x in ("ماوس", "mouse"))
        and any(x in g for x in ("حرّك", "حرك", "حركة", "move", "مسح", "تحرك", "تحرّك"))
        and not _is_meta_question(g)
    )
    # إن طُلب ماوس فقط بدون QC — نفّذ المسح كاملاً
    qc_words = any(
        x in low or x in g
        for x in (
            "quantconnect",
            "كوانت",
            "matrix",
            "ماتريكس",
            "backtest",
            "الروبوت",
            "روبوت",
        )
    )
    if mouse_cmd and not qc_words:
        steps.append(Action(kind="mouse_sweep", params={}, confidence=0.99, reason="عرض ماوس مرئي"))
        import pyautogui

        w, h = pyautogui.size()
        path = [
            (int(w * 0.15), int(h * 0.30)),
            (int(w * 0.85), int(h * 0.30)),
            (int(w * 0.85), int(h * 0.70)),
            (int(w * 0.15), int(h * 0.70)),
            (int(w * 0.50), int(h * 0.50)),
        ]
        for x, y in path:
            steps.append(
                Action(
                    kind="mouse_move",
                    params={"x": x, "y": y, "duration": 1.1},
                    confidence=0.97,
                    reason="متابعة ماوس واضحة",
                )
            )
        return Plan(
            g,
            steps,
            "execute",
            "حرّكت الماوس أمامك بوضوح عبر الشاشة (إطار + ضربات + مركز).",
        )

    # دورة matrix / QC — منفّذ API أولاً، والمتصفح احتياطي فقط
    if qc_words or any(
        x in low or x in g
        for x in (
            "strategyquant",
            "باك تست",
            "دورة",
            "افحص الروبوت",
            "فحص الروبوت",
            "افتح كوانت",
        )
    ):
        try:
            from cos import config as cos_config
            from cos.execution.qc_executor import has_credentials

            if cos_config.QC_PREFER_API:
                return Plan(g, [], "qc_api", "")
            if has_credentials():
                return Plan(g, [], "qc_api", "")
        except Exception:
            pass
        return Plan(g, [], "workflow", "")

    # طابور أهداف / مشاريع / مجدول / نموذج العالم
    if any(x in g or x in low for x in ("قائمة الأهداف", "هدف جديد", "أضف هدف", "goal queue", "الاهداف")):
        return Plan(g, [], "goals", "")
    if any(x in g or x in low for x in ("المشاريع", "project manager", "قائمة المشاريع")):
        return Plan(g, [], "projects", "")
    if any(
        x in g or x in low
        for x in ("جدول", "مجدول", "scheduler", "كل ساعة", "كل دقيقة", "شغّل المجدول", "شغل المجدول")
    ):
        return Plan(g, [], "schedule", "")
    if any(x in g or x in low for x in ("نموذج العالم", "world model", "ماذا تعرف عن البيئة")):
        return Plan(g, [], "world", "")
    if any(x in g or x in low for x in ("قائمة المنصات", "كل المنصات", "list plugins")):
        return Plan(g, [], "platforms_list", "")

    # افتح منصة من الكتالوج
    if any(x in g for x in ("افتح", "open", "شغّل", "شغل")):
        try:
            from cos.plugins import REGISTRY

            plug = REGISTRY.detect_from_goal(g)
            if plug:
                steps.append(
                    Action(
                        kind="open_platform",
                        params={"plugin": plug.id},
                        confidence=0.9,
                        reason=f"افتح {plug.id}",
                    )
                )
                return Plan(g, steps, "execute", f"أفتح منصة {plug.name}.")
        except Exception:
            pass

    focus_map = [
        (("cursor", "كورسر", "كورسا"), "Cursor"),
        (("chrome", "كروم"), "Chrome"),
        (("quantconnect", "كوانت"), "QuantConnect"),
        (("strategyquant", "ستراتيجي"), "StrategyQuant"),
        (("notepad", "مفكرة"), "Notepad"),
        (("telegram", "تيليجرام"), "Telegram"),
    ]
    for keys, title in focus_map:
        if any(k in low or k in g for k in keys) and any(
            x in g for x in ("افتح", "ركز", "ركّز", "انتقل", "روح", "open", "focus", "ادخل")
        ):
            steps.append(SKILLS["focus_window"].build({"title": title}))
            return Plan(g, steps, "execute", f"حاولت التركيز على {title}.")

    if any(x in g for x in ("استكشف", "explore", "ماذا ترى", "شاشت", "صف الشاشة", "العمليات")):
        return Plan(g, [], "explore", "")

    if any(x in g for x in ("تعلّم الشاشة", "تعلم الشاشة")):
        return Plan(g, [], "explore", "")

    if any(
        x in g or x in low
        for x in ("حالة العقل", "brain status", "ollama", "عقل محلي", "مزود العقل")
    ):
        return Plan(g, [], "brain", "")

    # عقل محلي للطلبات الغامضة/الطويلة قبل الاستكشاف الأعمى
    try:
        from cos import config as cos_config

        if cos_config.USE_BRAIN_PLANNER and (
            len(g) > 35
            or any(x in g for x in ("ثم", "بعدها", "خطّة", "خطة", "كيف", "نفّذ", "نفذ"))
        ):
            from cos.brain import plan_actions_from_goal

            ctx = ""
            try:
                from cos.plugins import REGISTRY

                plug = REGISTRY.detect_from_goal(g)
                if plug:
                    ctx = f"platform_hint={plug.id} url={plug.url}"
            except Exception:
                pass
            brain_steps, brain_reply, provider = plan_actions_from_goal(g, ctx)
            if brain_steps:
                return Plan(
                    g,
                    brain_steps,
                    "execute",
                    (brain_reply or "أنفّذ بخطة العقل.") + f" [{provider}]",
                )
            if brain_reply and provider != "rules":
                # رد محادثة من العقل
                return Plan(g, [], "chat", brain_reply + f" [{provider}]")
    except Exception:
        pass

    if len(g) > 40:
        return Plan(g, [], "explore", "")

    return Plan(
        g,
        [],
        "chat",
        "وضّح المطلوب بجملة قصيرة.\n"
        "مثال: حرّك الماوس · افتح TradingView · حالة العقل · أضف هدف: ...",
    )
