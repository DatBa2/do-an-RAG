"""Vẽ thêm 9 sơ đồ và biểu đồ cho đề cương."""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
plt.rcParams["font.family"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, text, fc="#E3F2FD", ec="#1565C0", fontsize=10, bold=False, lw=1.2):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                          linewidth=lw, edgecolor=ec, facecolor=fc)
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, weight="bold" if bold else "normal")


def arrow(ax, x1, y1, x2, y2, color="#37474F", style="-|>", label=None, fontsize=8):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                        linewidth=1.2, color=color)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.08, label,
                ha="center", va="bottom", fontsize=fontsize, style="italic", color=color)


# =====================================================================
# FIG 4: Pipeline RAG 4 pha
# =====================================================================
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis("off")
    ax.text(6.5, 5.5, "Quy trình 4 pha của hệ thống Retrieval-Augmented Generation",
            ha="center", fontsize=13, weight="bold")

    phases = [
        ("Pha 1: INGEST", 0.5, "#FFCDD2", "#B71C1C",
         "• Đọc tài liệu (MD, PDF, JSON)\n• Chuẩn hoá Unicode + tiếng Việt\n"
         "• Chia chunk section-aware\n• Sinh embedding (Gemini 768d)\n"
         "• Bulk index vào Elasticsearch"),
        ("Pha 2: RETRIEVE", 3.5, "#FFE0B2", "#E65100",
         "• Query rewrite (multi-turn)\n• Embed query (task=retrieval_query)\n"
         "• Chạy song song BM25 + KNN\n• Lọc ACL allowed_roles\n• RRF fuse → top-k chunks"),
        ("Pha 3: CONTEXT", 6.5, "#FFF9C4", "#F57F17",
         "• Ghép chunks + metadata\n• Áp template prompt tiếng Việt\n"
         "• Gắn citation (doc_id, section)\n• Cắt theo context window\n• System instruction RAG-aware"),
        ("Pha 4: GENERATE & VERIFY", 9.5, "#C8E6C9", "#1B5E20",
         "• LLM Gemini sinh câu trả lời\n• Function calling cho dữ liệu cấu trúc\n"
         "• Self-RAG lite kiểm tra grounding\n• Gắn warning nếu thiếu căn cứ\n• Ghi audit log"),
    ]
    for title, x, fc, ec, body in phases:
        box(ax, x, 2.8, 2.8, 2.2, body, fc=fc, ec=ec, fontsize=9)
        box(ax, x, 5.0, 2.8, 0.4, title, fc=ec, ec=ec, fontsize=10, bold=True)
        # White text on dark
        for txt in ax.texts:
            if txt.get_text() == title:
                txt.set_color("white")

    for i in range(3):
        arrow(ax, phases[i][1] + 2.85, 3.9, phases[i+1][1] - 0.05, 3.9, color="#455A64")

    # bottom: input/output
    box(ax, 0.5, 0.6, 2.8, 1.0,
        "Đầu vào\n• Câu hỏi tiếng Việt\n• role + chat_id", fc="#BBDEFB", ec="#0D47A1", fontsize=9)
    box(ax, 9.5, 0.6, 2.8, 1.0,
        "Đầu ra\n• Câu trả lời + citation\n• Cảnh báo nếu cần", fc="#BBDEFB", ec="#0D47A1", fontsize=9)
    arrow(ax, 1.9, 1.6, 1.9, 2.8); arrow(ax, 10.9, 2.8, 10.9, 1.6)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_4_pipeline.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 5: BM25 vs Dense vs Hybrid (Venn-like)
