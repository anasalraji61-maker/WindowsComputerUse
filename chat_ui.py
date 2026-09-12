"""
نافذة دردشة صغيرة أسفل يسار الشاشة — دائماً فوق النوافذ الأخرى.
تكتب المهمة هنا دون أن تغطي العمل كامل الشاشة.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import scrolledtext, messagebox
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).resolve().parent
LOG_FILE = BASE / "agent_run.log"


def log_line(msg: str) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {msg}\n")
    except Exception:
        pass


# استيراد منطق الوكيل
try:
    from agent import (
        run_task,
        chat_reply,
        looks_like_action,
        looks_like_report,
        report_screen_for_cursor,
        summarize_local_file,
        run_smart_mission,
        normalize_speech_ar,
    )
except Exception as e:
    log_line(f"IMPORT FATAL: {e}\n{traceback.format_exc()}")
    raise


def run_managed_task(goal: str) -> str:
    """مسار مدير المهام الحقيقي (COS) — بدل وكيل الشاشة المحدود."""
    apos = BASE / "APOS"
    if str(apos) not in sys.path:
        sys.path.insert(0, str(apos))
    from cos.core.task_manager import run_goal

    return run_goal(goal)


def _wants_mouse_only(text: str) -> bool:
    t = (text or "").strip().lower()
    keys = ("حرك الماوس", "حرّك الماوس", "move mouse", "مسح الماوس", "لماذا لا تتحرك")
    return any(k in (text or "") or k in t for k in keys)


def _is_chat_only(text: str) -> bool:
    """محادثة قصيرة فقط — لا تلتقط التوجيهات الطويلة بالخطأ."""
    t = text.strip()
    if not t:
        return False
    # توجيه طويل أو أمر واضح = ليس محادثة
    if len(t) > 80:
        return False
    if looks_like_action(t):
        return False
    low = t.lower()
    keys = (
        "مرحبا", "اهلا", "أهلا", "السلام", "شكرا", "شكراً",
        "من أنت", "من انت", "hello", "hi ", "hey",
        "كيف حالك", "كيفك", "شلونك",
        "ماذا تستطيع", "what can you", "هل انت معي", "هل أنت معي",
        "تسمعني",
    )
    return any(k in t or k in low for k in keys)


def _is_executive_brief(text: str) -> bool:
    """أي طلب عملي/طويل → تنفيذ على الشاشة."""
    t = text.strip()
    if not t or _is_chat_only(t):
        return False
    if looks_like_action(t) or _is_full_brief(t):
        return True
    low = t.lower()
    if any(x in low for x in ("quantconnect", "cursor", "chrome", "كوانت", "كورسر", "كورسا", "ماوس", "تحكم")):
        return True
    if "تقرير" in t or "للجوكر" in t:
        return True
    # فقرة توجيه (>40 حرف) ليست تحية = نفّذ
    if len(t) > 40:
        return True
    return False


def _is_full_brief(text: str) -> bool:
    t = text.strip()
    if len(t) < 40:
        return False
    marks = 0
    for w in ("ثم", "بعدها", "1)", "2)", "تقرير", "quantconnect", "overview", "للجوكر"):
        if w.lower() in t.lower() or w in t:
            marks += 1
    return marks >= 2


def _normalize_brief(text: str) -> str:
    """تنظيف لصق عربي/إنجليزي المختلط بدون تخريب المعنى."""
    if not text:
        return ""
    # حذف علامات اتجاه يونيكود التي تسبب الخربطة في Tk
    for ch in (
        "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff",
    ):
        text = text.replace(ch, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # أسطر منطقية: لا تلصق الكلمات ببعضها بسبب أسطر مكسورة وسط كلمة
    lines = []
    for ln in text.split("\n"):
        ln = " ".join(ln.split())  # مسافات زائدة فقط داخل السطر
        if ln:
            lines.append(ln)
    return "\n".join(lines).strip()


class ChatOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Computer Use Chat")
        self.root.attributes("-topmost", True)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # حجم ثابت تقريباً — الأزرار مثبتة أسفل
        w, h = 500, 460
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x, y = 8, max(40, sh - h - 70)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(460, 400)
        self.root.configure(bg="#1e1e1e")

        # خط عربي مستقر على ويندوز
        ui_font = ("Tahoma", 11)
        log_font = ("Tahoma", 10)
        btn_font = ("Tahoma", 10)

        # أسفل ثابت: حالة ثم أزرار ثم صندوق
        self.status = tk.Label(
            self.root, text="Idle", bg="#1e1e1e", fg="#9cdcfe", anchor="w", font=("Tahoma", 8)
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))

        row = tk.Frame(self.root, bg="#1e1e1e")
        row.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4))

        # أزرار: صوت | إيقاف | لصق | مسح | إرسال
        self.btn_voice = tk.Button(
            row, text="صوت", command=self.on_voice, bg="#6a1b9a", fg="white",
            relief=tk.FLAT, width=8, font=btn_font, padx=4, pady=4,
        )
        self.btn_voice.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_stop = tk.Button(
            row, text="إيقاف", command=self.on_voice_stop, bg="#c62828", fg="white",
            relief=tk.FLAT, width=8, font=btn_font, padx=4, pady=4,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_paste = tk.Button(
            row, text="لصق", command=self.paste_into_entry, bg="#3a3a3a", fg="white",
            relief=tk.FLAT, width=8, font=btn_font, padx=4, pady=4,
        )
        self.btn_paste.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_clear = tk.Button(
            row, text="مسح", command=self.clear_entry, bg="#5a1a1a", fg="white",
            relief=tk.FLAT, width=8, font=btn_font, padx=4, pady=4,
        )
        self.btn_clear.pack(side=tk.LEFT, padx=(0, 6))

        self.btn = tk.Button(
            row, text="إرسال", command=self.on_send, bg="#0e639c", fg="white",
            relief=tk.FLAT, width=10, font=btn_font, padx=4, pady=4,
        )
        self.btn.pack(side=tk.LEFT)

        self.listening = False
        self._voice_stopping = False
        self._partial_busy = False
        self._voice_last_partial = ""

        # صندوق الكتابة: بدون justify=right (كان يخرّب العربية)
        self.entry = tk.Text(
            self.root,
            height=5,
            bg="#2a2a2a",
            fg="#ffffff",
            insertbackground="white",
            wrap=tk.WORD,
            font=ui_font,
            padx=8,
            pady=8,
            undo=True,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#555",
            highlightcolor="#0e639c",
        )
        self.entry.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(4, 6))
        self.entry.bind("<Control-Return>", lambda e: self.on_send())
        self.entry.bind("<Control-KP_Enter>", lambda e: self.on_send())
        self._bind_clipboard(self.entry)

        hint = tk.Label(
            self.root,
            text="صوت ثم إيقاف | يظهر النص هنا وفي الصندوق ثم إرسال",
            bg="#1e1e1e",
            fg="#9cdcfe",
            anchor="w",
            font=("Tahoma", 9),
        )
        hint.pack(side=tk.BOTTOM, fill=tk.X, padx=8)

        self.log = scrolledtext.ScrolledText(
            self.root,
            height=10,
            bg="#252526",
            fg="#d4d4d4",
            insertbackground="white",
            wrap=tk.WORD,
            font=log_font,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.log.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        self.log.insert(tk.END, "جاهز.\n")
        self.log.insert(tk.END, "صوت → تكلم (يظهر كلامك في الشات) → إيقاف → إرسال\n")
        self.log.insert(tk.END, "-" * 36 + "\n")
        self.log.config(state=tk.DISABLED)

        self.busy = False
        self.msg_q: queue.Queue[str] = queue.Queue()
        self.root.after(200, self._drain_queue)

        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key or "YOUR_NEW_KEY" in key or len(key) < 20:
            self._append("تحذير: مفتاح API غير موجود أو غير صالح\n")

        log_line("UI started (clean layout, no RTL justify)")
        self.root.report_callback_exception = self._tk_exception
        self.entry.focus_set()

    def _get_entry_text(self) -> str:
        raw = self.entry.get("1.0", "end-1c")
        return _normalize_brief(raw)

    def _set_entry_text(self, text: str) -> None:
        self.entry.delete("1.0", tk.END)
        clean = _normalize_brief(text)
        if clean:
            self.entry.insert("1.0", clean)
        self.entry.mark_set(tk.INSERT, "end")
        self.entry.focus_set()

    def clear_entry(self):
        self.entry.delete("1.0", tk.END)
        self.entry.focus_set()

    def _bind_clipboard(self, widget: tk.Text) -> None:
        """Ctrl+V / Ctrl+C / Ctrl+X / Ctrl+A + قائمة يمين."""
        widget.bind("<Control-v>", self._on_paste)
        widget.bind("<Control-V>", self._on_paste)
        widget.bind("<Control-c>", self._on_copy)
        widget.bind("<Control-C>", self._on_copy)
        widget.bind("<Control-x>", self._on_cut)
        widget.bind("<Control-X>", self._on_cut)
        widget.bind("<Control-a>", self._on_select_all)
        widget.bind("<Control-A>", self._on_select_all)
        widget.bind("<Control-KeyPress>", self._on_ctrl_key)
        widget.bind("<Button-3>", self._show_entry_menu)

        self.entry_menu = tk.Menu(self.root, tearoff=0, bg="#2d2d2d", fg="white")
        self.entry_menu.add_command(label="لصق", command=self.paste_into_entry)
        self.entry_menu.add_command(label="نسخ", command=self.copy_from_entry)
        self.entry_menu.add_command(label="قص", command=self.cut_from_entry)
        self.entry_menu.add_separator()
        self.entry_menu.add_command(label="تحديد الكل", command=self.select_all_entry)
        self.entry_menu.add_command(label="مسح", command=self.clear_entry)

    def _on_ctrl_key(self, event):
        if event.keycode == 86:
            return self._on_paste(event)
        if event.keycode == 67:
            return self._on_copy(event)
        if event.keycode == 88:
            return self._on_cut(event)
        if event.keycode == 65:
            return self._on_select_all(event)

    def _clipboard_text(self) -> str:
        try:
            return self.root.clipboard_get()
        except tk.TclError:
            return ""

    def paste_into_entry(self):
        text = _normalize_brief(self._clipboard_text())
        if not text:
            return
        try:
            self.entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.entry.insert(tk.INSERT, text)
        self.entry.focus_set()

    def copy_from_entry(self):
        try:
            sel = self.entry.get("sel.first", "sel.last")
        except tk.TclError:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(sel)

    def cut_from_entry(self):
        self.copy_from_entry()
        try:
            self.entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

    def select_all_entry(self):
        self.entry.tag_add(tk.SEL, "1.0", "end-1c")
        self.entry.mark_set(tk.INSERT, "end-1c")
        self.entry.see(tk.INSERT)
        return "break"

    def _on_paste(self, event=None):
        self.paste_into_entry()
        return "break"

    def _on_copy(self, event=None):
        self.copy_from_entry()
        return "break"

    def _on_cut(self, event=None):
        self.cut_from_entry()
        return "break"

    def _on_select_all(self, event=None):
        return self.select_all_entry()

    def _show_entry_menu(self, event):
        self.entry.focus_set()
        try:
            self.entry_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.entry_menu.grab_release()
        return "break"

    def _tk_exception(self, exc, val, tb):
        err = "".join(traceback.format_exception(exc, val, tb))
        log_line(f"TK ERROR:\n{err}")
        try:
            self._append(f"ERROR (window stayed open): {val}\n")
            self._unlock()
        except Exception:
            pass

    def on_close(self):
        # أثناء العمل: ارفض الإغلاق بصمت (الوكيل كان يضغط X فيظهر الحوار)
        if self.busy:
            self._append("رفض الإغلاق — المهمة ما زالت تعمل.\n")
            log_line("close blocked while busy")
            return
        log_line("UI closed by user")
        self.root.destroy()

    def _append(self, text: str):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def on_voice(self):
        """بدء التسجيل — الكلام يظهر في الشات تدريجياً ثم نهائياً عند الإيقاف."""
        if self.busy:
            self._append("انتظر حتى ينتهي العمل الحالي.\n")
            return
        if self.listening:
            self.on_voice_stop()
            return
        try:
            import os
            from voice import voice_start

            secs = float(os.getenv("VOICE_SECONDS", "90"))
            voice_start(secs)
        except Exception as e:
            self._append(f"[صوت] فشل البدء: {e}\n")
            return

        self.listening = True
        self._voice_stopping = False
        self._voice_last_partial = ""
        self.status.config(text="يستمع... إرسال متاح الآن | إيقاف عند الانتهاء")
        self.btn_voice.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        # إبقاء إرسال مفعّلاً — يمكن إرسال النص الجزئي فوراً
        if not self.busy:
            self.btn.config(state=tk.NORMAL)
        try:
            interval = int(os.getenv("VOICE_PARTIAL_INTERVAL_MS", "1000"))
        except ValueError:
            interval = 1000
        interval = max(700, min(interval, 2500))
        self._append(f"[صوت] بدأ — تكلم؛ تحديث كل ~{interval // 1000 or 1}ث | إرسال جاهز\n")
        self.root.after(interval, self._voice_partial_tick)

    def _voice_partial_interval(self) -> int:
        try:
            interval = int(os.getenv("VOICE_PARTIAL_INTERVAL_MS", "1000"))
        except ValueError:
            interval = 1000
        return max(700, min(interval, 2500))

    def _voice_partial_tick(self):
        if not self.listening or self._voice_stopping:
            return
        if self._partial_busy:
            # لا نكدّس طلبات Google البطيئة
            self.root.after(800, self._voice_partial_tick)
            return

        self._partial_busy = True
        interval = self._voice_partial_interval()

        def worker():
            try:
                from voice import voice_partial_text

                partial = voice_partial_text()
                if partial and partial != self._voice_last_partial:
                    self._voice_last_partial = partial
                    self.msg_q.put("__VOICE_PARTIAL__:" + partial)
            except Exception as e:
                log_line(f"VOICE partial skip: {e}")
            finally:
                self._partial_busy = False
                if self.listening and not self._voice_stopping:
                    try:
                        self.root.after(interval, self._voice_partial_tick)
                    except Exception:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def on_voice_stop(self):
        """إيقاف التسجيل → نص نهائي في الشات والصندوق."""
        if not self.listening or self._voice_stopping:
            return
        self._voice_stopping = True
        self.btn_stop.config(state=tk.DISABLED)
        # أظهر الجزئي فوراً وفعّل إرسال — لا تنتظر التحويل النهائي
        if self._voice_last_partial:
            ready = normalize_speech_ar(self._voice_last_partial)
            self._set_entry_text(ready)
            self._append("[صوت] نص مبدئي جاهز — يمكنك إرسال الآن\n")
            if not self.busy:
                self.btn.config(state=tk.NORMAL)
            self.status.config(text="نص جاهز | يُحسَّن التحويل النهائي…")
        else:
            self.status.config(text="يحوّل الصوت إلى نص...")
        self._append("[صوت] جاري التحويل النهائي...\n")

        def worker():
            try:
                from voice import voice_stop_and_transcribe

                text = voice_stop_and_transcribe()
                self.msg_q.put("__VOICE_OK__:" + text)
            except Exception as e:
                try:
                    from voice import voice_cancel

                    voice_cancel()
                except Exception:
                    pass
                # إن فشل النهائي لكن عندنا جزئي — اعتبره كافياً
                if self._voice_last_partial:
                    self.msg_q.put("__VOICE_OK__:" + self._voice_last_partial)
                else:
                    self.msg_q.put(f"[صوت] فشل: {e}\n")
                    self.msg_q.put("__VOICE_DONE__")

        threading.Thread(target=worker, daemon=True).start()

    def _voice_done(self):
        self.listening = False
        self._voice_stopping = False
        self.status.config(text="Idle")
        try:
            self.btn_voice.config(state=tk.NORMAL, text="صوت")
            self.btn_stop.config(state=tk.DISABLED)
            if not self.busy:
                self.btn.config(state=tk.NORMAL)
        except Exception:
            pass

    def _drain_queue(self):
        while True:
            try:
                msg = self.msg_q.get_nowait()
            except queue.Empty:
                break
            if isinstance(msg, str) and msg.startswith("__VOICE_PARTIAL__:"):
                spoken = normalize_speech_ar(msg[len("__VOICE_PARTIAL__:") :])
                self._append(f"[صوت حي] {spoken}\n")
                self._set_entry_text(spoken)
                if not self.busy:
                    self.btn.config(state=tk.NORMAL)
                log_line(f"VOICE partial: {spoken}")
            elif isinstance(msg, str) and msg.startswith("__VOICE_OK__:"):
                spoken = normalize_speech_ar(msg[len("__VOICE_OK__:") :])
                self._append("[صوت] النهائي:\n")
                self._append(f"  {spoken}\n")
                self._append("— ظهر في الصندوق؛ اضغط إرسال إن جاهز —\n")
                self._set_entry_text(spoken)
                log_line(f"VOICE final: {spoken}")
                self._voice_done()
            elif msg == "__VOICE_DONE__":
                self._voice_done()
            elif isinstance(msg, str) and msg.startswith("__VOICE_TEXT__:"):
                spoken = normalize_speech_ar(msg[len("__VOICE_TEXT__:") :])
                self._append(f"[صوت] {spoken}\n")
                self._set_entry_text(spoken)
                self._voice_done()
            else:
                self._append(msg)
                log_line(str(msg).replace("\n", " | "))
        self.root.after(100, self._drain_queue)

    def on_go(self):
        self._append("زر ابدأ أُلغي. اكتب طلبك ثم إرسال.\n")

    def on_send(self):
        if self.busy:
            self._append("ما زال يعمل... انتظر Idle\n")
            return
        # إن كان التسجيل شغّالاً: أوقف وخذ النص الحالي فوراً
        if self.listening and not self._voice_stopping:
            task = self._get_entry_text() or self._voice_last_partial
            self.on_voice_stop()
            if not task.strip():
                self._append("انتظر ثانية للنص ثم أعد إرسال.\n")
                return
        else:
            task = self._get_entry_text()
        if not task:
            self._append("اكتب طلبك أولاً ثم إرسال.\n")
            return
        for prefix in ("You >", "you >", "أنت >", "انت >"):
            if task.startswith(prefix):
                task = task[len(prefix) :].strip()
        task = normalize_speech_ar(_normalize_brief(task))
        if not task:
            self._append("أعد كتابة الطلب.\n")
            return
        self.clear_entry()
        self._append("أنت >\n")
        for ln in task.split("\n"):
            self._append(f"  {ln}\n")
        self.busy = True
        self.status.config(text="ينفّذ على الشاشة — راقب الماوس...")
        self.btn.config(state=tk.DISABLED)
        try:
            self.btn_voice.config(state=tk.DISABLED)
        except Exception:
            pass
        log_line(f"TASK: {task}")

        def worker():
            try:
                # محادثة قصيرة فقط؛ أي توجيه عملي/طويل → تنفيذ حقيقي
                if _is_chat_only(task) and len(task) < 80:
                    self.msg_q.put("[محادثة]\n")
                    reply = chat_reply(task)
                    self.msg_q.put(f"الوكيل > {reply}\n" + "-" * 40 + "\n")
                elif looks_like_report(task):
                    self.msg_q.put("[تقرير شاشة]\n")
                    reply = report_screen_for_cursor(task)
                    self.msg_q.put(f"الوكيل > {reply}\n" + "-" * 40 + "\n")
                else:
                    # مهام عملية → مدير المهام. الماوس فقط عند طلب صريح.
                    if _wants_mouse_only(task):
                        self.msg_q.put("[ماوس] طلب تحريك مباشر...\n")
                        os.environ["AGENT_QUIET"] = "1"
                        reply = run_smart_mission(task)
                    else:
                        self.msg_q.put("[مدير المهام] خطة + تحقق + ملفات تعاون Cursor...\n")
                        reply = run_managed_task(task)
                    self.msg_q.put(f"الوكيل > {reply}\n" + "-" * 40 + "\n")
            except Exception as e:
                err = traceback.format_exc()
                log_line(f"WORKER ERROR: {e}\n{err}")
                self.msg_q.put(f"ERROR: {e}\n")
            finally:
                try:
                    self.root.after(0, self._unlock)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=False).start()

    def _unlock(self):
        self.busy = False
        self.status.config(text="Idle")
        self.btn.config(state=tk.NORMAL)
        try:
            if not self.listening:
                self.btn_voice.config(state=tk.NORMAL, text="صوت")
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    try:
        ChatOverlay().run()
    except Exception as e:
        log_line(f"FATAL: {e}\n{traceback.format_exc()}")
        try:
            import tkinter.messagebox as mb

            mb.showerror("Computer Use Chat", f"Crash: {e}\nSee agent_run.log")
        except Exception:
            pass
        sys.exit(1)
