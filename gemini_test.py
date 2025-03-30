import time
import google.generativeai as genai

# Cấu hình Gemini
genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
model = genai.GenerativeModel("gemini-2.0-flash")

# Khởi tạo lịch sử hội thoại
history = []

def send_message(prompt):
    global history
    chat = model.start_chat(history=history)  # Truyền lịch sử hội thoại vào
    
    start_time = time.time()  # Bắt đầu đo thời gian
    response = chat.send_message(prompt)
    end_time = time.time()  # Kết thúc đo thời gian
    
    history.append({"role": "user", "parts": [prompt]})  # Lưu tin nhắn của user
    history.append({"role": "model", "parts": [response.text]})  # Lưu phản hồi của bot
    
    response_time = end_time - start_time
    print(f"⏳ Thời gian phản hồi: {response_time:.4f} giây")
    
    return response.text

# Nhập tin nhắn từ bàn phím và gửi nhiều lần
while True:
    user_input = input("Bạn: ")
    if user_input.lower() in ["exit", "quit", "thoát"]:
        print("Kết thúc hội thoại.")
        break
    response_text = send_message(user_input)
    print("Bot:", response_text)