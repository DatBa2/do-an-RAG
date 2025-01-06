from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
import time

start_time = time.time()
# Khởi tạo model embedding sử dụng HuggingFace
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
# Giải thích:
# - Đây là model embedding để tạo vector biểu diễn văn bản.
# - Model `BAAI/bge-base-en-v1.5` có hiệu suất cao, đặc biệt khi dùng trong tìm kiếm.

# Thiết lập Large Language Model (LLM) sử dụng Ollama với model Gemma2:9b
Settings.llm = Ollama(model="gemma2:9b", prompt_key="You are a helpful AI assistant. Always respond in Vietnamese.", request_timeout=360.0)
# Giải thích:
# - `Ollama` dùng mô hình AI `gemma2:9b` để xử lý truy vấn.
# - `request_timeout` được cấu hình cao (360 giây) để đảm bảo mô hình không bị gián đoạn khi xử lý yêu cầu lớn.

# Tạo StorageContext từ thư mục được lưu trữ (persist_dir)
storage_context = StorageContext.from_defaults(persist_dir="indices/")
# Giải thích:
# - `persist_dir` chỉ định thư mục lưu trữ các file liên quan đến chỉ mục (index) được tạo trước đó.
# - `StorageContext` là lớp quản lý lưu trữ cấu trúc dữ liệu cần thiết để tìm kiếm và truy xuất thông tin.

# Tải lại index đã lưu từ `storage_context`
index = load_index_from_storage(storage_context)
# Giải thích:
# - Phục hồi dữ liệu từ bộ nhớ đã được lưu.
# - Điều này giúp không phải tái tạo chỉ mục mỗi khi khởi động.

# Tạo một query engine từ chỉ mục
query_engine = index.as_query_engine()
# Giải thích:
# - Biến `query_engine` được dùng để xử lý câu hỏi của người dùng dựa trên dữ liệu đã chỉ mục.
# - `query_engine` tự động ánh xạ giữa truy vấn và thông tin lưu trong vector embeddings.

# Gửi câu hỏi và nhận câu trả lời từ query engine
response = query_engine.query("Tên của tôi là?")
# Giải thích:
# - Mô hình truy xuất các đoạn văn liên quan trong dữ liệu từ chỉ mục.
# - Kết hợp với LLM (Gemma2:9b) để tổng hợp câu trả lời.

# In kết quả ra màn hình
print(response)
# Giải thích:
execution_time = time.time() - start_time
print(f"Thời gian thực thi: {execution_time:.2f} giây")