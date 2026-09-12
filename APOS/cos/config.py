"""إعدادات العقل — Ollama محلي أولاً، ثم OpenRouter/Anthropic اختياري."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# مفاتيح سحابية من جذر المشروع أولاً، ثم إعدادات APOS تتجاوزها
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env", override=True)

DATA = ROOT / "data"
EXPERIENCE_DIR = DATA / "experience"
LOGS_DIR = DATA / "logs"
WORKFLOWS_DIR = ROOT / "workflows"
SCREENSHOTS_DIR = DATA / "screenshots"
REPORTS_DIR = DATA / "reports"
DB_DIR = DATA / "db"
QDRANT_PATH = DATA / "qdrant"
ACTIVITY_LOG = LOGS_DIR / "activity.jsonl"

for d in (
    EXPERIENCE_DIR,
    LOGS_DIR,
    SCREENSHOTS_DIR,
    WORKFLOWS_DIR,
    REPORTS_DIR,
    DB_DIR,
    QDRANT_PATH,
):
    d.mkdir(parents=True, exist_ok=True)

WATCH_INTERVAL_MS = int(os.getenv("COS_WATCH_INTERVAL_MS", "800"))
CONFIDENCE_MIN = float(os.getenv("COS_CONFIDENCE_MIN", "0.55"))
LEARN_MODE = os.getenv("COS_LEARN_MODE", "1").strip() in ("1", "true", "yes")
REQUIRE_CONFIRM_RISKY = os.getenv("COS_REQUIRE_CONFIRM_RISKY", "1").strip() in (
    "1",
    "true",
    "yes",
)

_ws = os.getenv("COS_WORKSPACE", "").strip()
WORKSPACE = Path(_ws) if _ws else (Path.home() / "Documents" / "COS_Projects")
WORKSPACE.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("COS_DATABASE_URL", "").strip()
SQLITE_PATH = Path(os.getenv("COS_SQLITE_PATH", str(DB_DIR / "cos.db")))
REDIS_URL = os.getenv("COS_REDIS_URL", "redis://127.0.0.1:6379/0").strip()
QDRANT_URL = os.getenv("COS_QDRANT_URL", "").strip()
QDRANT_COLLECTION = os.getenv("COS_QDRANT_COLLECTION", "cos_experience")
TIMESCALE_ENABLED = os.getenv("COS_TIMESCALE", "0").strip() in ("1", "true", "yes")
VECTOR_DIM = int(os.getenv("COS_VECTOR_DIM", "384"))

BLOCKLIST_PATH = DATA / "blocklist.txt"
PERMISSIONS_PATH = DATA / "permissions.yaml"

AUTO_RESEARCH = os.getenv("COS_AUTO_RESEARCH", "1").strip() in ("1", "true", "yes")
AUTO_RESEARCH_RETRIES = int(os.getenv("COS_AUTO_RESEARCH_RETRIES", "2"))
AUTO_CLAUDE_ESCALATE = os.getenv("COS_AUTO_CLAUDE_ESCALATE", "0").strip() in (
    "1",
    "true",
    "yes",
)

# —— العقل ——
# auto = سحابة قوية أولاً ثم محلي
BRAIN_PROVIDER = os.getenv("COS_BRAIN_PROVIDER", "auto").strip().lower() or "auto"
# llama.cpp server (OpenAI-compatible) — احتياطي محلي
LLAMA_CPP_HOST = os.getenv("COS_LLAMA_CPP_HOST", "http://127.0.0.1:8080").strip()
LLAMA_CPP_MODEL = os.getenv("COS_LLAMA_CPP_MODEL", "qwen2.5-3b-instruct").strip()
LLAMA_CPP_API_KEY = os.getenv("COS_LLAMA_CPP_API_KEY", "no-key").strip() or "no-key"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
OLLAMA_MODEL = os.getenv("COS_OLLAMA_MODEL", "qwen2.5:7b").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv(
    "COS_OPENROUTER_MODEL", "openai/gpt-4o-mini"
).strip()
OPENROUTER_BASE = os.getenv(
    "OPENROUTER_BASE", "https://openrouter.ai/api/v1"
).strip()
# OpenAI — GPT-4o-mini رخيص وسريع
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("COS_OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com/v1").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5").strip()
# للأوامر المعقّدة: افتراضياً نفس الرخيص
ANTHROPIC_COMPLEX_MODEL = os.getenv(
    "COS_ANTHROPIC_COMPLEX_MODEL", "claude-haiku-4-5"
).strip() or ANTHROPIC_MODEL
BRAIN_TIMEOUT = float(os.getenv("COS_BRAIN_TIMEOUT", "60"))
BRAIN_MAX_TOKENS = int(os.getenv("COS_BRAIN_MAX_TOKENS", "700"))
# لا تستخدم المحلي للعقل إن وُجدت سحابة
CLOUD_ONLY_BRAIN = os.getenv("COS_CLOUD_ONLY_BRAIN", "1").strip() in (
    "1",
    "true",
    "yes",
)
USE_BRAIN_PLANNER = os.getenv("COS_USE_BRAIN_PLANNER", "1").strip() in (
    "1",
    "true",
    "yes",
)
# عقل: openai | anthropic | openrouter | auto | ...
COMPLEX_BRAIN_PROVIDER = (
    os.getenv("COS_COMPLEX_BRAIN", "auto").strip().lower() or "auto"
)
CLARIFY_BEFORE_EXECUTE = os.getenv("COS_CLARIFY_BEFORE_EXECUTE", "1").strip() in (
    "1",
    "true",
    "yes",
)
SESSION_MEMORY = os.getenv("COS_SESSION_MEMORY", "1").strip() in ("1", "true", "yes")
# صوت: small افتراضي؛ medium أدق وأبطأ قليلاً
WHISPER_MODEL = os.getenv("COS_WHISPER_MODEL", "small").strip() or "small"
STT_ENGINE = os.getenv("COS_STT_ENGINE", "auto").strip().lower() or "auto"

# —— منفّذ QuantConnect المباشر (API) ——
QC_USER_ID = os.getenv("QC_USER_ID", "").strip()
QC_API_TOKEN = os.getenv("QC_API_TOKEN", "").strip()
QC_PROJECT_NAME = os.getenv("QC_PROJECT_NAME", "MatrixRobotQC").strip() or "MatrixRobotQC"
QC_PREFER_API = os.getenv("COS_QC_PREFER_API", "1").strip() in ("1", "true", "yes")
