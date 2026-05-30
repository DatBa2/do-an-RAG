"""Đánh giá hệ thống RAG trên test_set.json v2 với 5 baseline + multi-turn + nhiều category.

Baselines:
- raw_llm     : Gemini không có tool, không có context.
- bm25_only   : chỉ BM25 trên tài liệu (qua doc_search mode=bm25).
- vector_only : chỉ KNN trên embedding (qua doc_search mode=vector).
- function_only: chỉ function-calling cho dữ liệu học sinh (không có search_documents).
- hybrid      : full system (function-calling + hybrid retrieval RRF + verify tuỳ chọn).

Metrics:
- tool_recall      : % câu gọi đúng (ít nhất 1) tool kỳ vọng.
- keyword_recall   : % keyword kỳ vọng xuất hiện trong câu trả lời.
- citation_match   : % câu có expected_source xuất hiện trong citations.
- ambiguity_handle : % câu ambiguity xử lý đúng (trả lời có hỏi lại + options).
- not_found_handle : % câu not_found không bịa số liệu (không match keyword điểm cụ thể).
- latency          : avg / p50 / p95 (ms).
- success_rate     : % không bị error.

Usage:
    python -m evaluation.run_eval --mode hybrid
    python -m evaluation.run_eval --all --out evaluation/results/run1.json
    python -m evaluation.run_eval --all --category structured,docs
"""
import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import Tool

# allow running both forms
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import config  # noqa: E402
from modules.doc_search import format_for_llm, search_documents_raw  # noqa: E402
from es_main import (  # noqa: E402
    STRUCTURED_TOOLS,
    SYSTEM_INSTRUCTION,
    Advisor,
    AdvisorContext,
)

config.configure_logging()
log = logging.getLogger("eval")
genai.configure(api_key=config.GEMINI_API_KEY)

TEST_SET_PATH = Path(__file__).resolve().parent / "test_set.json"

# Câu hỏi nghi ngờ bịa khi data không có
HALLUCINATION_PATTERNS = [
    r"\b\d+(?:\.\d+)?\s*(?:điểm|đ)\b",  # con số kèm "điểm"
    r"GPA\s*[:=]?\s*\d+(?:\.\d+)?",
    r"hạng\s*\d+",
]


def load_test_set(path: Optional[Path] = None) -> Dict[str, Any]:
    return json.loads((path or TEST_SET_PATH).read_text(encoding="utf-8"))


def keyword_hit_rate(answer: str, keywords: List[str]) -> float:
    if not keywords:
        return 1.0
    a = answer.lower()
    hits = sum(1 for k in keywords if k.lower() in a)
    return hits / len(keywords)


def detect_hallucination(answer: str) -> bool:
    """True nếu câu trả lời chứa con số đáng nghi ngờ trong khi data không có."""
    a = answer.lower()
    if any(neg in a for neg in ["không tìm thấy", "không có dữ liệu", "chưa có", "không thể"]):
        return False
    return any(re.search(p, answer) for p in HALLUCINATION_PATTERNS)


def detect_ambiguity_response(answer: str) -> bool:
    """True nếu câu trả lời thực sự yêu cầu phụ huynh disambiguate."""
    markers = [
        "vui lòng cung cấp",
        "vui lòng cho biết",
        "có nhiều học sinh",
        "có nhiều bạn",
        "trùng tên",
        "xác định",
        "lớp nào",
        "mã học sinh",
    ]
    a = answer.lower()
    return sum(m in a for m in markers) >= 1


def detect_denied_response(answer: str) -> bool:
    """True nếu câu trả lời cho thấy bot từ chối đúng vì RBAC."""
    markers = [
        "không có quyền",
        "không được phép",
        "dành cho giáo viên",
        "dành cho quản trị",
        "không thể truy cập",
        "không có quyền truy cập",
        "denied",
        "liên hệ quản trị",
    ]
    a = answer.lower()
    return any(m in a for m in markers)


# --- Baselines ---
def run_raw_llm(question: str, history: Optional[List[Dict]] = None, **_) -> Dict[str, Any]:
    model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
    t0 = time.time()
    try:
        chat = model.start_chat(history=history or [])
        r = chat.send_message(question)
        return {
            "answer": (r.text or "").strip(),
            "tools_called": [],
            "citations": [],
            "elapsed_ms": int((time.time() - t0) * 1000),
            "success": True,
        }
    except Exception as e:
        return {
            "answer": f"(error) {e}",
            "tools_called": [],
            "citations": [],
            "elapsed_ms": int((time.time() - t0) * 1000),
            "success": False,
        }


