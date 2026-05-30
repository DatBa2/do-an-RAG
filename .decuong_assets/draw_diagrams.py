"""Vẽ 3 sơ đồ kiến trúc cho đề cương đề án."""
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT_DIR, exist_ok=True)

# Tiếng Việt font fallback
plt.rcParams["font.family"] = ["DejaVu Sans", "Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, text, fc="#E3F2FD", ec="#1565C0", fontsize=10, bold=False):
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02",
        linewidth=1.2, edgecolor=ec, facecolor=fc,
    )
    ax.add_patch(rect)
    ax.text(
        x + w / 2, y + h / 2, text,
        ha="center", va="center", fontsize=fontsize,
        weight="bold" if bold else "normal", wrap=True,
    )


def arrow(ax, x1, y1, x2, y2, color="#37474F", style="-|>", label=None):
    ar = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style, mutation_scale=14,
        linewidth=1.2, color=color,
    )
    ax.add_patch(ar)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.08, label,
                ha="center", va="bottom", fontsize=8, style="italic", color=color)


# =====================================================================
# Sơ đồ 1: KIẾN TRÚC TỔNG THỂ 4 LỚP
# =====================================================================
def figure_1_architecture():
    fig, ax = plt.subplots(figsize=(12, 8.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.text(6, 9.6, "Kiến trúc 4 lớp của hệ thống RAG trợ lý ảo AI",
            ha="center", fontsize=14, weight="bold")

    # Lớp 1: Presentation
    ax.text(0.4, 8.4, "1. Presentation", fontsize=10, weight="bold",
            color="#0D47A1", rotation=90, va="center")
    box(ax, 1.8, 7.7, 3.6, 1.2, "Telegram Bot\n(python-telegram-bot v21)\n/start /help /stats /whoami",
        fc="#BBDEFB", ec="#0D47A1")
    box(ax, 6.6, 7.7, 3.6, 1.2, "Streamlit Dashboard\nOverview · Playground\nRetrieval Inspector · Audit · Docs",
        fc="#BBDEFB", ec="#0D47A1")

    # Lớp 2: Orchestration
    ax.text(0.4, 6.0, "2. Orchestration", fontsize=10, weight="bold",
            color="#1B5E20", rotation=90, va="center")
    box(ax, 1.8, 5.3, 8.4, 1.4,
        "Class Advisor\nrewrite (multi-turn)  →  planner (LLM Gemini 2.5)\n→  dispatcher (RBAC gate ADMIN_ONLY)  →  verifier (Self-RAG lite)",
        fc="#C8E6C9", ec="#1B5E20", fontsize=9.5)

    # Lớp 3: Retrieval & Tools
    ax.text(0.4, 3.6, "3. Retrieval & Tools", fontsize=10, weight="bold",
            color="#E65100", rotation=90, va="center")
    box(ax, 1.8, 2.9, 4.0, 1.4,
        "Function Calling Toolset\n18 tool dữ liệu HS + 2 tool ADMIN_ONLY\n(điểm, chuyên cần, xếp hạng, top N…)",
        fc="#FFE0B2", ec="#E65100", fontsize=9)
    box(ax, 6.2, 2.9, 4.0, 1.4,
        "Hybrid Document Search\nBM25  +  KNN (HNSW)  →  RRF (k=60)\nACL filter ở cả 2 nhánh",
        fc="#FFE0B2", ec="#E65100", fontsize=9)

    # Lớp 4: Data
    ax.text(0.4, 1.2, "4. Data", fontsize=10, weight="bold",
            color="#4A148C", rotation=90, va="center")
    box(ax, 1.8, 0.4, 2.6, 1.4,
        "ES index\nhs_records\n(student, mark)",
        fc="#E1BEE7", ec="#4A148C", fontsize=9)
    box(ax, 4.8, 0.4, 2.6, 1.4,
        "ES index\ninternal_docs\n(dense_vector 768)",
        fc="#E1BEE7", ec="#4A148C", fontsize=9)
    box(ax, 7.8, 0.4, 2.4, 1.4,
        "SQLite\naudit · cache · history",
        fc="#E1BEE7", ec="#4A148C", fontsize=9)

    # Mũi tên giữa các lớp
    arrow(ax, 3.6, 7.7, 5.0, 6.7)
    arrow(ax, 8.4, 7.7, 7.0, 6.7)
    arrow(ax, 3.8, 5.3, 3.8, 4.3)
    arrow(ax, 8.2, 5.3, 8.2, 4.3)
    arrow(ax, 3.8, 2.9, 3.1, 1.8)
    arrow(ax, 8.2, 2.9, 8.9, 1.8)
    arrow(ax, 5.0, 2.9, 5.0, 1.8)

    # Người dùng
    box(ax, 4.6, 9.0, 2.8, 0.5,
        "Người dùng (parent / teacher / admin)",
        fc="#FFF9C4", ec="#F57F17", fontsize=9, bold=True)
    arrow(ax, 6.0, 9.0, 3.6, 8.9)
    arrow(ax, 6.0, 9.0, 8.4, 8.9)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_1_architecture.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()
    print("Saved", out)


# =====================================================================
# Sơ đồ 2: SEQUENCE - CÂU HỎI TÀI LIỆU (HYBRID RAG)
# =====================================================================
def figure_2_sequence_docs():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(6, 9.6,
            "Sequence: câu hỏi tài liệu nội bộ (Hybrid BM25 + KNN + RRF)",
            ha="center", fontsize=13, weight="bold")

    # Actor lanes
    lanes = [
        ("User", 1.0, "#1565C0"),
        ("Bot", 2.8, "#1B5E20"),
        ("Advisor", 5.0, "#6A1B9A"),
        ("doc_search", 7.4, "#E65100"),
        ("Elasticsearch", 9.6, "#AD1457"),
        ("LLM Gemini", 11.2, "#283593"),
    ]
    for name, x, color in lanes:
        ax.plot([x, x], [0.8, 9.0], linestyle="--", color=color, linewidth=1)
        box(ax, x - 0.6, 8.6, 1.2, 0.5, name, fc="#ECEFF1", ec=color, fontsize=9, bold=True)

    def msg(ax, x_from, x_to, y, label, fontsize=8.5, color="#37474F"):
        arrow(ax, x_from, y, x_to, y, color=color)
        ax.text((x_from + x_to) / 2, y + 0.12, label,
                ha="center", va="bottom", fontsize=fontsize, color=color)

    # Sequence steps - chỉ dùng arrow 1 chiều
    msg(ax, 1.0, 2.8, 7.9, "1. \"Học phí lớp 7 năm 2024-2025?\"")
    msg(ax, 2.8, 5.0, 7.3, "2. forward + role=parent")
    msg(ax, 5.0, 5.0, 6.7, "3. rewrite (skip - lượt đầu)")
    msg(ax, 5.0, 11.2, 6.1, "4. plan: gọi search_documents")
    msg(ax, 11.2, 5.0, 5.5, "5. function_call(query, role, k=5)", color="#283593")
    msg(ax, 5.0, 7.4, 4.9, "6. search(query, role)")
    msg(ax, 7.4, 9.6, 4.3, "7a. BM25 query (filter allowed_roles)")
    msg(ax, 7.4, 9.6, 3.7, "7b. KNN query (filter allowed_roles)")
    msg(ax, 9.6, 7.4, 3.1, "8. 2 ranked lists", color="#AD1457")
    msg(ax, 7.4, 5.0, 2.5, "9. RRF fuse → top-k chunks", color="#E65100")
    msg(ax, 5.0, 11.2, 1.9, "10. context + system prompt")
    msg(ax, 11.2, 5.0, 1.3, "11. câu trả lời + citation", color="#283593")
    msg(ax, 5.0, 2.8, 0.9, "12. verify → bot → user")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_2_sequence_docs.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()
    print("Saved", out)


# =====================================================================
# Sơ đồ 3: SEQUENCE - CÂU HỎI ĐIỂM (FUNCTION CALLING + RBAC)
# =====================================================================
def figure_3_sequence_function():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(6, 9.6,
            "Sequence: câu hỏi dữ liệu cấu trúc (Function Calling + RBAC gate)",
            ha="center", fontsize=13, weight="bold")

    lanes = [
        ("User (parent)", 1.0, "#1565C0"),
        ("Bot", 2.8, "#1B5E20"),
        ("Advisor", 5.0, "#6A1B9A"),
        ("Dispatcher", 7.4, "#E65100"),
        ("ES hs_records", 9.6, "#AD1457"),
        ("LLM Gemini", 11.2, "#283593"),
    ]
    for name, x, color in lanes:
        ax.plot([x, x], [0.8, 9.0], linestyle="--", color=color, linewidth=1)
        box(ax, x - 0.7, 8.6, 1.4, 0.5, name, fc="#ECEFF1", ec=color, fontsize=8.5, bold=True)

    def msg(ax, x_from, x_to, y, label, fontsize=8.5, color="#37474F"):
        arrow(ax, x_from, y, x_to, y, color=color)
        ax.text((x_from + x_to) / 2, y + 0.12, label,
                ha="center", va="bottom", fontsize=fontsize, color=color)

    msg(ax, 1.0, 2.8, 8.0, "1. \"Điểm Toán em Trí lớp 7A10 HK2?\"")
    msg(ax, 2.8, 5.0, 7.4, "2. role=parent + history")
    msg(ax, 5.0, 11.2, 6.8, "3. plan với 20 FunctionDeclaration")
    msg(ax, 11.2, 5.0, 6.2, "4. function_call: get_subject_score(...)", color="#283593")
    msg(ax, 5.0, 7.4, 5.6, "5. dispatch (check ADMIN_ONLY=False → OK)")
    msg(ax, 7.4, 9.6, 5.0, "6. query: doc_type=mark AND class=7A10 …")
    msg(ax, 9.6, 7.4, 4.4, "7. điểm TX/GK/CK/TK + GPA", color="#AD1457")
    msg(ax, 7.4, 5.0, 3.8, "8. function_response JSON")
    msg(ax, 5.0, 11.2, 3.2, "9. tổng hợp tự nhiên tiếng Việt")
    msg(ax, 11.2, 5.0, 2.6, "10. câu trả lời + citation", color="#283593")
    msg(ax, 5.0, 5.0, 2.0, "11. _verify() grounding")
    msg(ax, 5.0, 2.8, 1.4, "12. answer (+ warning nếu có)")
    msg(ax, 2.8, 1.0, 0.8, "13. trả lời + ghi audit log")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "fig_3_sequence_function.png")
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close()
    print("Saved", out)


if __name__ == "__main__":
    figure_1_architecture()
    figure_2_sequence_docs()
    figure_3_sequence_function()
    print("DONE")
