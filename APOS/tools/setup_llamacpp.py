"""تنزيل llama-server + نموذج GGUF سريع لـ COS."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # WindowsComputerUse
LLAMA_DIR = ROOT / "APOS" / "llama_cpp"
BIN_DIR = LLAMA_DIR / "bin"
MODEL_DIR = LLAMA_DIR / "models"
SERVER = BIN_DIR / "llama-server.exe"


def _out(msg: str = "") -> None:
    """طباعة آمنة على كونسول ويندوز (cp1252/cp720)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((msg + "\n").encode(enc, errors="replace"))
        sys.stdout.buffer.flush()

# نموذج صغير نسبياً وسريع على 8GB VRAM (مستودع GGUF شائع)
MODELS = {
    "3b": (
        "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
        "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
        1_800_000_000,
    ),
    # ~4.68GB — أفضل فهم على RTX 5070 8GB مع Q4
    "7b": (
        "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/"
        "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        4_000_000_000,
    ),
}

_size = (os.getenv("COS_LLAMA_SIZE") or "3b").strip().lower()
if _size not in MODELS:
    _size = "3b"
MODEL_URL, MODEL_NAME, MODEL_MIN_BYTES = MODELS[_size]
MODEL_PATH = MODEL_DIR / MODEL_NAME


def _finalize_download(tmp: Path, dest: Path) -> None:
    """انقل .part إلى الوجهة مع إعادة محاولة (WinError 32 شائع على ويندوز)."""
    import shutil
    import time

    last_err: Exception | None = None
    for attempt in range(1, 12):
        try:
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            try:
                tmp.replace(dest)
            except OSError:
                # نسخة ثم حذف — يتجاوز قفل إعادة التسمية أحياناً
                shutil.copy2(tmp, dest)
                try:
                    tmp.unlink()
                except OSError:
                    pass
            if dest.exists() and dest.stat().st_size >= 1000:
                return
            raise RuntimeError("dest missing after finalize")
        except Exception as e:
            last_err = e
            time.sleep(min(0.4 * attempt, 3.0))
    raise RuntimeError(f"cannot finalize download: {last_err}")


def _download(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {label}...")
    print(f"  {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")

    # curl أكثر ثباتاً على ويندوز مع الملفات الكبيرة
    import shutil
    import subprocess

    curl = shutil.which("curl")
    if curl:
        # حلقة خارجية: الاتصال يسقط كثيراً على HuggingFace من ويندوز
        last_code = 1
        for round_i in range(1, 25):
            cmd = [
                curl,
                "-L",
                "--retry",
                "12",
                "--retry-all-errors",
                "--retry-delay",
                "5",
                "--connect-timeout",
                "30",
                "-C",
                "-",
                "-o",
                str(tmp),
                url,
            ]
            print(f"  using curl (round {round_i}/24)...")
            r = subprocess.run(cmd, check=False)
            last_code = r.returncode
            size = tmp.stat().st_size if tmp.exists() else 0
            if r.returncode == 0 and size >= MODEL_MIN_BYTES:
                break
            print(
                f"  curl interrupted code={r.returncode} size={size // (1024*1024)}MB; "
                "resume in 8s..."
            )
            import time

            time.sleep(8)
        if not tmp.exists() or tmp.stat().st_size < MODEL_MIN_BYTES:
            raise RuntimeError(
                f"curl failed code={last_code} "
                f"(got {tmp.stat().st_size if tmp.exists() else 0} bytes, "
                f"need >={MODEL_MIN_BYTES}); re-run to resume"
            )
        _finalize_download(tmp, dest)
        print(f"Saved: {dest} ({dest.stat().st_size // (1024 * 1024)} MB)")
        return

    # احتياطي urllib مع إعادة محاولة
    last_err: Exception | None = None
    for attempt in range(1, 6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "COS-setup"})
            with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = resp.read(1024 * 512)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = 100.0 * done / total
                        print(f"\r  {pct:5.1f}%  ({done // (1024*1024)} MB)", end="", flush=True)
            print()
            _finalize_download(tmp, dest)
            print(f"Saved: {dest}")
            return
        except Exception as e:
            last_err = e
            print(f"\n  attempt {attempt} failed: {e}")
    raise RuntimeError(str(last_err or "download failed"))


