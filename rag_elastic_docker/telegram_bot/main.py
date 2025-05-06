import requests  # Thêm dòng này để import thư viện requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters
from search_by_gemini import search_and_respond

TELEGRAM_TOKEN = '7201416424:AAHLwyzpJoyzr5A7CdmLxmrv1ZYe4HjcnvY'
CHAT_ID = '6554124253'

API_URL = 'http://localhost:8000/search'

async def chat_bot_bt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Trường hợp 1: Nếu người dùng gửi tin nhắn trực tiếp với bot
    if update.message.chat.type == 'private':  # Bot đang nhận tin nhắn từ chat riêng
        if update.message.text.startswith('/chat_bot'):
            user_message = ' '.join(update.message.text.split()[1:])  # Lấy câu hỏi từ sau /chat_bot
            print(user_message)
        else:  
            user_message = update.message.text
            print(user_message)

            try:
                # Gửi thông báo đang "typing"
                await update.message.chat.send_action("typing")

                # Gọi API với query
                reply_text = search_and_respond(user_message)
                # response.raise_for_status()
                # data = response.json()
                # reply_text = data.get("results", "⚠️ API không trả về kết quả.")
            except Exception as e:
                reply_text = f"🚫 Lỗi khi gọi API: {e}"
            await update.message.reply_text(reply_text[:4000])

    # Trường hợp 2: Nếu người dùng gửi tin nhắn trong nhóm và có lệnh /chat_bot
    elif update.message.chat.type == 'supergroup' or update.message.chat.type == 'group':  # Bot nhận tin nhắn từ nhóm
        if update.message.text.startswith('/chat_bot'):
            user_message = ' '.join(update.message.text.split()[1:])  # Lấy câu hỏi từ sau /chat_bot
            print(user_message)

            try:
                # Gửi thông báo đang "typing"
                await update.message.chat.send_action("typing")

                # Gọi API với query
                response = requests.get(API_URL, params={"q": user_message}, timeout=10)
                response.raise_for_status()
                data = response.json()
                reply_text = data.get("results", "⚠️ API không trả về kết quả.")
            except Exception as e:
                reply_text = f"🚫 Lỗi khi gọi API: {e}"

            # ✅ Phản hồi người dùng trong nhóm
            await update.message.reply_text(reply_text[:4000])

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_bot_bt))
    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
