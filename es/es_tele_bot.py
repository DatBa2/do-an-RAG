"""Telegram bot front-end với RBAC, audit log, citation, history persist."""
import asyncio
import html
import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, List

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from elasticsearch import Elasticsearch

from modules import config
from modules.audit import AUDIT
from modules.rbac import role_of
from modules.ingest_docs import ES_DOCS_INDEX, ingest_documents
import es_index
from es_main import AdvisorContext, get_advisor

config.configure_logging()
log = logging.getLogger("bot")

config.require_telegram()


# --- SQLite history store ---
class HistoryStore:
    def __init__(self, db_path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS chat_history (
                    chat_id INTEGER NOT NULL,
                    ts REAL NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    PRIMARY KEY (chat_id, ts)
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON chat_history(chat_id, ts)")

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def append(self, chat_id: int, role: str, text: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chat_history(chat_id, ts, role, text) VALUES (?,?,?,?)",
                (chat_id, time.time(), role, text),
            )

    def load(self, chat_id: int, turns: int) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, text FROM chat_history WHERE chat_id=? ORDER BY ts DESC LIMIT ?",
                (chat_id, turns * 2),
            ).fetchall()
        rows.reverse()
        return [{"role": r, "parts": [t]} for r, t in rows]

    def clear(self, chat_id: int) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM chat_history WHERE chat_id=?", (chat_id,))
            return cur.rowcount


HISTORY = HistoryStore(config.HISTORY_DB)


def bootstrap_index() -> None:
    es = Elasticsearch(config.ES_HOST, request_timeout=30)
    try:
        if not es.ping():
            log.warning("ES chưa sẵn sàng tại %s.", config.ES_HOST)
            return
    except Exception as e:
        log.warning("Không kết nối được ES: %s", e)
        return
    if not es.indices.exists(index=config.ES_INDEX):
        log.warning("Index %s chưa có — chạy full-refresh.", config.ES_INDEX)
        es_index.create_index()
        es_index.bulk_index_from_dir(full_refresh=True)
    if not es.indices.exists(index=ES_DOCS_INDEX):
        log.warning("Index %s chưa có — chạy ingest documents.", ES_DOCS_INDEX)
        try:
            ingest_documents(recreate=False)
        except Exception as e:
            log.warning("Ingest docs lỗi: %s", e)


def _guard(update: Update) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    if not config.is_allowed_chat(chat.id):
        log.info("Chặn chat_id chưa được phép: %s", chat.id)
        return False
    return True


async def _send_denied(update: Update) -> None:
    chat = update.effective_chat
    if not chat:
        return
    await update.message.reply_text(
        f"❌ Chat ID <code>{chat.id}</code> chưa được cấp quyền.\n"
        "Liên hệ admin để được thêm vào whitelist.",
        parse_mode="HTML",
    )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        await _send_denied(update)
        return
    role = role_of(update.effective_chat.id)
    await update.message.chat.send_action(ChatAction.TYPING)
    text = (
        "<b>👩‍🏫 Cố vấn học tập ảo</b>\n\n"
        f"Bạn đang đăng nhập với vai trò: <b>{role}</b>\n\n"
        "Tôi có thể giúp:\n"
        "• Tra cứu điểm, hạnh kiểm, chuyên cần, xếp hạng\n"
        "• Top học sinh, điểm TB lớp, xu hướng học tập\n"
        "• Tra cứu nội quy, quy định, lịch học, học phí\n\n"
        "Gõ <b>/help</b> để xem lệnh • <b>/clear</b> xoá lịch sử"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        await _send_denied(update)
        return
    text = (
        "<b>Lệnh:</b>\n"
        "/start • /help • /clear • /whoami • /stats\n\n"
        "<b>Ví dụ câu hỏi điểm số:</b>\n"
        "• Điểm Toán của Lê Nguyễn Minh Trí lớp 7A10\n"
        "• Top 5 lớp 7A10 học kỳ 2\n"
        "• Em Trí thế mạnh môn nào?\n"
        "• So sánh Trí với Nam lớp 7A10\n\n"
        "<b>Ví dụ câu hỏi tài liệu:</b>\n"
        "• Quy định nghỉ học không phép thế nào?\n"
        "• Học phí lớp 7 năm 2024-2025 bao nhiêu?\n"
        "• Lịch kiểm tra cuối kỳ 2 khi nào?\n"
        "• Tiêu chí xếp hạnh kiểm Tốt là gì?"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    role = role_of(chat.id)
    text = (
        f"<b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"<b>User ID:</b> <code>{user.id if user else '?'}</code>\n"
        f"<b>Role:</b> <code>{role}</code>\n"
        f"<b>Trạng thái:</b> "
        + ("✅ được phép" if config.is_allowed_chat(chat.id) else "❌ chưa được phép")
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        await _send_denied(update)
        return
    n = HISTORY.clear(update.effective_chat.id)
    await update.message.reply_text(f"🧹 Đã xoá {n} dòng lịch sử.", parse_mode="HTML")


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        await _send_denied(update)
        return
    if not config.is_admin_chat(update.effective_chat.id):
        await update.message.reply_text("Chỉ admin xem được stats.")
        return
    s = AUDIT.stats()
    text = (
        f"<b>📊 Audit stats</b>\n"
        f"Total queries: <code>{s['total']}</code>\n"
        f"Success: <code>{s['success']}</code> ({s['success_rate']*100:.1f}%)\n"
        f"Avg latency: <code>{s['avg_latency_ms']} ms</code>\n"
        f"By role: <code>{s['by_role']}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _guard(update):
        await _send_denied(update)
        return

    chat_id = update.effective_chat.id
    user_message = (update.message.text or "").strip()
    if not user_message:
        return
    role = role_of(chat_id)

    await update.message.chat.send_action(ChatAction.TYPING)
    history = HISTORY.load(chat_id, config.HISTORY_TURNS)

    try:
        loop = asyncio.get_running_loop()
        advisor = get_advisor()
        result = await loop.run_in_executor(
            None,
            lambda: advisor.answer(
                user_message, list(history), AdvisorContext(role=role, rewrite=True)
            ),
        )
    except Exception:
        log.exception("Lỗi xử lý chat %s", chat_id)
        AUDIT.log_query(chat_id, role, user_message, [], "", 0, False)
        await update.message.reply_text("❌ Đã có lỗi xử lý câu hỏi.")
        return

    HISTORY.append(chat_id, "user", user_message)
    HISTORY.append(chat_id, "model", result.answer)
    AUDIT.log_query(
        chat_id, role, user_message, result.tools_called,
        result.answer, result.elapsed_ms, result.success,
    )

    safe = html.escape(result.answer)
    footer_bits = [f"⏱ {result.elapsed_ms/1000:.2f}s"]
    if result.tools_called:
        footer_bits.append(f"🔧 {len(result.tools_called)} tool")
    if result.citations:
        footer_bits.append(f"📚 {len(result.citations)} nguồn")
    text = f"{safe}\n\n<i>{' • '.join(footer_bits)}</i>"

    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)


def build_app() -> Application:
    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("whoami", handle_whoami))
    app.add_handler(CommandHandler("clear", handle_clear))
    app.add_handler(CommandHandler("stats", handle_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    bootstrap_index()
    app = build_app()
    log.info(
        "Bot khởi động. allow_all=%s allowed=%s admins=%s",
        config.TELEGRAM_ALLOW_ALL,
        sorted(config.TELEGRAM_ALLOWED_IDS),
        sorted(config.TELEGRAM_ADMIN_IDS),
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
