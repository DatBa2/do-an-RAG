from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
import time

start_time = time.time()
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
execution_time = time.time() - start_time
print(f"Thời gian thực thi: {execution_time:.2f} giây")
print("Tải chỉ mục thành công. Bắt đầu sinh câu trả lời...")

while True:
    user_question = input("Vui lòng nhập câu hỏi (hoặc 'exit' để dừng): ")
    if user_question.lower() == "exit":
        print("Đã thoát khỏi chương trình.")
        break
    start_time_new = time.time()
    Settings.llm = Ollama(model="gemma2:9b", prompt_key="You are a helpful AI assistant. Always respond in Vietnamese.", request_timeout=360.0)
    storage_context = StorageContext.from_defaults(persist_dir="indices/")
    index = load_index_from_storage(storage_context)
    query_engine = index.as_query_engine()
    response = query_engine.query("Tôi là ai?")
    print(response)
    execution_time = time.time() - start_time_new
    print(f"Thời gian thực thi: {execution_time:.2f} giây")