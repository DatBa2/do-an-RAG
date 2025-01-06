# app.py
from data_loader import load_text_files
from elasticsearch_connector import index_documents, search_documents, count_occurrences

# Load tài liệu từ thư mục data/documents
documents = load_text_files("data/documents")

# Index tài liệu vào Elasticsearch
index_documents(documents)
# Tìm kiếm trong các tài liệu đã index
query = "Tổng"
results = search_documents(query)

# Đếm số lần xuất hiện của từ khóa trong các kết quả tìm kiếm
occurrences = count_occurrences(results, query)

# In ra kết quả tìm kiếm, bao gồm tên file và số lần xuất hiện
print(f"Kết quả tìm kiếm cho '{query}':")
for filename, count in occurrences:
    print(f"Tên file: {filename}, Số lần xuất hiện: {count}")