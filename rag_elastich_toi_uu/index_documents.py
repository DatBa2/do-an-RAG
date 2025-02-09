import os
import time
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
from tqdm import tqdm

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
es = Elasticsearch(ELASTICSEARCH_HOST)
INDEX_NAME = "documents_toi_uu"

# 🛠️ Tạo index nếu chưa có, thêm trường "folder"
if not es.indices.exists(index=INDEX_NAME):
    es.indices.create(index=INDEX_NAME, body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "content": {"type": "text"},
                "filename": {"type": "keyword"},
                "folder": {"type": "keyword"}  # 🆕 Thêm thông tin thư mục
            }
        }
    })

# 📂 Đọc dữ liệu từ nhiều thư mục con
BASE_FOLDER = "txt"  # 📌 Thư mục gốc chứa các thư mục con
documents = []

start_time = time.time()  # ⏳ Bắt đầu đo thời gian

for root, _, files in os.walk(BASE_FOLDER):
    folder_name = os.path.basename(root)  # Lấy tên thư mục con
    for file_name in tqdm(files, desc=f"📂 Đang xử lý ({folder_name})"):
        if file_name.endswith(".txt"):
            file_path = os.path.join(root, file_name)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 🔍 Kiểm tra nếu tài liệu đã tồn tại
            query = {"query": {"term": {"filename": file_name}}, "size": 1}
            existing_docs = es.search(index=INDEX_NAME, body=query)

            if existing_docs["hits"]["total"]["value"] > 0:
                doc_id = existing_docs["hits"]["hits"][0]["_id"]
                es.update(index=INDEX_NAME, id=doc_id, body={"doc": {"content": content, "folder": folder_name}})
                print(f"🔄 Đã cập nhật: {file_name} trong {folder_name}")
            else:
                documents.append({
                    "_index": INDEX_NAME,
                    "_source": {"content": content, "filename": file_name, "folder": folder_name}
                })

# 🚀 Bulk index
if documents:
    helpers.bulk(es, documents)
    print(f"✅ Đã index {len(documents)} tài liệu.")

end_time = time.time()
print(f"🚀 Hoàn tất nạp dữ liệu! ⏳ Tổng thời gian: {end_time - start_time:.2f} giây")
