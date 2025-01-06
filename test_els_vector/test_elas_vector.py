import os
import time  # Thêm thư viện time để đo thời gian
from sentence_transformers import SentenceTransformer
from elasticsearch import Elasticsearch
import google.generativeai as genai  # Use Google's Gemini API library instead of OpenAI's

genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")

# Tải mô hình embedding
model = SentenceTransformer('all-MiniLM-L6-v2')

# Kết nối Elasticsearch
es = Elasticsearch("http://localhost:9200")

# Tên thư mục chứa các file
folder_path = "data"
start_time = time.time()
# Kiểm tra nếu index chưa tồn tại, thì tạo index cho mỗi file
for filename in os.listdir(folder_path):
    file_path = os.path.join(folder_path, filename)

    if os.path.isfile(file_path) and filename.endswith(".txt"):  # Chỉ lấy các file .txt
        index_name = f"index_{filename.split('.')[0]}"  # Sử dụng tên file làm index

        if not es.indices.exists(index=index_name):
            es.indices.create(index=index_name, body={
                "mappings": {
                    "properties": {
                        "id": {"type": "integer"},
                        "text": {"type": "text"},
                        "text_vector": {"type": "dense_vector", "dims": 384}
                        # 384 là số chiều của mô hình all-MiniLM-L6-v2
                    }
                }
            })
            print(f"Index '{index_name}' đã được tạo.")

        documents = []
        with open(file_path, "r", encoding="utf-8") as file:
            for idx, line in enumerate(file):
                if line.strip():  # Bỏ qua dòng trống
                    documents.append({"id": len(documents) + 1, "text": line.strip()})

        # Tạo vector và thêm vào Elasticsearch
        for doc in documents:
            doc_vector = model.encode(doc["text"]).tolist()
            es.index(index=index_name, document={
                "id": doc["id"],
                "text": doc["text"],
                "text_vector": doc_vector
            })

        print(f"Đã chỉ mục tài liệu từ file '{filename}' vào index '{index_name}'.")

# Ví dụ về tìm kiếm vector (giữ nguyên như trong phần trước)
question = "Tổng doanh thu quý 4?"
query_vector = model.encode(question).tolist()

# Tìm kiếm trong tất cả các index hoặc cụ thể một index
search_body = {
    "query": {
        "script_score": {
            "query": {
                "match_all": {}
            },
            "script": {
                "source": "cosineSimilarity(params.query_vector, 'text_vector') + 1.0",  # Add the similarity score
                "params": {
                    "query_vector": query_vector
                }
            }
        }
    }
}
response = es.search(index="_all", body=search_body)
top_documents = [hit['_source']['text'] for hit in response['hits']['hits']]
input_text = f"Context: {top_documents}\n\nQuestion: {question}\n\nQuestion vector: {query_vector}. Trả lời cả tên file với ví dụ: ở file: "

# Start a chat with Gemini's model; use 'gemini-1.5-flash' or correct model name
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat(history=[{
    "role": "model",
    "parts": [
        {
            "text": "You are a helpful AI assistant. Always respond in Vietnamese."
        }
    ]
}])
response = chat.send_message(input_text)
print(response.text)
end_time = time.time()
execution_time = end_time - start_time
print(f"Thời gian thực thi: {execution_time:.2f} giây")