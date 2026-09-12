"""
وكيل Computer Use محلي لويندوز:
- يرى شاشتك (لقطة)
- يحرّك الماوس ويكتب على لوحة المفاتيح فعلياً أمامك
- يستخدم Claude Computer Use API

تشغيل:
  1) انسخ .env.example إلى .env وضع مفتاحاً جديداً
  2) python agent.py "افتح Chrome واذهب إلى quantconnect.com"

إيقاف طارئ: حرّك الماوس بسرعة إلى الزاوية اليسرى العليا.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Fix Arabic/UTF-8 display in Windows PowerShell/CMD
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

try:
    import anthropic
except ImportError:
    print("Install packages: pip install -r requirements.txt")
    sys.exit(1)

from desktop import execute_action, get_screen_map, take_screenshot_b64


CHAT_SYSTEM = """مساعد تنفيذي ويندوز. أجب بالعربية باختصار شديد (جملتان كحد أقصى). لا تشرح تفكيرك.
قيود النظام داخلية: لا إغلاق Computer Use Chat، لا Docker، لا إخفاء Cursor، لا Notepad بلا طلب صريح."""

REPORT_SYSTEM = """عيون شاشة ويندوز. تقرير دقيق قصير. لا تخمّن.
قالب:
## النافذة
-
## ظاهر حرفياً
-
## أرقام
-
## غير واضح
-
## للجوكر (سطران)
1)
2)
"""

# قيود أمان مضمّنة برمجياً — المستخدم لا يكتبها في التوجيه
SAFETY_RULES = """
HARD SAFETY:
- NEVER close Computer Use Chat / Docker / Cursor unless user explicitly asks to close that app.
- NEVER use bare Win key / Windows Search to guess apps.
- NEVER open Notepad unless user says Notepad.
- NEVER start QuantConnect Backtest unless user says run/start backtest.
"""

SYSTEM = """You control the REAL Windows desktop with mouse and keyboard. Act NOW.

CRITICAL IDENTITY:
- "Computer Use Chat" is YOUR local control panel — NEVER type messages to "Korsa/Cursor/Joker" inside it.
- Cursor IDE is a SEPARATE window (taskbar/title contains Cursor). Click THAT window to work with the coding agent.
- QuantConnect is the trading site — only if user asked.

