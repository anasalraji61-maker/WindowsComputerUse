"""سماع سحابي عالي الجودة: Groq Whisper-large / OpenAI Whisper API."""
from __future__ import annotations

import io
import os
import wave

import numpy as np


def _int16_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    a = np.asarray(audio, dtype=np.int16).reshape(-1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(a.tobytes())
    return buf.getvalue()


def _post_multipart(
    url: str,
    *,
    headers: dict[str, str],
    fields: dict[str, str],
    file_bytes: bytes,
    filename: str = "audio.wav",
    timeout: float = 45.0,
) -> dict:
    import json
    import urllib.request
    import uuid

    boundary = f"----COS{uuid.uuid4().hex}"
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for k, v in fields.items():
        add_field(k, v)

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    )
    body.extend(b"Content-Type: audio/wav\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            **headers,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "COS-Personal/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def groq_available() -> bool:
    return bool((os.getenv("GROQ_API_KEY") or "").strip())


def openai_stt_available() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def cloud_stt_ready() -> bool:
    return groq_available() or openai_stt_available()


def transcribe_cloud(
    audio: np.ndarray,
    sample_rate: int = 16000,
    *,
    language: str = "ar",
) -> tuple[str, str]:
    """أعلى جودة سحابية متاحة. يعيد (النص, الخلفية)."""
    wav = _int16_to_wav_bytes(audio, sample_rate)
    prompt = (
        os.getenv("COS_STT_CLOUD_PROMPT")
        or (
            "كلام عربي فصيح أو عراقي. أوامر مثل: حلل المشروع، أكمل المهمة، "
            "افحص الروبوت، حرك الماوس، افتح كورسر، نعم، لا، ابدأ."
        )
    ).strip()

    prefer = (os.getenv("COS_STT_CLOUD_PROVIDER") or "auto").strip().lower()
    order: list[str] = []
    if prefer in ("groq", "openai"):
        order = [prefer]
    else:
        if groq_available():
            order.append("groq")
        if openai_stt_available():
            order.append("openai")

    last_err = ""
    for prov in order:
        try:
            if prov == "groq":
                key = (os.getenv("GROQ_API_KEY") or "").strip()
                model = (os.getenv("COS_GROQ_STT_MODEL") or "whisper-large-v3-turbo").strip()
                data = _post_multipart(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    fields={
                        "model": model,
                        "language": language,
                        "response_format": "json",
                        "prompt": prompt,
                        "temperature": "0",
                    },
                    file_bytes=wav,
                )
                text = (data.get("text") or "").strip()
                if text:
                    return text, f"groq:{model}"
            elif prov == "openai":
                key = (os.getenv("OPENAI_API_KEY") or "").strip()
                model = (os.getenv("COS_OPENAI_STT_MODEL") or "whisper-1").strip()
                data = _post_multipart(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    fields={
                        "model": model,
                        "language": language,
                        "response_format": "json",
                        "prompt": prompt,
                    },
                    file_bytes=wav,
                )
                text = (data.get("text") or "").strip()
                if text:
                    return text, f"openai:{model}"
        except Exception as e:
            last_err = str(e)
            continue
    return "", f"cloud-empty:{last_err[:80]}" if last_err else "cloud-empty"
