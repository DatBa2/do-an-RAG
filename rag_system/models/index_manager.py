import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, Document
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

def build_llama_index(documents, persist_dir="models/indices/"):
    if not documents or len(documents) == 0:
        print("Danh sách tài liệu trống, không thể tạo LlamaIndex.")
        return None
    if not os.path.exists(persist_dir):
        os.makedirs(persist_dir)

    try:
        if isinstance(documents[0], tuple):
            documents = [Document(text=content, metadata={"filename": filename}) for filename, content in documents]

        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        Settings.llm = Ollama(model="gemma2:9b", request_timeout=360.0)
        index = VectorStoreIndex.from_documents(documents)
        index.storage_context.persist(persist_dir=persist_dir)
        print(f"LlamaIndex đã được tạo và lưu thành công tại: {persist_dir}")
        return index
    except Exception as e:
        print(f"Lỗi xảy ra khi tạo LlamaIndex: {e}")
        return None


def load_llama_index():
    try:
        storage_context = StorageContext.from_defaults(persist_dir="indices/")
        index = load_index_from_storage(storage_context)
        print("LlamaIndex đã được tải thành công.")
        return index
    except Exception as e:
        print(f"Đã xảy ra lỗi khi tải LlamaIndex: {e}")
        return None

