from elasticsearch import Elasticsearch

ELASTICSEARCH_HOST = "http://localhost:9200"
es = Elasticsearch(ELASTICSEARCH_HOST)

# Lấy danh sách tất cả index
indices = es.cat.indices(format="json")

# In danh sách index
if indices:
    print("📌 Danh sách tất cả index trong Elasticsearch:")
    for index in indices:
        print(f"- {index['index']} (Trạng thái: {index['status']}, Số tài liệu: {index['docs.count']})")
else:
    print("⚠️ Không có index nào trong Elasticsearch.")
