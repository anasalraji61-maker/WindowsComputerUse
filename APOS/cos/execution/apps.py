"""فتح تطبيقات/روابط وملفات — بدون ربط بأسماء أنس داخل النواة."""
from __future__ import annotations

import time
import webbrowser
from pathlib import Path
from typing import Iterable, Optional

from cos import config
from cos.perception.windows import focus_window
from cos.runtime import RUNTIME


QC_URL = "https://www.quantconnect.com/terminal"
QC_LAB = "https://www.quantconnect.com/project"


def open_url(url: str, wait: float = 2.0) -> str:
    """فتح سريع (احتياطي) — يفضّل human_open_url للتحكم بالماوس."""
    RUNTIME.check()
    webbrowser.open(url, new=0, autoraise=True)
    time.sleep(min(max(wait, 0.5), 5.0))
    RUNTIME.check()
    return f"فُتح الرابط: {url}"


def human_open_url(url: str, wait: float = 2.8) -> str:
    """
    افتح رابطاً بطريقة بشرية مرئية:
    مسح ماوس → تركيز/فتح المتصفح → شريط العنوان → لصق الرابط → Enter → ماوس لمنطقة العمل.
    """
    RUNTIME.check()
    import pyautogui

    from cos.execution.hand import hotkey, move_to, type_text
    from cos.perception.windows import focus_window

    notes: list[str] = []
    w, h = pyautogui.size()

    # لا تعمل مسح ماوس استعراضي — افتح الهدف مباشرة
    RUNTIME.check()

    focused = False
    for hint in ("QuantConnect", "Chrome", "Edge", "Firefox", "Brave"):
        ok, msg = focus_window(hint)
        if ok:
            notes.append(msg)
            focused = True
            break

    if not focused:
        # افتح سريعاً ثم ركّز المتصفح
        open_url(url, wait=wait)
        for hint in ("QuantConnect", "Chrome", "Edge", "Firefox", "Brave"):
            ok, msg = focus_window(hint)
            if ok:
                notes.append(msg)
                focused = True
                break
        if not focused:
            notes.append("احتياطي: webbrowser.open")
            return " | ".join(notes) if notes else f"فُتح: {url}"
        notes.append(f"تم فتح: {url}")
        move_to(int(w * 0.5), int(h * 0.42), duration=0.35)
        return " | ".join(notes)

    # تبويب جديد + شريط العنوان بالنقر بالماوس
    hotkey("ctrl", "t")
    time.sleep(0.45)
    RUNTIME.check()
    move_to(w // 2, max(40, int(h * 0.06)), duration=0.45)
    pyautogui.click()
    time.sleep(0.2)
    hotkey("ctrl", "l")
    time.sleep(0.25)
    RUNTIME.check()
    type_text(url)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(min(max(wait, 1.5), 6.0))
    RUNTIME.check()

    # حرّك الماوس داخل الصفحة كأنك تتصفح
    move_to(int(w * 0.5), int(h * 0.42), duration=0.5)
    time.sleep(0.15)
    move_to(int(w * 0.62), int(h * 0.55), duration=0.45)
    notes.append(f"تم الانتقال بالماوس إلى: {url}")
    return " | ".join(notes)


def focus_or_open_url(title_hint: str, url: str) -> str:
    """إن وُجدت نافذة مطابقة ركّزها، وإلا افتح بالماوس كبشر."""
    RUNTIME.check()
    ok, msg = focus_window(title_hint)
    if ok:
        # حتى مع التركيز: حرّك الماوس قليلاً داخل النافذة
        try:
            import pyautogui

            from cos.execution.hand import move_to

            w, h = pyautogui.size()
            move_to(int(w * 0.5), int(h * 0.4), duration=0.4)
        except Exception:
            pass
        return msg
    return human_open_url(url, wait=2.8)


def iter_search_roots() -> list[Path]:
    home = Path.home()
    downloads = home / "Downloads"
    roots = [
        config.WORKSPACE,
        home / "Documents",
        downloads,
        config.ROOT.parent,  # WindowsComputerUse
        # مشاريع ماتريكس المعروفة — أولوية واضحة
        downloads / "MatrixRobot_Handoff_Clean-3",
        downloads / "MatrixRobot_Handoff_Clean",
        downloads / "MATRIX--ROBOT-",
        downloads / "souq-ai",
    ]
    # أزل التكرار وغير الموجود
    out: list[Path] = []
    seen = set()
    for r in roots:
        if not r:
            continue
        try:
            s = str(r).strip()
            if not s or s in (".", ""):
                continue
            rp = Path(s).expanduser().resolve()
        except Exception:
            continue
        if rp in seen or not rp.exists():
            continue
        seen.add(rp)
        out.append(rp)
    return out


def find_robot_candidates(limit: int = 8) -> list[Path]:
    """ابحث عن ملفات بايثون مرشّحة لروبوت/خوارزمية."""
    RUNTIME.check()
    keys = (
        "matrix",
        "robot",
        "algo",
        "algorithm",
        "strategy",
        "qc",
        "main",
        "trading",
    )
    path_boost = ("matrixrobot", "matrix-robot", "matrix_robot", "quantconnect")
    found: list[tuple[float, Path]] = []
    for root in iter_search_roots():
        try:
            # لا تمسح كل Downloads بعمق لانهائي — حدّ العمق للسرعة
            depth_limit = 8 if root.name.lower() == "downloads" else 12
            for p in root.rglob("*.py"):
                parts = {x.lower() for x in p.parts}
                if parts & {
                    "venv",
                    ".venv",
                    "site-packages",
                    "node_modules",
                    "__pycache__",
                    ".git",
                    "windowscomputeruse",
                    "apos",
                }:
                    continue
                try:
                    rel_depth = len(p.relative_to(root).parts)
                except Exception:
                    rel_depth = 99
                if rel_depth > depth_limit:
                    continue
                name = p.name.lower()
                path_l = str(p).lower()
                score = float(p.stat().st_mtime)
                if any(k in name for k in keys):
                    score += 1_000_000
                if any(b in path_l for b in path_boost):
                    score += 5_000_000
                if name in ("main.py", "algorithm.py", "qc_algorithm.py"):
                    score += 2_000_000
                # تجاهل أدوات مساعدة داخل artifacts إن وُجد ملف أفضل لاحقاً
                if "artifacts" in parts and "tools" in parts:
                    score -= 500_000
                found.append((score, p))
        except Exception:
            continue
    found.sort(key=lambda x: x[0], reverse=True)
    uniq: list[Path] = []
    seen = set()
    for _, p in found:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        uniq.append(p)
        if len(uniq) >= limit:
            break
    return uniq


def copy_path_to_clipboard(path: Path) -> str:
    RUNTIME.check()
    text = str(path)
    try:
        import pyperclip

        pyperclip.copy(text)
        return f"نُسخ المسار للحافظة: {text}"
    except Exception:
        return f"المسار (انسخه يدوياً): {text}"


def copy_file_content_to_clipboard(path: Path, max_chars: int = 400_000) -> str:
    """انسخ محتوى ملف الروبوت للحافظة (للصق في QuantConnect)."""
    RUNTIME.check()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"تعذّر قراءة الملف: {e}"
    if len(raw) > max_chars:
        raw = raw[:max_chars]
    try:
        import pyperclip

        pyperclip.copy(raw)
        return f"نُسخ محتوى الملف للحافظة ({len(raw)} حرف): {path.name}"
    except Exception as e:
        return f"تعذّر النسخ للحافظة: {e}"


def qc_login_likely() -> bool:
    """تخمين بسيط إن كانت شاشة تسجيل الدخول ظاهرة."""
    try:
        from cos.perception.windows import list_windows

        titles = " | ".join((w.title or "") for w in list_windows()[:40]).lower()
    except Exception:
        return False
    markers = (
        "log in",
        "login",
        "sign in",
        "تسجيل",
        "account.quantconnect",
        "auth0",
    )
    return any(m in titles for m in markers)


def qc_paste_and_backtest() -> str:
    """
    محاولة لصق كود الروبوت وتشغيل Backtest بعد فتح QC.
    يعتمد إحداثيات نسبية قابلة للضبط عبر البيئة.
    """
    RUNTIME.check()
    import os
    import time

    import pyautogui

    from cos.execution.hand import hotkey, move_to

    notes: list[str] = []
    w, h = pyautogui.size()

    # ركّز نافذة QC/المتصفح
    for hint in ("QuantConnect", "Chrome", "Edge", "Firefox"):
        ok, msg = focus_window(hint)
        if ok:
            notes.append(msg)
            break

    # منطقة المحرر (قابلة للضبط)
    ex = float(os.getenv("COS_QC_EDITOR_RX", "0.48"))
    ey = float(os.getenv("COS_QC_EDITOR_RY", "0.45"))
    bx = float(os.getenv("COS_QC_BACKTEST_RX", "0.88"))
    by = float(os.getenv("COS_QC_BACKTEST_RY", "0.18"))

    move_to(int(w * ex), int(h * ey), duration=0.45)
    time.sleep(0.15)
    pyautogui.click()
    time.sleep(0.25)
    RUNTIME.check()

    # تحديد الكل + لصق
    hotkey("ctrl", "a")
    time.sleep(0.15)
    hotkey("ctrl", "v")
    time.sleep(0.6)
    notes.append("لصق الكود في منطقة المحرر التقريبية")
    RUNTIME.check()

    # زر Backtest التقريبي
    move_to(int(w * bx), int(h * by), duration=0.5)
    time.sleep(0.2)
    pyautogui.click()
    time.sleep(0.8)
    notes.append("نقرة تقريبية على زر Backtest")
    RUNTIME.check()

    # اختصار شائع أحياناً لتشغيل
    try:
        hotkey("f5")
        notes.append("جرّبت F5 كاحتياطي")
    except Exception:
        pass

    return " | ".join(notes)


def write_cursor_robot_request(robot: Optional[Path], goal: str) -> Path:
    """اكتب طلباً واضحاً لـ Cursor حول ملف الروبوت."""
    out = config.DATA / "reports"
    out.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"CURSOR_ROBOT_REQUEST_{stamp}.md"
    lines = [
        "# طلب ملف روبوت لـ QuantConnect",
        "",
        f"**الوقت:** {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"**طلب المستخدم:** {goal}",
        "",
        "## الملف المرشّح",
        str(robot) if robot else "(لم يُعثر على ملف تلقائياً — حدّد مساراً)",
        "",
        "## المطلوب من Cursor",
        "1. راجع/جهّز كود الروبوت ليعمل على QuantConnect (Algorithm Framework إن لزم).",
        "2. تأكد أن الملف جاهز للصق في Algorithm Lab.",
        "3. أعد ملخصاً قصيراً لأي تعديلات ضرورية.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        import os

        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        pass
    return path


def open_in_explorer(path: Path) -> str:
    RUNTIME.check()
    import os
    import subprocess

    target = path if path.is_dir() else path.parent
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
        return f"فُتح المستكشف عند: {target}"
    except Exception:
        subprocess.Popen(["explorer", str(target)])
        return f"فُتح المستكشف عند: {target}"
