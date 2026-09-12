"""تعرّف كلام عربي أدق: تطبيع صوت + عدة لهجات Google + Whisper عند الجاهزية."""
from __future__ import annotations

import os
import threading
from typing import Optional

import numpy as np

from cos.voice.dialects import WHISPER_AR_HINT, google_lang_list, normalize_dialect

_model = None
_model_name = ""
_last_backend = "none"
_last_error = ""
_whisper_ready = False
_whisper_loading = False
_lock = threading.Lock()

_AR_HINT = WHISPER_AR_HINT


def last_backend() -> str:
    return _last_backend


def last_error() -> str:
    return _last_error


def whisper_ready() -> bool:
    return _whisper_ready


def _engine() -> str:
    return (os.getenv("COS_STT_ENGINE") or "auto").strip().lower()


def _whisper_model_name() -> str:
    # small أفضل للعربية من base مع بقاء مقبول على CPU
    return (os.getenv("COS_WHISPER_MODEL") or "small").strip() or "small"


def _arabic_score(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return -1.0
    ar = sum(1 for c in t if "\u0600" <= c <= "\u06FF")
    weird = sum(1 for c in t if c in "`~@$%^&*+=<>[]{}|\\")
    return ar * 2.0 + len(t) * 0.15 - weird * 3.0


def _normalize_audio(audio: np.ndarray) -> np.ndarray:
    """رفع مستوى الصوت بهدوء + حشوة صمت قصيرة (يحسّن Google/Whisper)."""
    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    if a.size == 0:
        return np.zeros(0, dtype=np.int16)
    peak = float(np.max(np.abs(a))) + 1e-6
    # استهدف ~70% من المدى
    gain = min(12.0, (20000.0 / peak))
    a = np.clip(a * gain, -32767, 32767)
    pad = np.zeros(int(16000 * 0.25), dtype=np.float32)
    out = np.concatenate([pad, a, pad])
    return out.astype(np.int16)


def _load_whisper_sync():
    global _model, _model_name, _whisper_ready, _last_error
    name = _whisper_model_name()
    if _model is not None and _model_name == name:
        _whisper_ready = True
        return _model
    from faster_whisper import WhisperModel

    device = (os.getenv("COS_WHISPER_DEVICE") or "cpu").strip().lower()
    if device == "auto":
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    compute = (os.getenv("COS_WHISPER_COMPUTE") or "int8").strip()
    if device != "cuda":
        compute = "int8"
        device = "cpu"
    _model = WhisperModel(name, device=device, compute_type=compute)
    _model_name = name
    _whisper_ready = True
    _last_error = ""
    return _model


def warmup_whisper_async() -> None:
    """حمّل النموذج في الخلفية."""
    global _whisper_loading
    eng = _engine()
    if eng in ("google", "sr", "none", "off"):
        return
    with _lock:
        if _whisper_ready or _whisper_loading:
            return
        _whisper_loading = True

    def _run() -> None:
        global _whisper_loading, _last_error
        try:
            _load_whisper_sync()
        except Exception as e:
            _last_error = str(e)
        finally:
            _whisper_loading = False

    threading.Thread(target=_run, daemon=True, name="cos-whisper-warmup").start()


def _google_once(audio: np.ndarray, sample_rate: int, lang: str) -> str:
    import speech_recognition as sr

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 150
    recognizer.dynamic_energy_threshold = True
    audio_data = sr.AudioData(audio.astype("int16").tobytes(), sample_rate, 2)
    try:
        return (recognizer.recognize_google(audio_data, language=lang) or "").strip()
    except sr.UnknownValueError:
        return ""
    except Exception:
        return ""


def _google_transcribe(audio: np.ndarray, sample_rate: int) -> str:
    global _last_backend, _last_error
    langs = google_lang_list()
    # حدّ أقصى للمحاولات حتى لا يبطئ الرد كثيراً
    max_try = int(os.getenv("COS_STT_GOOGLE_MAX", "3") or "3")
    langs = langs[: max(2, max_try)]
    best = ""
    best_score = -1.0
    used = ""
    for lang in langs:
        text = _google_once(audio, sample_rate, lang)
        text = normalize_dialect(text) if text else text
        sc = _arabic_score(text)
        if sc > best_score:
            best, best_score, used = text, sc, lang
        if sc >= 10 and len(text) >= 3:
            break
    if best:
        _last_backend = f"google:{used}"
        return best
    _last_backend = "google-empty"
    return ""


def _whisper_transcribe(audio: np.ndarray, sample_rate: int) -> str:
    global _last_backend
    model = _load_whisper_sync()
    wav = audio.astype(np.float32) / 32768.0
    segments, _info = model.transcribe(
        wav,
        language="ar",
        task="transcribe",
        beam_size=1,
        best_of=1,
        patience=1.0,
        temperature=0.0,
        vad_filter=True,
        condition_on_previous_text=False,
        initial_prompt=_AR_HINT,
        word_timestamps=False,
    )
    text = " ".join(s.text.strip() for s in segments if s.text).strip()
    text = " ".join(text.replace(".", " ").replace("،", " ").split())
    text = normalize_dialect(text)
    if text:
        _last_backend = f"whisper:{_model_name}"
    else:
        _last_backend = "whisper-empty"
    return text


def transcribe_int16(audio: np.ndarray, sample_rate: int = 16000, language: str = "ar") -> str:
    """حوّل صوت int16 إلى نص عربي — سحابة عالية الجودة أولاً إن توفرت."""
    global _last_backend, _last_error
    raw = np.asarray(audio).reshape(-1)
    if raw.size < sample_rate * 0.12:
        return ""

    audio_n = _normalize_audio(raw)
    eng = _engine()
    candidates: list[tuple[float, str, str]] = []

    # 0) سحابة عالية الجودة (Groq / OpenAI Whisper)
    use_cloud = eng in ("auto", "", "cloud", "groq", "openai-whisper", "hq")
    if use_cloud:
        try:
            from cos.voice.cloud_stt import cloud_stt_ready, transcribe_cloud

            if cloud_stt_ready():
                ctext, cback = transcribe_cloud(audio_n, sample_rate, language="ar")
                ctext = normalize_dialect(ctext) if ctext else ctext
                if ctext:
                    candidates.append((_arabic_score(ctext) + 5.0, ctext, cback))
                    # إن كانت جودة عربية جيدة اكتفِ بالسحابة
                    if _arabic_score(ctext) >= 8:
                        _last_backend = cback
                        return _finalize_text(ctext, cback)
        except Exception as e:
            _last_error = str(e)

    prefer_whisper = eng in ("whisper", "faster-whisper", "fw")
    # 1) Google
    if eng not in ("whisper", "faster-whisper", "fw", "cloud", "groq", "openai-whisper", "hq"):
        try:
            g = _google_transcribe(audio_n, sample_rate)
            if g:
                candidates.append((_arabic_score(g), g, _last_backend))
        except Exception as e:
            _last_error = str(e)
    elif eng in ("cloud", "groq", "openai-whisper", "hq") and not candidates:
        try:
            g = _google_transcribe(audio_n, sample_rate)
            if g:
                candidates.append((_arabic_score(g), g, _last_backend))
        except Exception as e:
            _last_error = str(e)

    # 2) Whisper محلي
    use_whisper = prefer_whisper or (eng in ("auto", "") and _whisper_ready)
    if use_whisper:
        try:
            if prefer_whisper or _whisper_ready:
                w = _whisper_transcribe(audio_n, sample_rate)
                if w:
                    candidates.append((_arabic_score(w), w, _last_backend))
        except Exception as e:
            _last_error = str(e)
            if prefer_whisper:
                warmup_whisper_async()

    if not candidates and prefer_whisper:
        try:
            g = _google_transcribe(audio_n, sample_rate)
            if g:
                candidates.append((_arabic_score(g), g, _last_backend))
        except Exception as e:
            _last_error = str(e)

    if not candidates:
        _last_backend = "empty"
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    score, text, backend = candidates[0]
    return _finalize_text(text, backend)


def _finalize_text(text: str, backend: str) -> str:
    global _last_backend
    _last_backend = backend
    try:
        from cos.brain.intent import looks_gibberish

        if looks_gibberish(text):
            _last_backend = f"{backend}-rejected"
            return ""
    except Exception:
        pass
    ar = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    # اسمح بالأوامر القصيرة جداً (نعم/لا/يلا)
    if ar < 1 and len(text) >= 4:
        _last_backend = f"{backend}-no-ar"
        return ""
    return text
