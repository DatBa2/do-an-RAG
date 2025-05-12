import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters
from search_by_gemini import search_and_respond, chat_and_respond

TELEGRAM_TOKEN = '7201416424:AAHLwyzpJoyzr5A7CdmLxmrv1ZYe4HjcnvY'
ALLOWED_USER_IDS = [6554124253]

# /start - Chào mừng người dùng
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    welcome_text = (
        "<b>Chào mừng bạn đến với Trợ lý AI của Nguyễn Bá Đạt!</b>\n\n"
        "Tôi có thể hỗ trợ bạn trả lời câu hỏi, truy xuất dữ liệu nội bộ (nếu bạn có quyền), "
        "và lưu lịch sử trò chuyện.\n\n"
        "Gõ <b>/help</b> để xem danh sách lệnh hỗ trợ."
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML')

# /help - Hiển thị danh sách lệnh
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    help_text = (
        "<b>Danh sách lệnh hỗ trợ:</b>\n\n"
        "<b>/start</b> - Bắt đầu trò chuyện với bot\n"
        "<b>/help</b> - Hiển thị hướng dẫn sử dụng\n"
        "<b>/noi_bo [câu hỏi]</b> - Tìm kiếm dữ liệu nội bộ\n"
        "<b>/history</b> - Lấy lịch sử trò chuyện gần đây\n\n"
        "Bạn cũng có thể gửi tin nhắn để trò chuyện trực tiếp."
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# /noi_bo - Xử lý tìm kiếm nội bộ
async def handle_noi_bo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Bạn không có quyền truy cập vào dữ liệu nội bộ.")
        return

    user_message = ' '.join(context.args)
    if not user_message:
        await update.message.reply_text("Vui lòng nhập câu hỏi sau lệnh /noi_bo.")
        return

    try:
        await update.message.chat.send_action("typing")
        reply_text = search_and_respond(user_message, 0, user_id)
    except Exception as e:
        reply_text = f"Lỗi khi truy vấn dữ liệu nội bộ: {e}"

    await update.message.reply_text(reply_text[:4000])

# /history - Hiển thị lịch sử (tạm thời)
async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    await update.message.reply_text("Chức năng xem lịch sử đang được phát triển.")

# Xử lý tin nhắn thông thường
async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        await update.message.chat.send_action("typing")
        reply_text = chat_and_respond(user_message, 0, update.effective_user.id)
    except Exception as e:
        reply_text = f"Lỗi khi gọi AI: {e}"

    await update.message.reply_text(reply_text[:4000])

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("noi_bo", handle_noi_bo))
    app.add_handler(CommandHandler("history", handle_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
