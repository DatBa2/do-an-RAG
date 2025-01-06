from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

# Cấu hình mô hình embedding và LLM
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
Settings.llm = Ollama(model="gemma2:9b", request_timeout=360.0)

# Tạo StorageContext và tải chỉ mục
storage_context = StorageContext.from_defaults(persist_dir="indices/")
index = load_index_from_storage(storage_context)

# Tạo Query Engine
query_engine = index.as_query_engine()

# Nhận câu hỏi từ bàn phím
user_question = input("Vui lòng nhập câu hỏi: ")

# Chạy truy vấn và in kết quả
response = query_engine.query(user_question)
print(response)
