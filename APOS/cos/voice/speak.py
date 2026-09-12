"""نطق قابل للمقاطعة — صوت فتاة (Edge Zariyah) مع إيقاف فوري عند الكلام."""
from __future__ import annotations

import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

_enabled = True
_cancel = threading.Event()
_speaking = threading.Event()
_interrupted = threading.Event()
_q: queue.Queue[Optional[tuple[str, threading.Event | None]]] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
_proc_lock = threading.Lock()
_active_proc: Optional[subprocess.Popen] = None
_last_error = ""

EDGE_FEMALE_VOICE = os.getenv("COS_TTS_VOICE", "ar-SA-ZariyahNeural")
# auto: elevenlabs → edge → local | elevenlabs | edge | local
TTS_ENGINE = (os.getenv("COS_TTS_ENGINE") or "auto").strip().lower()
WIN_FEMALE_PREF = ("zira", "hazel", "susan", "helena", "catherine", "female")
_CREATE = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ELEVEN_VOICE_ID = os.getenv("COS_ELEVEN_VOICE_ID", "EXAVITQu4vr4xnSDxMaL").strip()
ELEVEN_MODEL = os.getenv("COS_ELEVEN_MODEL", "eleven_multilingual_v2").strip()


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = bool(on)
    if not _enabled:
        stop_speaking()


def is_enabled() -> bool:
    return _enabled


def is_speaking() -> bool:
    return _speaking.is_set()


def last_error() -> str:
    return _last_error


def was_interrupted() -> bool:
    return _interrupted.is_set()


def stop_speaking() -> None:
    """أوقف النطق فوراً (للمقاطعة)."""
    _cancel.set()
    _interrupted.set()
    _kill_active()
    try:
        while True:
            _q.get_nowait()
    except queue.Empty:
        pass


def speak(text: str, *, wait: bool = False) -> bool:
    global _last_error
    if not _enabled or not (text or "").strip():
        return False
    clean = " ".join(str(text).split())
    # للنطق فقط — قصير جداً في الوضع السريع حتى يقل التأخير
    max_len = 140 if (os.getenv("COS_TTS_FAST") or "").strip() in ("1", "true", "yes") else 220
    if len(clean) > max_len:
        clean = clean[:max_len].rsplit(" ", 1)[0] + "…"

    _ensure_worker()
    _cancel.clear()
    _interrupted.clear()
    done: threading.Event | None = threading.Event() if wait else None
    _q.put((clean, done))
    if wait and done is not None:
        done.wait(timeout=90)
        if _interrupted.is_set():
            return True
        return not bool(_last_error)
    return True


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker, daemon=True, name="cos-tts-worker")
        t.start()
        _worker_started = True


def _worker() -> None:
    global _last_error
    while True:
        item = _q.get()
        if item is None:
            continue
        text, done = item
        try:
            _last_error = ""
            if _cancel.is_set() or not _enabled:
                continue
            _speaking.set()
            ok = _speak_windows(text)
            if not ok and not _interrupted.is_set():
                _last_error = "تعذر تشغيل الصوت على الجهاز"
                _beep()
        except Exception as e:
            if not _interrupted.is_set():
                _last_error = str(e)
                try:
                    _beep()
                except Exception:
                    pass
        finally:
            _speaking.clear()
            if done is not None:
                done.set()


def _beep() -> None:
    try:
        import winsound

        winsound.MessageBeep(-1)
    except Exception:
        pass


def _kill_active() -> None:
    """أوقف عملية النطق وكل أبناءها (مهم لـ PowerShell/MediaPlayer)."""
    global _active_proc
    with _proc_lock:
        proc = _active_proc
        _active_proc = None
    if proc is None:
        return
    pid = getattr(proc, "pid", None)
    if pid:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE,
                timeout=3,
            )
        except Exception:
            pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=1.0)
    except Exception:
        pass


def _run_killable(cmd: list[str], *, timeout: float = 180) -> bool:
    """شغّل عملية يمكن قتلها فوراً عند المقاطعة."""
    global _active_proc
    if _cancel.is_set():
        return False
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE,
        )
    except Exception:
        return False
    with _proc_lock:
        _active_proc = proc
    deadline = time.time() + timeout
    try:
        while proc.poll() is None:
            if _cancel.is_set() or time.time() > deadline:
                _kill_active()
                return False
            time.sleep(0.04)
        return proc.returncode == 0 and not _cancel.is_set()
    finally:
        with _proc_lock:
            if _active_proc is proc:
                _active_proc = None


