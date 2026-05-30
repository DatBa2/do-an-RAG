"""Centralized configuration loader.

Reads .env (next to es_main.py) and exposes typed config values.
Fail fast at startup if a required value is missing.
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _csv_int_set(raw: str) -> set:
    if not raw:
        return set()
    out = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.add(int(token))
        except ValueError:
            pass
    return out


# --- Elasticsearch ---
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX", "hs_records")
BULK_BATCH_SIZE = int(os.getenv("BULK_BATCH_SIZE", "1000"))

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- Telegram ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_ALLOWED_IDS = _csv_int_set(os.getenv("TELEGRAM_ALLOWED_IDS", ""))
TELEGRAM_ADMIN_IDS = _csv_int_set(os.getenv("TELEGRAM_ADMIN_IDS", ""))
TELEGRAM_ALLOW_ALL = os.getenv("TELEGRAM_ALLOW_ALL", "false").lower() == "true"

# --- Paths ---
DATA_DIR = os.getenv("DATA_DIR", str(PROJECT_ROOT / "organized_results"))
HISTORY_DB = Path(os.getenv("HISTORY_DB", str(PROJECT_ROOT / "data" / "chat_history.db")))
TIMESTAMP_FILE = PROJECT_ROOT / ".last_run_timestamp"
SYNONYMS_FILE = Path(__file__).resolve().parent / "synonyms.json"

# --- Other ---
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "20"))
MAX_CLASS_SIZE = int(os.getenv("MAX_CLASS_SIZE", "300"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)


def require_gemini() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY chưa được đặt trong .env")


def require_telegram() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN chưa được đặt trong .env")
    if not TELEGRAM_ALLOW_ALL and not TELEGRAM_ALLOWED_IDS and not TELEGRAM_ADMIN_IDS:
        raise RuntimeError(
            "Bot chưa có whitelist. Đặt TELEGRAM_ALLOWED_IDS / TELEGRAM_ADMIN_IDS, "
            "hoặc TELEGRAM_ALLOW_ALL=true cho chế độ demo."
        )


def is_allowed_chat(chat_id: int) -> bool:
    if TELEGRAM_ALLOW_ALL:
        return True
    return chat_id in TELEGRAM_ALLOWED_IDS or chat_id in TELEGRAM_ADMIN_IDS


def is_admin_chat(chat_id: int) -> bool:
    return chat_id in TELEGRAM_ADMIN_IDS
