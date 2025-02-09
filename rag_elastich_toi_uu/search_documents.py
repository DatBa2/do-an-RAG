import os
import time
import ollama
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
INDEX_NAME = "documents_toi_uu"
es = Elasticsearch(ELASTICSEARCH_HOST)

# Danh mục thư mục theo chủ đề
TOPIC_FOLDERS = {
    "Kinh tế": "kinh-te",
    "Khoa học": "khoa-hoc",
    "Nhân sự": "nhan-su",
}

def classify_question(question):
    """Dùng AI để xác định chủ đề câu hỏi."""
    prompt = f"""
    Dưới đây là danh sách chủ đề:
    {', '.join(TOPIC_FOLDERS.keys())}

    Hãy phân loại câu hỏi sau vào một trong các chủ đề trên:
    "{question}"

    Trả lời chỉ bằng tên chủ đề chính xác.
    """
    response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": prompt}])
    topic = response["message"]["content"].strip()
    return TOPIC_FOLDERS.get(topic, None)  # Trả về thư mục hoặc None nếu không có kết quả rõ ràng

def search_and_respond(question):
    """Tìm kiếm tài liệu trong Elasticsearch sau khi phân loại câu hỏi."""
    start_time = time.time()
    # 🧠 Xác định thư mục dựa trên AI
    folder = classify_question(question)
    if folder:
        print(f"📂 AI xác định câu hỏi thuộc thư mục: {folder}")
        search_query = {"match": {"folder": folder}}
    else:
        print("🔍 AI không chắc chắn, tìm kiếm trên tất cả thư mục.")
        search_query = {"match_all": {}}

    # 🔎 Tìm kiếm trong Elasticsearch
    search_result = es.search(index=INDEX_NAME, body={
        "query": search_query,
        "size": 3,
        "_source": ["content", "filename"]
    })

    documents = search_result["hits"]["hits"]
    
    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    # 📄 Lấy nội dung và nguồn tài liệu
    context = "\n\n".join([f"(📄 {doc['_source']['filename']}) {doc['_source']['content']}" for doc in documents])
    
    prompt = f"""
    Dưới đây là tài liệu tham khảo:
    
    {context}

    Câu hỏi: {question}

    Trả lời một cách chính xác dựa trên tài liệu trên.
    """

    # 🤖 Gọi AI để tạo câu trả lời
    response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": prompt}])
    
    end_time = time.time()
    print(f"⏳ Hoàn thành trong {end_time - start_time:.4f} giây")
    return response["message"]["content"]

if __name__ == "__main__":
    while True:
        question = input("Nhập câu hỏi (hoặc 'exit' để thoát): ")
        if question.lower() == "exit":
            break
        answer = search_and_respond(question)
        print("Trợ lý AI:", answer)
