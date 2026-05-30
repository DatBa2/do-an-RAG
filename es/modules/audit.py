"""Audit log SQLite: ghi mọi truy vấn của user.

Schema:
- id INTEGER PRIMARY KEY
- ts REAL
- chat_id INTEGER
- role TEXT
- question TEXT
- tools_called TEXT (JSON list)
- answer TEXT
- latency_ms INTEGER
- success INTEGER
"""
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

from modules import config

log = logging.getLogger("audit")

_AUDIT_PATH = config.PROJECT_ROOT / "data" / "audit.db"


class AuditLog:
    def __init__(self, path: Path = _AUDIT_PATH) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    question TEXT NOT NULL,
                    tools_called TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    success INTEGER NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_chat ON audit(chat_id, ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts)")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def log_query(
        self,
        chat_id: int,
        role: str,
        question: str,
        tools_called: Iterable[str],
        answer: str,
        latency_ms: int,
        success: bool,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO audit
                   (ts, chat_id, role, question, tools_called, answer, latency_ms, success)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    time.time(),
                    chat_id,
                    role,
                    question,
                    json.dumps(list(tools_called), ensure_ascii=False),
                    answer,
                    int(latency_ms),
                    1 if success else 0,
                ),
            )

    def recent(self, limit: int = 100, chat_id: Optional[int] = None) -> List[dict]:
        sql = "SELECT id, ts, chat_id, role, question, tools_called, answer, latency_ms, success FROM audit"
        params: tuple = ()
        if chat_id is not None:
            sql += " WHERE chat_id=?"
            params = (chat_id,)
        sql += " ORDER BY ts DESC LIMIT ?"
        params = params + (limit,)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        cols = ("id", "ts", "chat_id", "role", "question", "tools_called", "answer", "latency_ms", "success")
        return [dict(zip(cols, r)) for r in rows]

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
            avg = conn.execute("SELECT AVG(latency_ms) FROM audit").fetchone()[0] or 0
            succ = conn.execute("SELECT SUM(success) FROM audit").fetchone()[0] or 0
            by_role = dict(
                conn.execute("SELECT role, COUNT(*) FROM audit GROUP BY role").fetchall()
            )
        return {
            "total": total,
            "success": succ,
            "success_rate": round(succ / total, 3) if total else 0.0,
            "avg_latency_ms": round(avg, 1),
            "by_role": by_role,
        }


AUDIT = AuditLog()