def _pick_windows_zip(assets: list[dict]) -> str | None:
    """اختر أفضل zip لويندوز — يفضّل CUDA ثم CPU (يتجنب cudart فقط)."""
    names = [(a.get("name") or "", a.get("browser_download_url") or "") for a in assets]

    def ok(name: str) -> bool:
        n = name.lower()
        if not n.endswith(".zip"):
            return False
        if "cudart" in n:
            return False
        if "win" not in n and "windows" not in n:
            return False
        return True

    scored: list[tuple[int, str, str]] = []
    for name, url in names:
        if not ok(name) or not url:
            continue
        n = name.lower()
        score = 0
        if n.startswith("llama-") and "bin-win" in n:
            score += 200
        if "cuda" in n or "cu12" in n or "cu13" in n:
            score += 100
        if "12.4" in n or "cu12.4" in n:
            score += 25
        if "vulkan" in n:
            score += 50
        if "cpu-x64" in n:
            score += 40
        if "avx" in n or "cpu" in n:
            score += 20
        scored.append((score, name, url))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"Release asset: {scored[0][1]} (score={scored[0][0]})")
    return scored[0][2]


def _extract_server(zip_path: Path) -> None:
    print("Extracting...")
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(BIN_DIR)
    found = list(BIN_DIR.rglob("llama-server.exe"))
    if not found:
        found = list(BIN_DIR.rglob("server.exe"))
    if not found:
        raise RuntimeError("llama-server.exe not found after extract.")
    target = found[0]
    if target.resolve() != SERVER.resolve():
        SERVER.write_bytes(target.read_bytes())
    print(f"Ready: {SERVER}")


def ensure_server() -> None:
    # exe صغير + dll التنفيذ — اعتبره جاهزاً إن وُجد impl أو حجم معقول
    impl = BIN_DIR / "llama-server-impl.dll"
    if SERVER.exists() and (impl.exists() or SERVER.stat().st_size > 50_000):
        _out(f"llama-server OK: {SERVER}")
        return

    zip_path = LLAMA_DIR / "llama-bin.zip"
    if zip_path.exists() and zip_path.stat().st_size > 10_000_000:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                bad = zf.testzip()
            if bad is None:
                print(f"Using existing zip: {zip_path.name}")
                _extract_server(zip_path)
                if SERVER.exists():
                    return
        except zipfile.BadZipFile:
            print("Existing zip corrupt — re-downloading...")

    print("Looking up latest llama.cpp Windows release...")
    api = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "COS-setup", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    url = _pick_windows_zip(list(data.get("assets") or []))
    if not url:
        raise RuntimeError(
            "No Windows llama.cpp zip found. Download manually from:\n"
            "https://github.com/ggml-org/llama.cpp/releases"
        )
    _download(url, zip_path, "llama.cpp Windows binary")
    _extract_server(zip_path)


def ensure_model() -> None:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > MODEL_MIN_BYTES:
        _out(f"Model OK: {MODEL_PATH.name}")
        return
    _download(MODEL_URL, MODEL_PATH, MODEL_NAME)


def write_env_hint() -> None:
    env_path = ROOT / "APOS" / ".env"
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    kv = {
        "COS_BRAIN_PROVIDER": "llamacpp",
        "COS_LLAMA_CPP_HOST": "http://127.0.0.1:8080",
        "COS_LLAMA_CPP_MODEL": MODEL_NAME,
        "COS_COMPLEX_BRAIN": "auto",
        "COS_CLARIFY_BEFORE_EXECUTE": "1",
        "COS_SESSION_MEMORY": "1",
        "COS_WHISPER_MODEL": "small",
    }
    out = []
    seen = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in kv:
                out.append(f"{k}={kv[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in kv.items():
        if k not in seen:
            out.append(f"{k}={v}")
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"Updated: {env_path}")


def main() -> int:
    try:
        LLAMA_DIR.mkdir(parents=True, exist_ok=True)
        ensure_server()
        ensure_model()
        write_env_hint()
        print()
        print(f"Selected size: {_size} -> {MODEL_NAME}")
        print("Next:")
        print("  1) start_llamacpp.bat")
        print("  2) check_brain.bat")
        print("  3) open_system.bat")
        print("For stronger local brain: set COS_LLAMA_SIZE=7b then re-run, or setup_llamacpp_7b.bat")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
