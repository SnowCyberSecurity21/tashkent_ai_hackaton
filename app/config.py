"""Settings from environment / .env (never hard-code keys)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
UPLOAD_DIR = DATA_DIR / "uploads"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except Exception:  # python-dotenv missing: rely on the real environment
    pass


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip().strip('"').strip("'")


DEMO_MODE = _env("DEMO_MODE", "1") == "1"
DB_PATH = Path(_env("MEZON_DB", str(ROOT / "mezon.db")))

LLM_PROVIDER = _env("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_FALLBACK_MODEL = _env("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ANTHROPIC_FALLBACK_MODEL = _env("ANTHROPIC_FALLBACK_MODEL", "claude-haiku-5-5")
LLM_TIMEOUT_S = float(_env("LLM_TIMEOUT_S", "20"))
# MEZON_LLM_OFFLINE=1 forces the precomputed path (used by tests and offline demos)
LLM_OFFLINE = _env("MEZON_LLM_OFFLINE", "0") == "1"

DEFAULT_CITY = "Toshkent"
CONSULT_UZ = "Shifokor yoki farmatsevt bilan maslahatlashing."
