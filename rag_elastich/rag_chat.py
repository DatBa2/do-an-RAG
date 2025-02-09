import os
import time
import ollama
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from functools import lru_cache  # Dùng cache để tối ưu query trùng lặp

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
INDEX_NAME = "documents"
es = Elasticsearch(ELASTICSEARCH_HOST)

# ⚡ Tạo cache để tránh truy vấn trùng lặp
@lru_cache(maxsize=50)
def search_documents(query):
    start_time = time.time()  # ⏳ Bắt đầu đo thời gian tìm kiếm
    
    # Tìm kiếm trong Elasticsearch
    search_result = es.search(index=INDEX_NAME, body={
        "query": {
            "match": {"content": query}
        },
        "size": 3,  # Lấy 3 kết quả tốt nhất
        "_source": ["content", "filename"]  # Lấy cả nội dung & tên file
    })

    end_time = time.time()  # ⏳ Kết thúc đo thời gian tìm kiếm
    print(f"🔍 Tìm kiếm trong Elasticsearch hoàn thành trong {end_time - start_time:.4f} giây")

    # Trích xuất nội dung và file gốc
    documents = [(hit["_source"]["content"], hit["_source"]["filename"]) for hit in search_result["hits"]["hits"]]
    
    return documents

def search_and_respond(query):
    # Lấy dữ liệu từ Elasticsearch
    documents = search_documents(query)

    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    # Chọn tài liệu có nội dung phù hợp nhất
    best_doc, best_filename = documents[0]

    # Ghép nội dung & tên file vào prompt cho Ollama
    prompt = f"""Dưới đây là tài liệu từ file [{best_filename}]:\n\n{best_doc}\n\nCâu hỏi: {query}\n\nTrả lời một cách chính xác dựa trên tài liệu trên."""

    start_time = time.time()  # ⏳ Bắt đầu đo thời gian gọi AI
    response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": prompt}])
    end_time = time.time()  # ⏳ Kết thúc đo thời gian gọi AI
    print(f"🤖 Ollama phản hồi trong {end_time - start_time:.4f} giây")

    return response["message"]["content"], best_filename

if __name__ == "__main__":
    while True:
        query = input("Nhập câu hỏi (hoặc gõ 'exit' để thoát): ")
        if query.lower() == "exit":
            break
        start_time = time.time()  # ⏳ Bắt đầu đo tổng thời gian
        response, filename = search_and_respond(query)
        end_time = time.time()  # ⏳ Kết thúc đo tổng thời gian

        # In kết quả
        print("\n🎯 Trợ lý AI:\n", response, "")
        print(f"📂 Thông tin lấy từ file: {filename}")
        print(f"🚀 Tổng thời gian xử lý: {end_time - start_time:.4f} giây\n")
