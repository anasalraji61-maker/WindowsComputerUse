"""محادثة صوتية سلسة مثل ChatGPT Voice: يرد بعد صمتك تلقائياً دون زر إنهاء."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

from cos.voice.speak import (
    last_error,
    set_enabled,
    speak,
    stop_speaking,
    was_interrupted,
)


OnHeard = Callable[[str], None]
OnStatus = Callable[[str], None]
OnReply = Callable[[str], str]

# المقاطعة أثناء النطق تحتاج سماعات رأس؛ الافتراضي Off لتجنب صدى السماعات
_BARGE_IN = (os.getenv("COS_VOICE_BARGE_IN") or "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_INCOMPLETE_ENDS = (
    "و",
    "في",
    "من",
    "على",
    "إلى",
    "الى",
    "أن",
    "ان",
    "ثم",
    "أو",
    "او",
    "يعني",
    "عشان",
    "علشان",
)


def instant_voice_reply(text: str) -> Optional[str]:
    """رد فوري للتحية فقط — لا تبلع أوامر التنفيذ."""
    try:
        from cos.brain.chat import is_pure_chat
        from cos.brain import chat as chat_mod
    except Exception:
        return None
    if not is_pure_chat(text):
        return None
    return chat_mod._instant(text) or None


class VoiceConversation:
    """حلقة استماع → صمت → رد → استماع، بدون ضغط زر لكل جملة."""

    def __init__(
        self,
        *,
        on_heard: OnHeard,
        on_reply: OnReply,
        on_status: Optional[OnStatus] = None,
        on_spoken: Optional[OnHeard] = None,
        language: str = "ar-SA",
    ) -> None:
        self.on_heard = on_heard
        self.on_reply = on_reply
        self.on_status = on_status or (lambda _s: None)
        self.on_spoken = on_spoken or (lambda _t: None)
        self.language = language
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        if self._active:
            return
        self._stop.clear()
        self._active = True
        set_enabled(True)
        try:
            from cos.voice.stt import warmup_whisper_async

            warmup_whisper_async()
        except Exception:
            pass
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="cos-voice-chat"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        stop_speaking()
        self._active = False
        self.on_status("توقفت المحادثة الصوتية")

    def _loop(self) -> None:
        empty_streak = 0
        try:
            self.on_status("المحادثة جاهزة — تكلم ثم اصمت قليلاً")
            greeting = "جاهزة. تكلم."
            self.on_spoken(greeting)
            self._speak_and_settle(greeting)

            while not self._stop.is_set():
                self.on_status("أسمعك… أكمل كلامك")
                try:
                    text = listen_full_utterance(stop_event=self._stop)
                except Exception as e:
                    if self._stop.is_set():
                        break
                    self.on_status(f"خطأ مايك: {e}")
                    time.sleep(0.4)
                    continue

                if self._stop.is_set():
                    break
                if not text:
                    empty_streak += 1
                    if empty_streak >= 3:
                        self.on_status("ما زلت أسمعك — تكلم بوضوح")
                        empty_streak = 0
                    else:
                        self.on_status("لم ألتقط جملة واضحة — أعد")
                    continue
                empty_streak = 0

                try:
                    from cos.voice.dialects import normalize_dialect

                    text = normalize_dialect(text)
                except Exception:
                    pass

                try:
                    from cos.brain.intent import looks_gibberish

                    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
                    # ارفض فقط إن لم يوجد عربي تقريباً
                    if looks_gibberish(text) or (ar < 1 and len(text) >= 5):
                        self.on_status("ما التقطت كلاماً عربياً واضحاً — أقرب للمايك أو استخدم سماعات")
                        continue
                except Exception:
                    ar = sum(1 for c in (text or "") if "\u0600" <= c <= "\u06FF")
                    if ar < 2:
                        self.on_status("ما التقطت كلاماً واضحاً — أعد")
                        continue

                low = text.replace(" ", "")
                if any(
                    x in low
                    for x in (
                        "انهيالمحادثة",
                        "إيقافالمحادثة",
                        "وقفالمحادثة",
                        "انهاءالجلسة",
                        "إيقافالجلسة",
                        "باي",
                        "معالسلامة",
                    )
                ):
                    self.on_heard(text)
                    bye = "إلى اللقاء."
                    self.on_spoken(bye)
                    speak(bye, wait=True)
                    break

                self.on_heard(text)
                try:
                    from cos.voice.stt import last_backend

                    self.on_status(f"سمعت: {text[:40]}… ({last_backend()})")
                except Exception:
                    self.on_status(f"سمعت: {text[:48]}")
                instant = instant_voice_reply(text)
                if instant:
                    reply = instant
                    self.on_status("أرد…")
                else:
                    self.on_status("أفكر…")
                    try:
                        reply = (self.on_reply(text) or "").strip() or "تمام."
                    except Exception as e:
                        reply = f"حصل خطأ: {e}"

                try:
                    from cos.brain.intent import looks_gibberish
                    from cos.brain.chat import _for_speech

                    reply = _for_speech(reply)
                    if looks_gibberish(reply):
                        reply = "ما فهمت جيداً. أعد بجملة عربية واضحة."
                except Exception:
                    pass

                if self._stop.is_set():
                    break

                self.on_spoken(reply)
                self.on_status("أتكلم…")
                spoken = reply if len(reply) <= 140 else (reply[:140].rsplit(" ", 1)[0] + "…")
                if _BARGE_IN:
                    barged = self._speak_interruptible(spoken)
                    if barged:
                        # المستخدم قاطع — عالج جملته في الدورة التالية مباشرة
                        self.on_status("سمعْت مقاطعتك")
                        self.on_heard(barged)
                        try:
                            reply2 = (self.on_reply(barged) or "").strip() or "تمام."
                        except Exception as e:
                            reply2 = f"حصل خطأ: {e}"
                        if self._stop.is_set():
                            break
                        self.on_spoken(reply2)
                        self._speak_and_settle(
                            reply2 if len(reply2) <= 220 else reply2[:220].rsplit(" ", 1)[0] + "…"
                        )
                        continue
                else:
                    self._speak_and_settle(spoken)
        finally:
            self._active = False
            self.on_status("انتهت المحادثة الصوتية")
            try:
                self.on_status("__ENDED__")
            except Exception:
                pass

    def _speak_and_settle(self, text: str) -> None:
        """انطق ثم انتظر صدى السماعات يهدأ قبل الاستماع."""
        if not text.strip():
            return
        ok = speak(text, wait=True)
        if not ok and last_error() and not was_interrupted():
            self.on_status(f"تعذر النطق: {last_error()}")
        # تهدئة قصيرة حتى لا يُحسب صوت الرد ككلام منك
        time.sleep(0.18)

    def _speak_interruptible(self, text: str) -> Optional[str]:
        if not text.strip():
            return None
        barged: dict[str, Optional[str]] = {"text": None}
        speak_done = threading.Event()

        def do_speak() -> None:
            try:
                ok = speak(text, wait=True)
                if not ok and last_error() and not was_interrupted():
                    self.on_status(f"تعذر النطق: {last_error()}")
            finally:
                speak_done.set()

        def do_barge() -> None:
            time.sleep(1.1)
            if self._stop.is_set() or speak_done.is_set():
                return
            if not wait_for_barge_in(
                stop_event=self._stop,
                speak_done=speak_done,
                sustain_sec=0.55,
            ):
                return
            stop_speaking()
            self.on_status("مقاطعة…")
            try:
                heard = listen_full_utterance(
                    stop_event=self._stop,
                    already_speaking=True,
                    start_timeout=3.0,
                )
            except Exception:
                heard = ""
            if heard:
                barged["text"] = heard

        t_speak = threading.Thread(target=do_speak, daemon=True, name="cos-speak")
        t_barge = threading.Thread(target=do_barge, daemon=True, name="cos-barge")
        t_speak.start()
        t_barge.start()
        t_speak.join(timeout=120)
        t_barge.join(timeout=14)
        time.sleep(0.25)
        return barged["text"]


def looks_incomplete(text: str) -> bool:
    """ناقص فقط إن انتهى برابط واضح — لا تؤخر الجمل القصيرة المكتملة."""
    t = (text or "").strip()
    if not t:
        return True
    if t.endswith((".", "!", "؟", "?")):
        return False
    words = [w for w in t.replace("؟", " ").replace("?", " ").split() if w]
    if not words:
        return True
    last = words[-1].strip(".,!؟?")
    if len(words) <= 8 and last not in _INCOMPLETE_ENDS:
        return False
    return last in _INCOMPLETE_ENDS


def listen_full_utterance(
    *,
    stop_event: Optional[threading.Event] = None,
    already_speaking: bool = False,
    start_timeout: float = 20.0,
) -> str:
    stop_event = stop_event or threading.Event()
    silence = float(os.getenv("COS_VOICE_SILENCE_SEC") or "0.55")
    early = float(os.getenv("COS_VOICE_EARLY_SILENCE") or "0.7")
    first = listen_until_silence(
        stop_event=stop_event,
        # صمت أقصر = رد أسرع
        silence_sec=max(0.4, silence),
        grace_sec=0.2,
        max_sec=22.0,
        min_speech_sec=0.28,
        start_timeout=start_timeout,
        already_speaking=already_speaking,
        early_silence_sec=max(0.45, early),
        early_until_sec=1.4,
    )
    if not first:
        return ""
    # لا تؤخر الجمل العربية الواضحة بانتظار تكملة
    if not looks_incomplete(first) or stop_event.is_set():
        return first
    words = [w for w in first.split() if w]
    if len(words) >= 3:
        return first

    more = listen_until_silence(
        stop_event=stop_event,
        silence_sec=0.5,
        grace_sec=0.18,
        max_sec=8.0,
        min_speech_sec=0.22,
        start_timeout=1.2,
        already_speaking=False,
        early_silence_sec=0.6,
        early_until_sec=1.0,
    )
    if not more:
        return first
    return f"{first} {more}".strip()


def wait_for_barge_in(
    *,
    stop_event: threading.Event,
    speak_done: threading.Event,
    sustain_sec: float = 0.55,
    sample_rate: int = 16000,
) -> bool:
    """رصد كلام المستخدم أثناء النطق — عتبة عالية لتجنب صدى السماعات."""
    import numpy as np
    import sounddevice as sd

    block = int(sample_rate * 0.05)
    need = max(4, int(sustain_sec / 0.05))
    hit = 0
    noise: list[float] = []

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=block,
        ) as stream:
            while not stop_event.is_set() and not speak_done.is_set():
                data, _ = stream.read(block)
                mono = data.reshape(-1).astype(np.float32)
                energy = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0
                noise.append(energy)
                if len(noise) < 14:
                    continue
                base = float(np.median(noise[-30:]))
                thr = max(1400.0, base * 5.0 + 700.0)
                if energy >= thr:
                    hit += 1
                    if hit >= need:
                        return True
                else:
                    hit = 0
    except Exception:
        return False
    return False


def listen_until_silence(
    *,
    sample_rate: int = 16000,
    silence_sec: float = 0.8,
    grace_sec: float = 0.35,
    max_sec: float = 28.0,
    min_speech_sec: float = 0.35,
    start_timeout: float = 20.0,
    stop_event: Optional[threading.Event] = None,
    already_speaking: bool = False,
    early_silence_sec: float = 1.15,
    early_until_sec: float = 1.8,
) -> str:
    """
    استمع حتى ينتهي كلام المستخدم بصمت كافٍ ثم حوّل إلى نص.
    في بداية الجملة نطلب صمتاً أطول حتى لا نقطعه على سكتة قصيرة.
    """
    import numpy as np
    import sounddevice as sd

    stop_event = stop_event or threading.Event()
    block = int(sample_rate * 0.05)
    chunks: list = []
    speech_started = already_speaking
    silent_blocks = 0
    speech_blocks = 1 if already_speaking else 0
    grace_blocks = max(1, int(grace_sec / 0.05))
    max_blocks = int(max_sec / 0.05)
    start_deadline = time.time() + start_timeout
    noise_samples: list[float] = []
    threshold = 180.0
    sens = float(os.getenv("COS_MIC_SENSITIVITY") or "1.35")
    sens = max(1.0, min(2.5, sens))
    in_grace = False
    grace_left = 0
    t0 = time.time()

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=block,
    ) as stream:
        while not stop_event.is_set():
            data, _ = stream.read(block)
            mono = data.reshape(-1).astype(np.float32)
            energy = float(np.sqrt(np.mean(mono * mono))) if mono.size else 0.0

            if not speech_started:
                noise_samples.append(energy)
                if len(noise_samples) >= 3:
                    base = float(np.median(noise_samples[-20:]))
                    # حساسية أعلى = عتبة أقل = يسمع أسهل
                    threshold = max(55.0, (base * 1.55 + 28.0) / sens)
                if energy >= threshold:
                    speech_started = True
                    speech_blocks = 1
                    silent_blocks = 0
                    chunks.append(data.copy())
                    t0 = time.time()
                elif time.time() > start_deadline:
                    return ""
                continue

            chunks.append(data.copy())
            elapsed = time.time() - t0
            need_silent = max(
                1,
                int(
                    (
                        early_silence_sec
                        if elapsed < early_until_sec
                        else silence_sec
                    )
                    / 0.05
                ),
            )

            if energy >= threshold * 0.45:
                silent_blocks = 0
                speech_blocks += 1
                if in_grace:
                    in_grace = False
                    grace_left = 0
            else:
                silent_blocks += 1

            if (
                not in_grace
                and silent_blocks >= need_silent
                and speech_blocks * 0.05 >= min_speech_sec
            ):
                in_grace = True
                grace_left = grace_blocks
                silent_blocks = 0
                continue

            if in_grace:
                grace_left -= 1
                if grace_left <= 0:
                    break

            if len(chunks) >= max_blocks:
                break

    if stop_event.is_set() or not chunks:
        return ""

    audio = np.concatenate(chunks, axis=0).reshape(-1)
    if audio.size < sample_rate * 0.15:
        return ""
    if int(np.abs(audio.astype(np.float32)).mean()) < 2:
        return ""

    from cos.voice.stt import transcribe_int16

    return transcribe_int16(audio.astype("int16"), sample_rate=sample_rate, language="ar")