def _speak_windows(text: str) -> bool:
    """جرّب المحركات بالترتيب حسب الإعداد (يُقرأ من البيئة كل مرة)."""
    engine = (os.getenv("COS_TTS_ENGINE") or TTS_ENGINE or "auto").strip().lower()
    fast = (os.getenv("COS_TTS_FAST") or "").strip().lower() in ("1", "true", "yes", "on")
    if engine in ("eleven", "elevenlabs", "11labs") and not fast:
        engines = ["elevenlabs", "edge", "local"]
    elif engine in ("local", "sapi", "windows"):
        engines = ["local", "edge", "elevenlabs"]
    elif engine == "edge" or fast:
        engines = ["edge", "local", "elevenlabs"]
    else:
        engines = ["elevenlabs", "edge", "local"]

    for eng in engines:
        if _cancel.is_set():
            return False
        if eng == "elevenlabs" and _speak_elevenlabs(text):
            return True
        if eng == "edge" and _speak_edge(text):
            return True
        if eng == "local":
            if _speak_powershell(text):
                return True
            if _cancel.is_set():
                return False
            if _speak_sapi(text):
                return True
            if _cancel.is_set():
                return False
            if _speak_pyttsx3(text):
                return True
    return False


def _speak_elevenlabs(text: str) -> bool:
    """نطق بشري فائق عبر ElevenLabs (متعدد اللغات/عربي)."""
    key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    if not key or not text.strip():
        return False
    voice = ELEVEN_VOICE_ID or "EXAVITQu4vr4xnSDxMaL"
    model = ELEVEN_MODEL or "eleven_multilingual_v2"
    out = Path(tempfile.gettempdir()) / f"cos_eleven_{os.getpid()}.mp3"
    try:
        import json
        import urllib.request

        payload = {
            "text": text.strip(),
            "model_id": model,
            "voice_settings": {
                "stability": float(os.getenv("COS_ELEVEN_STABILITY", "0.4")),
                "similarity_boost": float(os.getenv("COS_ELEVEN_SIMILARITY", "0.8")),
                "style": float(os.getenv("COS_ELEVEN_STYLE", "0.35")),
                "use_speaker_boost": True,
            },
        }
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio = resp.read()
        if not audio or len(audio) < 200:
            return False
        out.write_bytes(audio)
        if _cancel.is_set():
            return False
        ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Volume = 1
$p.Open([Uri]((Resolve-Path '{out}').Path))
$sw = [Diagnostics.Stopwatch]::StartNew()
do {{ Start-Sleep -Milliseconds 40 }} while (-not $p.NaturalDuration.HasTimeSpan -and $sw.Elapsed.TotalSeconds -lt 6)
$p.Play()
Start-Sleep -Milliseconds 120
while ($p.Position -lt $p.NaturalDuration.TimeSpan) {{
  Start-Sleep -Milliseconds 80
}}
$p.Close()
"""
        return _run_killable(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            timeout=180,
        )
    except Exception as e:
        global _last_error
        _last_error = str(e)
        return False


def _speak_edge(text: str) -> bool:
    try:
        import asyncio
        import edge_tts  # type: ignore
    except Exception:
        return False

    out = Path(tempfile.gettempdir()) / f"cos_edge_tts_{os.getpid()}.mp3"
    voice = EDGE_FEMALE_VOICE
    # أسرع قليلاً وأكثر حيوية
    rate = os.getenv("COS_TTS_RATE", "+12%")

    async def _gen() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(out))

    try:
        # توليد مع فحص إلغاء
        gen_done = threading.Event()
        gen_err: list[BaseException] = []

        def _gen_thread() -> None:
            try:
                asyncio.run(_gen())
            except BaseException as e:
                gen_err.append(e)
            finally:
                gen_done.set()

        threading.Thread(target=_gen_thread, daemon=True).start()
        while not gen_done.wait(0.05):
            if _cancel.is_set():
                return False
        if gen_err or _cancel.is_set():
            return False
        if not out.exists() or out.stat().st_size < 100:
            return False

        ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Volume = 1
$p.Open([Uri]((Resolve-Path '{out}').Path))
$sw = [Diagnostics.Stopwatch]::StartNew()
do {{ Start-Sleep -Milliseconds 40 }} while (-not $p.NaturalDuration.HasTimeSpan -and $sw.Elapsed.TotalSeconds -lt 6)
$p.Play()
Start-Sleep -Milliseconds 120
while ($p.Position -lt $p.NaturalDuration.TimeSpan) {{
  Start-Sleep -Milliseconds 80
}}
$p.Close()
"""
        return _run_killable(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            timeout=180,
        )
    except Exception:
        return False


