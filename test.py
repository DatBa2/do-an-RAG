from vncorenlp import VnCoreNLP

# Tải và khởi tạo bộ phân tích tiếng Việt
vncorenlp = VnCoreNLP.VnCoreNLP(url='http://localhost:9000')  # Nếu bạn cài VnCoreNLP trên localhost
# Hoặc sử dụng API từ dịch vụ bên ngoài

# Đoạn văn mẫu
text = "Tôi muốn tìm hiểu về trí tuệ nhân tạo và cách áp dụng nó vào giáo dục."

# Phân tích văn bản
tokenized_text = vncorenlp.tokenize(text)

# In các từ đã được token hóa
print("Tokenized text:", tokenized_text)
