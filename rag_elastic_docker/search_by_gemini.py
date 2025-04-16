import os
import time
import google.generativeai as genai
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

es = Elasticsearch(ES_HOST)

# Cấu hình Gemini
genai.configure(api_key="AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
model = genai.GenerativeModel("gemini-2.0-flash")

# Lịch sử hội thoại
history = []

# Danh mục thư mục theo chủ đề
TOPIC_FOLDERS = {
    "Kinh tế": "kinh-te",
    "Khoa học": "khoa-hoc",
    "Nhân sự": "nhan-su",
    "Chưa xác định": "chua-xac-dinh",
    "Thông tin cá nhân": "thong-tin-ca-nhan",
}

def analyze_question(question):
    global history
    chat = model.start_chat(history=history)
    prompt = f"""
    Dưới đây là danh sách các chủ đề có sẵn:
    {', '.join(TOPIC_FOLDERS.keys())}

    Câu hỏi: "{question}"

    Hãy phân loại câu hỏi vào một trong các loại sau:

    1. **Cuộc hội thoại thông thường**: Câu hỏi không liên quan đến tài liệu hoặc chủ đề cụ thể. Ví dụ: "Chào bạn!"
    2. **Câu hỏi yêu cầu tìm kiếm tài liệu**: Câu hỏi muốn tìm thông tin cụ thể trong tài liệu. Ví dụ: "Tìm tài liệu về kinh tế."
    3. **Câu hỏi liên quan đến một trong các chủ đề**: Câu hỏi cần tìm kiếm theo một trong các chủ đề sau: {', '.join(TOPIC_FOLDERS.keys())}. Ví dụ: "Tìm tài liệu về khoa học."
    4. **Câu hỏi cần tìm kiếm trên tất cả các thư mục**: Nếu câu hỏi không thể xác định chủ đề rõ ràng. Ví dụ: "Tìm tài liệu liên quan đến nhân sự."

    Trả lời chỉ bằng một trong các kết quả sau:
    - "Cuộc hội thoại"
    - "Tìm kiếm cụ thể"
    - Tên chủ đề chính xác (ví dụ: "Kinh tế")
    - "Tìm kiếm tất cả"
    """
    response = chat.send_message(prompt)
    return response.text.strip()

def search_and_respond(question):
    global history
    INDEX_NAMES = []
    try:
        all_indices = es.cat.indices(format="json")
        INDEX_NAMES = [index["index"] for index in all_indices if "index" in index and index["index"].startswith("documents_")]
    except Exception as e:
        print(f"⚠️ Lỗi khi lấy danh sách index: {e}")
        INDEX_NAMES = []

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

    selected_indices = INDEX_NAMES
    search_query = {}

    if action == "Tìm kiếm cụ thể":
        print("🔍 Cần tìm kiếm dữ liệu cụ thể trong tài liệu.")
        search_query = {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": question,
                            "fields": ["content_clean^2", "content"],
                            "type": "most_fields"
                        }
                    }
                ]
            }
        }
    elif action in TOPIC_FOLDERS:
        folder = TOPIC_FOLDERS[action]
        print(f"📂 AI xác định câu hỏi thuộc thư mục: {folder}")
        selected_indices = []
        main_index = f"documents_{folder}"
        backup_index = "documents_chua-xac-dinh"

        if main_index in INDEX_NAMES:
            selected_indices.append(main_index)
        if backup_index in INDEX_NAMES:
            selected_indices.append(backup_index)

        if not selected_indices:
            print(f"⚠️ Không tìm thấy index phù hợp.")
            return "Không tìm thấy tài liệu phù hợp."

        search_query = {
            "bool": {
                "must": [{"match": {"content_clean": question}}],
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
                "must": [{"match": {"content_clean": question}}],
                "should": [{"match_phrase": {"content": question}}]
            }
        }

    documents = []
    if selected_indices:
        try:
            size_limit = 5
            search_result = es.search(index=",".join(selected_indices), body={
                "query": search_query,
                "_source": ["content", "filename", "folder", "file_path"],
                "from": 0, 
                "size": size_limit,
                "track_total_hits": False,
                "highlight": {
                    "fields": {"content": {"fragment_size": 500, "number_of_fragments": 5}}
                }
            }, request_cache=True)
            documents = search_result["hits"].get("hits", [])
        except Exception as e:
            print(f"⚠️ Lỗi khi tìm kiếm: {e}")

    if not documents:
        return "Không tìm thấy tài liệu phù hợp."

    context = " ".join([
        f"(📄 {doc['_source']['filename']} - {doc['_source']['folder']})\n"
        f"Đường dẫn: {doc['_source'].get('file_path', 'Không rõ')}\n"
        f"{' '.join(doc.get('highlight', {}).get('content', []) or [doc['_source']['content'][:500]])}"
        for doc in documents
    ])
    prompt = f"""
    Dưới đây là tài liệu tham khảo:
    {context}
    Câu hỏi: {question}
    Trả lời một cách chính xác dựa trên tài liệu trên.
    """
    history.append({"role": "user", "parts": [f"[Tài liệu tham khảo]\n{context}\n\nCâu hỏi: {question}"]})

    chat = model.start_chat(history=history)
    response = chat.send_message(prompt)

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
