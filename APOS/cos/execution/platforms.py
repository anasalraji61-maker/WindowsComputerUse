"""فتح منصات بذكاء: سطح مكتب إن وُجد → وإلا متصفح → تسجيل الدخول يدوي من المستخدم."""
from __future__ import annotations

from typing import Optional

from cos.execution import browser
from cos.execution.hand import Action, execute
from cos.memory.experience import ExperienceStore
from cos.perception import processes, vision, windows as winmod
from cos.perception.world_model import get_world_model
from cos.plugins import REGISTRY, Plugin
from cos.runtime import RUNTIME


def _window_present(hints: list[str]) -> tuple[bool, str]:
    for h in hints:
        ok, msg = winmod.focus_window(h)
        if ok:
            return True, msg
    # فحص بدون تركيز فاشل بالكامل
    titles = " | ".join((w.title or "").lower() for w in winmod.list_windows())
    for h in hints:
        if h.lower() in titles:
            return True, f"نافذة موجودة: {h}"
    return False, "لا نافذة سطح مكتب مطابقة"


def _process_present(hints: list[str]) -> bool:
    try:
        procs = processes.list_processes(limit=40)
    except Exception:
        return False
    blob = " ".join(p.name.lower() for p in procs)
    return any(h.lower().split()[0] in blob for h in hints if h)


def _remember_access(plugin_id: str, mode: str, detail: str) -> None:
    wm = get_world_model()
    note = f"access={mode}; {detail}"
    wm.remember_platform(plugin_id, note)
    wm.model.apps.setdefault(plugin_id, {})
    wm.model.apps[plugin_id]["access_mode"] = mode
    wm.model.apps[plugin_id]["last_access"] = detail[:200]
    wm.save()


def resolve_how_to_open(plug: Plugin) -> dict:
    """يقرر: desktop | browser | cli | unknown — مع أسباب."""
    wm = get_world_model()
    remembered = (wm.model.apps.get(plug.id) or {}).get("access_mode")
    hints = list(plug.window_hints or [plug.name])

    present, wmsg = _window_present(hints)
    if present:
        return {"mode": "desktop", "reason": wmsg, "hints": hints}

    if _process_present(hints):
        return {
            "mode": "desktop",
            "reason": "عملية قيد التشغيل لكن النافذة غير مركّزة بعد",
            "hints": hints,
        }

    # ذاكرة سابقة: ويب فقط
    if remembered == "browser" or plug.kind == "web":
        if plug.url:
            return {
                "mode": "browser",
                "reason": remembered
                and "خبرة سابقة: لا سطح مكتب — فتح متصفح"
                or "المنصة من نوع web في الكتالوج",
                "hints": hints,
            }

    if plug.kind == "cli":
        return {"mode": "cli", "reason": "أداة سطر أوامر", "hints": hints}

    if plug.kind in ("desktop", "mixed"):
        # لا سطح مكتب ظاهر الآن
        if plug.url:
            return {
                "mode": "browser",
                "reason": "لم أجد تطبيق سطح مكتب مفتوحاً — سأفتح الرابط في المتصفح إن وُجد",
                "hints": hints,
            }
        return {
            "mode": "unknown",
            "reason": "لم أجد نافذة/عملية سطح مكتب ولا يوجد رابط ويب في الكتالوج",
            "hints": hints,
        }

    if plug.url:
        return {"mode": "browser", "reason": "فتح عبر المتصفح", "hints": hints}

    return {"mode": "unknown", "reason": "لا مسار فتح معروف", "hints": hints}


def open_plugin(plugin_id: str) -> str:
    RUNTIME.check()
    REGISTRY.load_all()
    plug = REGISTRY.get(plugin_id)
    if not plug:
        return f"plugin غير معروف: {plugin_id}"
    return open_plugin_obj(plug)