def _pick_female_powershell_snippet() -> str:
    prefs = ", ".join(f"'{p}'" for p in WIN_FEMALE_PREF)
    return f"""
$femalePrefs = @({prefs})
$chosen = $null
foreach ($v in $s.GetInstalledVoices()) {{
  $n = $v.VoiceInfo.Name
  $c = $v.VoiceInfo.Culture.Name
  $g = [string]$v.VoiceInfo.Gender
  if ($c -like 'ar*' -and $g -match 'Female') {{ $chosen = $n; break }}
}}
if (-not $chosen) {{
  foreach ($v in $s.GetInstalledVoices()) {{
    $n = $v.VoiceInfo.Name
    $g = [string]$v.VoiceInfo.Gender
    $nl = $n.ToLower()
    if ($g -match 'Female') {{
      foreach ($p in $femalePrefs) {{ if ($nl -match $p) {{ $chosen = $n; break }} }}
      if ($chosen) {{ break }}
    }}
  }}
}}
if (-not $chosen) {{
  foreach ($v in $s.GetInstalledVoices()) {{
    if ([string]$v.VoiceInfo.Gender -match 'Female') {{ $chosen = $v.VoiceInfo.Name; break }}
  }}
}}
if ($chosen) {{ $s.SelectVoice($chosen) }}
"""


def _speak_powershell(text: str) -> bool:
    path = Path(tempfile.gettempdir()) / "cos_tts_utterance.txt"
    try:
        path.write_text(text, encoding="utf-8")
    except Exception:
        return False
    pick = _pick_female_powershell_snippet()
    ps = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Volume = 100
$s.Rate = 2
{pick}
$t = Get-Content -LiteralPath '{path}' -Raw -Encoding UTF8
$s.Speak($t)
"""
    return _run_killable(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        timeout=90,
    )


def _speak_sapi(text: str) -> bool:
    try:
        import win32com.client  # type: ignore

        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Volume = 100
        speaker.Rate = 2
        try:
            voices = speaker.GetVoices()
            picked = None
            for i in range(voices.Count):
                v = voices.Item(i)
                desc = (v.GetDescription() or "").lower()
                if "zira" in desc:
                    picked = v
                    break
            if picked is None:
                for i in range(voices.Count):
                    v = voices.Item(i)
                    desc = (v.GetDescription() or "").lower()
                    if any(p in desc for p in WIN_FEMALE_PREF):
                        picked = v
                        break
            if picked is not None:
                speaker.Voice = picked
        except Exception:
            pass
        # 1 = async flags — نستخدم sync مع فحص إلغاء عبر أجزاء
        for part in _split_for_speech(text, 120):
            if _cancel.is_set():
                return False
            speaker.Speak(part, 0)
        return not _cancel.is_set()
    except Exception:
        return False


def _speak_pyttsx3(text: str) -> bool:
    try:
        import pyttsx3

        eng = pyttsx3.init()
        try:
            voices = list(eng.getProperty("voices") or [])
            chosen = None
            for v in voices:
                name = (getattr(v, "name", "") or "").lower()
                vid = (getattr(v, "id", "") or "").lower()
                if "zira" in name or "zira" in vid:
                    chosen = v.id
                    break
            if chosen is None:
                for v in voices:
                    name = (getattr(v, "name", "") or "").lower()
                    if any(p in name for p in WIN_FEMALE_PREF):
                        chosen = v.id
                        break
            if chosen:
                eng.setProperty("voice", chosen)
        except Exception:
            pass
        eng.setProperty("volume", 1.0)
        eng.setProperty("rate", 185)
        for part in _split_for_speech(text, 120):
            if _cancel.is_set() or not _enabled:
                break
            eng.say(part)
            eng.runAndWait()
        try:
            eng.stop()
        except Exception:
            pass
        return not _cancel.is_set()
    except Exception:
        return False


def _split_for_speech(text: str, max_len: int = 220) -> list[str]:
    text = text.strip()
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    buf = ""
    for chunk in text.replace("\n", " ").split(" "):
        if not chunk:
            continue
        trial = f"{buf} {chunk}".strip()
        if len(trial) > max_len and buf:
            parts.append(buf)
            buf = chunk
        else:
            buf = trial
    if buf:
        parts.append(buf)
    return parts or [text]