# =====================================================================
def fig_retrieval_modes():
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_xlim(0, 11); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(5.5, 6.5, "So sánh ba phương pháp truy xuất",
            ha="center", fontsize=13, weight="bold")

    # 3 columns
    cols = [
        (0.5, "BM25 (Sparse)", "#FFE0B2", "#E65100",
         ["+ Nhanh, đơn giản, ổn định", "+ Tốt với từ khoá, mã số, tên",
          "+ Giải thích được kết quả", "- Không hiểu ngữ nghĩa",
          "- Trượt khi diễn đạt khác từ", "- Yêu cầu khớp mặt chữ"]),
        (4.0, "Dense Vector", "#C8E6C9", "#1B5E20",
         ["+ Hiểu ngữ nghĩa, đồng nghĩa", "+ Robust với biến thể chữ",
          "+ Cross-lingual khả thi", "- Embedding tốn API/GPU",
          "- 'Trơn' với số liệu, mã", "- Khó debug"]),
        (7.5, "Hybrid + RRF", "#E1BEE7", "#4A148C",
         ["+ Kế thừa cả hai", "+ Không cần tuning weights",
          "+ Robust trước thang điểm", "+ Native trong ES/OpenSearch",
          "+ Chuẩn de-facto 2024-2025", "- Phải duy trì 2 nhánh"]),
    ]
    for x, title, fc, ec, items in cols:
        box(ax, x, 1.0, 3.0, 4.2, "", fc=fc, ec=ec, fontsize=9)
        box(ax, x, 4.7, 3.0, 0.5, title, fc=ec, ec=ec, fontsize=11, bold=True)
        # title white
        for t in ax.texts:
            if t.get_text() == title:
                t.set_color("white")
        for i, item in enumerate(items):
            ax.text(x + 0.15, 4.4 - i * 0.55, item, fontsize=9.5,
                    va="top", color="#212121")

    # Bottom: equation RRF
    ax.text(5.5, 0.5,
            r"RRF(d) = Σᵢ 1 / (k + rankᵢ(d))    với k = 60 (Cormack et al., 2009)",
            ha="center", fontsize=10.5, style="italic", color="#4A148C")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_5_retrieval_modes.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 6: Ví dụ RRF minh hoạ
# =====================================================================
def fig_rrf_example():
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.set_xlim(0, 13); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(6.5, 6.5, "Ví dụ minh hoạ Reciprocal Rank Fusion (k = 60)",
            ha="center", fontsize=13, weight="bold")
    ax.text(6.5, 6.05,
            "Câu hỏi: \"Học phí năm 2024-2025 lớp 7 là bao nhiêu?\"",
            ha="center", fontsize=10.5, style="italic", color="#37474F")

    # BM25 column
    box(ax, 0.3, 1.0, 3.6, 4.7, "", fc="#FFF3E0", ec="#E65100", lw=1.3)
    ax.text(2.1, 5.4, "Bảng xếp hạng BM25", ha="center", fontsize=11, weight="bold", color="#E65100")
    bm25 = [("bieu-phi-2024-2025.md", 1, 18.4),
            ("noi-quy.md", 2, 7.2),
            ("lich-hoc-2024.md", 3, 5.1),
            ("dieu-le-hoc-sinh.md", 4, 3.8),
            ("huong-dan-gvcn.md", 5, 1.9)]
    for i, (doc, rank, score) in enumerate(bm25):
        y = 4.9 - i * 0.7
        ax.text(0.5, y, f"#{rank}", fontsize=10, color="#E65100", weight="bold")
        ax.text(0.95, y, doc, fontsize=9)
        ax.text(3.6, y, f"{score:.1f}", fontsize=9, color="#37474F", ha="right", style="italic")

    # KNN column
    box(ax, 4.3, 1.0, 3.6, 4.7, "", fc="#E8F5E9", ec="#1B5E20", lw=1.3)
    ax.text(6.1, 5.4, "Bảng xếp hạng KNN (cosine)", ha="center", fontsize=11, weight="bold", color="#1B5E20")
    knn = [("noi-quy.md", 1, 0.81),
            ("bieu-phi-2024-2025.md", 2, 0.78),
            ("dieu-le-hoc-sinh.md", 3, 0.71),
            ("lich-thi.md", 4, 0.65),
            ("lich-hoc-2024.md", 5, 0.62)]
    for i, (doc, rank, score) in enumerate(knn):
        y = 4.9 - i * 0.7
        ax.text(4.5, y, f"#{rank}", fontsize=10, color="#1B5E20", weight="bold")
        ax.text(4.95, y, doc, fontsize=9)
        ax.text(7.6, y, f"{score:.2f}", fontsize=9, color="#37474F", ha="right", style="italic")

    # RRF column
    box(ax, 8.3, 1.0, 4.4, 4.7, "", fc="#F3E5F5", ec="#4A148C", lw=1.3)
    ax.text(10.5, 5.4, "Sau khi RRF fuse", ha="center", fontsize=11, weight="bold", color="#4A148C")
    rrf = [
        ("bieu-phi-2024-2025.md", 1/(60+1) + 1/(60+2), 1, "BM25 #1 + KNN #2"),
        ("noi-quy.md",            1/(60+2) + 1/(60+1), 2, "BM25 #2 + KNN #1"),
        ("dieu-le-hoc-sinh.md",   1/(60+4) + 1/(60+3), 3, "BM25 #4 + KNN #3"),
        ("lich-hoc-2024.md",      1/(60+3) + 1/(60+5), 4, "BM25 #3 + KNN #5"),
        ("lich-thi.md",           0       + 1/(60+4), 5, "KNN #4 only"),
    ]
    for i, (doc, score, rank, detail) in enumerate(rrf):
        y = 4.9 - i * 0.7
        ax.text(8.5, y, f"#{rank}", fontsize=10, color="#4A148C", weight="bold")
        ax.text(8.95, y, doc, fontsize=9)
        ax.text(12.55, y, f"{score:.4f}", fontsize=8.5, color="#37474F", ha="right", style="italic")
        ax.text(8.95, y - 0.25, detail, fontsize=7.5, color="#6A1B9A", style="italic")

    arrow(ax, 3.9, 3.4, 4.3, 3.4, color="#7B1FA2")
    arrow(ax, 7.9, 3.4, 8.3, 3.4, color="#7B1FA2")

    ax.text(6.5, 0.5,
            "Kết quả: tài liệu xuất hiện ở cả hai danh sách được ưu tiên dù không ở vị trí #1 trong bất kỳ danh sách nào.",
            ha="center", fontsize=9.5, style="italic", color="#37474F")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_6_rrf_example.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 7: Chunking strategies
