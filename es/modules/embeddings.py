"""Wrapper cho Gemini embedding API kèm SQLite cache.

Cache giúp:
- Tránh re-embed khi reindex (tiết kiệm cost + thời gian).
- Cho phép chạy evaluation lặp lại deterministically.
"""
import hashlib
import logging
import sqlite3
import struct
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

import google.generativeai as genai

from modules import config

log = logging.getLogger("embeddings")

EMBED_MODEL = "models/gemini-embedding-001"
EMBED_DIM = 768

_CACHE_PATH = config.PROJECT_ROOT / "data" / "embed_cache.db"


def _ensure_genai_configured() -> None:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY chưa được đặt.")
    genai.configure(api_key=config.GEMINI_API_KEY)


class EmbedCache:
    def __init__(self, path: Path = _CACHE_PATH) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS embed_cache (
                    key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    task TEXT NOT NULL,
                    vec BLOB NOT NULL
                )"""
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _key(text: str, task: str, model: str) -> str:
        h = hashlib.sha256()
        h.update(model.encode())
        h.update(b"|")
        h.update(task.encode())
        h.update(b"|")
        h.update(text.encode("utf-8"))
        return h.hexdigest()

    @staticmethod
    def _pack(vec: List[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack(blob: bytes) -> List[float]:
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def get(self, text: str, task: str, model: str) -> Optional[List[float]]:
        key = self._key(text, task, model)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT vec FROM embed_cache WHERE key=?", (key,)
            ).fetchone()
        return self._unpack(row[0]) if row else None

    def put(self, text: str, task: str, model: str, vec: List[float]) -> None:
        key = self._key(text, task, model)
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO embed_cache(key,model,task,vec) VALUES (?,?,?,?)",
                (key, model, task, self._pack(vec)),
            )

    def stats(self) -> dict:
        with self._conn() as conn:
            n = conn.execute("SELECT COUNT(*) FROM embed_cache").fetchone()[0]
        return {"entries": n, "path": str(self.path)}


_CACHE = EmbedCache()


def embed_text(text: str, task_type: str = "retrieval_document") -> List[float]:
    """Embed 1 chuỗi văn bản. task_type='retrieval_query' khi search."""
    _ensure_genai_configured()
    cached = _CACHE.get(text, task_type, EMBED_MODEL)
    if cached is not None:
        return cached
    result = genai.embed_content(
        model=EMBED_MODEL, content=text, task_type=task_type,
        output_dimensionality=EMBED_DIM,
    )
    vec = list(result["embedding"])
    _CACHE.put(text, task_type, EMBED_MODEL, vec)
    return vec


def embed_batch(
    texts: List[str], task_type: str = "retrieval_document"
) -> List[List[float]]:
    """Embed nhiều chuỗi. Dùng cache khi có thể, gọi API cho phần còn lại."""
    _ensure_genai_configured()
    results: List[Optional[List[float]]] = [None] * len(texts)
    pending_idx: List[int] = []
    pending_text: List[str] = []
    for i, t in enumerate(texts):
        v = _CACHE.get(t, task_type, EMBED_MODEL)
        if v is not None:
            results[i] = v
        else:
            pending_idx.append(i)
            pending_text.append(t)

    if pending_text:
        log.info("Embedding %d/%d items (cache hit %d).",
                 len(pending_text), len(texts), len(texts) - len(pending_text))
        # API embed_content xử lý từng item; với batch lớn nên gọi tuần tự để tránh quota burst
        for idx, text in zip(pending_idx, pending_text):
            r = genai.embed_content(
                model=EMBED_MODEL, content=text, task_type=task_type,
                output_dimensionality=EMBED_DIM,
            )
            vec = list(r["embedding"])
            _CACHE.put(text, task_type, EMBED_MODEL, vec)
            results[idx] = vec
    else:
        log.info("Embedding: tất cả %d items lấy từ cache.", len(texts))

    return results  # type: ignore[return-value]


def cache_stats() -> dict:
    return _CACHE.stats()
