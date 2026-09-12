"""عقل لغوي موحّد — llama.cpp → Ollama → OpenRouter → Anthropic نصي."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from cos import config


@dataclass
class BrainReply:
    text: str
    provider: str
    model: str
    ok: bool
    error: str = ""


def _http_json(
    url: str,
    payload: dict[str, Any],
    headers: Optional[dict[str, str]] = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_get_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def llamacpp_available() -> bool:
    host = config.LLAMA_CPP_HOST.rstrip("/")
    for path in ("/health", "/v1/models", "/props"):
        try:
            url = host + path
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            continue
    return False


def list_llamacpp_models() -> list[str]:
    try:
        data = _http_get_json(config.LLAMA_CPP_HOST.rstrip("/") + "/v1/models", timeout=3.0)
        out = []
        for m in data.get("data") or []:
            mid = str(m.get("id") or "").strip()
            if mid:
                out.append(mid)
        return out
    except Exception:
        return []


def ollama_available() -> bool:
    try:
        url = config.OLLAMA_HOST.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def list_ollama_models() -> list[str]:
    try:
        url = config.OLLAMA_HOST.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models") or [] if m.get("name")]
    except Exception:
        return []


def _chat_openai_compatible(
    *,
    base: str,
    model: str,
    system: str,
    user: str,
    provider: str,
    api_key: str = "no-key",
    max_tokens: int | None = None,
    temperature: float = 0.2,
    timeout: float | None = None,
) -> BrainReply:
    url = base.rstrip("/") + "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": int(max_tokens or config.BRAIN_MAX_TOKENS),
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # يمنع spill من قوالب Qwen/chat عند llama.cpp
        "stop": [
            "<|im_end|>",
            "<|endoftext|>",
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        data = _http_json(url, payload, headers=headers, timeout=timeout or config.BRAIN_TIMEOUT)
        text = (
            (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            or ""
        ).strip()
        used = str(data.get("model") or model)
        return BrainReply(text=text, provider=provider, model=used, ok=bool(text))
    except Exception as e:
        return BrainReply("", provider, model, False, str(e))


def _chat_llamacpp(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float = 0.2,
    timeout: float | None = None,
) -> BrainReply:
    models = list_llamacpp_models()
    model = config.LLAMA_CPP_MODEL
    if models and model not in models:
        # الخادم يحمّل نموذجاً واحداً غالباً — استخدم أول متاح
        model = models[0]
    return _chat_openai_compatible(
        base=config.LLAMA_CPP_HOST,
        model=model,
        system=system,
        user=user,
        provider="llamacpp",
        api_key=config.LLAMA_CPP_API_KEY,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )


def _chat_ollama(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float = 0.2,
    timeout: float | None = None,
) -> BrainReply:
    model = config.OLLAMA_MODEL
    url = config.OLLAMA_HOST.rstrip("/") + "/api/chat"
    options: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)
    payload = {
        "model": model,
        "stream": False,
        "options": options,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        data = _http_json(url, payload, timeout=timeout or config.BRAIN_TIMEOUT)
        text = ((data.get("message") or {}).get("content") or "").strip()
        return BrainReply(text=text, provider="ollama", model=model, ok=bool(text))
    except Exception as e:
        return BrainReply(text="", provider="ollama", model=model, ok=False, error=str(e))


def _chat_openai(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float = 0.2,
    timeout: float | None = None,
    model: str | None = None,
) -> BrainReply:
    key = config.OPENAI_API_KEY
    model = (model or config.OPENAI_MODEL).strip() or "gpt-4o-mini"
    if not key:
        return BrainReply("", "openai", model, False, "no OPENAI_API_KEY")
    return _chat_openai_compatible(
        base=config.OPENAI_BASE,
        model=model,
        system=system,
        user=user,
        provider="openai",
        api_key=key,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )


def _chat_openrouter(system: str, user: str) -> BrainReply:
    key = config.OPENROUTER_API_KEY
    model = config.OPENROUTER_MODEL
    if not key:
        return BrainReply("", "openrouter", model, False, "no OPENROUTER_API_KEY")
    url = config.OPENROUTER_BASE.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": config.BRAIN_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://localhost/cos",
        "X-Title": "COS Personal",
    }
    try:
        data = _http_json(url, payload, headers=headers, timeout=config.BRAIN_TIMEOUT)
        text = (
            (((data.get("choices") or [{}])[0].get("message") or {}).get("content"))
            or ""
        ).strip()
        return BrainReply(text=text, provider="openrouter", model=model, ok=bool(text))
    except Exception as e:
        return BrainReply("", "openrouter", model, False, str(e))


def _chat_anthropic(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> BrainReply:
    key = config.ANTHROPIC_API_KEY
    model = (model or config.ANTHROPIC_MODEL).strip()
    if not key:
        return BrainReply("", "anthropic", model, False, "no ANTHROPIC_API_KEY")
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens or config.BRAIN_MAX_TOKENS),
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        msg = client.messages.create(**kwargs)
        parts = []
        for block in msg.content:
            t = getattr(block, "text", None)
            if t:
                parts.append(t)
        text = "\n".join(parts).strip()
        try:
            from cos.brain.intent import looks_gibberish

            if looks_gibberish(text):
                return BrainReply("", "anthropic", model, False, "gibberish reply")
        except Exception:
            pass
        return BrainReply(text=text, provider="anthropic", model=model, ok=bool(text))
    except Exception as e:
        return BrainReply("", "anthropic", model, False, str(e))


# GPT-4o-mini أولاً إن وُجد — ثم Anthropic/OpenRouter — المحلي أخيراً
_PROVIDERS = ("openai", "anthropic", "openrouter", "ollama", "llamacpp")


def resolve_provider() -> str:
    pref = (config.BRAIN_PROVIDER or "auto").lower()
    if pref in (*_PROVIDERS, "rules", "none", "llama.cpp", "llama", "gpt", "gpt4o-mini"):
        if pref in ("llama.cpp", "llama"):
            return "llamacpp"
        if pref in ("gpt", "gpt4o-mini", "gpt-4o-mini"):
            return "openai"
        return pref
    if config.OPENAI_API_KEY:
        return "openai"
    if config.ANTHROPIC_API_KEY:
        return "anthropic"
    if config.OPENROUTER_API_KEY:
        return "openrouter"
    if ollama_available():
        return "ollama"
    if llamacpp_available():
        return "llamacpp"
    return "rules"


def chat_complex(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
) -> BrainReply:
    """للأوامر المعقّدة: GPT-4o-mini / سحابة رخيصة أولاً."""
    pref = (config.COMPLEX_BRAIN_PROVIDER or "auto").lower()
    if pref in ("llama.cpp", "llama"):
        pref = "llamacpp"
    if pref in ("gpt", "gpt4o-mini", "gpt-4o-mini"):
        pref = "openai"
    temp = 0.15 if temperature is None else temperature

    if config.OPENAI_API_KEY and pref in ("auto", "openai"):
        last = _chat_openai(
            system,
            user,
            max_tokens=max_tokens or min(1200, int(config.BRAIN_MAX_TOKENS) + 300),
            temperature=temp,
            timeout=timeout,
            model=config.OPENAI_MODEL,
        )
        if last.ok:
            return last

    if config.ANTHROPIC_API_KEY and pref in ("auto", "anthropic"):
        strong = getattr(config, "ANTHROPIC_COMPLEX_MODEL", None) or config.ANTHROPIC_MODEL
        last = _chat_anthropic(
            system,
            user,
            max_tokens=max_tokens or min(1400, int(config.BRAIN_MAX_TOKENS) + 400),
            temperature=temp,
            model=strong,
        )
        if last.ok:
            return last

    if pref == "auto":
        order: list[str] = []
        if config.OPENAI_API_KEY:
            order.append("openai")
        if config.ANTHROPIC_API_KEY:
            order.append("anthropic")
        if config.OPENROUTER_API_KEY:
            order.append("openrouter")
        if not getattr(config, "CLOUD_ONLY_BRAIN", False):
            order.extend(["ollama", "llamacpp"])
        last = BrainReply("", "none", "", False, "no cloud provider")
        for p in order:
            last = chat(
                system,
                user,
                prefer=p,
                max_tokens=max_tokens,
                temperature=temp,
                timeout=timeout,
            )
            if last.ok:
                return last
        return last
    return chat(
        system,
        user,
        prefer=pref,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )


def chat(
    system: str,
    user: str,
    *,
    prefer: str = "",
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float | None = None,
) -> BrainReply:
    """محادثة نصية عبر أفضل مزوّد متاح."""
    pref = (prefer or config.BRAIN_PROVIDER or "auto").lower()
    if pref in ("llama.cpp", "llama"):
        pref = "llamacpp"
    if pref in ("gpt", "gpt4o-mini", "gpt-4o-mini"):
        pref = "openai"
    cloud_only = bool(getattr(config, "CLOUD_ONLY_BRAIN", False)) and (
        bool(config.OPENAI_API_KEY)
        or bool(config.ANTHROPIC_API_KEY)
        or bool(config.OPENROUTER_API_KEY)
    )
    if pref == "auto":
        order = []
        if config.OPENAI_API_KEY:
            order.append("openai")
        if config.ANTHROPIC_API_KEY:
            order.append("anthropic")
        if config.OPENROUTER_API_KEY:
            order.append("openrouter")
        if not cloud_only:
            order.extend([p for p in _PROVIDERS if p not in order])
    elif pref in ("rules", "none"):
        return BrainReply("", "rules", "rules", False, "rules-only")
    else:
        order = [pref] + [p for p in _PROVIDERS if p != pref]
        if cloud_only:
            cloud = [p for p in order if p in ("openai", "anthropic", "openrouter")]
            if cloud:
                order = cloud

    last = BrainReply("", "none", "", False, "no provider")
    temp = 0.2 if temperature is None else temperature
    for p in order:
        if p == "llamacpp":
            if cloud_only or not llamacpp_available():
                last = BrainReply(
                    "",
                    "llamacpp",
                    config.LLAMA_CPP_MODEL,
                    False,
                    "llamacpp skipped/offline",
                )
                continue
            last = _chat_llamacpp(
                system,
                user,
                max_tokens=max_tokens,
                temperature=temp,
                timeout=timeout,
            )
        elif p == "ollama":
            if cloud_only or not ollama_available():
                last = BrainReply(
                    "", "ollama", config.OLLAMA_MODEL, False, "ollama skipped/offline"
                )
                continue
            last = _chat_ollama(
                system,
                user,
                max_tokens=max_tokens,
                temperature=temp,
                timeout=timeout,
            )
        elif p == "openai":
            last = _chat_openai(
                system,
                user,
                max_tokens=max_tokens,
                temperature=temp,
                timeout=timeout,
            )
        elif p == "openrouter":
            last = _chat_openrouter(system, user)
        elif p == "anthropic":
            last = _chat_anthropic(
                system,
                user,
                max_tokens=max_tokens,
                temperature=temp,
            )
        else:
            continue
        if last.ok:
            try:
                from cos.brain.intent import looks_gibberish

                if looks_gibberish(last.text):
                    last = BrainReply(
                        "", last.provider, last.model, False, "gibberish reply"
                    )
                    continue
            except Exception:
                pass
            return last
    return last


def status() -> dict[str, Any]:
    return {
        "provider_pref": config.BRAIN_PROVIDER,
        "resolved": resolve_provider(),
        "complex_brain": config.COMPLEX_BRAIN_PROVIDER,
        "clarify_before_execute": config.CLARIFY_BEFORE_EXECUTE,
        "session_memory": config.SESSION_MEMORY,
        "llamacpp_host": config.LLAMA_CPP_HOST,
        "llamacpp_up": llamacpp_available(),
        "llamacpp_model": config.LLAMA_CPP_MODEL,
        "llamacpp_models": list_llamacpp_models()[:8],
        "ollama_host": config.OLLAMA_HOST,
        "ollama_up": ollama_available(),
        "ollama_model": config.OLLAMA_MODEL,
        "ollama_models": list_ollama_models()[:12],
        "openrouter_configured": bool(config.OPENROUTER_API_KEY),
        "openrouter_model": config.OPENROUTER_MODEL,
        "openai_configured": bool(config.OPENAI_API_KEY),
        "openai_model": config.OPENAI_MODEL,
        "anthropic_configured": bool(config.ANTHROPIC_API_KEY),
        "anthropic_model": config.ANTHROPIC_MODEL,
        "claude_escalate": config.AUTO_CLAUDE_ESCALATE,
        "brain_planner": config.USE_BRAIN_PLANNER,
    }
