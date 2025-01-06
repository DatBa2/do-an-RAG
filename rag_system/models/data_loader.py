import os
from llama_index.core import Document

def load_text_files(directory = "data/documents"):
    documents = []
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory, filename)
            with open(file_path, "r", encoding="utf-8") as file:
                documents.append(Document(text=file.read(), metadata={"filename": filename}))
    return documents