# =====================================================================
def fig_chunking():
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.set_xlim(0, 13); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(6.5, 6.5, "Các chiến lược chia chunk cho RAG",
            ha="center", fontsize=13, weight="bold")

    strategies = [
        (0.3, "Fixed-size", "Cắt cố định 200-512 token",
         "+ Đơn giản, nhanh\n- Có thể đứt câu",  "#FFEBEE", "#B71C1C"),
        (3.5, "Recursive", "Cắt đệ quy: section → đoạn → câu",
         "+ Giữ cấu trúc\n+ Tham số ít",            "#E3F2FD", "#0D47A1"),
        (6.7, "Section-aware ✓", "Cắt theo heading Markdown\n(đề án sử dụng)",
         "+ Mỗi chunk ~ 1 chủ đề\n+ Overlap 64 token", "#E8F5E9", "#1B5E20"),
        (9.9, "Semantic / Late", "Gom câu theo embedding similarity\nhoặc embed cả tài liệu rồi cắt",
         "+ Coherence cao\n- Chi phí gấp đôi",   "#F3E5F5", "#4A148C"),
    ]
    for x, name, desc, pros, fc, ec in strategies:
        box(ax, x, 2.5, 2.9, 3.5, "", fc=fc, ec=ec, lw=1.4)
        box(ax, x, 5.4, 2.9, 0.6, name, fc=ec, ec=ec, fontsize=11, bold=True)
        for t in ax.texts:
            if t.get_text() == name:
                t.set_color("white")
        ax.text(x + 1.45, 4.6, desc, ha="center", fontsize=9.2, style="italic")
        ax.text(x + 0.15, 3.6, pros, fontsize=9, va="top")

    # Citation
    ax.text(6.5, 1.5,
            "NAACL 2025 Findings: fixed-200 đôi khi tương đương semantic chunking với chi phí thấp hơn.\n"
            "MDPI Bioengineering 11/2025: adaptive chunking theo biên chủ đề đạt 87% với câu hỏi y khoa so với 13% baseline.",
            ha="center", fontsize=9, color="#37474F", style="italic")
    ax.text(6.5, 0.4,
            "Khuyến nghị công nghiệp: chunk 256–512 token, overlap 10–20%. Đề án ablation: 128–1024 × {0, 32, 64, 128}.",
            ha="center", fontsize=9.5, color="#1B5E20", weight="bold")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_7_chunking.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 8: RBAC hai lớp pre/post filter
