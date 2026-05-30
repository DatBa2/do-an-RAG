"""Vẽ sơ đồ Elasticsearch one-store cho cả BM25 + KNN."""
import os
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
plt.rcParams["font.family"] = ["DejaVu Sans"]


def box(ax, x, y, w, h, text, fc, ec, fontsize=10, bold=False, lw=1.2):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                          linewidth=lw, edgecolor=ec, facecolor=fc)
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, weight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2, color="#37474F", label=None, fontsize=8.5):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                        mutation_scale=14, linewidth=1.2, color=color)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.10, label,
                ha="center", fontsize=fontsize, style="italic", color=color)


fig, ax = plt.subplots(figsize=(13, 7.5))
ax.set_xlim(0, 13); ax.set_ylim(0, 8); ax.axis("off")

ax.text(6.5, 7.7, "Elasticsearch như một 'one-store' cho cả BM25 và KNN",
        ha="center", fontsize=13.5, weight="bold")
ax.text(6.5, 7.3,
        "Một dịch vụ duy nhất phục vụ cả sparse retrieval (BM25) và dense retrieval (HNSW) - hợp nhất bằng RRF native",
        ha="center", fontsize=10, style="italic", color="#37474F")

# Input
box(ax, 0.3, 5.8, 2.4, 1.0, "Câu hỏi\ntiếng Việt", fc="#FFF9C4", ec="#F57F17", fontsize=10.5)
arrow(ax, 2.7, 6.3, 3.4, 6.3)

# Query rewrite + embed
box(ax, 3.4, 5.5, 2.6, 1.6,
    "Tiền xử lý câu hỏi\n• rewrite (multi-turn)\n• embed retrieval_query\n• xác định role",
    fc="#E1BEE7", ec="#4A148C", fontsize=9.5)

# ES box -- big container
box(ax, 6.4, 1.5, 5.5, 5.5, "", fc="#FFF3E0", ec="#E65100", lw=2.0)
ax.text(9.15, 6.6, "ELASTICSEARCH 8.x", ha="center", fontsize=12, weight="bold", color="#E65100")
ax.text(9.15, 6.25, "(single service, single cluster)",
        ha="center", fontsize=9, style="italic", color="#E65100")

# Inside ES: BM25 retriever
box(ax, 6.7, 4.3, 2.4, 1.5,
    "BM25 retriever\nanalyzer vn_text\nfilter allowed_roles",
    fc="#FFCCBC", ec="#BF360C", fontsize=9.5)

# Inside ES: KNN retriever
box(ax, 9.3, 4.3, 2.4, 1.5,
    "KNN retriever\ndense_vector(768)\nHNSW + int8\nfilter allowed_roles",
    fc="#C8E6C9", ec="#1B5E20", fontsize=9.5)

# RRF combiner
box(ax, 7.4, 2.8, 3.6, 1.0,
    "RRF retriever (k=60)\nnative trong ES 8.8+",
    fc="#E1BEE7", ec="#4A148C", fontsize=10, bold=True)

# Storage layer inside ES
box(ax, 6.7, 1.8, 5.0, 0.7,
    "Index: hs_records (text + keyword)   |   Index: internal_docs (text + dense_vector + acl)",
    fc="#B3E5FC", ec="#01579B", fontsize=9)

# Arrows inside ES
arrow(ax, 7.9, 4.3, 8.5, 3.8, color="#BF360C")
arrow(ax, 10.5, 4.3, 9.8, 3.8, color="#1B5E20")
arrow(ax, 9.15, 2.8, 9.15, 2.55, color="#4A148C")
arrow(ax, 6.0, 6.3, 6.4, 5.0, label="single API call", color="#7B1FA2")

# Output
box(ax, 0.3, 2.7, 2.4, 1.0, "Top-k chunks\n+ citation metadata",
    fc="#FFF9C4", ec="#F57F17", fontsize=10.5)
arrow(ax, 6.4, 3.3, 2.7, 3.2, color="#4A148C", label="fused result")

# Benefits panel (left bottom)
benefits = (
    "Lợi ích 'one-store':\n"
    "• Triển khai 1 service thay vì 2 (ES + vector DB)\n"
    "• 1 ACL model duy nhất (allowed_roles)\n"
    "• 1 backup/restore policy\n"
    "• Đồng bộ filter giữa BM25 và KNN tự động\n"
    "• Retriever API hỗ trợ RRF native từ ES 8.8"
)
ax.text(0.3, 0.4, benefits, fontsize=9.5, va="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#E8F5E9",
                  edgecolor="#1B5E20", linewidth=1.2))

plt.tight_layout()
out = os.path.join(OUT_DIR, "fig_13_es_onestore.png")
plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
plt.close()
print("Saved", out)
