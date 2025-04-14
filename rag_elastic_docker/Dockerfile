# Sử dụng image Python chuẩn
FROM python:3.10-slim

# Cài các tiện ích hỗ trợ
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Đặt thư mục làm việc trong container
WORKDIR /app

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Mặc định chạy Uvicorn với app FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
