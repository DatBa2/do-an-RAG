import os
import time
import ollama
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Khởi tạo Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
INDEX_NAME = "documents"
es = Elasticsearch(ELASTICSEARCH_HOST)

def search_and_respond(query):
    total_start = time.time()  # Bắt đầu đo tổng thời gian

    # Tìm kiếm trong Elasticsearch
    es_start = time.time()
    search_result = es.search(index=INDEX_NAME, body={
        "query": {
            "match": {"content": query}
        },
        "size": 3
    })
    es_time = time.time() - es_start  # Thời gian tìm kiếm trong Elasticsearch

    # Lấy nội dung tài liệu tìm được
    documents = [hit["_source"]["content"] for hit in search_result["hits"]["hits"]]

    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    # Ghép nội dung lại để gửi vào Ollama
    context = "\n\n".join(documents)
    prompt = f"""Dưới đây là tài liệu tham khảo:\n\n{context}\n\nCâu hỏi: {query}\n\nTrả lời một cách chính xác dựa trên tài liệu trên."""

    # Gọi Ollama (Gemma 2 9B)
    ollama_start = time.time()
    response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": prompt}])
    ollama_time = time.time() - ollama_start  # Thời gian xử lý của Ollama

    total_time = time.time() - total_start  # Tổng thời gian xử lý

    # Trả về kết quả cùng thời gian thực thi
    return {
        "response": response["message"]["content"],
        "times": {
            "elasticsearch": f"{es_time:.4f} giây",
            "ollama": f"{ollama_time:.4f} giây",
            "total": f"{total_time:.4f} giây"
        }
    }

if __name__ == "__main__":
    while True:
        query = input("Nhập câu hỏi (hoặc gõ 'exit' để thoát): ")
        if query.lower() == "exit":
            break
        
        result = search_and_respond(query)
        
        print("\nTrợ lý AI:\n", result["response"])
        print(f"Elasticsearch: {result['times']['elasticsearch']}")
        print(f"Ollama: {result['times']['ollama']}")
        print(f"Tổng thời gian: {result['times']['total']}\n")
