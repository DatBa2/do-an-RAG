from sentence_transformers import SentenceTransformer
from elasticsearch import Elasticsearch
from llama_index.core import StorageContext, load_index_from_storage

# Tải mô hình nhúng văn bản
embed_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
es = Elasticsearch("http://localhost:9200")


def search_documents(query, top_k=5):
    # Tạo StorageContext và tải index từ storage
    # storage_context = StorageContext.from_defaults(persist_dir="indices/")
    # index = load_index_from_storage(storage_context)
    # print("LlamaIndex đã được tải thành công.")

    # Example with the correct index name
    response = es.search(index="indices/", body={
        "query": {
            "match": {
                "content": query  # Assuming 'content' is the field you're querying
            }
        }
    })

    print(response)
    exit()
    # Tạo vector embedding cho câu hỏi
    query_embedding = embed_model.encode(query).tolist()

    # Script query cho cosine similarity
    script_query = {
        "script_score": {
            "query": {"match_all": {}},
            "script": {
                "source": """
                    double cosineSimilarity = 0;
                    double dotProduct = 0.0;
                    double queryMagnitude = 0.0;
                    double docMagnitude = 0.0;

                    if (params.query_vector != null && doc['embedding'] != null && params.query_vector.length == doc['embedding'].length) {
                        for (int i = 0; i < params.query_vector.length; i++) {
                            dotProduct += params.query_vector[i] * doc['embedding'][i];
                            queryMagnitude += params.query_vector[i] * params.query_vector[i];
                            docMagnitude += doc['embedding'][i] * doc['embedding'][i];
                        }

                        queryMagnitude = Math.sqrt(queryMagnitude);
                        docMagnitude = Math.sqrt(docMagnitude);

                        if (queryMagnitude > 0 && docMagnitude > 0) {
                            cosineSimilarity = dotProduct / (queryMagnitude * docMagnitude);
                        }
                    }

                    return cosineSimilarity;
                """,
                "params": {"query_vector": query_embedding}
            }
        }
    }

    # Thực hiện truy vấn
    response = es.search(index="indices", body={
        "size": top_k,
        "query": script_query
    })

    # Lấy kết quả tài liệu
    results = []
    for hit in response['hits']['hits']:
        results.append((hit['_source']['filename'], hit['_source']['content']))
    return results