RULES:
- Every turn: one real mouse/keyboard action (mouse_move, click, type, key, scroll).
- Do NOT waste turns on screenshot-only or waiting for a reply.
- At most ONE short wait. Prefer Alt+Tab / taskbar clicks.
- Move the mouse visibly then click.
- When done or stuck twice: stop with 2 Arabic lines.
Coords match screenshot size.
""" + SAFETY_RULES

ACTION_HINTS = (
    "افتح", "اضغط", "اكتب", "انقر", "شغّل", "شغل", "اذهب", "انتقل", "خذ", "روح",
    "ابدأ", "ابدا", "مراسلة", "ملف", "روبوت", "كورسر", "كورسا", "ماوس", "تحكم",
    "لابتوب", "اللاب", "سطح المكتب",
    "open", "click", "type", "press", "go to", "launch", "run ", "close ",
    "notepad", "chrome", "quantconnect", "cursor", "mouse", "أرسل", "ارسل",
    "احذف", "انسخ", "الكمبيوتر", "نقل",
)

REPORT_HINTS = (
    "صف الشاشة",
    "وصف الشاشة",
    "ماذا ترى",
    "ما الذي تراه",
    "انظر للشاشة",
    "أخبر الجوكر بما ترى",
    "انقل للجوكر ما على الشاشة",
    "تقرير للجوكر من الشاشة",
    "اقرأ الشاشة",
    "screenshot only",
)

# إذا ظهرت هذه، الأولوية للتنفيذ/القراءة وليس لتقرير الشاشة
READ_FILE_HINTS = (
    "اقرأ هذا الملف",
    "اقرأ الملف",
    "افتح الملف",
    "protocol_qc_bridge",
    "handoff_for_agent",
    ".md",
)


def looks_like_report(text: str) -> bool:
    t = text.strip().lower()
    # طلب قراءة ملف له أولوية على كلمة report داخل المسار
    if any(h in t for h in READ_FILE_HINTS):
        return False
    if "report_for_cursor" in t and ("اقرأ" in t or "افتح" in t or "لخّص" in t or "لخص" in t):
        return False
    return any(h in t for h in REPORT_HINTS)


def extract_windows_path(text: str):
    import re

    m = re.search(r"[A-Za-z]:\\[^\s\"']+", text)
    if not m:
        return None
    return m.group(0).rstrip(".,;:)")


def summarize_local_file(task: str):
    """
    فتح ملف محلي في Notepad فقط — بدون إرسال محتواه إلى API (توفير رصيد).
    يرجع نصاً قصيراً محلياً، أو None إن لم يكن الطلب عن ملف.
    """
    from pathlib import Path
    import subprocess

    path_str = extract_windows_path(task)
    low = task.lower()
    base = Path(__file__).resolve().parent
    if not path_str:
        for name in ("PROTOCOL_QC_BRIDGE.md", "HANDOFF_FOR_AGENT.md", "REPORT_FOR_CURSOR.md"):
            if name.lower().replace(".md", "") in low or name.lower() in low:
                path_str = str(base / name)
                break
    if not path_str:
        return None

    file_words = (
        "اقرأ", "اقرا", "لخّص", "لخص", "افتح الملف", "افتح", "محتوى",
        "read", "summar", "protocol", "handoff", ".md",
    )
    if not any(w in low for w in file_words):
        return None

    p = Path(path_str)
    if not p.exists():
        alt = base / p.name
        if alt.exists():
            p = alt
        else:
            return f"الملف غير موجود: {path_str}"

    try:
        # لا نفتح Notepad — الجوكر يقرأ الملف من المسار مباشرة
        pass
    except Exception:
        pass

    size_kb = p.stat().st_size / 1024.0
    return (
        f"الملف جاهز بدون فتح Notepad.\n"
        f"المسار: {p}\n"
        f"الحجم: {size_kb:.1f} KB\n"
        f"اطلب من الجوكر قراءته من Cursor."
    )


def looks_like_action(text: str) -> bool:
    t = text.strip().lower()
    if len(t) < 2:
        return False
    if looks_like_report(t):
        return False
    # قراءة ملف = تنفيذ (فتح Notepad/المسار) وليس محادثة فقط
    if any(h in t for h in READ_FILE_HINTS):
        return True
    return any(h in t for h in ACTION_HINTS)


def chat_reply(message: str) -> str:
    """رد نصي عربي بدون تحريك الماوس."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "YOUR_NEW_KEY" in api_key:
        return "خطأ: مفتاح API غير موجود في .env"
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=350,
            temperature=0,
            system=CHAT_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
    except Exception as e:
        return f"خطأ API: {e}"
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip() or "(لا رد)"


