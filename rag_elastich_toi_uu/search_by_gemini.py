import os
import time
import ollama
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
es = Elasticsearch(ELASTICSEARCH_HOST)

# Lấy danh sách tất cả index có tài liệu
try:
    all_indices = es.cat.indices(format="json")
    INDEX_NAMES = [index["index"] for index in all_indices if "index" in index and index["index"].startswith("documents_")]
except Exception as e:
    print(f"⚠️ Lỗi khi lấy danh sách index: {e}")
    INDEX_NAMES = []

# Danh mục thư mục theo chủ đề
TOPIC_FOLDERS = {
    "Kinh tế": "kinh-te",
    "Khoa học": "khoa-hoc",
    "Nhân sự": "nhan-su",
    "Công việc": "cong-viec-cua-toi",
}

def analyze_question(question):
    """Dùng AI để phân tích câu hỏi và xác định hướng xử lý."""
    prompt = f"""
    Dưới đây là danh sách chủ đề:
    {', '.join(TOPIC_FOLDERS.keys())}

    Câu hỏi: "{question}"

    Hãy phân loại câu hỏi vào một trong các trường hợp sau:
    1. Cuộc hội thoại thông thường (ví dụ: xin chào, tạm biệt, hỏi thăm, ...).
    2. Câu hỏi cần tìm kiếm dữ liệu cụ thể trong tài liệu (ví dụ: ai, cái gì, ở đâu, khi nào, tại sao, như thế nào...).
    3. Cần tìm kiếm theo một trong các chủ đề: {', '.join(TOPIC_FOLDERS.keys())}.
    4. Cần tìm kiếm trên tất cả các thư mục nếu không xác định được chủ đề cụ thể.

    Trả lời chỉ bằng một trong các kết quả sau:
    - "Cuộc hội thoại"
    - "Tìm kiếm cụ thể"
    - Tên chủ đề chính xác (ví dụ: "Kinh tế")
    - "Tìm kiếm tất cả"
    """
    response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"].strip()

def search_and_respond(question):
    """Tìm kiếm tài liệu trong Elasticsearch hoặc trả lời trực tiếp tùy vào phân tích AI."""
    start_time = time.time()
    action = analyze_question(question)

    if action == "Cuộc hội thoại":
        print("🗣️ Câu hỏi là cuộc hội thoại thông thường.")
        response = ollama.chat(model="gemma2:9b", messages=[{"role": "user", "content": question}])
        return response["message"]["content"]

    # 🧠 Xác định kiểu tìm kiếm
    if action == "Tìm kiếm cụ thể":
        print("🔍 Cần tìm kiếm dữ liệu cụ thể trong tài liệu.")
        search_query = {"match_all": {}}
    elif action in TOPIC_FOLDERS:
        folder = TOPIC_FOLDERS[action]
        print(f"📂 AI xác định câu hỏi thuộc thư mục: {folder}")
        search_query = {"match": {"folder": folder}}
    else:
        print("🔍 AI không chắc chắn, tìm kiếm trên tất cả thư mục.")
        search_query = {"match_all": {}}

    # 🔎 Tìm kiếm trong tất cả index có sẵn
    documents = []
    if INDEX_NAMES:
        try:
            search_result = es.search(index=",".join(INDEX_NAMES), body={
                "query": search_query,
                "size": 3,
                "_source": ["content", "filename", "folder"]
            })
            documents = search_result["hits"].get("hits", [])
        except Exception as e:
            print(f"⚠️ Lỗi khi tìm kiếm: {e}")

    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    # 📄 Debug: In ra nội dung tìm được
    print(f"🔎 Tìm thấy {len(documents)} tài liệu:")
    for doc in documents:
        source = doc.get("_source", {})
        print(f"📄 File: {source.get('filename', 'N/A')} (Folder: {source.get('folder', 'N/A')})")
        print(f"📜 Nội dung: {source.get('content', '')[:500]}...\n")

    # 📄 Lấy nội dung và nguồn tài liệu
    context = "\n\n".join([f"(📄 {doc['_source']['filename']}) {doc['_source']['content']}" for doc in documents])

    prompt = f"""
    Dưới đây là tài liệu tham khảo:
    
    {context}

    Câu hỏi: {question}

    Trả lời một cách chính xác dựa trên tài liệu trên.
    """

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