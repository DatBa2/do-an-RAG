import os
import time
import google.generativeai as genai
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
es = Elasticsearch(ELASTICSEARCH_HOST)

# Cấu hình Gemini
genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
model = genai.GenerativeModel("gemini-2.0-flash")

# Lịch sử hội thoại
history = []

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
    "Chưa xác định": "chua-xac-dinh",
    "Thông tin cá nhân": "thong-tin-ca-nhan",
}

def analyze_question(question):
    """Dùng Gemini để phân tích câu hỏi và xác định hướng xử lý."""
    global history
    chat = model.start_chat(history=history)
    prompt = f"""
    Dưới đây là danh sách chủ đề:
    {', '.join(TOPIC_FOLDERS.keys())}

    Câu hỏi: "{question}"

    Hãy phân loại câu hỏi vào một trong các trường hợp sau:
    1. Cuộc hội thoại thông thường.
    2. Câu hỏi cần tìm kiếm dữ liệu cụ thể trong tài liệu.
    3. Cần tìm kiếm theo một trong các chủ đề: {', '.join(TOPIC_FOLDERS.keys())}.
    4. Cần tìm kiếm trên tất cả các thư mục nếu không xác định được chủ đề cụ thể.

    Trả lời chỉ bằng một trong các kết quả sau:
    - "Cuộc hội thoại"
    - "Tìm kiếm cụ thể"
    - Tên chủ đề chính xác (ví dụ: "Kinh tế")
    - "Tìm kiếm tất cả"
    """
    response = chat.send_message(prompt)
    return response.text.strip()

def search_and_respond(question):
    """Tìm kiếm tài liệu trong Elasticsearch hoặc trả lời trực tiếp bằng Gemini."""
    global history
    start_time = time.time()
    action = analyze_question(question)

    if action == "Cuộc hội thoại":
        print("🗣️ Câu hỏi là cuộc hội thoại thông thường.")
        chat = model.start_chat(history=history)
        response = chat.send_message(question)
        history.append({"role": "user", "parts": [question]})
        history.append({"role": "model", "parts": [response.text]})
        end_time = time.time()
        print(f"⏳ Hoàn thành trong {end_time - start_time:.4f} giây")
        return response.text

    # 🧠 Xác định kiểu tìm kiếm
    if action == "Tìm kiếm cụ thể":
        print("🔍 Cần tìm kiếm dữ liệu cụ thể trong tài liệu.")
        search_query = {
            "bool": {
                "must": [
                    {"match": {"content": question}},
                    {"match_phrase": {"content": question}}
                ]
            }
        }
    elif action in TOPIC_FOLDERS:
        folder = TOPIC_FOLDERS[action]
        print(f"📂 AI xác định câu hỏi thuộc thư mục: {folder}")
        search_query = {
            "bool": {
                "must": [{"match": {"content": question}}],
                "should": [
                    {"match": {"folder": folder}},
                    {"match": {"folder": "chua-xac-dinh"}},
                ]
            }
        }
    else:
        print("🔍 AI không chắc chắn, tìm kiếm trên tất cả thư mục.")
        search_query = {
            "bool": {
                "must": [{"match": {"content": question}}],
                "should": [{"match_phrase": {"content": question}}]
            }
        }

    # 🔎 Tìm kiếm trong tất cả index có sẵn
    documents = []
    if INDEX_NAMES:
        try:
            size_limit = 3
            if action == "Tìm kiếm tất cả" or action == "Tìm kiếm cụ thể":
                size_limit = 5  # 🔹 Nếu tìm trên tất cả, lấy thêm tài liệu
            search_result = es.search(index=",".join(INDEX_NAMES), body={
                "query": search_query,
                "_source": ["content", "filename", "folder"],  # Chỉ lấy các field cần thiết
                "from": 0,  # Bắt đầu từ kết quả đầu tiên
                "size": size_limit,   # Giới hạn số lượng kết quả trả về
                "track_total_hits": False,  # Giúp tối ưu hiệu suất khi không cần tổng số kết quả
                "highlight": {
                    "fields": {"content": {"fragment_size": 200, "number_of_fragments": 3}}
                }
            }, request_cache=True)  # Kích hoạt caching cho query
            documents = search_result["hits"].get("hits", [])
        except Exception as e:
            print(f"⚠️ Lỗi khi tìm kiếm: {e}")

    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    # 📄 Lấy nội dung và nguồn tài liệu
    context = "\n\n".join([f"(📄 {doc['_source']['filename']} - {doc['_source']['folder']}) {doc['_source']['content']}" for doc in documents])

    # 🖥️ Cập nhật lịch sử hội thoại với cả tài liệu tham khảo
    prompt = f"""
    Dưới đây là tài liệu tham khảo:

    {context}

    Câu hỏi: {question}

    Trả lời một cách chính xác dựa trên tài liệu trên.
    """

    history.append({"role": "user", "parts": [f"[Tài liệu tham khảo]\n{context}\n\nCâu hỏi: {question}"]})

    # 🖨️ In nội dung gửi lên chatbot trước khi gửi
    # print("\n🚀 Nội dung gửi lên chatbot:")
    # print(prompt)
    # print("\n📡 Gửi yêu cầu đến chatbot...\n")

    chat = model.start_chat(history=history)
    response = chat.send_message(prompt)

    # Lưu lại phản hồi
    history.append({"role": "model", "parts": [response.text]})

    end_time = time.time()
    print(f"⏳ Hoàn thành trong {end_time - start_time:.4f} giây")
    return response.text

if __name__ == "__main__":
    while True:
        question = input("Nhập câu hỏi (hoặc 'exit' để thoát): ")
        if question.lower() in ["exit", "quit", "thoát"]:
            print("Kết thúc hội thoại.")
            break
        answer = search_and_respond(question)
        print("Trợ lý AI:", answer)
