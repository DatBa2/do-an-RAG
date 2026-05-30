"""Loại bỏ duplicate ảnh do chạy postprocess 2 lần.

Quét toàn bộ paragraphs, với mỗi ảnh embed kiểm tra rId. Nếu cùng một rId
xuất hiện nhiều lần và caption trùng, xóa các paragraph image dup (giữ lần đầu).

Cách đơn giản hơn: tìm các caption trùng nhau theo text, giữ lần đầu, xóa các
caption và paragraph image ngay TRƯỚC nó.
"""
import os
from collections import defaultdict
from docx import Document
from docx.oxml.ns import qn

SRC = "/Users/badat/do_an_ths/do-an-RAG/Decuong_NguyenBaDat_v2.docx"

doc = Document(SRC)
paras = list(doc.paragraphs)

# Phát hiện caption: text bắt đầu bằng "Hình 1." "Hình 2." "Hình 3." "Hình 4."
caption_idx = defaultdict(list)
for i, p in enumerate(paras):
    txt = p.text.strip()
    if txt.startswith("Hình ") and "." in txt[:10]:
        caption_idx[txt].append(i)

dup_to_remove = []
for cap, idxs in caption_idx.items():
    if len(idxs) > 1:
        print(f"DUP caption ({len(idxs)}x): {cap[:80]}")
        # Giữ lần đầu, xoá các lần sau (xoá caption + paragraph ngay trước = image)
        for keep_idx in idxs[1:]:
            dup_to_remove.append(keep_idx)        # caption itself
            dup_to_remove.append(keep_idx - 1)    # the image paragraph

dup_to_remove = sorted(set(dup_to_remove), reverse=True)
for idx in dup_to_remove:
    el = paras[idx]._element
    el.getparent().remove(el)

print(f"Removed {len(dup_to_remove)} paragraphs (dup images + captions)")
doc.save(SRC)
print("OK")
