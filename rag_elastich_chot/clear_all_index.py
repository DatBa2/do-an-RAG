from elasticsearch import Elasticsearch

ELASTICSEARCH_HOST = "http://localhost:9200"
es = Elasticsearch(ELASTICSEARCH_HOST)

# Lấy danh sách tất cả index
indices = es.cat.indices(format="json")

if not indices:
    print("⚠️ Không có index nào để xóa.")
else:
    print("🗑 Đang xóa tất cả index trong Elasticsearch...")

    for index in indices:
        index_name = index["index"]
        es.options(ignore_status=[400, 404]).indices.delete(index=index_name)
        print(f"✅ Đã xóa index: {index_name}")

    print("🚀 Xóa tất cả index thành công!")
