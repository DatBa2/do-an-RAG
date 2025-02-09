import requests
import time
import redis

def send_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        'chat_id': chat_id,
        'text': message
    }

    try:
        response = requests.post(url, data=payload)

        if response.status_code == 200:
            print("\u0110\u00e3 gửi tin nhắn thành công!")
        else:
            print("Lỗi khi gửi tin nhắn:", response.text)
    except Exception as e:
        print("Lỗi khi kết nối với API Telegram:", str(e))

# Chạy tin nhắn theo queue sử dụng Redis

def run_queue(redis_client, bot_token, interval):
    while True:
        message_data = redis_client.lpop("telegram_queue")
        if message_data:
            chat_id, message = message_data.split("|", 1)  # No need to decode, it's already a string
            send_message(bot_token, chat_id, message)
        else:
            print("Queue rỗng. Dừng xử lý.")
            break
        time.sleep(interval)

def main():
    BOT_TOKEN = "7309035623:AAHelK5OGpMCOHYUF3L8o8oMBL2D1SGB2iI"
    INTERVAL = 5  # Thời gian nghỉ giữa mỗi lần gửi (giây)

    # Kết nối tới Redis
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

    # Thêm tin nhắn vào hàng đợi Redis
    redis_client.rpush("telegram_queue", "6554124253|Ha Ha bot ngu đây! Lần 1")
    redis_client.rpush("telegram_queue", "6554124253|Ha Ha bot ngu đây! Lần 2")
    redis_client.rpush("telegram_queue", "6554124253|Ha Ha bot ngu đây! Lần 3")
    redis_client.rpush("telegram_queue", "6554124253|Ha Ha bot ngu đây! Lần 4")

    # Xử lý hàng đợi
    run_queue(redis_client, BOT_TOKEN, INTERVAL)

if __name__ == "__main__":
    main()