def open_plugin_obj(plug: Plugin, *, research_if_unknown: bool = True) -> str:
    """
    التدفق:
    1) ابحث عن نافذة/عملية سطح مكتب
    2) إن وُجدت → ركّزها
    3) وإلا إن وجد URL → افتح المتصفح
    4) احفظ الخبرة (web/desktop)
    5) ذكّر المستخدم أن تسجيل الدخول يدوي مرة واحدة
    """
    RUNTIME.check()
    notes: list[str] = []
    decision = resolve_how_to_open(plug)
    mode = decision["mode"]
    notes.append(f"قرار الفتح: {mode} — {decision['reason']}")

    if mode == "desktop":
        focused = False
        for h in decision.get("hints") or []:
            try:
                notes.append(
                    execute(
                        Action(
                            kind="focus",
                            params={"title": h},
                            confidence=0.9,
                            reason=f"open:{plug.id}",
                        )
                    )
                )
                focused = True
                break
            except Exception as e:
                notes.append(f"focus({h}): {e}")
        if not focused and plug.url:
            mode = "browser"
            notes.append("فشل التركيز — التحويل للمتصفح")
        else:
            _remember_access(plug.id, "desktop", notes[-1] if notes else "focused")

    if mode == "browser":
        if not plug.url:
            notes.append("لا يوجد URL في plugin.yaml")
            _remember_access(plug.id, "unknown", "no url")
        else:
            hint = (plug.window_hints or [plug.name])[0]
            notes.append(browser.open_or_focus(hint, plug.url))
            _remember_access(plug.id, "browser", plug.url)
            # QuantConnect وغيره: غالباً ويب فقط — ثبّت الخبرة
            if plug.kind == "web" or plug.id == "quantconnect":
                get_world_model().remember_platform(
                    plug.id,
                    "web_only: لا تطبيق سطح مكتب رسمي معروف — استخدم المتصفح بعد تسجيل دخولك اليدوي",
                )

    if mode == "cli":
        from cos.execution import terminal

        notes.append(terminal.open_powershell(f"Write-Host 'COS plugin {plug.id}'"))
        _remember_access(plug.id, "cli", "powershell")

    if mode == "unknown" and research_if_unknown:
        # بحث خفيف + قرار
        try:
            from cos.agents.research import ResearchAgent

            brief = ResearchAgent().investigate(
                goal=f"Is there an official desktop app for {plug.name}? official download URL",
                platform=plug.name,
                action="find_desktop_app",
                error="not found locally",
                open_browser=True,
            )
            notes.append("بحث تلقائي عن وجود تطبيق سطح مكتب:")
            notes.append(brief.summary[:500])
            if plug.url:
                notes.append("لم يُعثر محلياً — أفتح المتصفح بالرابط المعروف في الكتالوج.")
                notes.append(browser.open_or_focus(plug.name, plug.url))
                _remember_access(plug.id, "browser", plug.url)
        except Exception as e:
            notes.append(f"بحث: {e}")

    try:
        vision.capture_event(f"plugin_{plug.id}", force=True)
    except Exception:
        pass

    ExperienceStore().record(
        plug.id, "smart_open", mode, "; ".join(notes)[:220], mode in ("desktop", "browser", "cli")
    )

    login_hint = (
        "\n\nتسجيل الدخول: يدوياً منك مرة واحدة (آمن أكثر). "
        "بعد دخولك وبقاء الجلسة، أعمل على المنصة بشكل مستمر دون إعادة إدخال كلمة السر."
    )
    return (
        f"فتحت {plug.name} ({plug.id}) عبر: {mode}\n"
        + "\n".join(notes)
        + login_hint
    )


def open_from_goal(goal: str) -> str:
    REGISTRY.load_all()
    plug = REGISTRY.detect_from_goal(goal)
    if not plug:
        if any(x in goal for x in ("كل المنصات", "list plugins", "قائمة المنصات")):
            cat = REGISTRY.catalog()
            lines = ["المنصات المسجّلة:"]
            for k, ids in cat.items():
                lines.append(f"- {k}: {', '.join(ids)}")
            return "\n".join(lines)
        return ""
    return open_plugin_obj(plug)
