"""Pipeline ingest tài liệu nội bộ:

1. Đọc file (.md, .txt; .pdf nếu có pdfplumber).
2. Chia chunk theo section (heading) + window token-bound.
3. Embed bằng Gemini (có cache).
4. Index vào ES `internal_docs` với cả nội dung (BM25) và dense_vector.

Mỗi document có thể khai báo metadata ở front-matter:
---
title: ...
acl_roles: parent,teacher,admin
section_prefix: ...
---
"""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from elasticsearch import Elasticsearch, helpers

from modules import config
from modules.embeddings import EMBED_DIM, embed_batch

log = logging.getLogger("ingest_docs")

ES_DOCS_INDEX = "internal_docs"
DEFAULT_ROLES = ["parent", "teacher", "admin"]

DOCS_SETTINGS = {
    "analysis": {
        "analyzer": {
            "vn_text": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            }
        }
    }
}

DOCS_MAPPINGS = {
    "properties": {
        "doc_id": {"type": "keyword"},
        "chunk_id": {"type": "keyword"},
        "title": {"type": "text", "analyzer": "vn_text"},
        "source_path": {"type": "keyword"},
        "section": {"type": "text", "analyzer": "vn_text"},
        "content": {"type": "text", "analyzer": "vn_text"},
        "content_tokens": {"type": "integer"},
        "allowed_roles": {"type": "keyword"},
        "indexed_at": {"type": "date"},
        "embedding": {
            "type": "dense_vector",
            "dims": EMBED_DIM,
            "index": True,
            "similarity": "cosine",
        },
    }
}


def es_client() -> Elasticsearch:
    return Elasticsearch(config.ES_HOST, request_timeout=60)


def ensure_docs_index(es: Optional[Elasticsearch] = None, recreate: bool = False) -> None:
    es = es or es_client()
    exists = es.indices.exists(index=ES_DOCS_INDEX)
    if exists and recreate:
        log.info("Xoá index %s...", ES_DOCS_INDEX)
        es.indices.delete(index=ES_DOCS_INDEX)
        exists = False
    if not exists:
        log.info("Tạo index %s.", ES_DOCS_INDEX)
        es.indices.create(index=ES_DOCS_INDEX, settings=DOCS_SETTINGS, mappings=DOCS_MAPPINGS)


# --- Parse frontmatter ---
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm_raw = m.group(1)
    body = text[m.end():]
    meta: Dict[str, str] = {}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    return meta, body


# --- Section-aware chunker ---
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _approx_tokens(text: str) -> int:
    """Xấp xỉ token: 1 token ~ 0.75 từ tiếng Việt. Đủ chính xác để chunk."""
    return max(1, int(len(text.split()) / 0.75))


def split_into_sections(body: str) -> List[Tuple[str, str]]:
    """Trả list (section_title, content)."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [("(no heading)", body.strip())]

    sections: List[Tuple[str, str]] = []
    # Phần trước heading đầu tiên
    if matches[0].start() > 0:
        intro = body[:matches[0].start()].strip()
        if intro:
            sections.append(("(intro)", intro))

    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if content:
            sections.append((title, content))
    return sections


def chunk_sections(
    sections: List[Tuple[str, str]],
    max_tokens: int = 320,
    overlap_tokens: int = 64,
) -> List[Tuple[str, str]]:
    """Cắt mỗi section thành nhiều chunk nếu quá max_tokens. Giữ overlap để không đứt câu."""
    chunks: List[Tuple[str, str]] = []
    for title, text in sections:
        if _approx_tokens(text) <= max_tokens:
            chunks.append((title, text))
            continue
        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        buf: List[str] = []
        buf_tokens = 0
        for sent in sentences:
            t = _approx_tokens(sent)
            if buf_tokens + t > max_tokens and buf:
                chunks.append((title, " ".join(buf).strip()))
                # overlap: giữ vài câu cuối
                overlap_buf: List[str] = []
                overlap_t = 0
                for prev in reversed(buf):
                    pt = _approx_tokens(prev)
                    if overlap_t + pt > overlap_tokens:
                        break
                    overlap_buf.insert(0, prev)
                    overlap_t += pt
                buf = overlap_buf
                buf_tokens = overlap_t
            buf.append(sent)
            buf_tokens += t
        if buf:
            chunks.append((title, " ".join(buf).strip()))
    return chunks


# --- File readers ---
def _read_md_or_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError as e:
        raise RuntimeError("Cần `pip install pdfplumber` để đọc PDF.") from e
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            out.append(t)
    return "\n\n".join(out)


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return _read_md_or_txt(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    raise ValueError(f"Không hỗ trợ định dạng: {suffix}")


# --- Build chunks for 1 file ---
def build_chunks(path: Path) -> List[Dict]:
    raw = read_file(path)
    meta, body = parse_frontmatter(raw)
    title = meta.get("title") or path.stem.replace("_", " ").title()
    roles_raw = meta.get("acl_roles", "")
    roles = [r.strip() for r in roles_raw.split(",") if r.strip()] or DEFAULT_ROLES

    sections = split_into_sections(body)
    chunks = chunk_sections(sections)

    abs_path = path.resolve()
    try:
        rel = abs_path.relative_to(config.PROJECT_ROOT)
        source_path = str(rel)
    except ValueError:
        source_path = str(abs_path)

    out: List[Dict] = []
    doc_id = path.stem
    for idx, (section, content) in enumerate(chunks):
        if not content.strip():
            continue
        out.append({
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}::chunk_{idx:03d}",
            "title": title,
            "section": section,
            "source_path": source_path,
            "content": content,
            "content_tokens": _approx_tokens(content),
            "allowed_roles": roles,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


# --- Ingest pipeline ---
def iter_doc_files(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".md", ".txt", ".pdf"}:
            yield p


def ingest_documents(
    docs_dir: Optional[Path] = None,
    recreate: bool = False,
) -> int:
    docs_dir = docs_dir or (config.PROJECT_ROOT / "documents")
    if not docs_dir.exists():
        log.error("Thư mục documents không tồn tại: %s", docs_dir)
        return 0

    es = es_client()
    ensure_docs_index(es, recreate=recreate)

    all_chunks: List[Dict] = []
    files = list(iter_doc_files(docs_dir))
    if not files:
        log.warning("Không có file trong %s.", docs_dir)
        return 0

    for path in files:
        try:
            chunks = build_chunks(path)
            log.info("%s → %d chunks", path.name, len(chunks))
            all_chunks.extend(chunks)
        except Exception as e:
            log.warning("Lỗi đọc %s: %s", path, e)

    if not all_chunks:
        return 0

    texts = [c["content"] for c in all_chunks]
    vecs = embed_batch(texts, task_type="retrieval_document")
    for c, v in zip(all_chunks, vecs):
        c["embedding"] = v

    actions = [
        {
            "_index": ES_DOCS_INDEX,
            "_id": c["chunk_id"],
            "_op_type": "index",
            "_source": c,
        }
        for c in all_chunks
    ]
    helpers.bulk(es, actions)
    log.info("Đã index %d chunks vào %s.", len(all_chunks), ES_DOCS_INDEX)
    return len(all_chunks)


def main() -> None:
    import argparse

    config.configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true", help="Xoá index trước khi ingest")
    parser.add_argument("--dir", type=str, default=None, help="Thư mục docs (mặc định ./documents)")
    args = parser.parse_args()
    n = ingest_documents(
        docs_dir=Path(args.dir) if args.dir else None,
        recreate=args.recreate,
    )
    print(json.dumps({"chunks_indexed": n}, ensure_ascii=False))


if __name__ == "__main__":
    main()
