# do-an-RAG
ở folder rag_elastic_docker chứa code sẵn cho gemini
Docker chạy bao gồm cài elastichsearch và chạy ở cổng 9200
và dùng FastAPI để start server ở cổng 8000
Chỉ cần cài đặt docker và chạy lệnh
1. `docker build -t rag_elastic_docker .`

sau đó vào bằng đường dẫn dưới để dùng chatbot
2. `http://localhost:8000/`

