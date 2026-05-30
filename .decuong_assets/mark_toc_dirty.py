"""Đánh dấu TOC field là 'dirty' để Word tự nhắc cập nhật khi mở file."""
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = "/Users/badat/do_an_ths/do-an-RAG/Decuong_NguyenBaDat_v2.docx"

doc = Document(SRC)

# Tìm fldChar đầu tiên có begin và set dirty=true
for p in doc.paragraphs:
    for fld in p._element.iter(qn("w:fldChar")):
        if fld.get(qn("w:fldCharType")) == "begin":
            fld.set(qn("w:dirty"), "true")
            print("Marked dirty:", fld.attrib)
            break

doc.save(SRC)
print("OK")
