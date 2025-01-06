import os
from elasticsearch import Elasticsearch
from docx import Document
import win32com.client

# Kết nối đến Elasticsearch
es = Elasticsearch([{'scheme': 'http', 'host': 'localhost', 'port': 9200}])

# Đường dẫn thư mục chứa các tệp tin
folder_path = r"C:\Users\badat\Downloads\data_test"

# Tạo chỉ mục Elasticsearch nếu chưa có
index_name = 'documents'
if not es.indices.exists(index=index_name):
    es.indices.create(index=index_name, body={
        "settings": {
            "analysis": {
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                        "type": "edge_ngram",
                        "min_gram": 1,
                        "max_gram": 10,
                        "token_chars": ["letter", "digit"]
                    }
                },
                "analyzer": {
                    "standard_analyzer": {
                        "type": "standard",
                        "filter": ["lowercase"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "content": {
                    "type": "text",
                    "analyzer": "standard_analyzer"  # Sử dụng analyzer chuyển tất cả về chữ thường
                },
                "file_name": {
                    "type": "keyword"
                }
            }
        }
    })


# Hàm để đọc nội dung của tệp .docx
def read_docx(file_path):
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)


# Hàm để đọc nội dung của tệp .doc (chỉ dành cho Windows với pywin32)
def read_doc(file_path):
    word = win32com.client.Dispatch("Word.Application")
    doc = word.Documents.Open(file_path)
    content = doc.Content.Text
    doc.Close()
    return content


# Đọc tất cả các tệp tin trong thư mục và chỉ mục vào Elasticsearch
for file_name in os.listdir(folder_path):
    file_path = os.path.join(folder_path, file_name)

    # Kiểm tra nếu file_name rỗng hoặc không phải là tệp tin, bỏ qua
    if not file_name or not os.path.isfile(file_path):
        continue

    if file_name.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

    elif file_name.endswith('.docx'):
        content = read_docx(file_path)

    elif file_name.endswith('.doc'):
        content = read_doc(file_path)

    else:
        # Nếu không phải là tệp txt, doc, docx thì bỏ qua
        continue

    # Chỉ mục tài liệu vào Elasticsearch
    document = {
        'content': content,
        'file_name': file_name  # Đảm bảo trường file_name được chỉ mục
    }

    # Lưu tài liệu vào Elasticsearch
    es.index(index=index_name, id=file_name, document=document)

# Vòng lặp để nhập từ cần tìm liên tục
while True:
    # Nhập từ cần tìm từ bàn phím
    search_word = input("Nhập từ cần tìm (hoặc 'exit' để thoát): ")

    # Kiểm tra nếu người dùng nhập 'exit' thì thoát vòng lặp
    if search_word.lower() == 'exit':
        print("Thoát chương trình.")
        break

    # Tìm kiếm từ trong chỉ mục Elasticsearch và đếm số lần xuất hiện
    search_query = {
        "query": {
            "match": {
                "content": {
                    "query": search_word,
                    "operator": "and"  # Tìm kiếm tất cả các từ khóa xuất hiện trong nội dung
                }
            }
        }
    }

    # Thực hiện tìm kiếm
    response = es.search(index=index_name, body=search_query)

    # Đếm số lần xuất hiện từ trong các tệp tin và in ra tên tệp
    count = 0
    found_files = set()  # Dùng set để theo dõi các tệp đã tìm thấy
    for hit in response['hits']['hits']:
        content = hit['_source']['content']
        file_name = hit['_source'].get('file_name', None)  # Nếu không có 'file_name', trả về None
        if file_name:  # Chỉ xử lý các tệp có 'file_name'
            count += content.lower().count(
                search_word.lower())  # Chuyển đổi cả nội dung và từ tìm kiếm thành chữ thường
            found_files.add(file_name)  # Thêm tên tệp vào tập hợp

    # Hiển thị các tệp đã tìm thấy
    if found_files:
        for file in found_files:
            print(f"Từ '{search_word}' xuất hiện trong tệp: {file}")
    else:
        print(f"Từ '{search_word}' không xuất hiện trong bất kỳ tệp tin nào.")

    # Hiển thị tổng số lần xuất hiện
    print(f"Số lần xuất hiện tổng cộng của từ '{search_word}': {count}")
