import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

documents = SimpleDirectoryReader("data").load_data()

# bge-base embedding model
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")

# ollama sử dụng Gemma2:9B
Settings.llm = Ollama(model="gemma2:9b", request_timeout=360.0)

# Tạo chỉ mục từ tài liệu
index = VectorStoreIndex.from_documents(documents)

# Lưu index vào file
index.storage_context.persist(persist_dir="indices/")

print("Tạo chỉ mục thành công!")