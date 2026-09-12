"""واجهة منظومة موحّدة: COS + صوت + تحكم هاتف."""
from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# حمّل .env قبل وحدات الصوت حتى تُقرأ إعدادات السرعة/السمع
from cos import config  # noqa: F401

import tkinter as tk
from tkinter import font as tkfont

from cos.core.router import BrainRouter, Route
from cos.remote import hub
from cos.runtime import RUNTIME
from cos.voice import VoiceConversation, cancel_listening
from cos.voice.speak import set_enabled as tts_set_enabled
from cos.voice.speak import speak
from cos.voice.speak import stop_speaking
from cos.brain.chat import (
    brief_result,
    should_execute,
    smart_chat,
    voice_chat,
    wants_computer_action,
)
from cos.brain.clarify import decide as clarify_decide
from cos.brain.session import SESSION


class CosUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("COS Personal — Unified")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0f0f0f")
        w, h = 520, 660
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+12+{max(40, sh - h - 60)}")
        self.root.minsize(440, 520)

        self.ui_font = tkfont.Font(family="Tahoma", size=11)
        self.small = tkfont.Font(family="Tahoma", size=9)
        self.btn_font = tkfont.Font(family="Tahoma", size=10)

        self.router = BrainRouter()
        hub._router = self.router  # نفس الموجّه للهاتف
        self.mode: Route | None = None
        self._listening = False
        self._voice_conv: VoiceConversation | None = None
        self._voice_history: list[tuple[str, str]] = []
        self.tts_on = True
        tts_set_enabled(True)

        self.status = tk.Label(
            self.root,
            text="جاهز · الوضع: تلقائي · صوت: تشغيل",
            bg="#0f0f0f",
            fg="#6bcf7f",
            anchor="w",
            font=self.small,
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 8))

        modes = tk.Frame(self.root, bg="#0f0f0f")
        modes.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 2))
        modes2 = tk.Frame(self.root, bg="#0f0f0f")
        modes2.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 4))
        for label, route in (
            ("تلقائي", None),
            ("COS", Route.COS),
            ("برمجة", Route.CODING),
            ("كوانت", Route.QUANT),
            ("تداول", Route.TRADING),
        ):
            tk.Button(
                modes,
                text=label,
                command=lambda r=route: self._set_mode(r),
                bg="#263238",
                fg="white",
                relief=tk.FLAT,
                font=self.small,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=(0, 3))
        for label, route in (
            ("بحث", Route.RESEARCH),
            ("ذاكرة", Route.MEMORY),
            ("مشرف", Route.SUPERVISOR),
            ("رؤية", Route.CLAUDE),
        ):
            tk.Button(
                modes2,
                text=label,
                command=lambda r=route: self._set_mode(r),
                bg="#263238",
                fg="white",
                relief=tk.FLAT,
                font=self.small,
                padx=6,
                pady=2,
            ).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(
            modes2,
            text="تعلّم",
            command=self.show_learning_report,
            bg="#6a1b9a",
            fg="white",
            relief=tk.FLAT,
            font=self.small,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(
            modes2,
            text="لوحة",
            command=self.open_dashboard,
            bg="#00695c",
            fg="white",
            relief=tk.FLAT,
            font=self.small,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(
            modes2,
            text="هاتف",
            command=self.open_remote,
            bg="#ef6c00",
            fg="white",
            relief=tk.FLAT,
            font=self.small,
            padx=6,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 3))

        row = tk.Frame(self.root, bg="#0f0f0f")
        row.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 4))

        tk.Button(
            row,
            text="إيقاف",
            command=self.on_kill,
            bg="#c62828",
            fg="white",
            relief=tk.FLAT,
            font=self.btn_font,
            padx=10,
            pady=5,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            row,
            text="مسح",
            command=self.clear_entry,
            bg="#2a2a2a",
            fg="white",
            relief=tk.FLAT,
            font=self.btn_font,
            padx=10,
            pady=5,
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.btn_voice = tk.Button(
            row,
            text="🎧 محادثة",
            command=self.toggle_voice,
            bg="#7b1fa2",
            fg="white",
            relief=tk.FLAT,
            font=self.btn_font,
            padx=10,
            pady=5,
        )
        self.btn_voice.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_tts = tk.Button(
            row,
            text="🔊 نطق",
            command=self.toggle_tts,
            bg="#00695c",
            fg="white",
            relief=tk.FLAT,
            font=self.btn_font,
            padx=10,
            pady=5,
        )
        self.btn_tts.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_send = tk.Button(
            row,
            text="إرسال",
            command=self.on_send,
            bg="#1e88e5",
            fg="white",
            relief=tk.FLAT,
            font=self.btn_font,
            padx=14,
            pady=5,
        )
        self.btn_send.pack(side=tk.LEFT)

        entry_wrap = tk.Frame(self.root, bg="#2a2a2a", padx=1, pady=1)
        entry_wrap.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(4, 6))
        self.entry = tk.Text(
            entry_wrap,
            height=3,
            bg="#1a1a1a",
            fg="#ffffff",
            insertbackground="white",
            wrap=tk.WORD,
            font=self.ui_font,
            padx=10,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry.pack(fill=tk.BOTH)
        self.entry.bind("<Control-Return>", lambda e: self.on_send())
        self.entry.bind("<Return>", self._enter_send)

        outer = tk.Frame(self.root, bg="#0f0f0f")
        outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(outer, bg="#0f0f0f", highlightthickness=0)
        self.scroll = tk.Scrollbar(outer, orient=tk.VERTICAL, command=self.canvas.yview)
        self.chat = tk.Frame(self.canvas, bg="#0f0f0f")
        self.chat.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._chat_win = self.canvas.create_window((0, 0), window=self.chat, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Configure>", self._on_canvas_cfg)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        self._remote_started = False
        self._hub_seen_ids: set[int] = set()
        welcome = (
            "منظومة v0.8 — محادثة صوتية سلسة.\n"
            "🎧 محادثة: تكلم ثم اصمت قليلاً وسأرد فوراً — بدون زر لكل جملة.\n"
            "⏹ إيقاف الجلسة يوقف المحادثة كلها فقط.\n"
            "هاتف: زر «هاتف» → لوحة الجوال على 8787"
        )
        self._add_assistant(welcome)
        speak("مرحبا، أنا COS. اضغط محادثة، تكلم ثم اسكت شوي وأرد عليك.")
        RUNTIME.on_log = None
        self.root.after(1500, self._sync_hub)

    def _render_bubble(self, role: str, text: str, *, prefix: str = "") -> None:
        if role == "user":
            wrap = tk.Frame(self.chat, bg="#0f0f0f")
            wrap.pack(fill=tk.X, pady=(8, 4), padx=4)
            bubble = tk.Frame(wrap, bg="#1e3a5f", padx=12, pady=8)
            bubble.pack(anchor="e", padx=(40, 4))
            tk.Label(
                bubble,
                text=f"{prefix}{text}",
                bg="#1e3a5f",
                fg="#ffffff",
                justify=tk.RIGHT,
                wraplength=340,
                font=self.ui_font,
            ).pack(anchor="e")
        else:
            wrap = tk.Frame(self.chat, bg="#0f0f0f")
            wrap.pack(fill=tk.X, pady=(2, 8), padx=4)
            tk.Label(
                wrap,
                text=f"{prefix}{text}",
                bg="#0f0f0f",
                fg="#e8e8e8",
                justify=tk.RIGHT,
                wraplength=420,
                font=self.ui_font,
                anchor="e",
            ).pack(anchor="e", padx=(4, 8))
        self._scroll_end()

    def _sync_hub(self) -> None:
        """اعرض رسائل الهاتف في نافذة اللابتوب دون تكرار."""
        try:
            for m in hub.snapshot().get("messages") or []:
                mid = m.get("id")
                if mid is None or mid in self._hub_seen_ids:
                    continue
                self._hub_seen_ids.add(mid)
                if m.get("source") != "phone":
                    continue
                role = m.get("role") or "assistant"
                text = (m.get("text") or "").strip()
                if not text:
                    continue
                prefix = "📱 " if role == "user" else ""
                self._render_bubble(role, text, prefix=prefix)
                if role == "assistant" and self.tts_on:
                    speak(text)
        except Exception:
            pass
        self.root.after(2000, self._sync_hub)

    def open_remote(self) -> None:
        if self._remote_started:
            from ui.remote_server import local_ip

            ip = local_ip()
            self._add_assistant(
                f"لوحة الهاتف تعمل مسبقاً.\n"
                f"من هاتفك (نفس الواي فاي):\nhttp://{ip}:8787"
            )
            return

        def serve() -> None:
            from http.server import ThreadingHTTPServer

            from ui.remote_server import Handler, local_ip

            ip = local_ip()
            server = ThreadingHTTPServer(("0.0.0.0", 8787), Handler)
            self._remote_started = True

            def ready():
                self._add_assistant(
                    "لوحة الهاتف جاهزة (نفس جلسة الشات).\n"
                    f"على اللابتوب: http://127.0.0.1:8787\n"
                    f"على الهاتف: http://{ip}:8787\n"
                    "خارج البيت: Tailscale أو نفق آمن (ngrok)."
                )
                speak("لوحة الهاتف جاهزة")

            self.root.after(0, ready)
            try:
                server.serve_forever()
            except Exception as e:
                self._remote_started = False
                self.root.after(0, lambda: self._add_assistant(f"توقف خادم الهاتف: {e}"))

        threading.Thread(target=serve, daemon=True, name="cos-remote").start()

    def open_dashboard(self) -> None:
        import subprocess

        subprocess.Popen(
            [sys.executable, str(ROOT / "ui" / "dashboard.py")],
            cwd=str(ROOT),
            env={**dict(**__import__("os").environ), "PYTHONPATH": str(ROOT)},
        )
        self._add_assistant("فُتحت لوحة المراقبة.")

    def show_learning_report(self) -> None:
        self._dispatch("ماذا تعلمت هذا الأسبوع")

    def toggle_tts(self) -> None:
        self.tts_on = not self.tts_on
        tts_set_enabled(self.tts_on)
        self.btn_tts.config(bg="#00695c" if self.tts_on else "#424242")
        if not self.tts_on:
            stop_speaking()
            self._add_assistant("النطق متوقف")
            return
        self._add_assistant("النطق مفعّل — أختبر الصوت الآن…")

        def worker():
            from cos.voice.speak import last_error, speak as speak_now

            # أوقف مراقبة المقاطعة مؤقتاً عبر نطق مباشر
            ok = speak_now("مرحبا، أنا COS. إذا سمعتني فالصوت يعمل.", wait=True)
            msg = (
                "الصوت يعمل."
                if ok
                else f"تعذر النطق: {last_error() or 'تحقق من السماعات ومستوى الصوت'}"
            )
            self.root.after(0, lambda: self._add_assistant(msg))

        threading.Thread(target=worker, daemon=True).start()

    def toggle_voice(self) -> None:
        """محادثة صوتية مستمرة مثل ChatGPT Voice — بدون ضغط لكل جملة."""
        if self._voice_conv and self._voice_conv.active:
            self._voice_conv.stop()
            self._voice_conv = None
            self._listening = False
            stop_speaking()
            self.btn_voice.config(text="🎧 محادثة", bg="#7b1fa2", state=tk.NORMAL)
            self._add_assistant("أنهيت المحادثة الصوتية.")
            self._refresh_status()
            return

        try:
            cancel_listening()
        except Exception:
            pass
        stop_speaking()
        self.tts_on = True
        tts_set_enabled(True)
        self.btn_tts.config(bg="#00695c")

        def on_status(msg: str) -> None:
            def ui() -> None:
                if msg == "__ENDED__":
                    self._listening = False
                    self._voice_conv = None
                    self.btn_voice.config(text="🎧 محادثة", bg="#7b1fa2", state=tk.NORMAL)
                    self._refresh_status()
                    return
                self.status.config(text=msg, fg="#ffd54f")

            self.root.after(0, ui)

        def on_heard(text: str) -> None:
            def ui() -> None:
                self._add_user(text)

            self.root.after(0, ui)

        def on_spoken(text: str) -> None:
            def ui() -> None:
                # دائماً نعرض النص في الشات؛ النطق يتم من حلقة المحادثة
                self._add_assistant(text, speak_it=False)
                self._voice_history.append(("assistant", text))
                if len(self._voice_history) > 4:
                    self._voice_history = self._voice_history[-4:]
                self.root.update_idletasks()

            self.root.after(0, ui)

        def on_reply(text: str) -> str:
            self._voice_history.append(("user", text))
            if len(self._voice_history) > 4:
                self._voice_history = self._voice_history[-4:]

            mode, payload = self._resolve_turn(text, voice=True)
            if mode in ("clarify", "ask", "chat"):
                return payload

            # تنفيذ بعد التأكيد
            self.root.after(
                0,
                lambda: self.status.config(
                    text="أنفّذ الأمر على الجهاز…", fg="#ffd54f"
                ),
            )
            full = self._run_on_desktop(payload)

            def show_full() -> None:
                self._add_assistant(full, speak_it=False)

            self.root.after(0, show_full)
            return brief_result(full)

        self._voice_conv = VoiceConversation(
            on_heard=on_heard,
            on_reply=on_reply,
            on_status=on_status,
            on_spoken=on_spoken,
        )
        self._listening = True
        self.btn_voice.config(text="⏹ إيقاف الجلسة", bg="#c62828")
        self.status.config(text="محادثة نشطة — تكلم ثم اصمت وسأرد", fg="#ffd54f")
        self._add_assistant(
            "بدأت المحادثة: تكلم بحرية، ولما تسكت قليلاً أرد تلقائياً. "
            "لا تضغط الزر الأحمر إلا لإيقاف الجلسة كلها."
        )
        self._voice_conv.start()

    def _release_desktop(self) -> None:
        """أنزل نافذة COS حتى لا تمنع الماوس عن باقي الشاشة."""
        try:
            self.root.attributes("-topmost", False)
            self.root.lower()
            self.root.update_idletasks()
        except Exception:
            pass

    def _restore_ui(self) -> None:
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.root.update_idletasks()
        except Exception:
            pass

    def _run_on_desktop(self, goal: str) -> str:
        """نفّذ على سطح المكتب مع تحرير الماوس من نافذة COS."""
        import time

        ready = threading.Event()

        def prepare() -> None:
            self._release_desktop()
            self.status.config(text="أنفّذ على الشاشة بالماوس…", fg="#ffd54f")
            ready.set()

        self.root.after(0, prepare)
        ready.wait(timeout=2.0)
        time.sleep(0.45)
        try:
            SESSION.mark_executing(goal)
            out = (self.router.run(goal) or "").strip() or "تم."
            SESSION.mark_done(out)
            SESSION.add_turn("assistant", out[:400])
            return out
        except Exception as e:
            SESSION.mark_failed(str(e))
            raise
        finally:
            self.root.after(0, self._restore_ui)

    def _intent_kind(self, text: str) -> str:
        try:
            from cos.brain.intent import parse_intent

            return parse_intent(text, use_llm=False).kind
        except Exception:
            return ""

    def _resolve_turn(self, text: str, *, voice: bool = False) -> tuple[str, str]:
        """
        حل جولة مستخدم: (mode, payload)
        mode: clarify|ask|chat|execute
        """
        try:
            from cos.brain.intent import looks_gibberish

            if looks_gibberish(text):
                return "ask", "ما فهمت الكلام. أعد الجملة بوضوح."
        except Exception:
            pass

        needs = should_execute(text) or wants_computer_action(text)
        # إن كان هناك pending تأكيد، اعتبر الجولة جزءاً من مسار التنفيذ
        if SESSION.get_pending() is not None:
            needs = True

        kind = self._intent_kind(text)
        try:
            from cos.brain.clarify import is_mouse_urgency, is_urgency_confirm
            from cos.core.task_manager import looks_like_managed_task

            if looks_like_managed_task(text):
                # مهام مركبة → تنفيذ مباشر عبر مدير المهام (بدون توضيح)
                return "execute", text
            if is_mouse_urgency(text):
                kind = "mouse"
                needs = True
            elif is_urgency_confirm(text):
                needs = True
        except Exception:
            pass
        # التنفيذ المباشر افتراضياً — لا تقف عند تقرير توضيحي
        clarify_on = config.CLARIFY_BEFORE_EXECUTE and kind not in ("mouse",)
        decision = clarify_decide(
            text,
            session=SESSION,
            needs_execute=needs,
            kind=kind,
            clarify_enabled=clarify_on,
        )
        if decision.action in ("clarify", "ask"):
            return decision.action, decision.message
        if decision.action == "execute":
            return "execute", decision.goal or text
        # chat
        if voice:
            hist = "\n".join(f"{r}: {t}" for r, t in self._voice_history[:-1])
            return "chat", voice_chat(text, history=hist)
        return "chat", smart_chat(text)

    def _mode_label(self) -> str:
        if self.mode is None:
            return "تلقائي"
        return {
            Route.COS: "COS",
            Route.CODING: "برمجة",
            Route.QUANT: "كوانت",
            Route.TRADING: "تداول",
            Route.RESEARCH: "بحث",
            Route.BUSINESS: "أعمال",
            Route.MARKETING: "تسويق",
            Route.MEMORY: "ذاكرة",
            Route.SUPERVISOR: "مشرف",
            Route.CLAUDE: "رؤية",
        }.get(self.mode, str(self.mode))

    def _refresh_status(self) -> None:
        tts = "تشغيل" if self.tts_on else "إيقاف"
        self.status.config(
            text=f"جاهز · الوضع: {self._mode_label()} · صوت: {tts}",
            fg="#6bcf7f",
        )

    def _set_mode(self, route: Route | None) -> None:
        self.mode = route
        self.router.set_force(route)
        self._refresh_status()
        self._add_assistant(f"تم ضبط الوضع: {self._mode_label()}")

    def _on_canvas_cfg(self, event):
        self.canvas.itemconfig(self._chat_win, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _enter_send(self, event):
        if event.state & 0x4:
            return None
        self.on_send()
        return "break"

    def _scroll_end(self):
        self.root.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _scrub_chat_text(self, text: str, *, role: str) -> str | None:
        """لا تعرض رموزاً عشوائية في الشات أبداً."""
        t = (text or "").strip()
        if not t:
            return None
        try:
            from cos.brain.intent import looks_gibberish
            from cos.brain.chat import _for_speech

            if looks_gibberish(t):
                if role == "user":
                    return None  # لا تعرض التقاطاً تالفاً
                return "ما فهمت جيداً. أعد بجملة عربية واضحة."
            if role == "assistant":
                return _for_speech(t)
        except Exception:
            pass
        ar = sum(1 for c in t if "\u0600" <= c <= "\u06FF")
        if role == "user" and ar < 2 and len(t) >= 8:
            return None
        return t

    def _add_user(self, text: str) -> None:
        text = self._scrub_chat_text(text, role="user")
        if not text:
            return
        wrap = tk.Frame(self.chat, bg="#0f0f0f")
        wrap.pack(fill=tk.X, pady=(8, 4), padx=4)
        bubble = tk.Frame(wrap, bg="#1e3a5f", padx=12, pady=8)
        bubble.pack(anchor="e", padx=(40, 4))
        tk.Label(
            bubble,
            text=text,
            bg="#1e3a5f",
            fg="#ffffff",
            justify=tk.RIGHT,
            wraplength=340,
            font=self.ui_font,
        ).pack(anchor="e")
        mid = hub.push("user", text)
        self._hub_seen_ids.add(mid)
        self._scroll_end()

    def _add_assistant(self, text: str, *, speak_it: bool = False) -> None:
        text = self._scrub_chat_text(text, role="assistant")
        if not text:
            return
        wrap = tk.Frame(self.chat, bg="#0f0f0f")
        wrap.pack(fill=tk.X, pady=(2, 8), padx=4)
        tk.Label(
            wrap,
            text=text,
            bg="#0f0f0f",
            fg="#e8e8e8",
            justify=tk.RIGHT,
            wraplength=420,
            font=self.ui_font,
            anchor="e",
        ).pack(anchor="e", padx=(4, 8))
        mid = hub.push("assistant", text)
        self._hub_seen_ids.add(mid)
        self._scroll_end()
        if speak_it and self.tts_on:
            speak(text)

    def clear_entry(self) -> None:
        self.entry.delete("1.0", tk.END)
        self.entry.focus_set()

    def on_kill(self) -> None:
        RUNTIME.kill()
        if self._voice_conv and self._voice_conv.active:
            self._voice_conv.stop()
            self._voice_conv = None
        try:
            cancel_listening()
        except Exception:
            pass
        stop_speaking()
        self._listening = False
        self.btn_voice.config(text="🎧 محادثة", bg="#7b1fa2")
        self.status.config(text="توقف", fg="#ff8a80")
        self._add_assistant("توقفت.", speak_it=True)

    def _dispatch(self, goal: str) -> None:
        if RUNTIME.busy:
            self._add_assistant("ما زلت أنفّذ. اضغط إيقاف إن أردت.", speak_it=True)
            return
        self._add_user(goal)
        self.status.config(text=f"يعمل... ({self._mode_label()})", fg="#ffd54f")
        self.btn_send.config(state=tk.DISABLED)

        def worker():
            try:
                mode, payload = self._resolve_turn(goal, voice=False)
                if mode in ("clarify", "ask", "chat"):
                    text = payload.strip() or "تم."

                    def done_msg():
                        self._add_assistant(text, speak_it=True)

                    self.root.after(0, done_msg)
                    return

                out = self._run_on_desktop(payload)
                text = out.strip() or "تم."

                def done():
                    self._add_assistant(text, speak_it=True)

                self.root.after(0, done)
            except Exception as e:
                self.root.after(
                    0, lambda: self._add_assistant(f"حدث خطأ: {e}", speak_it=True)
                )
                traceback.print_exc()
            finally:
                self.root.after(0, self._unlock)

        threading.Thread(target=worker, daemon=True).start()

    def on_send(self) -> None:
        goal = self.entry.get("1.0", "end-1c").strip()
        if not goal:
            return
        self.clear_entry()
        self._dispatch(goal)

    def _unlock(self) -> None:
        self.btn_send.config(state=tk.NORMAL)
        if RUNTIME.killed:
            self.status.config(text=f"توقف — جاهز ({self._mode_label()})", fg="#ff8a80")
            RUNTIME.reset_kill()
        else:
            self._refresh_status()

    def run(self) -> None:
        self.entry.focus_set()
        self.root.mainloop()


def main() -> None:
    CosUI().run()


if __name__ == "__main__":
    main()