def _retrieval_only_baseline(
    question: str,
    mode: str,
    history: Optional[List[Dict]] = None,
    role: str = "parent",
) -> Dict[str, Any]:
    t0 = time.time()
    try:
        hits = search_documents_raw(question, k=5, mode=mode, role=role)
    except Exception as e:
        return {
            "answer": f"(retrieval error) {e}",
            "tools_called": [],
            "citations": [],
            "elapsed_ms": int((time.time() - t0) * 1000),
            "success": False,
        }
    formatted = format_for_llm(hits)
    ctx_text = "\n\n".join(
        f"[{d['rank']}] {d['title']} / {d['section']} ({d['source_path']}):\n{d['content']}"
        for d in formatted
    ) or "(không có tài liệu)"
    prompt = (
        f"Dựa vào các đoạn tài liệu sau, trả lời bằng tiếng Việt, "
        f"trích nguồn cuối câu 'Nguồn: <title> (<source_path>)'.\n\n"
        f"=== Tài liệu ===\n{ctx_text}\n\n"
        f"=== Câu hỏi ===\n{question}\n\n=== Câu trả lời ==="
    )
    model = genai.GenerativeModel(model_name=config.GEMINI_MODEL)
    try:
        chat = model.start_chat(history=history or [])
        r = chat.send_message(prompt)
        return {
            "answer": (r.text or "").strip(),
            "tools_called": [f"search_{mode}"],
            "citations": [
                {"source_path": d["source_path"], "title": d["title"]} for d in formatted
            ],
            "elapsed_ms": int((time.time() - t0) * 1000),
            "success": True,
        }
    except Exception as e:
        return {
            "answer": f"(error) {e}",
            "tools_called": [f"search_{mode}"],
            "citations": [],
            "elapsed_ms": int((time.time() - t0) * 1000),
            "success": False,
        }


def run_bm25_only(question: str, **kw) -> Dict[str, Any]:
    return _retrieval_only_baseline(
        question, "bm25", history=kw.get("history"), role=kw.get("role", "parent")
    )


def run_vector_only(question: str, **kw) -> Dict[str, Any]:
    return _retrieval_only_baseline(
        question, "vector", history=kw.get("history"), role=kw.get("role", "parent")
    )


def _structured_only_tools() -> Tool:
    """Build a Tool excluding search_documents.

    Workaround: google-generativeai 0.8.x cannot re-wrap a proto Schema into
    FunctionDeclaration (needs dict). We convert proto → dict via proto.Message helper.
    """
    from google.generativeai.types import FunctionDeclaration
    import proto

    def to_dict(schema):
        if isinstance(schema, dict):
            return schema
        try:
            return proto.Message.to_dict(schema)
        except Exception:
            return type(schema).to_dict(schema) if hasattr(type(schema), "to_dict") else dict(schema)

    fds = [
        FunctionDeclaration(
            name=fd.name,
            description=fd.description,
            parameters=to_dict(fd.parameters),
        )
        for fd in STRUCTURED_TOOLS.function_declarations
        if fd.name != "search_documents"
    ]
    return Tool(function_declarations=fds)


class _FunctionOnlyAdvisor(Advisor):
    def __init__(self) -> None:
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            tools=[_structured_only_tools()],
            system_instruction=SYSTEM_INSTRUCTION,
        )
        self._verifier = None


_FN_ONLY: Optional[_FunctionOnlyAdvisor] = None


def run_function_only(question: str, **kw) -> Dict[str, Any]:
    global _FN_ONLY
    if _FN_ONLY is None:
        _FN_ONLY = _FunctionOnlyAdvisor()
    history = kw.get("history") or []
    r = _FN_ONLY.answer(
        question, history, AdvisorContext(role=kw.get("role", "parent"), rewrite=False)
    )
    return {
        "answer": r.answer,
        "tools_called": r.tools_called,
        "citations": [
            {"source_path": c.get("source_path"), "title": c.get("title")} for c in r.citations
        ],
        "elapsed_ms": r.elapsed_ms,
        "success": r.success,
    }


_HYBRID: Optional[Advisor] = None


def run_hybrid(
    question: str,
    history: Optional[List[Dict]] = None,
    verify: bool = False,
    rewrite: bool = True,
    role: str = "parent",
    **_,
) -> Dict[str, Any]:
    global _HYBRID
    if _HYBRID is None:
        _HYBRID = Advisor()
    r = _HYBRID.answer(
        question,
        list(history or []),
        AdvisorContext(role=role, rewrite=rewrite, verify=verify),
    )
    return {
        "answer": r.answer,
        "tools_called": r.tools_called,
        "citations": [
            {"source_path": c.get("source_path"), "title": c.get("title")} for c in r.citations
        ],
        "elapsed_ms": r.elapsed_ms,
        "success": r.success,
    }


