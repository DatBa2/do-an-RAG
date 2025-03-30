import os
import time
import hashlib
import pandas as pd
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
from tqdm import tqdm

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
es = Elasticsearch(ELASTICSEARCH_HOST)

# 📚 Đọc dữ liệu từ nhiều thư mục con
BASE_FOLDER = "txt"  # 📌 Thư mục gốc chứa các thư mục con

documents = []
start_time = time.time()  # ⏳ Bắt đầu đo thời gian

def hash_content(content):
    """Tạo hash SHA256 cho nội dung file để kiểm tra thay đổi."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

# 🛠️ Tạo index nếu chưa có
def create_index_if_not_exists(index_name):
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body={
            "settings": {
                "number_of_shards": 3,  # 🔹 Chia dữ liệu ra 3 phần để tăng tốc truy vấn
                "number_of_replicas": 1  # 🔹 Mỗi shard có 1 bản sao để tăng độ tin cậy
            },
            "mappings": {
                "properties": {
                    "content": {"type": "text"},
                    "filename": {"type": "keyword"},
                    "folder": {"type": "keyword"},
                    "content_hash": {"type": "keyword"}  # 🔍 Dùng để kiểm tra trùng lặp
                }
            }
        })

for root, _, files in os.walk(BASE_FOLDER):
    folder_name = os.path.basename(root)  # Lấy tên thư mục con
    index_name = f"documents_{folder_name.lower()}"  # Tạo index theo tên thư mục
    create_index_if_not_exists(index_name)  # Tạo index nếu chưa có

    batch_documents = []  # Lưu batch dữ liệu để bulk update

    for file_name in tqdm(files, desc=f"📂 Đang xử lý ({folder_name})"):
        file_path = os.path.join(root, file_name)
        content = ""

        try:
            # Xử lý file .txt
            if file_name.endswith(".txt"):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            # Xử lý file .xlsx và .xls
            elif file_name.endswith(".xlsx"):
                df = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
                content = "\n".join([df[sheet].to_string(index=False) for sheet in df])
            elif file_name.endswith(".xls"):
                try:
                    df = pd.read_excel(file_path, sheet_name=None, engine="xlrd")
                    content = "\n".join([df[sheet].to_string(index=False) for sheet in df])
                except Exception as xlrd_error:
                    print(f"⚠️ Lỗi xlrd với file {file_name}, thử openpyxl: {xlrd_error}")
                    try:
                        df = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
                        content = "\n".join([df[sheet].to_string(index=False) for sheet in df])
                    except Exception as openpyxl_error:
                        print(f"❌ Không thể đọc file {file_name}: {openpyxl_error}")
                        continue
        except Exception as e:
            print(f"⚠️ Lỗi đọc file {file_name}: {e}")
            continue

        if not content:
            continue

        # 🔍 Tạo hash nội dung làm ID
        content_hash = hash_content(content)
        doc_id = hashlib.sha1(content.encode("utf-8")).hexdigest()

        # ✅ Gom dữ liệu vào batch để bulk update
        batch_documents.append({
            "_op_type": "index",
            "_index": index_name,
            "_id": doc_id,  # Dùng hash làm ID để kiểm tra trùng lặp
            "_source": {
                "content": content,
                "filename": file_name,
                "folder": folder_name,
                "content_hash": content_hash
            }
        })

    # 🚀 Bulk index toàn bộ batch
    if batch_documents:
        helpers.bulk(es, batch_documents)
        print(f"✅ Đã index {len(batch_documents)} tài liệu mới trong {folder_name}.")

end_time = time.time()
print(f"🚀 Hoàn tất nạp dữ liệu! ⏳ Tổng thời gian: {end_time - start_time:.2f} giây")