# =====================================================================
def fig_rbac():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(6, 6.5, "Cơ chế RBAC hai lớp: pre-filter + post-gate",
            ha="center", fontsize=13, weight="bold")

    # User
    box(ax, 0.3, 4.5, 2.0, 0.9,
        "User\n(parent / teacher / admin)", fc="#FFF9C4", ec="#F57F17", fontsize=9.5)

    # Pre-filter (ES level)
    box(ax, 3.0, 4.5, 3.2, 0.9,
        "PRE-FILTER\nES query với filter\nallowed_roles ∋ role", fc="#C8E6C9", ec="#1B5E20", fontsize=9.5)
    arrow(ax, 2.3, 4.95, 3.0, 4.95)
    ax.text(2.65, 5.25, "câu hỏi", ha="center", fontsize=8.5, style="italic")

    # ES
    box(ax, 7.0, 4.5, 2.4, 0.9,
        "Elasticsearch\nBM25 + KNN", fc="#E1BEE7", ec="#4A148C", fontsize=9.5)
    arrow(ax, 6.2, 4.95, 7.0, 4.95)

    # Post-gate
    box(ax, 3.0, 2.7, 3.2, 0.9,
        "POST-GATE (dispatcher)\nKiểm tra ADMIN_ONLY\ntrước khi gọi tool", fc="#FFE0B2", ec="#E65100", fontsize=9.5)
    arrow(ax, 8.2, 4.5, 6.2, 3.6)
    ax.text(7.4, 4.0, "chunks/data", fontsize=8.5, style="italic", rotation=-20)

    # Render filter
    box(ax, 7.0, 2.7, 2.4, 0.9,
        "RENDER FILTER\nKiểm tra citation\ntrùng tài liệu hợp lệ", fc="#FFCDD2", ec="#B71C1C", fontsize=9.5)
    arrow(ax, 6.2, 3.15, 7.0, 3.15)

    # Output
    box(ax, 9.7, 2.7, 2.0, 0.9,
        "Trả về User\n(hoặc 'denied')", fc="#FFF9C4", ec="#F57F17", fontsize=9.5, bold=True)
    arrow(ax, 9.4, 3.15, 9.7, 3.15)

    # Audit log
    box(ax, 4.3, 0.9, 4.0, 0.9,
        "Audit log SQLite\nchat_id · role · tools · latency", fc="#B3E5FC", ec="#01579B", fontsize=9.5)
    arrow(ax, 6.3, 2.7, 6.3, 1.8)
    ax.text(6.5, 2.2, "ghi log", fontsize=8.5, style="italic", color="#01579B")

    # Legend
    ax.text(0.3, 1.5, "Hai lớp khớp khuyến nghị\nOWASP LLM02 - 2025:\nLLM không bao giờ thấy\ntài liệu vượt quyền",
            fontsize=9.2, color="#B71C1C", style="italic",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#FFEBEE", edgecolor="#B71C1C"))

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_8_rbac.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 9: Inverted Index minh hoạ
# =====================================================================
def fig_inverted_index():
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6); ax.axis("off")
    ax.text(6.5, 5.5, "Chỉ mục đảo (Inverted Index) trong Elasticsearch",
            ha="center", fontsize=13, weight="bold")

    # Documents
    docs = [
        "D1: \"Nguyễn Văn A đạt điểm Toán cao.\"",
        "D2: \"Em B lớp 7A10 hạnh kiểm Tốt.\"",
        "D3: \"Học phí năm 2024-2025 lớp 7 là...\"",
    ]
    box(ax, 0.3, 1.0, 4.5, 3.6, "", fc="#E3F2FD", ec="#0D47A1", lw=1.3)
    ax.text(2.55, 4.2, "Tài liệu nguồn", ha="center", fontsize=11, weight="bold", color="#0D47A1")
    for i, d in enumerate(docs):
        ax.text(0.5, 3.7 - i * 0.8, d, fontsize=9.5)
        ax.text(0.5, 3.45 - i * 0.8, "→ tokenize + lowercase + asciifolding", fontsize=8, style="italic", color="#37474F")

    # Inverted index
    box(ax, 5.5, 1.0, 7.2, 3.6, "", fc="#FFF3E0", ec="#E65100", lw=1.3)
    ax.text(9.1, 4.2, "Inverted Index (term → posting list)", ha="center", fontsize=11, weight="bold", color="#E65100")
    terms = [
        ("toan", "D1:[3]"),
        ("hoc-sinh", "—"),
        ("hanh-kiem", "D2:[4]"),
        ("hoc-phi", "D3:[1]"),
        ("nam", "D3:[2]"),
        ("lop-7", "D2:[2], D3:[5]"),
    ]
    for i, (term, postings) in enumerate(terms):
        y = 3.7 - i * 0.4
        ax.text(5.7, y, term, fontsize=10, weight="bold", color="#E65100")
        ax.text(8.0, y, "→", fontsize=10)
        ax.text(8.3, y, postings, fontsize=9.5, family="monospace", color="#37474F")

    # Arrow
    arrow(ax, 4.8, 2.8, 5.5, 2.8, color="#7B1FA2")

    # Bottom
    ax.text(6.5, 0.45,
            "Khi người dùng truy vấn 'lop 7 hoc phi' → tra cứu nhanh các posting list → giao tập → xếp hạng BM25.",
            ha="center", fontsize=9.5, style="italic", color="#37474F")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_9_inverted_index.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 10: HNSW graph minh hoạ
