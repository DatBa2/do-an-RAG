"""Hybrid retrieval cho tài liệu nội bộ.

Triển khai 3 strategy có thể chọn qua tham số `mode`:
- "bm25"   : chỉ BM25 (baseline).
- "vector" : chỉ KNN trên embedding (baseline).
- "hybrid" : BM25 + KNN gộp bằng RRF (Reciprocal Rank Fusion) — hệ thống thật.

Trả về kết quả kèm citation (source_path + section) để LLM trích nguồn.
"""
import logging
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch

from modules import config
from modules.embeddings import embed_text
from modules.ingest_docs import ES_DOCS_INDEX

log = logging.getLogger("doc_search")

DEFAULT_K = 5
RRF_RANK_WINDOW = 50
RRF_K = 60  # hằng số RRF chuẩn

_es: Optional[Elasticsearch] = None


def _client() -> Elasticsearch:
    global _es
    if _es is None:
        _es = Elasticsearch(config.ES_HOST, request_timeout=60)
    return _es


def _role_filter(role: Optional[str]) -> List[Dict[str, Any]]:
    if not role or role == "any":
        return []
    return [{"term": {"allowed_roles": role}}]


def _bm25_search(query: str, k: int, role: Optional[str]) -> List[Dict[str, Any]]:
    body = {
        "size": k,
        "query": {
            "bool": {
                "must": [{"match": {"content": {"query": query, "operator": "or"}}}],
                "filter": _role_filter(role),
            }
        },
    }
    res = _client().search(index=ES_DOCS_INDEX, body=body)
    return res.get("hits", {}).get("hits", [])


def _knn_search(query: str, k: int, role: Optional[str]) -> List[Dict[str, Any]]:
    qvec = embed_text(query, task_type="retrieval_query")
    body = {
        "size": k,
        "knn": {
            "field": "embedding",
            "query_vector": qvec,
            "k": k,
            "num_candidates": max(50, k * 10),
            "filter": _role_filter(role),
        },
    }
    res = _client().search(index=ES_DOCS_INDEX, body=body)
    return res.get("hits", {}).get("hits", [])


def _rrf_fuse(
    lists: List[List[Dict[str, Any]]], k_top: int, rrf_k: int = RRF_K
) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion: score = sum(1 / (rrf_k + rank_i))."""
    scores: Dict[str, float] = {}
    docs: Dict[str, Dict[str, Any]] = {}
    for hits in lists:
        for rank, h in enumerate(hits, start=1):
            doc_id = h["_id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank)
            if doc_id not in docs:
                docs[doc_id] = h
    fused = sorted(
        ((doc_id, score) for doc_id, score in scores.items()),
        key=lambda x: x[1],
        reverse=True,
    )
    out = []
    for doc_id, score in fused[:k_top]:
        h = dict(docs[doc_id])
        h["_score"] = score
        out.append(h)
    return out


def search_documents_raw(
    query: str,
    k: int = DEFAULT_K,
    mode: str = "hybrid",
    role: Optional[str] = "parent",
) -> List[Dict[str, Any]]:
    """Trả về danh sách hit thô (ES hit format)."""
    if mode == "bm25":
        return _bm25_search(query, k, role)
    if mode == "vector":
        return _knn_search(query, k, role)
    if mode == "hybrid":
        bm = _bm25_search(query, RRF_RANK_WINDOW, role)
        kn = _knn_search(query, RRF_RANK_WINDOW, role)
        return _rrf_fuse([bm, kn], k_top=k)
    raise ValueError(f"Unknown mode: {mode}")


def format_for_llm(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format gọn để đưa vào prompt LLM. Giới hạn độ dài content để tiết kiệm token."""
    out = []
    for i, h in enumerate(hits, start=1):
        src = h["_source"]
        content = src.get("content", "")
        if len(content) > 800:
            content = content[:800] + "..."
        out.append({
            "rank": i,
            "title": src.get("title"),
            "section": src.get("section"),
            "source_path": src.get("source_path"),
            "content": content,
            "score": round(h.get("_score") or 0, 4),
        })
    return out


def search_documents(
    query: str,
    k: int = DEFAULT_K,
    role: Optional[str] = "parent",
) -> Dict[str, Any]:
    """Tool wrapper trả về dict cho LLM (đã filter theo role)."""
    try:
        hits = search_documents_raw(query, k=k, mode="hybrid", role=role)
    except Exception as e:
        log.exception("search_documents lỗi")
        return {"status": "error", "message": str(e)}
    if not hits:
        return {
            "status": "not_found",
            "message": "Không tìm thấy tài liệu nội bộ nào khớp với câu hỏi.",
        }
    return {"status": "success", "data": format_for_llm(hits)}
