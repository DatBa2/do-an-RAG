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

for root, _, files in os.walk(BASE_FOLDER):
    folder_name = os.path.basename(root)  # Lấy tên thư mục con
    index_name = f"documents_{folder_name.lower()}"  # Tạo index theo tên thư mục
    
    # 🛠️ Tạo index nếu chưa có
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "content": {"type": "text"},
                    "filename": {"type": "keyword"},
                    "folder": {"type": "keyword"},
                    "content_hash": {"type": "keyword"}  # Lưu hash để kiểm tra thay đổi
                }
            }
        })
    
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

        # Tạo hash nội dung
        new_hash = hash_content(content)

        # 🔍 Kiểm tra nếu tài liệu đã tồn tại
        query = {"query": {"term": {"filename": file_name}}, "size": 1}
        existing_docs = es.search(index=index_name, body=query)

        if existing_docs["hits"]["total"]["value"] > 0:
            doc_id = existing_docs["hits"]["hits"][0]["_id"]
            old_hash = existing_docs["hits"]["hits"][0]["_source"].get("content_hash", "")

            if old_hash == new_hash:
                print(f"✅ Không có thay đổi: {file_name}, bỏ qua cập nhật.")
                continue  # Bỏ qua nếu nội dung không thay đổi

            # Cập nhật nội dung nếu có thay đổi
            es.update(index=index_name, id=doc_id, body={"doc": {"content": content, "folder": folder_name, "content_hash": new_hash}})
            print(f"🔄 Đã cập nhật: {file_name} trong {folder_name}")
        else:
            documents.append({
                "_index": index_name,
                "_source": {"content": content, "filename": file_name, "folder": folder_name, "content_hash": new_hash}
            })

# 🚀 Bulk index
if documents:
    helpers.bulk(es, documents)
    print(f"✅ Đã index {len(documents)} tài liệu mới.")

end_time = time.time()
print(f"🚀 Hoàn tất nạp dữ liệu! ⏳ Tổng thời gian: {end_time - start_time:.2f} giây")
