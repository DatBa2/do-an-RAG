import os
import time
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
from tqdm import tqdm

# Load biến môi trường
load_dotenv()

# Kết nối Elasticsearch với xử lý lỗi
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")

try:
    es = Elasticsearch(ELASTICSEARCH_HOST)
    if not es.ping():
        raise ValueError("❌ Không thể kết nối Elasticsearch! Kiểm tra lại cấu hình.")
except Exception as e:
    print(f"❌ Lỗi kết nối: {e}")
    exit(1)

INDEX_NAME = "documents"

# 🛠️ Kiểm tra và tạo index nếu chưa tồn tại
if not es.indices.exists(index=INDEX_NAME):
    es.indices.create(index=INDEX_NAME, body={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "content": {"type": "text"},
                "filename": {"type": "keyword"}
            }
        }
    })
    print(f"✅ Đã tạo index: {INDEX_NAME}")

# 📂 Đọc và nạp dữ liệu từ thư mục
TXT_FOLDER = "txt"
documents_to_add = []
documents_to_update = []

start_time = time.time()  # ⏳ Bắt đầu đo thời gian

for file_name in tqdm(os.listdir(TXT_FOLDER), desc="📄 Đang xử lý"):
    if not file_name.endswith(".txt"):
        continue
    
    file_path = os.path.join(TXT_FOLDER, file_name)
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 🔍 Kiểm tra nếu tài liệu đã tồn tại
    query = {
        "query": {"term": {"filename": file_name}},
        "size": 1  # Chuyển `size` vào trong `body` để tránh cảnh báo
    }
    existing_docs = es.search(index=INDEX_NAME, body=query)

    if existing_docs["hits"]["total"]["value"] > 0:
        # 🛠️ Cập nhật nội dung nếu file đã tồn tại
        doc_id = existing_docs["hits"]["hits"][0]["_id"]
        documents_to_update.append({
            "_op_type": "update",
            "_index": INDEX_NAME,
            "_id": doc_id,
            "doc": {"content": content}
        })
    else:
        # ➕ Thêm tài liệu mới vào danh sách để index
        documents_to_add.append({
            "_index": INDEX_NAME,
            "_source": {"content": content, "filename": file_name}
        })

# 🚀 Bulk cập nhật tài liệu đã tồn tại
if documents_to_update:
    helpers.bulk(es, documents_to_update)
    print(f"🔄 Đã cập nhật {len(documents_to_update)} tài liệu.")

# 🚀 Bulk thêm tài liệu mới
if documents_to_add:
    helpers.bulk(es, documents_to_add)
    print(f"✅ Đã index {len(documents_to_add)} tài liệu mới.")

end_time = time.time()  # ⏳ Kết thúc đo thời gian
print(f"🚀 Hoàn tất nạp dữ liệu! ⏳ Tổng thời gian: {end_time - start_time:.2f} giây")
