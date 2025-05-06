# Sử dụng image Python chuẩn
FROM python:3.10-slim

# Cài các tiện ích hỗ trợ và client MySQL nếu cần debug
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    default-mysql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Đặt thư mục làm việc trong container
WORKDIR /app

# Sao chép file requirements trước để cache layer hiệu quả
COPY requirements.txt .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Mặc định chạy Uvicorn với app FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
