import os
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = os.getenv("ES_INDEX", "hs_records")

# Xem mapping
mapping = es.indices.get_mapping(index=INDEX_NAME)
print("Mapping:", mapping)

# Lấy 1 document bất kỳ
res = es.search(index=INDEX_NAME, size=1)
for hit in res["hits"]["hits"]:
    print("Document:", hit["_source"])

# Lấy 5 document
res = es.search(index=INDEX_NAME, size=5)
for hit in res["hits"]["hits"]:
    print(hit["_id"], hit["_source"])
