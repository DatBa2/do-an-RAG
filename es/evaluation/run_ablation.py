"""Ablation study cho hệ thống Hybrid.

Thay đổi 1 hyperparameter mỗi lần, các param khác giữ default. Mục đích là cung cấp
bảng số liệu cho luận văn: "tăng K từ 3→10 ảnh hưởng metric thế nào?".

Các trục được khảo sát:
- retrieval_k     : 1, 3, 5, 10
- rrf_k_constant  : 10, 30, 60, 100
- query_rewriting : on / off
- self_rag_verify : on / off

Kết quả lưu evaluation/results/ablation_*.json + summary console.

Usage:
    python -m evaluation.run_ablation --axis k
    python -m evaluation.run_ablation --all
    python -m evaluation.run_ablation --all --out evaluation/results/ablation.json
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import config  # noqa: E402
from modules import doc_search  # noqa: E402
from es_main import Advisor, AdvisorContext  # noqa: E402
from evaluation.run_eval import load_test_set, _aggregate, print_summary, _avg, _score_case, _run_multi_turn_case, _run_single_turn_case  # noqa: E402

config.configure_logging()
log = logging.getLogger("ablation")
genai.configure(api_key=config.GEMINI_API_KEY)


# --- Ablation axes ---
RETRIEVAL_K_VALUES = [1, 3, 5, 10]
RRF_K_VALUES = [10, 30, 60, 100]
REWRITE_VALUES = [False, True]
VERIFY_VALUES = [False, True]


def _patch_doc_search(retrieval_k: int, rrf_k: int):
    """Patch tham số doc_search runtime — đơn giản hơn re-init."""
    doc_search.DEFAULT_K = retrieval_k
    doc_search.RRF_K = rrf_k


def _restore_doc_search():
    doc_search.DEFAULT_K = 5
    doc_search.RRF_K = 60


def run_hybrid_with_config(
    cases: List[Dict[str, Any]],
    retrieval_k: int,
    rrf_k: int,
    rewrite: bool,
    verify: bool,
) -> Dict[str, Any]:
    _patch_doc_search(retrieval_k, rrf_k)
    advisor = Advisor()  # fresh model — instructions không đổi nhưng tránh state cũ

    def runner(question, history=None, **kw):
        r = advisor.answer(
            question,
            list(history or []),
            AdvisorContext(role="parent", rewrite=rewrite, verify=verify),
        )
        return {
            "answer": r.answer,
            "tools_called": r.tools_called,
            "citations": [
                {"source_path": c.get("source_path"), "title": c.get("title")}
                for c in r.citations
            ],
            "elapsed_ms": r.elapsed_ms,
            "success": r.success,
        }

    rows = []
    for c in cases:
        if "turns" in c:
            row = _run_multi_turn_case(runner, c, verify, "hybrid")
        else:
            row = _run_single_turn_case(runner, c, verify, "hybrid")
        rows.append(row)
    return {"rows": rows, "metrics": _aggregate(rows)}


def run_axis_k(cases) -> Dict[str, Dict[str, Any]]:
    out = {}
    for k in RETRIEVAL_K_VALUES:
        log.info("=== retrieval_k = %d ===", k)
        out[f"k={k}"] = run_hybrid_with_config(cases, retrieval_k=k, rrf_k=60, rewrite=True, verify=False)
    _restore_doc_search()
    return out


def run_axis_rrf(cases) -> Dict[str, Dict[str, Any]]:
    out = {}
    for rk in RRF_K_VALUES:
        log.info("=== rrf_k = %d ===", rk)
        out[f"rrf_k={rk}"] = run_hybrid_with_config(cases, retrieval_k=5, rrf_k=rk, rewrite=True, verify=False)
    _restore_doc_search()
    return out


def run_axis_rewrite(cases) -> Dict[str, Dict[str, Any]]:
    out = {}
    for v in REWRITE_VALUES:
        log.info("=== rewrite = %s ===", v)
        out[f"rewrite={v}"] = run_hybrid_with_config(cases, retrieval_k=5, rrf_k=60, rewrite=v, verify=False)
    _restore_doc_search()
    return out


def run_axis_verify(cases) -> Dict[str, Dict[str, Any]]:
    out = {}
    for v in VERIFY_VALUES:
        log.info("=== verify = %s ===", v)
        out[f"verify={v}"] = run_hybrid_with_config(cases, retrieval_k=5, rrf_k=60, rewrite=True, verify=v)
    _restore_doc_search()
    return out


AXES = {
    "k": run_axis_k,
    "rrf": run_axis_rrf,
    "rewrite": run_axis_rewrite,
    "verify": run_axis_verify,
}


def print_axis_summary(axis: str, results: Dict[str, Dict[str, Any]]) -> None:
    print(f"\n=== Ablation: {axis} ===")
    print(f"{'Config':<14}{'ToolR':>8}{'KwR':>8}{'Cite':>8}{'Succ':>8}{'AvgMs':>9}{'p95Ms':>9}")
    print("-" * 64)
    for cfg, res in results.items():
        m = res["metrics"]
        def f(x):
            return f"{x:.2f}" if x is not None else "—"
        print(
            f"{cfg:<14}{f(m['tool_recall_avg']):>8}{f(m['keyword_recall_avg']):>8}"
            f"{f(m['citation_match_avg']):>8}{f(m['success_rate']):>8}"
            f"{m['latency_ms']['avg']:>9}{m['latency_ms']['p95']:>9}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis", choices=list(AXES.keys()))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--category", type=str)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=str)
    args = parser.parse_args()

    test_set = load_test_set()
    cases = test_set["cases"]
    if args.category:
        want = {c.strip() for c in args.category.split(",")}
        cases = [c for c in cases if c["category"] in want]
    if args.limit:
        cases = cases[: args.limit]
    log.info("Test cases: %d", len(cases))

    axes_to_run = list(AXES.keys()) if args.all else ([args.axis] if args.axis else ["k"])

    all_results: Dict[str, Any] = {}
    t0 = time.time()
    for axis in axes_to_run:
        res = AXES[axis](cases)
        all_results[axis] = res
        print_axis_summary(axis, res)
    log.info("Total ablation time: %.1fs", time.time() - t0)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "axes": all_results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("Đã ghi %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
