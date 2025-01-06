# app.py
import time
from models.data_loader import load_text_files
from models.elasticsearch_connector import  search_documents
from models.index_manager import build_llama_index, load_llama_index
from models.query_engine import query_llama_index, generate_gemini_answer

start_time = time.time()

# Load tài liệu từ thư mục data/documents
documents = load_text_files("models/data/documents")
# Xây dựng chỉ mục LlamaIndex với tài liệu từ Elasticsearch
build_llama_index(documents)
# Index tài liệu vào Elasticsearch
index_documents(documents)
# Tìm kiếm tài liệu từ Elasticsearch trước
index = load_llama_index()
# Truy vấn LlamaIndex để tìm tài liệu liên quan
retrieved_docs = query_llama_index(index, user_question)


# Câu hỏi từ người dùng
user_question = "Tổng chi phí hết quý 4 bao tiền?"
search_results = search_documents(user_question)
# Ghép ngữ cảnh từ các tài liệu truy xuất được
context = "".join(search_results)
# Tạo câu trả lời từ Gemini API
answer = generate_gemini_answer(search_results, user_question)
# Hiển thị câu trả lời
print("Câu trả lời từ hệ thống:")
print(answer)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"Thời gian thực thi: {elapsed_time:.2f} giây")