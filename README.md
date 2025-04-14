# do-an-RAG
ở folder rag_elastic_docker chứa code sẵn cho gemini
Docker chạy bao gồm cài elastichsearch và chạy ở cổng 9200
và dùng FastAPI để start server ở cổng 8000
Di chuyển vào folder chưa file docker-compose
1. `cd rag_elastic_docker`
Chay lệnh build docker
2. `docker-compose up --build -d`
sau đó mở bằng đường dẫn dưới bằng trình duyệt bất kỳ
3. `http://localhost:8000/`

