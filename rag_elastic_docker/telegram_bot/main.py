import requests
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters
from search_by_gemini import search_and_respond, chat_and_respond
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = '7201416424:AAHLwyzpJoyzr5A7CdmLxmrv1ZYe4HjcnvY'
ALLOWED_USER_IDS = [6554124253]

# Tạo danh sách để lưu trữ message_id của các tin nhắn bot đã gửi
sent_messages = []

# /start - Chào mừng người dùng
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    welcome_text = (
        "<b>Chào mừng bạn đến với Trợ lý AI của Nguyễn Bá Đạt!</b>\n\n"
        "Tôi có thể hỗ trợ bạn trả lời câu hỏi, truy xuất dữ liệu nội bộ (nếu bạn có quyền), "
        "và lưu lịch sử trò chuyện.\n\n"
        "Gõ <b>/help</b> để xem danh sách lệnh hỗ trợ."
    )
    new_message = await update.message.reply_text(welcome_text, parse_mode='HTML')
    # Lưu message_id của tin nhắn bot đã gửi
    sent_messages.append(new_message.message_id)

# /help - Hiển thị danh sách lệnh
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    help_text = (
        "<b>Danh sách lệnh hỗ trợ:</b>\n\n"
        "<b>/start</b> - Bắt đầu trò chuyện với bot\n"
        "<b>/help</b> - Hiển thị hướng dẫn sử dụng\n"
        "<b>/noi_bo [câu hỏi]</b> - Tìm kiếm dữ liệu nội bộ\n"
        "<b>/history</b> - Lấy lịch sử trò chuyện gần đây\n"
        "<b>/jira</b> - Xem danh sách ticket Jira mới nhất\n"
        "<b>/jira_login [tài khoản] [mật khẩu]</b> - Đăng nhập vào Jira và xem ticket của bạn\n\n"
        "<b>Lưu ý:</b>\n"
        "  - Lệnh /jira yêu cầu bạn phải có quyền truy cập Jira của VNPT.\n"
        "  - Lệnh /jira_login yêu cầu tài khoản và mật khẩu của bạn.\n"
        "Bạn cũng có thể gửi tin nhắn để trò chuyện trực tiếp."
    )
    new_message = await update.message.reply_text(help_text, parse_mode='HTML')
    sent_messages.append(new_message.message_id)

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

    new_message = await update.message.reply_text(reply_text[:4000])
    sent_messages.append(new_message.message_id)

# Xóa tất cả tin nhắn đã gửi
async def delete_previous_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for message_id in sent_messages:
        try:
            await update.message.chat.delete_message(message_id)
        except Exception as e:
            print(f"Không thể xóa tin nhắn với message_id {message_id}: {e}")
    sent_messages.clear()

# Xử lý lệnh /new_chat
async def handle_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Xóa tất cả các tin nhắn trước đó
    await delete_previous_messages(update, context)

    # Gửi lại thông báo chào mừng như khi bắt đầu trò chuyện mới
    welcome_text = (
        "<b>Chào mừng bạn đến với Trợ lý AI của Nguyễn Bá Đạt!</b>\n\n"
        "Tôi có thể hỗ trợ bạn trả lời câu hỏi, truy xuất dữ liệu nội bộ (nếu bạn có quyền), "
        "và lưu lịch sử trò chuyện.\n\n"
        "Gõ <b>/help</b> để xem danh sách lệnh hỗ trợ."
    )
    new_message = await update.message.reply_text(welcome_text, parse_mode='HTML')
    sent_messages.append(new_message.message_id)

async def handle_jira(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Bạn không có quyền truy cập Jira.")
        return

    await update.message.chat.send_action("typing")

    try:
        # Lấy thông tin xác thực từ biến môi trường (hoặc file .env)
        jira_user = os.getenv("JIRA_USERNAME", "your_username")
        jira_pass = os.getenv("JIRA_PASSWORD", "your_password")
        jira_url = "https://cntt.vnpt.vn/rest/api/2/search"
        project_key = "VNPTEDU"

        params = {
            "jql": f"project={project_key} ORDER BY created DESC",
            "maxResults": 5
        }

        response = requests.get(jira_url, params=params, auth=HTTPBasicAuth(jira_user, jira_pass))

        if response.status_code == 200:
            issues = response.json().get("issues", [])
            if not issues:
                await update.message.reply_text("Không tìm thấy ticket nào.")
                return

            message = "<b>Danh sách ticket Jira mới nhất:</b>\n\n"
            for issue in issues:
                key = issue["key"]
                summary = issue["fields"]["summary"]
                status = issue["fields"]["status"]["name"]
                message += f"🔹 <b>{key}</b> | {status}\n➡️ {summary}\n\n"

            await update.message.reply_text(message[:4000], parse_mode="HTML")
        else:
            await update.message.reply_text(f"Lỗi gọi Jira API: {response.status_code}\n{response.text}")
    except Exception as e:
        await update.message.reply_text(f"Lỗi khi gọi Jira: {e}")

async def handle_jira_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("Bạn không có quyền truy cập Jira.")
        return

    # Kiểm tra xem người dùng đã nhập đủ tài khoản và mật khẩu chưa
    if len(context.args) != 2:
        await update.message.reply_text("Vui lòng nhập tài khoản và mật khẩu như sau: /jira_login [tài khoản] [mật khẩu]")
        return

    jira_user = context.args[0]
    jira_pass = context.args[1]

    try:
        # Xử lý xác thực với tài khoản và mật khẩu mới
        jira_url = "https://cntt.vnpt.vn/rest/api/2/search"
        project_key = "VNPTEDU"

        params = {
            "jql": f"project={project_key} ORDER BY created DESC",
            "maxResults": 5
        }

        response = requests.get(jira_url, params=params, auth=HTTPBasicAuth(jira_user, jira_pass))

        if response.status_code == 200:
            issues = response.json().get("issues", [])
            if not issues:
                await update.message.reply_text("Không tìm thấy ticket nào.")
                return

            message = "<b>Danh sách ticket Jira mới nhất:</b>\n\n"
            for issue in issues:
                key = issue["key"]
                summary = issue["fields"]["summary"]
                status = issue["fields"]["status"]["name"]
                message += f"🔹 <b>{key}</b> | {status}\n➡️ {summary}\n\n"

            await update.message.reply_text(message[:4000], parse_mode="HTML")
        else:
            await update.message.reply_text(f"Lỗi gọi Jira API: {response.status_code}\n{response.text}")
    except Exception as e:
        await update.message.reply_text(f"Lỗi khi gọi Jira: {e}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("noi_bo", handle_noi_bo))
    app.add_handler(CommandHandler("history", handle_history))
    app.add_handler(CommandHandler("new_chat", handle_new_chat))
    app.add_handler(CommandHandler("jira", handle_jira))
    app.add_handler(CommandHandler("jira_login", handle_jira_login))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat))

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
