import os
import time
import asyncio
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv
from es_main import answer_question # Đã đổi tên file import

# Tải các biến môi trường từ tệp .env
load_dotenv()

# --- Cấu hình ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7201416424:AAHLwyzpJoyzr5A7CdmLxmrv1ZYe4HjcnvY")

# --- Hàm tiện ích để xử lý MarkdownV2 ---
def escape_markdown_v2(text: str) -> str:
    """Thoát các ký tự đặc biệt cho chế độ MarkdownV2 của Telegram."""
    # Các ký tự cần được thoát theo tài liệu của Telegram
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Sử dụng re.sub() để thay thế tất cả các ký tự trong danh sách bằng phiên bản đã được thoát
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# --- Các hàm xử lý lệnh (Command Handlers) ---
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi tin nhắn chào mừng khi người dùng gõ /start."""
    await update.message.chat.send_action("typing")
    welcome_text = (
        "<b>Chào mừng bạn đến với Trợ lý AI Cố vấn học tập!</b>\n\n"
        "Tôi có thể hỗ trợ bạn tra cứu điểm số, xếp hạng, và phân tích tình hình học tập của học sinh.\n\n"
        "Gõ <b>/help</b> để xem danh sách lệnh hỗ trợ.\n"
        "Gõ <b>/clear</b> để xoá lịch sử cuộc trò chuyện."
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML')


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị danh sách các lệnh hỗ trợ khi người dùng gõ /help."""
    await update.message.chat.send_action("typing")
    help_text = (
        "<b>Danh sách lệnh hỗ trợ:</b>\n\n"
        "<b>/start</b> - Bắt đầu trò chuyện với bot\n"
        "<b>/help</b> - Hiển thị hướng dẫn sử dụng\n"
        "<b>/clear</b> - Xoá các tin nhắn trong cuộc trò chuyện hiện tại\n\n"
        "Bạn cũng có thể gửi tin nhắn để trò chuyện trực tiếp."
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /history (hiện là placeholder)."""
    await update.message.chat.send_action("typing")
    await update.message.reply_text("Chức năng xem lịch sử đang được phát triển.")


async def handle_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xoá các tin nhắn đã được bot ghi lại trong cuộc trò chuyện."""
    chat_id = update.message.chat_id
    messages_to_delete = context.chat_data.get('messages_to_delete', [])
    
    if not messages_to_delete:
        await update.message.reply_text("Không có tin nhắn nào gần đây để xoá.")
        return

    messages_to_delete.append(update.message.message_id)
    
    count = 0
    for message_id in messages_to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            count += 1
        except Exception as e:
            print(f"Không thể xoá tin nhắn {message_id} trong chat {chat_id}: {e}")

    context.chat_data['messages_to_delete'] = []
    context.chat_data['history'] = []
    
    confirmation_msg = await update.message.reply_text(f"Đã xoá thành công {count} tin nhắn.")
    await asyncio.sleep(5)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=confirmation_msg.message_id)
    except Exception as e:
        print(f"Không thể xoá tin nhắn xác nhận: {e}")

# --- Hàm xử lý tin nhắn chính ---

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn văn bản thông thường từ người dùng."""
    user_message = update.message.text
    chat_id = update.message.chat_id

    history_chat = context.chat_data.get('history', [])
    messages_to_delete = context.chat_data.get('messages_to_delete', [])
    
    if not history_chat:
        history_chat.extend([
            {"role": "user", "parts": ["Xin chào, bạn là ai?"]},
            {"role": "model", "parts": ["Xin chào! Tôi là Cố vấn học tập ảo, tôi có thể giúp bạn tra cứu thông tin về tình hình học tập của các em học sinh."]}
        ])
    
    messages_to_delete.append(update.message.message_id)

    answer = ""
    start_time = time.time()

    try:
        await update.message.chat.send_action("typing")
        
        answer = answer_question(user_message, history_chat)

        history_chat.append({"role": "user", "parts": [user_message]})
        history_chat.append({"role": "model", "parts": [answer]})
        
        context.chat_data['history'] = history_chat[-20:]
        
    except Exception as e:
        print(f"Lỗi khi gọi AI cho chat {chat_id}: {e}")
        answer = "Rất tiếc, đã có lỗi xảy ra. Vui lòng thử lại."

    end_time = time.time()
    elapsed = end_time - start_time
    
    # THAY ĐỔI QUAN TRỌNG: Thoát các ký tự đặc biệt trong câu trả lời của AI
    escaped_answer = escape_markdown_v2(answer)
    
    # Gắn thông tin thời gian vào cuối câu trả lời đã được thoát ký tự
    final_reply_text = f"{escaped_answer}\n\n*Thời gian phản hồi:* `{elapsed:.2f} giây`"

    reply_message = await update.message.reply_text(final_reply_text, parse_mode='MarkdownV2')
    
    messages_to_delete.append(reply_message.message_id)
    context.chat_data['messages_to_delete'] = messages_to_delete


def main():
    """Hàm chính để khởi chạy bot."""
    if not TELEGRAM_TOKEN or "YOUR_FALLBACK_TOKEN_HERE" in TELEGRAM_TOKEN:
        print("Vui lòng đặt TELEGRAM_TOKEN hợp lệ trong code hoặc tệp .env!")
        return

    print("Xây dựng ứng dụng...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Đăng ký các handler
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("history", handle_history))
    app.add_handler(CommandHandler("clear", handle_clear))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))

    print("Bot đang chạy...")
    app.run_polling()


if __name__ == '__main__':
    main()