# =====================================================================
def fig_hnsw():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
    ax.text(6, 6.6, "Hierarchical Navigable Small World (HNSW)",
            ha="center", fontsize=13, weight="bold")
    ax.text(6, 6.2, "Cấu trúc đồ thị phân tầng cho tìm kiếm KNN xấp xỉ trên Elasticsearch dense_vector",
            ha="center", fontsize=10, style="italic", color="#37474F")

    np.random.seed(42)
    layers = [
        (5.0, 0.7, 3, "#B71C1C", "Tầng 2: thưa, định tuyến nhanh xa"),
        (3.4, 0.7, 8, "#E65100", "Tầng 1: trung bình"),
        (1.6, 0.7, 18, "#1B5E20", "Tầng 0: dày, chứa toàn bộ vector"),
    ]
    rng = np.random.default_rng(7)

    nodes_by_layer = []
    for cy, h, n, color, label in layers:
        xs = rng.uniform(1, 11, size=n)
        ys = rng.uniform(cy - h/2, cy + h/2, size=n)
        nodes = list(zip(xs, ys))
        nodes_by_layer.append((nodes, color))
        # connect nearest neighbors within layer
        for i, (xi, yi) in enumerate(nodes):
            # find nearest 2
            d = sorted([(abs(xi-xj)+abs(yi-yj), j) for j, (xj, yj) in enumerate(nodes) if j != i])[:2]
            for _, j in d:
                xj, yj = nodes[j]
                ax.plot([xi, xj], [yi, yj], color=color, alpha=0.3, lw=0.7)
        for (xi, yi) in nodes:
            ax.plot(xi, yi, "o", color=color, markersize=6)
        ax.text(0.3, cy, label, fontsize=9.5, va="center", color=color)

    # Vertical jump arrows between layers
    arrow(ax, 5.0, 5.0, 5.0, 3.7, color="#7B1FA2", style="-|>")
    arrow(ax, 5.0, 3.7, 5.0, 1.7, color="#7B1FA2", style="-|>")
    ax.text(5.2, 4.4, "greedy descend", fontsize=9, color="#7B1FA2", style="italic")
    ax.text(5.2, 2.6, "greedy descend", fontsize=9, color="#7B1FA2", style="italic")

    # Query node
    box(ax, 9.6, 5.4, 2.0, 0.6, "Query vector", fc="#FFF9C4", ec="#F57F17", fontsize=9.5)
    arrow(ax, 9.6, 5.7, 5.0, 5.0, color="#F57F17", style="-|>")

    # Params box
    ax.text(6, 0.3,
            "Tham số chính: m (số neighbor mỗi node, mặc định 16) · ef_construction (chất lượng build, 100) · "
            "ef_search (chất lượng search, runtime)",
            ha="center", fontsize=9.2, style="italic", color="#37474F")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_10_hnsw.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 11: Dự kiến kết quả baseline (bar chart)
