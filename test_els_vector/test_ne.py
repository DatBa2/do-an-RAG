import os
import time  # Thêm thư viện time để đo thời gian
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json
import requests
import google.generativeai as genai  # Use Google's Gemini API library instead of OpenAI's

genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
# Kết nối Elasticsearch
es = Elasticsearch(['http://localhost:9200'])

# Thư mục chứa các file .txt
data_dir = 'data/'  # Đảm bảo thay đường dẫn chính xác của thư mục data

# Định nghĩa chỉ mục và thông số
index_name = 'documents'

# Hàm đọc file .txt và tạo dữ liệu
def read_txt_files(data_dir):
    for filename in os.listdir(data_dir):
        if filename.endswith(".txt"):
            with open(os.path.join(data_dir, filename), 'r', encoding='utf-8') as f:
                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": filename,
                    "_source": {
                        "text": f.read()
                    }
                }

# Thời gian bắt đầu thực thi
start_time = time.time()

# Câu hỏi cần tìm kiếm
query = "Tổng doanh thu quý 4?"

# Tạo truy vấn
search_body = {
    "query": {
        "match": {
            "text": query
        }
    },
    "size": 5  # Hạn chế trả về 5 kết quả phù hợp nhất
}

# Thực hiện tìm kiếm
response = es.search(index=index_name, body=search_body)

# Gom tất cả kết quả vào một chuỗi duy nhất
if response['hits']['total']['value'] > 0:
    results = []
    # Thêm thông tin vào danh sách
    for hit in response['hits']['hits']:
        result_text = f"file name: {hit['_id']}, Score: {hit['_score']}\n"
        result_text += f"Text: {hit['_source']['text'][:300]}...\n"

        results.append(result_text)

    # Kết hợp tất cả kết quả vào một chuỗi duy nhất
    combined_text = "\n\n".join(results)
else:
    combined_text = ""
print(combined_text)
exit()
end_time = time.time()
execution_time = end_time - start_time
print(f"Thời gian thực thi: {execution_time:.2f} giây")

input_text = f"Context: {combined_text}\n\nQuestion: {query}. Trả lời cả tên file với ví dụ: ở file: "
print(input_text)
# Start a chat with Gemini's model; use 'gemini-1.5-flash' or correct model name
# model = genai.GenerativeModel("gemini-1.5-flash")
# chat = model.start_chat(history=[{
#     "role": "model",
#     "parts": [
#         {
#             "text": "You are a helpful AI assistant. Always respond in Vietnamese."
#         }
#     ]
# }])
# response = chat.send_message(input_text)
# print(response.text)

url = "http://localhost:11434/api/chat"
headers = {"Content-Type": "application/json"}
data = {
    "model": "gemma2:9b",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant. Always respond in Vietnamese."},
        {"role": "user", "content": input_text}
    ]
}
response = requests.post(url, headers=headers, json=data)
# Lấy phản hồi thô
raw_response = response.text
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

end_time = time.time()
execution_time = end_time - start_time
print(f"Thời gian thực thi: {execution_time:.2f} giây")
