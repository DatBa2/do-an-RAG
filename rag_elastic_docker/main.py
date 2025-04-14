import os
from fastapi import FastAPI, Query
from index_docs_excel import index_documents
from search_by_gemini import search_and_respond
from elasticsearch import Elasticsearch, exceptions
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
import time
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def wait_for_es(es_host, retries=10, delay=5):
    """Chờ Elasticsearch sẵn sàng."""
    es = Elasticsearch(es_host)
    for _ in range(retries):
        try:
            es.ping()
            print("✅ Elasticsearch đã sẵn sàng.")
            return True
        except exceptions.ConnectionError:
            print("⚠️ Elasticsearch chưa sẵn sàng. Đang thử lại...")
            time.sleep(delay)
    print("❌ Không thể kết nối đến Elasticsearch sau nhiều lần thử.")
    return False

@app.get("/index_documents")
async def startup_event():
    if wait_for_es(os.getenv("ES_HOST", "http://localhost:9200")):
        return index_documents()
    else:
        print("❌ Không thể tiếp tục vì Elasticsearch không sẵn sàng.")
        # Có thể dừng ứng dụng hoặc thực hiện hành động khác tùy ý


@app.get("/search")
async def search(q: str = Query(..., alias="q")):
    results = search_and_respond(q)
    return {"query": q, "results": results.strip()}

@app.get("/show_index")
async def show_index():
    es = Elasticsearch(os.getenv("ES_HOST", "http://localhost:9200"))
    # Lấy danh sách tất cả index
    indices = es.cat.indices(format="json")

    # In danh sách index
    if indices:
        print("📌 Danh sách tất cả index trong Elasticsearch:")
        for index in indices:
            print(f"- {index['index']} (Trạng thái: {index['status']}, Số tài liệu: {index['docs.count']})")
    else:
        print("⚠️ Không có index nào trong Elasticsearch.")

@app.get("/clear_index")
async def clear_index():
    es = Elasticsearch(os.getenv("ES_HOST", "http://localhost:9200"))
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


@app.get("/", response_class=HTMLResponse)
async def get_chatbot():
    path = "chatbot.html"
    if not os.path.exists(path):
        return HTMLResponse(content="File not found!", status_code=404)
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
