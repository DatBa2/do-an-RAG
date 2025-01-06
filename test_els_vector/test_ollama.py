import json
import requests

# Đường dẫn API
url = "http://localhost:11434/api/chat"
headers = {"Content-Type": "application/json"}
data = {
    "model": "gemma2:9b",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant. Always respond in Vietnamese."},
        {"role": "user", "content": "Xin chào"}
    ]
}

response = requests.post(url, headers=headers, json=data)

# Lấy phản hồi thô
raw_response = response.text
print("Raw Response:")
print(raw_response)

# Tách từng dòng JSON và ghép thành văn bản hoàn chỉnh
final_text = ""
for line in raw_response.splitlines():
    try:
        # Parse từng dòng JSON
        json_line = json.loads(line)
        if "message" in json_line and "content" in json_line["message"]:
            final_text += json_line["message"]["content"]
    except json.JSONDecodeError:
        # Nếu dòng không phải JSON hợp lệ, bỏ qua
        continue

print(final_text)
