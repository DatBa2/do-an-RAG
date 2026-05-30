"""Admin Dashboard — Streamlit app.

Run: streamlit run admin_dashboard.py

Features:
- Overview: stats audit log, embedding cache, ES indices.
- Playground: thử hỏi-đáp với hệ thống (chọn role, bật/tắt verify).
- Audit log: xem N truy vấn gần nhất, filter theo chat_id.
- Documents: upload tài liệu mới và ingest.
- Retrieval inspector: thử retrieval thuần (bm25 / vector / hybrid) — show hits + scores.
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st
from elasticsearch import Elasticsearch

from modules import config
from modules.audit import AUDIT
from modules.doc_search import search_documents_raw, format_for_llm
from modules.embeddings import cache_stats
from modules.ingest_docs import ES_DOCS_INDEX, ingest_documents
from es_main import AdvisorContext, get_advisor

st.set_page_config(page_title="RAG Admin", page_icon="🎓", layout="wide")


def es_client():
    return Elasticsearch(config.ES_HOST, request_timeout=30)


# --- Sidebar ---
st.sidebar.title("🎓 RAG Admin")
page = st.sidebar.radio(
    "Trang", ["Overview", "Playground", "Retrieval", "Audit log", "Documents"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption(f"ES: `{config.ES_HOST}`")
st.sidebar.caption(f"Model: `{config.GEMINI_MODEL}`")


# --- Overview ---
if page == "Overview":
    st.title("Tổng quan hệ thống")

    col1, col2, col3, col4 = st.columns(4)
    try:
        es = es_client()
        ok = es.ping()
    except Exception:
        ok = False
    col1.metric("Elasticsearch", "✅ Online" if ok else "❌ Offline")

    try:
        hs_count = es.count(index=config.ES_INDEX).get("count", 0) if ok else 0
        col2.metric("Docs hs_records", f"{hs_count:,}")
    except Exception:
        col2.metric("Docs hs_records", "—")

    try:
        docs_count = es.count(index=ES_DOCS_INDEX).get("count", 0) if ok else 0
        col3.metric("Chunks internal_docs", f"{docs_count:,}")
    except Exception:
        col3.metric("Chunks internal_docs", "—")

    cs = cache_stats()
    col4.metric("Embedding cache", f"{cs['entries']:,}")

    st.markdown("---")
    st.subheader("Audit stats")
    s = AUDIT.stats()
    a, b, c, d = st.columns(4)
    a.metric("Tổng queries", s["total"])
    b.metric("Thành công", f"{s['success']} ({s['success_rate']*100:.1f}%)")
    c.metric("Latency TB (ms)", s["avg_latency_ms"])
    d.metric("Theo role", json.dumps(s["by_role"], ensure_ascii=False))


# --- Playground (multi-turn chat) ---
elif page == "Playground":
    st.title("💬 Cố vấn học tập")

    # Sidebar config — đặt trong sidebar cùng để chat panel rộng tối đa
    with st.sidebar:
        st.markdown("### Cấu hình hội thoại")
        role = st.selectbox(
            "Role",
            ["parent", "teacher", "admin"],
            key="pg_role",
            help="Ảnh hưởng tới ACL tài liệu và quyền truy cập.",
        )
        rewrite = st.checkbox("Query rewriting", value=True, key="pg_rewrite")
        verify = st.checkbox("Self-RAG verify", value=False, key="pg_verify")
        show_meta = st.checkbox("Hiện metadata mỗi lượt", value=True, key="pg_meta")
        st.markdown("---")
        col_clear, col_count = st.columns([2, 1])
        if col_clear.button("🧹 New chat", use_container_width=True):
            st.session_state["pg_messages"] = []
            st.session_state["pg_history"] = []
            st.rerun()
        col_count.metric("Lượt", len(st.session_state.get("pg_messages", [])) // 2)

    # Khởi tạo state
    if "pg_messages" not in st.session_state:
        st.session_state["pg_messages"] = []  # list[{role, content, meta?}]
    if "pg_history" not in st.session_state:
        st.session_state["pg_history"] = []  # Gemini chat history format

    SUGGESTIONS = [
        "Điểm Toán của Lê Nguyễn Minh Trí lớp 7A10 học kỳ 2",
        "Top 5 lớp 7A10 học kỳ 2",
        "Học sinh nghỉ học không phép quá 5 buổi bị xử lý thế nào?",
        "Tiêu chí xếp loại học sinh Xuất sắc?",
    ]
    if not st.session_state["pg_messages"]:
        st.caption("Gợi ý câu hỏi — bấm để gửi:")
        cols = st.columns(2)
        for i, s in enumerate(SUGGESTIONS):
            if cols[i % 2].button(s, key=f"sug_{i}", use_container_width=True):
                st.session_state["_pending_q"] = s
                st.rerun()

    # Render lịch sử
    for msg in st.session_state["pg_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            meta = msg.get("meta")
            if meta and show_meta and msg["role"] == "assistant":
                bits = [f"⏱ {meta['elapsed_ms']/1000:.2f}s"]
                if meta.get("tools_called"):
                    bits.append("🔧 " + " → ".join(f"`{t}`" for t in meta["tools_called"]))
                if meta.get("citations"):
                    bits.append(f"📚 {len(meta['citations'])} nguồn")
                st.caption(" • ".join(bits))
                if meta.get("rewritten_query"):
                    st.caption(f"✏ Query rewritten: _{meta['rewritten_query']}_")
                if meta.get("citations"):
                    with st.expander(f"📚 Nguồn trích dẫn ({len(meta['citations'])})"):
                        for c in meta["citations"]:
                            st.markdown(f"**{c.get('title')}** — _{c.get('section')}_")
                            st.caption(c.get("source_path"))
                            st.write(c.get("content"))
                            st.markdown("---")

    # Input — chấp nhận từ chat_input hoặc từ nút gợi ý
    user_input = st.chat_input("Hỏi về điểm số, xếp hạng, nội quy, học phí...")
    if not user_input and "_pending_q" in st.session_state:
        user_input = st.session_state.pop("_pending_q")

    if user_input:
        st.session_state["pg_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Đang suy nghĩ..."):
                advisor = get_advisor()
                ctx = AdvisorContext(role=role, rewrite=rewrite, verify=verify)
                # Truyền lịch sử Gemini cho multi-turn
                r = advisor.answer(
                    user_input,
                    list(st.session_state["pg_history"]),
                    ctx,
                )
            st.markdown(r.answer)
            if show_meta:
                bits = [f"⏱ {r.elapsed_ms/1000:.2f}s"]
                if r.tools_called:
                    bits.append("🔧 " + " → ".join(f"`{t}`" for t in r.tools_called))
                if r.citations:
                    bits.append(f"📚 {len(r.citations)} nguồn")
                st.caption(" • ".join(bits))
                if r.rewritten_query:
                    st.caption(f"✏ Query rewritten: _{r.rewritten_query}_")
                if r.citations:
                    with st.expander(f"📚 Nguồn trích dẫn ({len(r.citations)})"):
                        for c in r.citations:
                            st.markdown(f"**{c.get('title')}** — _{c.get('section')}_")
                            st.caption(c.get("source_path"))
                            st.write(c.get("content"))
                            st.markdown("---")

        # Persist
        st.session_state["pg_messages"].append({
            "role": "assistant",
            "content": r.answer,
            "meta": {
                "elapsed_ms": r.elapsed_ms,
                "tools_called": r.tools_called,
                "citations": r.citations,
                "rewritten_query": r.rewritten_query,
            },
        })
        st.session_state["pg_history"].append({"role": "user", "parts": [user_input]})
        st.session_state["pg_history"].append({"role": "model", "parts": [r.answer]})
        # Cắt history để tránh phình
        max_turns = config.HISTORY_TURNS
        st.session_state["pg_history"] = st.session_state["pg_history"][-max_turns * 2:]


# --- Retrieval inspector ---
elif page == "Retrieval":
    st.title("🔍 Retrieval Inspector")
    st.caption("So sánh trực tiếp các strategy retrieval trên cùng câu hỏi.")
    q = st.text_input("Câu hỏi", "Quy định miễn giảm học phí")
    k = st.slider("k", 1, 10, 5)
    role = st.selectbox("Role filter", ["parent", "teacher", "admin", "any"])

    if st.button("Tìm kiếm", type="primary"):
        col1, col2, col3 = st.columns(3)
        for col, mode in zip([col1, col2, col3], ["bm25", "vector", "hybrid"]):
            with col:
                st.subheader(f"`{mode}`")
                t0 = time.time()
                try:
                    hits = search_documents_raw(q, k=k, mode=mode, role=role)
                    formatted = format_for_llm(hits)
                except Exception as e:
                    st.error(str(e))
                    continue
                st.caption(f"⏱ {(time.time()-t0)*1000:.0f}ms • {len(formatted)} hits")
                for d in formatted:
                    with st.expander(f"#{d['rank']} • {d['title']} — score {d['score']}"):
                        st.caption(f"{d['section']} • {d['source_path']}")
                        st.write(d["content"])


# --- Audit log ---
elif page == "Audit log":
    st.title("📋 Audit log")
    col1, col2 = st.columns([1, 3])
    with col1:
        limit = st.number_input("Số bản ghi", 10, 1000, 100, step=10)
        chat_id = st.text_input("Filter chat_id", "")
        chat_id_int = int(chat_id) if chat_id.isdigit() else None
    with col2:
        rows = AUDIT.recent(limit=int(limit), chat_id=chat_id_int)
        st.caption(f"{len(rows)} bản ghi")

    if rows:
        for r in rows:
            ts = datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            tools = ", ".join(json.loads(r["tools_called"])) or "—"
            with st.expander(
                f"[{ts}] {r['role']} @{r['chat_id']} • "
                f"{r['latency_ms']}ms • {'✅' if r['success'] else '❌'} — "
                f"{r['question'][:80]}"
            ):
                st.caption(f"Tools: {tools}")
                st.markdown("**Q:** " + r["question"])
                st.markdown("**A:** " + r["answer"])


# --- Documents ---
elif page == "Documents":
    st.title("📚 Documents")
    docs_dir = config.PROJECT_ROOT / "documents"
    files = sorted(p for p in docs_dir.glob("*") if p.is_file())
    st.caption(f"Thư mục: `{docs_dir}` • {len(files)} file")

    for p in files:
        with st.expander(f"📄 {p.name} ({p.stat().st_size//1024} KB)"):
            st.code(p.read_text(encoding="utf-8")[:2000], language="markdown")

    st.markdown("---")
    st.subheader("Upload tài liệu mới")
    uploaded = st.file_uploader("File .md hoặc .txt", type=["md", "txt"], accept_multiple_files=True)
    if uploaded and st.button("Lưu + Ingest"):
        for f in uploaded:
            dest = docs_dir / f.name
            dest.write_bytes(f.read())
            st.success(f"Đã lưu: {dest}")
        with st.spinner("Đang ingest..."):
            n = ingest_documents(docs_dir=docs_dir, recreate=False)
        st.success(f"Đã ingest {n} chunks.")
        st.rerun()

    st.markdown("---")
    st.subheader("Reindex toàn bộ")
    if st.button("Re-ingest (xoá + index lại)"):
        with st.spinner("Đang chạy..."):
            n = ingest_documents(docs_dir=docs_dir, recreate=True)
        st.success(f"Đã ingest {n} chunks.")