# =====================================================================
def fig_baseline_chart():
    fig, ax = plt.subplots(figsize=(12, 6))
    baselines = ["raw_llm", "bm25_only", "vector_only", "function_only", "hybrid_full"]
    metrics = {
        "Tool recall":        [0.10, 0.55, 0.55, 0.88, 0.92],
        "Citation match":     [0.05, 0.62, 0.58, 0.70, 0.86],
        "Not-found handle":   [0.20, 0.55, 0.50, 0.78, 0.90],
        "ACL compliance":     [0.30, 0.65, 0.60, 0.92, 1.00],
    }
    x = np.arange(len(baselines))
    width = 0.20
    colors = ["#1565C0", "#1B5E20", "#E65100", "#4A148C"]
    for i, (name, vals) in enumerate(metrics.items()):
        ax.bar(x + (i - 1.5) * width, vals, width, label=name, color=colors[i], edgecolor="white", lw=0.6)

    ax.set_ylim(0, 1.10)
    ax.set_xticks(x); ax.set_xticklabels(baselines, fontsize=10)
    ax.set_ylabel("Điểm chuẩn hoá (0 – 1)", fontsize=10)
    ax.set_title("Dự kiến kết quả định lượng giữa 5 baseline trên bộ test set 80 case", fontsize=12, weight="bold")
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    ax.text(0.5, -0.20,
            "Chú thích: đây là giá trị KỲ VỌNG dùng để minh hoạ kế hoạch thực nghiệm; con số chính thức sẽ được công bố ở Chương 4 sau khi chạy đánh giá.",
            transform=ax.transAxes, ha="center", fontsize=8.5, style="italic", color="#37474F")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_11_baseline_chart.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


# =====================================================================
# FIG 12: Heatmap chunking ablation
# =====================================================================
def fig_chunking_heatmap():
    fig, ax = plt.subplots(figsize=(11, 5.5))
    sizes = [128, 256, 320, 512, 1024]
    overlaps = [0, 32, 64, 128]
    rng = np.random.default_rng(11)
    # peak ở 320 × 64
    Z = np.zeros((len(overlaps), len(sizes)))
    for i, ov in enumerate(overlaps):
        for j, sz in enumerate(sizes):
            base = 0.65
            base += -((sz - 320) / 600) ** 2 * 0.30
            base += -((ov - 64) / 100) ** 2 * 0.12
            base += rng.normal(0, 0.015)
            Z[i, j] = max(0.40, min(0.92, base + 0.20))

    im = ax.imshow(Z, cmap="YlGnBu", aspect="auto", vmin=0.4, vmax=0.95)
    ax.set_xticks(range(len(sizes))); ax.set_xticklabels(sizes)
    ax.set_yticks(range(len(overlaps))); ax.set_yticklabels(overlaps)
    ax.set_xlabel("Kích thước chunk (token)", fontsize=10)
    ax.set_ylabel("Overlap (token)", fontsize=10)
    ax.set_title("Dự kiến: F1 nhóm tài liệu theo (chunk_size × overlap)", fontsize=12, weight="bold")
    for i in range(len(overlaps)):
        for j in range(len(sizes)):
            ax.text(j, i, f"{Z[i,j]:.2f}", ha="center", va="center",
                    color="white" if Z[i,j] > 0.7 else "#212121", fontsize=10, weight="bold")
    fig.colorbar(im, ax=ax, label="F1 (kỳ vọng)")
    # mark peak
    pi, pj = np.unravel_index(np.argmax(Z), Z.shape)
    ax.add_patch(patches.Rectangle((pj - 0.45, pi - 0.45), 0.9, 0.9,
                                    edgecolor="#B71C1C", facecolor="none", lw=2.5))

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_12_chunking_heatmap.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white"); plt.close()
    print("Saved", out)


if __name__ == "__main__":
    fig_pipeline()
    fig_retrieval_modes()
    fig_rrf_example()
    fig_chunking()
    fig_rbac()
    fig_inverted_index()
    fig_hnsw()
    fig_baseline_chart()
    fig_chunking_heatmap()
    print("DONE - 9 ảnh bổ sung")
