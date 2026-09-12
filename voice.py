"""
تسجيل صوت قابل للإيقاف + تعرّف عربي (نهائي ومؤقت أثناء التسجيل).
"""
from __future__ import annotations

import os
import threading
from typing import Optional


class VoiceSession:
    def __init__(self, max_seconds: float = 90.0, sample_rate: int = 16000):
        self.max_seconds = max(3.0, min(float(max_seconds), 90.0))
        self.fs = sample_rate
        self._chunks: list = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._chunks = []
        self._stop.clear()

        def callback(indata, frames, time_info, status):
            if self._stop.is_set():
                return
            with self._lock:
                self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.fs,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

        def auto_stop():
            if not self._stop.wait(self.max_seconds):
                self._stop.set()

        threading.Thread(target=auto_stop, daemon=True).start()

    def snapshot_audio(self):
        import numpy as np

        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.int16)
            return np.concatenate(self._chunks, axis=0).reshape(-1).copy()

    def stop_and_get_audio(self):
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        return self.snapshot_audio()


def _transcribe_array(audio, fs: int) -> str:
    import numpy as np
    import speech_recognition as sr

    if audio is None or getattr(audio, "size", 0) < fs * 0.5:
        return ""
    if int(np.abs(audio).mean()) < 3:
        return ""

    recognizer = sr.Recognizer()
    audio_data = sr.AudioData(audio.astype("int16").tobytes(), fs, 2)
    try:
        return (recognizer.recognize_google(audio_data, language="ar-SA") or "").strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        raise RuntimeError("تعذر الوصول لخدمة التعرف (إنترنت).") from e


_session: Optional[VoiceSession] = None
_session_lock = threading.Lock()


def voice_start(max_seconds: float | None = None) -> float:
    global _session
    if max_seconds is None:
        try:
            max_seconds = float(os.getenv("VOICE_SECONDS", "90"))
        except ValueError:
            max_seconds = 90.0
    max_seconds = max(3.0, min(max_seconds, 90.0))
    with _session_lock:
        if _session is not None:
            raise RuntimeError("تسجيل جارٍ بالفعل.")
        try:
            import sounddevice as sd

            sd.query_devices(kind="input")
        except Exception as e:
            raise RuntimeError(f"لا يوجد مايكروفون جاهز: {e}") from e
        _session = VoiceSession(max_seconds=max_seconds)
        _session.start()
    return max_seconds


def voice_partial_text(window_seconds: float | None = None) -> str:
    """تعرّف سريع على آخر ثوانٍ فقط (أسرع من الملف كاملاً)."""
    if window_seconds is None:
        try:
            window_seconds = float(os.getenv("VOICE_PARTIAL_WINDOW_SEC", "3"))
        except ValueError:
            window_seconds = 3.0
    window_seconds = max(1.5, min(float(window_seconds), 8.0))
    with _session_lock:
        sess = _session
    if sess is None:
        return ""
    audio = sess.snapshot_audio()
    if audio.size == 0:
        return ""
    # نافذة منزلقة: آخر N ثانية فقط
    max_samples = int(sess.fs * window_seconds)
    if audio.size > max_samples:
        audio = audio[-max_samples:]
    return _transcribe_array(audio, sess.fs)


def voice_stop_and_transcribe() -> str:
    global _session
    with _session_lock:
        sess = _session
        _session = None
    if sess is None:
        raise RuntimeError("لا يوجد تسجيل نشط.")

    try:
        import numpy as np
    except ImportError as e:
        raise RuntimeError(
            "حزم الصوت غير مثبتة. شغّل:\npip install SpeechRecognition sounddevice numpy"
        ) from e

    audio = sess.stop_and_get_audio()
    if audio.size < sess.fs * 0.4:
        raise RuntimeError("التسجيل قصير جداً — تكلم ثم اضغط إيقاف.")
    if int(np.abs(audio).mean()) < 3:
        raise RuntimeError("الصوت ضعيف أو صامت — تكلم أقرب للمايك.")

    # للنهائي: حد أقصى ~25 ثانية الأخيرة (أسرع بكثير من دقيقة كاملة)
    max_final = int(sess.fs * 25)
    if audio.size > max_final:
        audio = audio[-max_final:]

    text = _transcribe_array(audio, sess.fs)
    if not text:
        raise RuntimeError("لم أفهم الكلام — أعد المحاولة بوضوح.")
    return text


def voice_cancel() -> None:
    global _session
    with _session_lock:
        sess = _session
        _session = None
    if sess is not None:
        try:
            sess.stop_and_get_audio()
        except Exception:
            pass
