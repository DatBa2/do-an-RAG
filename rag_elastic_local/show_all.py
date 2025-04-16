import os
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# Tải biến môi trường
load_dotenv()

# Kết nối Elasticsearch
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
es = Elasticsearch(ES_HOST)

def get_documents_from_index(index_name="documents_example", size=100):
    """
    Lấy tất cả tài liệu từ Elasticsearch.

    :param index_name: Tên của index trong Elasticsearch
    :param size: Số lượng tài liệu cần lấy
    :return: Danh sách các tài liệu
    """
    try:
        response = es.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "_source": ["filename", "content", "last_modified"],
                "size": size
            }
        )

        documents = response['hits']['hits']
        results = []
        for doc in documents:
            filename = doc['_source']['filename']
            content = doc['_source']['content']  # Không cắt ngắn nội dung
            last_modified = doc['_source']['last_modified']
            results.append({"filename": filename, "content": content, "last_modified": last_modified})

        return results

    except Exception as e:
        return {"error": f"Lỗi khi lấy dữ liệu từ Elasticsearch: {e}"}