BASELINES = {
    "raw_llm": run_raw_llm,
    "bm25_only": run_bm25_only,
    "vector_only": run_vector_only,
    "function_only": run_function_only,
    "hybrid": run_hybrid,
}


def _score_case(
    case: Dict[str, Any],
    question: str,
    expected_tools: List[str],
    expected_keywords: List[str],
    expected_source: Optional[str],
    expected_status: Optional[str],
    out: Dict[str, Any],
    expected_denied_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Tính các metric cho 1 turn."""
    called = set(out["tools_called"])
    expected = set(expected_tools or [])

    if not expected:
        tool_recall = 1.0  # OOS / security: không nên gọi tool nào quan trọng
    else:
        tool_recall = 1.0 if expected & called else 0.0

    kw_recall = keyword_hit_rate(out["answer"], expected_keywords or [])

    if expected_source:
        cite_paths = [c.get("source_path") for c in out["citations"]]
        citation_match = 1.0 if any(expected_source in (p or "") for p in cite_paths) else 0.0
    else:
        citation_match = None

    ambiguity_handle = None
    if expected_status == "ambiguous":
        ambiguity_handle = 1.0 if detect_ambiguity_response(out["answer"]) else 0.0

    not_found_handle = None
    if expected_status == "not_found":
        # Không được "bịa": không có con số điểm trong câu trả lời
        not_found_handle = 0.0 if detect_hallucination(out["answer"]) else 1.0

    # ACL compliance: nguồn cấm KHÔNG được xuất hiện trong citations
    acl_compliance = None
    if expected_denied_source:
        cite_paths = [c.get("source_path") for c in out["citations"]]
        leaked = any(expected_denied_source in (p or "") for p in cite_paths)
        acl_compliance = 0.0 if leaked else 1.0

    # Denial-handle: với case role=parent gọi tool admin-only, bot phải trả "denied"
    denial_handle = None
    if expected_status == "denied":
        denial_handle = 1.0 if detect_denied_response(out["answer"]) else 0.0

    return {
        "tool_recall": tool_recall,
        "keyword_recall": kw_recall,
        "citation_match": citation_match,
        "ambiguity_handle": ambiguity_handle,
        "not_found_handle": not_found_handle,
        "acl_compliance": acl_compliance,
        "denial_handle": denial_handle,
    }


_LAST_API_CALL_TS = [0.0]
_RATE_LIMIT_DELAY = float(os.environ.get("EVAL_RATE_LIMIT_DELAY", "13.0"))  # 5 RPM safe


def _rate_limit():
    """Đảm bảo tối thiểu _RATE_LIMIT_DELAY giây giữa các API call để tránh 429 (5 RPM)."""
    import time as _t
    elapsed = _t.time() - _LAST_API_CALL_TS[0]
    if elapsed < _RATE_LIMIT_DELAY:
        _t.sleep(_RATE_LIMIT_DELAY - elapsed)
    _LAST_API_CALL_TS[0] = _t.time()


def _run_with_retry(fn, *args, max_attempts=4, **kwargs):
    """Wrap a baseline runner; retry on 429 with exponential backoff."""
    import time as _t
    for attempt in range(max_attempts):
        _rate_limit()
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                wait = (2 ** attempt) * _RATE_LIMIT_DELAY
                log.warning("429 attempt %d/%d, wait %.1fs", attempt + 1, max_attempts, wait)
                _t.sleep(wait)
                continue
            raise
    log.error("Max retries reached for fn=%s", getattr(fn, "__name__", "?"))
    return {
        "answer": "(error) max retries",
        "citations": [],
        "tools_called": [],
        "success": False,
        "elapsed_ms": 0,
        "latency_ms": 0,
    }


def _run_single_turn_case(runner, case: Dict[str, Any], verify: bool, mode_name: str) -> Dict[str, Any]:
    question = case["question"]
    case_role = case.get("role", "parent")
    log.info("[%s] %s (role=%s) | %s", mode_name, case["id"], case_role, question[:60])
    if mode_name == "hybrid":
        out = _run_with_retry(runner, question, verify=verify, role=case_role)
    elif mode_name in {"bm25_only", "vector_only", "function_only"}:
        out = _run_with_retry(runner, question, role=case_role)
    else:
        out = _run_with_retry(runner, question)

    metrics = _score_case(
        case, question,
        case.get("expected_tools") or [],
        case.get("expected_keywords") or [],
        case.get("expected_source"),
        case.get("expected_status"),
        out,
        expected_denied_source=case.get("expected_denied_source"),
    )
    return {
        "id": case["id"],
        "category": case["category"],
        "role": case_role,
        "question": question,
        "answer": out["answer"],
        "tools_called": out["tools_called"],
        "citations": out["citations"],
        "elapsed_ms": out["elapsed_ms"],
        "success": out["success"],
        **metrics,
    }


def _run_multi_turn_case(runner, case: Dict[str, Any], verify: bool, mode_name: str) -> Dict[str, Any]:
    """Chạy multi-turn: build history giữa các turn, score per-turn rồi average."""
    history: List[Dict[str, Any]] = []
    turn_results: List[Dict[str, Any]] = []
    total_elapsed = 0
    total_success = True
    case_role = case.get("role", "parent")
    for ti, turn in enumerate(case["turns"]):
        q = turn["q"]
        log.info("[%s] %s T%d (role=%s) | %s", mode_name, case["id"], ti + 1, case_role, q[:60])
        if mode_name == "hybrid":
            out = runner(q, history=history, verify=verify, role=case_role)
        elif mode_name in {"bm25_only", "vector_only", "function_only"}:
            out = runner(q, history=history, role=case_role)
        else:
            out = runner(q, history=history)
        history.append({"role": "user", "parts": [q]})
        history.append({"role": "model", "parts": [out["answer"]]})

        m = _score_case(
            case, q,
            turn.get("expected_tools") or [],
            turn.get("expected_keywords") or [],
            turn.get("expected_source"),
            turn.get("expected_status"),
            out,
        )
        turn_results.append({
            "turn": ti + 1,
            "q": q,
            "answer": out["answer"],
            "tools_called": out["tools_called"],
            "elapsed_ms": out["elapsed_ms"],
            **m,
        })
        total_elapsed += out["elapsed_ms"]
        if not out["success"]:
            total_success = False

    # Aggregate: average per metric
    avg = lambda key: _avg([t[key] for t in turn_results if t.get(key) is not None])
    return {
        "id": case["id"],
        "category": case["category"],
        "question": " | ".join(t["q"] for t in turn_results),
        "answer": " || ".join(t["answer"][:200] for t in turn_results),
        "tools_called": sum((t["tools_called"] for t in turn_results), []),
        "citations": [],
        "elapsed_ms": total_elapsed,
        "success": total_success,
        "tool_recall": avg("tool_recall"),
        "keyword_recall": avg("keyword_recall"),
        "citation_match": None,
        "ambiguity_handle": None,
        "not_found_handle": None,
        "turns": turn_results,
    }


def run_one_mode(
    mode: str,
    cases: List[Dict[str, Any]],
    verify: bool = False,
) -> Dict[str, Any]:
    runner = BASELINES[mode]
    rows: List[Dict[str, Any]] = []
    for c in cases:
        if "turns" in c:
            row = _run_multi_turn_case(runner, c, verify, mode)
        else:
            row = _run_single_turn_case(runner, c, verify, mode)
        rows.append(row)
    return {"mode": mode, "rows": rows, "metrics": _aggregate(rows)}


def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = [r["elapsed_ms"] for r in rows]
    n = len(rows)
    succ = sum(1 for r in rows if r["success"])

    tool_recalls = [r["tool_recall"] for r in rows if r["tool_recall"] is not None]
    kw_recalls = [r["keyword_recall"] for r in rows if r["keyword_recall"] is not None]
    cite_eval = [r["citation_match"] for r in rows if r["citation_match"] is not None]
    amb_eval = [r["ambiguity_handle"] for r in rows if r["ambiguity_handle"] is not None]
    nf_eval = [r["not_found_handle"] for r in rows if r["not_found_handle"] is not None]
    acl_eval = [r.get("acl_compliance") for r in rows if r.get("acl_compliance") is not None]
    denial_eval = [r.get("denial_handle") for r in rows if r.get("denial_handle") is not None]

    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    cat_summary = {
        cat: {
            "n": len(items),
            "tool_recall": _avg([x["tool_recall"] for x in items if x["tool_recall"] is not None]),
            "keyword_recall": _avg([x["keyword_recall"] for x in items if x["keyword_recall"] is not None]),
            "latency_avg_ms": int(statistics.mean(x["elapsed_ms"] for x in items)) if items else 0,
        }
        for cat, items in by_cat.items()
    }

    return {
        "n": n,
        "tool_recall_avg": _avg(tool_recalls),
        "keyword_recall_avg": _avg(kw_recalls),
        "citation_match_avg": _avg(cite_eval) if cite_eval else None,
        "ambiguity_handle_avg": _avg(amb_eval) if amb_eval else None,
        "not_found_handle_avg": _avg(nf_eval) if nf_eval else None,
        "acl_compliance_avg": _avg(acl_eval) if acl_eval else None,
        "denial_handle_avg": _avg(denial_eval) if denial_eval else None,
        "success_rate": round(succ / n, 3) if n else 0.0,
        "latency_ms": {
            "avg": int(statistics.mean(latencies)) if latencies else 0,
            "p50": int(statistics.median(latencies)) if latencies else 0,
            "p95": int(_percentile(latencies, 95)) if latencies else 0,
        },
        "by_category": cat_summary,
    }


def _avg(xs: List[float]) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def _percentile(xs: List[int], p: int) -> float:
    if not xs:
        return 0
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def print_summary(all_results: Dict[str, Dict[str, Any]]) -> None:
    print("\n" + "=" * 110)
    print(
        f"{'Mode':<14}{'ToolR':>7}{'KwR':>7}{'Cite':>7}{'Amb':>7}{'NotF':>7}"
        f"{'ACL':>7}{'Denied':>8}{'Succ':>7}{'AvgMs':>9}{'p95Ms':>9}"
    )
    print("-" * 110)
    for mode, res in all_results.items():
        m = res["metrics"]
        def f(x):
            return f"{x:.2f}" if x is not None else "—"
        print(
            f"{mode:<14}{f(m['tool_recall_avg']):>7}{f(m['keyword_recall_avg']):>7}"
            f"{f(m['citation_match_avg']):>7}{f(m['ambiguity_handle_avg']):>7}"
            f"{f(m['not_found_handle_avg']):>7}{f(m['acl_compliance_avg']):>7}"
            f"{f(m['denial_handle_avg']):>8}{f(m['success_rate']):>7}"
            f"{m['latency_ms']['avg']:>9}{m['latency_ms']['p95']:>9}"
        )
    print("=" * 110)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=list(BASELINES.keys()))
    parser.add_argument("--modes", type=str, help="csv list of modes, e.g. raw_llm,bm25_only")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--out", type=str)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--category", type=str, help="csv categories filter, vd: structured,docs")
    parser.add_argument("--testset", type=str, help="đường dẫn test set JSON (mặc định test_set.json; vd test_set_mini.json để chạy nhanh / LLM local)")
    args = parser.parse_args()

    test_set = load_test_set(Path(args.testset) if args.testset else None)
    cases = test_set["cases"]

    if args.category:
        wanted = {c.strip() for c in args.category.split(",")}
        cases = [c for c in cases if c["category"] in wanted]

    if args.limit:
        cases = cases[: args.limit]

    log.info("Test cases: %d", len(cases))

    if args.all:
        modes = list(BASELINES.keys())
    elif args.modes:
        modes = [m.strip() for m in args.modes.split(",") if m.strip() in BASELINES]
    elif args.mode:
        modes = [args.mode]
    else:
        modes = ["hybrid"]

    results: Dict[str, Any] = {}
    out_path = Path(args.out) if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Nếu file đã tồn tại, load lại để cộng dồn (incremental, không mất kết quả cũ)
        if out_path.exists():
            try:
                prev = json.loads(out_path.read_text(encoding="utf-8"))
                results.update(prev.get("results", {}))
                log.info("Loaded %d previous modes from %s", len(results), out_path)
            except Exception as e:
                log.warning("Could not load previous results: %s", e)

    def _save():
        if not out_path:
            return
        out_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "test_set_version": test_set["metadata"].get("version"),
                    "total_cases": len(cases),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("[checkpoint] Saved %d modes to %s", len(results), out_path)

    for m in modes:
        log.info("=== Running %s ===", m)
        try:
            results[m] = run_one_mode(m, cases, verify=args.verify)
            _save()  # save sau mỗi mode
        except KeyboardInterrupt:
            log.warning("Interrupted; saving partial results...")
            _save()
            return 130
        except Exception as e:
            log.error("Mode %s failed: %s; saving partial...", m, e)
            _save()
            # tiếp tục mode kế tiếp

    print_summary(results)
    _save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
