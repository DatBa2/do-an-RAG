import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

data_dir = "data"
for file_name in os.listdir(data_dir):
    file_path = os.path.join(data_dir, file_name)
    if os.path.isfile(file_path):
        print(f"Đang xử lý file: {file_name}")
        documents = SimpleDirectoryReader("data").load_data()
        # bge-base embedding model
        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        # ollama sử dụng Gemma2:9B
        Settings.llm = Ollama(model="gemma2:9b", request_timeout=360.0)
        # Tạo chỉ mục từ tài liệu
        index = VectorStoreIndex.from_documents(documents)
        # Lưu index vào file
        index.storage_context.persist(persist_dir="indices/")
        print(f"File {file_name} đã được chỉ mục thành công!\n")

print("Hoàn thành quá trình tạo chỉ mục cho tất cả các file.")
