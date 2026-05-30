"""Ablation chunking: re-index tài liệu với nhiều cấu hình chunk khác nhau,
chạy lại docs-only test cases để so sánh.

Khảo sát:
- chunk_size ∈ {128, 256, 320, 512, 1024} tokens
- overlap   ∈ {0, 64, 128} tokens

Mỗi cấu hình:
1. Patch hàm chunk_sections để dùng tham số mới.
2. Re-index thư mục documents (xoá index cũ).
3. Chạy hybrid trên các case category=docs + citation.
4. Ghi nhận metrics.

Lưu ý: re-ingest tốn API calls embedding. Vì có cache theo (text, model, task), chỉ
lần đầu tốn token; các lần sau chunk identical sẽ hit cache.

Usage:
    python -m evaluation.run_chunking_ablation
    python -m evaluation.run_chunking_ablation --quick   # ít config hơn
    python -m evaluation.run_chunking_ablation --out evaluation/results/chunking.json
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules import config  # noqa: E402
from modules import ingest_docs  # noqa: E402
from es_main import Advisor, AdvisorContext  # noqa: E402
from evaluation.run_eval import (  # noqa: E402
    _aggregate,
    _run_single_turn_case,
    load_test_set,
)

config.configure_logging()
log = logging.getLogger("chunk_ablation")


FULL_GRID = [
    (128, 0), (128, 32),
    (256, 0), (256, 64),
    (320, 64),
    (512, 64), (512, 128),
    (1024, 128),
]
QUICK_GRID = [(128, 0), (320, 64), (1024, 128)]


def _reindex(chunk_size: int, overlap: int) -> int:
    """Patch chunk_sections để dùng tham số mới rồi re-ingest."""
    original = ingest_docs.chunk_sections

    def patched(sections, max_tokens=chunk_size, overlap_tokens=overlap):
        return original(sections, max_tokens=max_tokens, overlap_tokens=overlap_tokens)

    ingest_docs.chunk_sections = patched
    try:
        n = ingest_docs.ingest_documents(recreate=True)
    finally:
        ingest_docs.chunk_sections = original
    return n


def _docs_eval_cases() -> List[Dict[str, Any]]:
    test_set = load_test_set()
    return [c for c in test_set["cases"] if c["category"] in {"docs", "citation"} and "turns" not in c]


def _hybrid_runner(question, **kw):
    advisor = _HYBRID  # set ở main
    r = advisor.answer(
        question,
        list(kw.get("history") or []),
        AdvisorContext(role="parent", rewrite=True, verify=False),
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


_HYBRID: Advisor


def run_grid(grid: List[Tuple[int, int]]) -> Dict[str, Any]:
    global _HYBRID
    cases = _docs_eval_cases()
    log.info("Using %d docs/citation cases", len(cases))

    out: Dict[str, Any] = {}
    for chunk_size, overlap in grid:
        cfg = f"size={chunk_size}_ovl={overlap}"
        log.info("=== %s ===", cfg)
        n_chunks = _reindex(chunk_size, overlap)
        # Đợi ES refresh
        time.sleep(2)
        _HYBRID = Advisor()  # reset advisor cho mỗi config

        rows = []
        for c in cases:
            row = _run_single_turn_case(_hybrid_runner, c, verify=False, mode_name=f"chunk_{cfg}")
            rows.append(row)

        out[cfg] = {
            "config": {"chunk_size": chunk_size, "overlap": overlap},
            "n_chunks": n_chunks,
            "rows": rows,
            "metrics": _aggregate(rows),
        }
    return out


def print_summary(results: Dict[str, Any]) -> None:
    print("\n=== Chunking Ablation ===")
    print(f"{'Config':<22}{'#chunks':>9}{'KwR':>8}{'Cite':>8}{'Succ':>8}{'AvgMs':>9}{'p95Ms':>9}")
    print("-" * 73)
    for cfg, res in results.items():
        m = res["metrics"]
        def f(x):
            return f"{x:.2f}" if x is not None else "—"
        print(
            f"{cfg:<22}{res['n_chunks']:>9}{f(m['keyword_recall_avg']):>8}"
            f"{f(m['citation_match_avg']):>8}{f(m['success_rate']):>8}"
            f"{m['latency_ms']['avg']:>9}{m['latency_ms']['p95']:>9}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Chỉ 3 cấu hình thay vì 8")
    parser.add_argument("--out", type=str)
    args = parser.parse_args()

    grid = QUICK_GRID if args.quick else FULL_GRID
    t0 = time.time()
    results = run_grid(grid)
    log.info("Total time: %.1fs", time.time() - t0)
    print_summary(results)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "grid": [{"chunk_size": cs, "overlap": ov} for cs, ov in grid],
                    "results": results,
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
