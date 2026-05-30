"""Tổng hợp các JSON kết quả thành markdown report cho luận văn.

Đọc các file JSON do run_eval.py / run_ablation.py / run_chunking_ablation.py xuất ra,
gen bảng markdown sẵn để copy vào báo cáo / slide.

Usage:
    python -m evaluation.gen_report \\
        --baselines evaluation/results/baselines.json \\
        --ablation evaluation/results/ablation.json \\
        --chunking evaluation/results/chunking.json \\
        --out evaluation/results/REPORT.md
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fmt(x, fmt=".2f"):
    if x is None:
        return "—"
    if isinstance(x, (int, float)):
        return format(x, fmt)
    return str(x)


def render_baselines(data: Dict[str, Any]) -> str:
    md = ["## Bảng 1 — So sánh 5 baseline\n"]
    md.append("Kết quả tạo lúc: `" + data.get("generated_at", "?") + "` • "
              f"Số case: {data.get('total_cases', '?')} • Test set v{data.get('test_set_version', '?')}\n")
    md.append("| Mode | Tool R | Keyword R | Citation | Ambiguity | NotFound | ACL | Denied | Success | Lat avg (ms) | Lat p95 (ms) |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for mode, res in data.get("results", {}).items():
        m = res["metrics"]
        md.append(
            f"| `{mode}` | {_fmt(m['tool_recall_avg'])} | {_fmt(m['keyword_recall_avg'])} | "
            f"{_fmt(m['citation_match_avg'])} | {_fmt(m['ambiguity_handle_avg'])} | "
            f"{_fmt(m['not_found_handle_avg'])} | {_fmt(m.get('acl_compliance_avg'))} | "
            f"{_fmt(m.get('denial_handle_avg'))} | {_fmt(m['success_rate'])} | "
            f"{m['latency_ms']['avg']} | {m['latency_ms']['p95']} |"
        )

    md.append("\n### Phân tích theo category (mode hybrid)\n")
    hybrid = data.get("results", {}).get("hybrid")
    if hybrid:
        md.append("| Category | n | Tool Recall | Keyword Recall | Latency avg (ms) |")
        md.append("|---|---:|---:|---:|---:|")
        for cat, c in hybrid["metrics"]["by_category"].items():
            md.append(
                f"| {cat} | {c['n']} | {_fmt(c['tool_recall'])} | "
                f"{_fmt(c['keyword_recall'])} | {c['latency_avg_ms']} |"
            )

    md.append("\n### So sánh per-category (cross-mode)\n")
    modes = list(data.get("results", {}).keys())
    if modes:
        cats = set()
        for mres in data["results"].values():
            cats.update(mres["metrics"]["by_category"].keys())
        cats_sorted = sorted(cats)
        header = "| Category |" + " | ".join(modes) + " |"
        md.append(header)
        md.append("|---|" + "---:|" * len(modes))
        for cat in cats_sorted:
            row = [f"| {cat} |"]
            for mode in modes:
                cat_data = data["results"][mode]["metrics"]["by_category"].get(cat)
                if cat_data:
                    row.append(f" {_fmt(cat_data['keyword_recall'])} |")
                else:
                    row.append(" — |")
            md.append("".join(row))
    return "\n".join(md)


def render_ablation(data: Dict[str, Any]) -> str:
    md = ["\n## Bảng 2 — Ablation hyperparameter\n"]
    md.append("Kết quả tạo lúc: `" + data.get("generated_at", "?") + "`\n")
    for axis, results in data.get("axes", {}).items():
        md.append(f"\n### Trục: `{axis}`\n")
        md.append("| Config | Tool R | Keyword R | Citation | Success | Lat avg (ms) | Lat p95 (ms) |")
        md.append("|---|---:|---:|---:|---:|---:|---:|")
        for cfg, res in results.items():
            m = res["metrics"]
            md.append(
                f"| `{cfg}` | {_fmt(m['tool_recall_avg'])} | {_fmt(m['keyword_recall_avg'])} | "
                f"{_fmt(m['citation_match_avg'])} | {_fmt(m['success_rate'])} | "
                f"{m['latency_ms']['avg']} | {m['latency_ms']['p95']} |"
            )
    return "\n".join(md)


def render_chunking(data: Dict[str, Any]) -> str:
    md = ["\n## Bảng 3 — Ablation chunking strategy\n"]
    md.append("Kết quả tạo lúc: `" + data.get("generated_at", "?") + "`\n")
    md.append("| Chunk size | Overlap | # chunks | Keyword R | Citation | Success | Lat avg (ms) |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|")
    for cfg, res in data.get("results", {}).items():
        c = res["config"]
        m = res["metrics"]
        md.append(
            f"| {c['chunk_size']} | {c['overlap']} | {res['n_chunks']} | "
            f"{_fmt(m['keyword_recall_avg'])} | {_fmt(m['citation_match_avg'])} | "
            f"{_fmt(m['success_rate'])} | {m['latency_ms']['avg']} |"
        )
    return "\n".join(md)


def render_qualitative(data: Dict[str, Any], max_cases: int = 5) -> str:
    """Vài câu trả lời mẫu để minh hoạ định tính trong báo cáo."""
    md = ["\n## Bảng 4 — Ví dụ định tính (qualitative)\n"]
    md.append("Một số câu hỏi minh hoạ và câu trả lời của các baseline.\n")
    hybrid = data.get("results", {}).get("hybrid")
    raw = data.get("results", {}).get("raw_llm")
    if not hybrid or not raw:
        return ""
    # match theo id
    raw_by_id = {r["id"]: r for r in raw["rows"]}
    chosen = hybrid["rows"][:max_cases]
    for h in chosen:
        r = raw_by_id.get(h["id"])
        md.append(f"\n**{h['id']}** _{h['category']}_ — {h['question']}")
        md.append(f"- **raw_llm**: {(r['answer'][:200] + '...') if r and len(r['answer'])>200 else (r['answer'] if r else '—')}")
        md.append(f"- **hybrid**: {h['answer'][:200] + ('...' if len(h['answer'])>200 else '')}")
        if h["tools_called"]:
            md.append(f"  - Tools: {h['tools_called']}")
        if h.get("citations"):
            md.append(f"  - Citations: {[c.get('source_path') for c in h['citations']]}")
    return "\n".join(md)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baselines", type=str, help="JSON từ run_eval.py --all")
    parser.add_argument("--ablation", type=str, help="JSON từ run_ablation.py")
    parser.add_argument("--chunking", type=str, help="JSON từ run_chunking_ablation.py")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--qualitative", type=int, default=5, help="Số ví dụ định tính")
    args = parser.parse_args()

    parts = [f"# Báo cáo đánh giá thực nghiệm\n\nGenerated: {datetime.utcnow().isoformat()}Z\n"]
    if args.baselines:
        data = json.loads(Path(args.baselines).read_text(encoding="utf-8"))
        parts.append(render_baselines(data))
        if args.qualitative > 0:
            parts.append(render_qualitative(data, max_cases=args.qualitative))
    if args.ablation:
        data = json.loads(Path(args.ablation).read_text(encoding="utf-8"))
        parts.append(render_ablation(data))
    if args.chunking:
        data = json.loads(Path(args.chunking).read_text(encoding="utf-8"))
        parts.append(render_chunking(data))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(parts), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