def _force_foreground(hwnd: int) -> None:
    """رفع نافذة ويندوز للأمام بقوة أكبر من activate العادية."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def focus_window_by_score(matchers: list[str], prefer: list[str] | None = None, avoid: list[str] | None = None):
    """
    يجد أفضل نافذة حسب كلمات في العنوان.
    يرجع (title, ok) أو (None, False).
    """
    prefer = prefer or []
    avoid = avoid or []
    try:
        import pygetwindow as gw
    except Exception as e:
        return None, False, f"pygetwindow: {e}"

    scored = []
    for w in gw.getAllWindows():
        title = (w.title or "").strip()
        if not title:
            continue
        low = title.lower()
        if any(a in low for a in avoid):
            continue
        if not any(m in low for m in matchers):
            continue
        score = 1
        for p in prefer:
            if p in low:
                score += 2
        scored.append((score, w))
    if not scored:
        return None, False, "لا نافذة مطابقة"
    scored.sort(key=lambda x: x[0], reverse=True)
    w = scored[0][1]
    try:
        if w.isMinimized:
            w.restore()
        try:
            _force_foreground(int(w._hWnd))  # type: ignore[attr-defined]
        except Exception:
            w.activate()
        return w.title, True, "ok"
    except Exception as e:
        return w.title, False, str(e)


def normalize_speech_ar(text: str) -> str:
    """تصحيح أخطاء التعرف الصوتي الشائعة قبل التنفيذ."""
    if not text:
        return text
    fixes = (
        ("كورسا", "Cursor"),
        ("كورسر", "Cursor"),
        ("كورش", "Cursor"),
        ("كورسور", "Cursor"),
        ("كونت كونكت", "QuantConnect"),
        ("كونكت كونكت", "QuantConnect"),
        ("كوانت كونكت", "QuantConnect"),
        ("كوانتكونيكت", "QuantConnect"),
        ("كوانت", "QuantConnect"),
        ("الجوكر", "Cursor"),
    )
    out = text
    for a, b in fixes:
        out = out.replace(a, b)
    return out


def find_or_focus_cursor() -> tuple[bool, str]:
    """ركّز نافذة Cursor IDE (ليست Computer Use Chat)."""
    title, ok, detail = focus_window_by_score(
        matchers=["cursor"],
        prefer=["cursor"],
        avoid=["computer use chat", "docker"],
    )
    if ok:
        return True, f"ركزت Cursor: {title}"
    return False, f"Cursor غير ظاهر ({detail})"


def find_or_open_quantconnect(allow_open: bool = True) -> tuple[bool, str]:
    """
    ابحث عن QuantConnect في النوافذ المفتوحة → ادخل إليه.
    إن لم يوجد وallow_open: افتحه في المتصفح الافتراضي.
    لا يغلق ولا يخفي نوافذ أخرى.
    """
    import time

    title, ok, detail = focus_window_by_score(
        matchers=["quantconnect", "algorithm lab", "sky blue snake"],
        prefer=["chrome", "edge", "quantconnect", "snake", "backtest", "overview"],
        avoid=["connection failed", "err_connection", "computer use chat"],
    )
    if ok:
        return True, f"وجدتُه ودخلتُ إليه: {title}"

    # بحث أوسع بأي عنوان فيه quantconnect
    title2, ok2, _ = focus_window_by_score(
        matchers=["quantconnect"],
        prefer=["google chrome", "chrome", "edge", "brave"],
        avoid=["computer use chat", "connection failed"],
    )
    if ok2:
        return True, f"وجدتُه ودخلتُ إليه: {title2}"

    if not allow_open:
        return False, "لم أجده مفتوحاً — وطلبتَ عدم الفتح التلقائي"

    # افتح QC دون إغلاق أي شيء آخر
    try:
        import webbrowser

        webbrowser.open("https://www.quantconnect.com/", new=0, autoraise=True)
        time.sleep(2.2)
    except Exception as e:
        return False, f"لم أجده، وفشل فتح المتصفح: {e}"

    title3, ok3, _ = focus_window_by_score(
        matchers=["quantconnect", "algorithm lab"],
        prefer=["chrome", "edge", "quantconnect"],
        avoid=["computer use chat", "connection failed"],
    )
    if ok3:
        return True, f"لم يكن ظاهراً — فتحته ودخلتُ إليه: {title3}"
    return True, "فتحته في المتصفح (قد يحتاج تسجيل دخول يدوياً إن ظهرت صفحة الدخول)"


def run_smart_mission(user_text: str = "") -> str:
    """
    ينفّذ نص المستخدم فقط — بلا مهمة جاهزة وبلا فتح QuantConnect تلقائياً.
    """
    from datetime import datetime
    from pathlib import Path

    text = normalize_speech_ar((user_text or "").strip())
    if not text:
        return "لا يوجد طلب — اكتب ما تريد ثم إرسال."

    notes: list[str] = []
    notes.append("تنفيذ طلبك فقط — الماوس/لوحة المفاتيح على الشاشة الآن")

    low = text.lower()
    mentions_cursor = ("cursor" in low) or ("كورسر" in text) or ("كورسا" in text)
    wants_mouse = any(
        x in text.lower() or x in text
        for x in ("ماوس", "mouse", "تحكم", "لابتوب", "اللاب", "سطح المكتب", "desktop")
    )
    mentions_qc = ("quantconnect" in low) or ("كوانت" in text) or ("كوينت" in text)
    asks_open = any(x in text for x in ("افتح", "افتحه", "ادخل", "أدخل", "روح", "انتقل", "open "))

    if mentions_cursor or wants_mouse:
        ok, msg = find_or_focus_cursor()
        notes.append(f"تركيز Cursor: {msg}")
        if not ok and wants_mouse:
            # حتى لو Cursor غير ظاهر: نفّذ على سطح المكتب فوراً
            notes.append("سأحرّك الماوس على الشاشة حسب طلبك")

    if mentions_qc and asks_open:
        ok, msg = find_or_open_quantconnect(allow_open=True)
        notes.append(f"مساعدة QC (بطلب صريح): {msg}")
    elif mentions_qc:
        ok, msg = find_or_open_quantconnect(allow_open=False)
        notes.append(f"بحث QC بدون فتح جديد: {msg}")

    brain_task = (
        text
        + "\n\n[CRITICAL] Computer Use Chat is YOUR panel — do NOT type into it as a chat with Korsa/Cursor. "
        "Cursor IDE is a separate window. "
        "MOVE THE REAL MOUSE NOW: mouse_move then click on taskbar/desktop/Cursor. "
        "Do NOT wait for replies. Do NOT open QuantConnect unless asked. "
        "Do NOT close Computer Use Chat. Short Arabic when done."
    )
    steps = int(os.getenv("SMART_MISSION_STEPS", "8"))
    brain_out = run_task(brain_task, steps) or ""
    if brain_out:
        notes.append("--- تنفيذ ---\n" + brain_out)

    out = Path(__file__).resolve().parent / "REPORT_FOR_CURSOR.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body = brain_out.strip() or "\n".join(notes)
    out.write_text(
        f"# تقرير للجوكر\n\n**الوقت:** {stamp}\n\n"
        f"**طلب المستخدم:**\n{text}\n\n---\n\n{body}\n",
        encoding="utf-8",
    )
    notes.append(f"حُفظ: {out}")
    return chr(10).join(notes)


def run_full_bridge_task() -> str:
    """لم يعد يفتح QC تلقائياً — يطلب نصاً من المستخدم."""
    return "أُلغي المسار الجاهز. اكتب طلبك ثم اضغط إرسال."


def run_executive_brief(brief: str = "") -> str:
    """للمهام المركبة: مدير المهام. للماوس فقط: المسار القديم."""
    text = (brief or "").strip()
    low = text.lower()
    mouse_only = any(
        k in text or k in low
        for k in ("حرك الماوس", "حرّك الماوس", "move mouse", "مسح الماوس", "لماذا لا تتحرك")
    )
    if mouse_only:
        return run_smart_mission(brief)
    try:
        from pathlib import Path
        import sys

        apos = Path(__file__).resolve().parent / "APOS"
        if str(apos) not in sys.path:
            sys.path.insert(0, str(apos))
        from cos.core.task_manager import run_goal

        return run_goal(text)
    except Exception as e:
        return f"تعذّر مدير المهام ({e}). مسار احتياطي:\n" + run_smart_mission(brief)


def report_screen_for_cursor(extra_note: str = "") -> str:
    """يلتقط الشاشة ويكتب تقريراً دقيقاً يقرأه وكيل Cursor."""
    from datetime import datetime
    from pathlib import Path

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "YOUR_NEW_KEY" in api_key:
        return "خطأ: مفتاح API غير موجود في .env"
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
    client = anthropic.Anthropic(api_key=api_key)
    screen = get_screen_map()
    b64, media_type = take_screenshot_b64(screen)

    user_content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        },
        {
            "type": "text",
            "text": (extra_note.strip() or "صف الشاشة الحالية بدقة لتقرير يُرسل لوكيل البرمجة."),
        },
    ]
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=700,
            temperature=0,
            system=REPORT_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        return f"خطأ API: {e}"

    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    report = "\n".join(parts).strip() or "(لا وصف)"

    out = Path(__file__).resolve().parent / "REPORT_FOR_CURSOR.md"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out.write_text(
        f"# تقرير الشاشة للجوكر\n\n"
        f"**الوقت:** {stamp}\n\n"
        f"**طلب المستخدم:** {extra_note or 'وصف الشاشة'}\n\n"
        f"---\n\n{report}\n",
        encoding="utf-8",
    )
    return report + f"\n\n[حُفظ أيضاً في: {out}]"



def call_claude_with_retry(client, **kwargs):
    """Retry on temporary Anthropic/Cloudflare 502/529 errors."""
    last_err = None
    for attempt in range(1, 6):
        try:
            return client.beta.messages.create(**kwargs)
        except anthropic.APIStatusError as e:
            last_err = e
            code = getattr(e, "status_code", None)
            if code in (429, 500, 502, 503, 529):
                wait = min(2 ** attempt, 20)
                print(f"Temporary API error {code}. Retry {attempt}/5 in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            last_err = e
            wait = min(2 ** attempt, 20)
            print(f"Connection issue. Retry {attempt}/5 in {wait}s...")
            time.sleep(wait)
    raise last_err


def build_tools(screen) -> list:
    # computer_20250124 يعمل مع نماذج Sonnet 4.5 / Haiku 4.5
    return [
        {
            "type": "computer_20250124",
            "name": "computer",
            "display_width_px": screen.model_w,
            "display_height_px": screen.model_h,
            "display_number": 1,
        }
    ]


def tool_result_text_only(tool_use_id: str, status: str) -> dict:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": [{"type": "text", "text": status}],
    }


def tool_result_with_screenshot(tool_use_id: str, status: str, screen) -> dict:
    b64, media_type = take_screenshot_b64(screen)
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": [
            {"type": "text", "text": status},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            },
        ],
    }


def _needs_screenshot_after(action: str | None) -> bool:
    """لا ترسل صورة بعد انتظار/لقطة — أكبر موفّر للتكلفة."""
    a = (action or "").lower()
    if a in ("wait", "hold_key", "screenshot"):
        return False
    return True


def prune_old_images(messages: list, keep_last: int = 1) -> list:
    """احذف الصور القديمة من التاريخ — أكبر سبب للبطء بعد عدة خطوات."""
    # اجمع مواقع الصور من الأحدث للأقدم
    image_locs: list[tuple[int, int, int]] = []  # msg_idx, block_idx, content_idx_or_-1
    for mi, msg in enumerate(messages):
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for bi, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "image":
                image_locs.append((mi, bi, -1))
            elif block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    for ci, part in enumerate(inner):
                        if isinstance(part, dict) and part.get("type") == "image":
                            image_locs.append((mi, bi, ci))
    drop = set(image_locs[:-keep_last]) if len(image_locs) > keep_last else set()
    if not drop:
        return messages

    out = []
    for mi, msg in enumerate(messages):
        content = msg.get("content")
        if not isinstance(content, list):
            out.append(msg)
            continue
        new_blocks = []
        for bi, block in enumerate(content):
            if not isinstance(block, dict):
                new_blocks.append(block)
                continue
            if block.get("type") == "image" and (mi, bi, -1) in drop:
                new_blocks.append({"type": "text", "text": "[old screenshot removed]"})
                continue
            if block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                new_inner = []
                for ci, part in enumerate(block["content"]):
                    if isinstance(part, dict) and part.get("type") == "image" and (mi, bi, ci) in drop:
                        new_inner.append({"type": "text", "text": "[old screenshot removed]"})
                    else:
                        new_inner.append(part)
                nb = dict(block)
                nb["content"] = new_inner
                new_blocks.append(nb)
                continue
            new_blocks.append(block)
        nm = dict(msg)
        nm["content"] = new_blocks
        out.append(nm)
    return out


def _out(msg: str = "") -> None:
    """طباعة عادية، أو إلى السجل فقط إذا AGENT_QUIET=1 (من نافذة الدردشة)."""
    quiet = os.getenv("AGENT_QUIET", "").strip() in ("1", "true", "yes")
    if quiet:
        try:
            from pathlib import Path
            from datetime import datetime

            log = Path(__file__).resolve().parent / "agent_run.log"
            with log.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%H:%M:%S} | {msg}\n")
        except Exception:
            pass
        return
    print(msg)


def run_task(task: str, max_steps: int) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or "YOUR_NEW_KEY" in api_key:
        _out("خطأ: ضع ANTHROPIC_API_KEY في ملف .env")
        return "خطأ: مفتاح API غير موجود"

    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
    client = anthropic.Anthropic(api_key=api_key)
    screen = get_screen_map()
    last_texts: list[str] = []

    _out("=" * 60)
    _out("Windows Agent - Computer Use + PyAutoGUI (BRAIN ON)")
    _out(f"Real screen:  {screen.real_w}x{screen.real_h}")
    _out(f"Model size:   {screen.model_w}x{screen.model_h}")
    _out(f"Model:        {model}")
    _out("NEVER close Computer Use Chat window")
    _out("=" * 60)
    _out(f"Task: {task}")
    start_delay = float(os.getenv("START_DELAY", "0.15"))
    _out(f"Starting in {start_delay}s...")
    time.sleep(max(0.0, start_delay))

    # أول رسالة: لقطة + المهمة + تذكير أمان
    first_shot, media_type = take_screenshot_b64(screen)
    safe_task = task + "\n\nAct FAST from screenshot. Short Arabic summary when done.\n" + SAFETY_RULES
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": first_shot,
                    },
                },
                {"type": "text", "text": safe_task},
            ],
        }
    ]

    tools = build_tools(screen)
    betas = ["computer-use-2025-01-24"]
    max_tokens = int(os.getenv("MAX_TOKENS_ACTION", "280"))
    step_pause = float(os.getenv("STEP_DELAY", "0.02"))
    # تخزين مؤقت للـ system يقلّل التكلفة عند تكرار الخطوات
    system_cached = [
        {
            "type": "text",
            "text": SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    for step in range(1, max_steps + 1):
        _out(f"\n--- Step {step}/{max_steps} ---")
        messages = prune_old_images(messages, keep_last=1)
        try:
            response = call_claude_with_retry(
                client,
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                system=system_cached,
                tools=tools,
                messages=messages,
                betas=betas,
            )
        except Exception as e:
            _out(f"API error: {e}")
            _out("Tip: 502 is temporary. Wait 1 minute and run again.")
            return f"خطأ API: {e}"

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if getattr(block, "type", None) == "text" and block.text:
                _out("Claude: " + block.text)
                last_texts.append(block.text.strip())

        if response.stop_reason == "end_turn":
            _out("\nTask finished.")
            return last_texts[-1] if last_texts else "انتهى بدون نص"

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if block.name != "computer":
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"unsupported tool: {block.name}",
                        "is_error": True,
                    }
                )
                continue

            action_input = dict(block.input)
            action_name = action_input.get("action")
            _out("Action: " + str(action_name) + " " + str(action_input))
            if action_name == "screenshot" and step == 1:
                status = "ok: already have screenshot — act now"
            else:
                try:
                    status = execute_action(action_input, screen)
                except Exception as e:
                    _out(f"Stopped: {e}")
                    return f"توقف: {e}"

            if step_pause > 0:
                time.sleep(step_pause)
            if _needs_screenshot_after(action_name):
                tool_results.append(tool_result_with_screenshot(block.id, status, screen))
            else:
                tool_results.append(tool_result_text_only(block.id, status + " (no new screenshot — act)"))

        if not tool_results:
            _out("No actions — stop.")
            return last_texts[-1] if last_texts else "توقف بدون إجراء"

        messages.append({"role": "user", "content": tool_results})

    _out("\nReached max steps.")
    return last_texts[-1] if last_texts else "وصل للحد الأقصى من الخطوات"


def main():
    parser = argparse.ArgumentParser(description="Windows Computer Use Agent")
    parser.add_argument(
        "task",
        nargs="?",
        default="",
        help="Task in English or Arabic",
    )
    parser.add_argument("--steps", type=int, default=0, help="Max steps")
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Interactive chat mode: type tasks one by one",
    )
    args = parser.parse_args()

    max_steps = args.steps or int(os.getenv("MAX_STEPS", "40"))

    # Chat mode: keep asking for tasks
    if args.chat or not args.task.strip():
        print("=" * 60)
        print("CHAT MODE - type a task and press Enter")
        print("Examples:")
        print('  Open Notepad and type Hello')
        print('  Open Chrome and go to quantconnect.com')
        print("Type exit to quit")
        print("=" * 60)
        while True:
            try:
                task = input("\nYou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return
            if not task:
                continue
            if task.lower() in ("exit", "quit", "خروج"):
                print("Bye.")
                return
            try:
                run_task(task, max_steps)
            except KeyboardInterrupt:
                print("\nStopped this task. Type next task or exit.")
        return

    try:
        run_task(args.task.strip(), max_steps)
    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C).")


if __name__ == "__main__":
    main()
