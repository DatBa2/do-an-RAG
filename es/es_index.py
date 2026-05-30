"""ETL: đọc JSON học sinh từ DATA_DIR, index vào Elasticsearch.

CLI:
  python es_index.py                  # incremental, dựa trên .last_run_timestamp
  python es_index.py --full-refresh   # xoá index, index lại toàn bộ
  python es_index.py --delete         # xoá index (có xác nhận)
  python es_index.py --ensure         # tạo index nếu chưa tồn tại (cho container init)
"""
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from elasticsearch import Elasticsearch, helpers

from modules import config

config.configure_logging()
log = logging.getLogger("es_index")

es = Elasticsearch(config.ES_HOST, request_timeout=30)

INDEX_SETTINGS = {
    "analysis": {
        "analyzer": {
            "vn_text": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            },
        },
        "normalizer": {
            "vn_normalizer": {"type": "custom", "filter": ["lowercase", "asciifolding"]},
        },
    }
}

INDEX_MAPPINGS = {
    "dynamic": True,
    "properties": {
        "doc_type": {"type": "keyword"},
        "student_id": {"type": "keyword"},
        "full_name": {
            "type": "text",
            "analyzer": "vn_text",
            "fields": {"raw": {"type": "keyword", "normalizer": "vn_normalizer"}},
        },
        "class_name": {
            "type": "text",
            "analyzer": "vn_text",
            "fields": {"raw": {"type": "keyword", "normalizer": "vn_normalizer"}},
        },
        "year": {"type": "keyword"},
        "semester": {"type": "integer"},
        "overall_gpa": {"type": "float"},
        "conduct": {"type": "keyword"},
        "academic": {"type": "keyword"},
        "promotion": {"type": "keyword"},
        "homeroom_comment": {"type": "text", "analyzer": "vn_text"},
        "subject": {
            "type": "text",
            "analyzer": "vn_text",
            "fields": {"raw": {"type": "keyword", "normalizer": "vn_normalizer"}},
        },
        "subject_comment": {"type": "text", "analyzer": "vn_text"},
        "scores": {
            "properties": {
                "TX": {"type": "float"},
                "GK": {"type": "float"},
                "CK": {"type": "float"},
                "TK": {"type": "float"},
            }
        },
        "attendance": {
            "properties": {
                "phep": {"type": "integer"},
                "khong_phep": {"type": "integer"},
                "bo_tiet": {"type": "integer"},
            }
        },
        "raw_path": {"type": "keyword", "index": False},
    },
}


def ensure_index(index_name: str = config.ES_INDEX) -> bool:
    """Tạo index nếu chưa tồn tại. Trả về True nếu vừa tạo mới."""
    if es.indices.exists(index=index_name):
        return False
    log.info("Tạo index %s với mapping mới...", index_name)
    es.indices.create(index=index_name, settings=INDEX_SETTINGS, mappings=INDEX_MAPPINGS)
    return True


def create_index(index_name: str = config.ES_INDEX) -> None:
    if es.indices.exists(index=index_name):
        log.info("Xoá index cũ %s...", index_name)
        es.indices.delete(index=index_name)
    log.info("Tạo index mới %s...", index_name)
    es.indices.create(index=index_name, settings=INDEX_SETTINGS, mappings=INDEX_MAPPINGS)


def delete_index(index_name: str = config.ES_INDEX) -> None:
    if not es.indices.exists(index=index_name):
        log.info("Index %s không tồn tại.", index_name)
        return
    print(f"!!! CẢNH BÁO !!! Sắp xoá index '{index_name}'. Toàn bộ dữ liệu sẽ mất.")
    if input("Nhập 'delete' để xác nhận: ").strip().lower() != "delete":
        log.info("Đã huỷ.")
        return
    es.indices.delete(index=index_name)
    if config.TIMESTAMP_FILE.exists():
        config.TIMESTAMP_FILE.unlink()
    log.info("Đã xoá index %s.", index_name)


def _to_floats(items: List[Dict[str, Any]]) -> List[float]:
    out = []
    for x in items:
        v = x.get("diem")
        if v is None:
            continue
        try:
            out.append(float(v))
        except (ValueError, TypeError):
            pass
    return out


def _avg(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 2) if values else None


def extract_docs_from_json(
    data: Dict[str, Any], raw_path: str = ""
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    user = data.get("data", {}).get("user", {})
    so_diem = data.get("data", {}).get("soDiem", {})
    mon_diem = so_diem.get("mon_hoc_tinh_diem", {}) or {}
    mon_nhan_xet = so_diem.get("mon_hoc_nhan_xet", {}) or {}
    tong_ket = so_diem.get("tong_ket", {}) or {}
    a_chuyen_can = data.get("data", {}).get("aChuyenCan", {}) or {}

    full_name = user.get("full_name")
    student_id = user.get("ma_hoc_sinh") or user.get("hoc_sinh_id")
    if not full_name or not student_id:
        return None, []

    class_name = user.get("ten_lop")
    year = user.get("nam_hoc_text") or user.get("nam_hoc")
    semester = data.get("data", {}).get("hocKyID") or so_diem.get("hoc_ky")
    sem_int = int(semester) if semester is not None else None
    year_str = str(year) if year is not None else None

    student_doc = {
        "doc_type": "student",
        "id": f"student::{student_id}::sem{sem_int}::year{year_str}",
        "student_id": str(student_id),
        "full_name": full_name,
        "class_name": class_name,
        "year": year_str,
        "semester": sem_int,
        "attendance": {
            "phep": a_chuyen_can.get("phep"),
            "khong_phep": a_chuyen_can.get("khong_phep"),
            "bo_tiet": a_chuyen_can.get("bo_tiet"),
        },
        "conduct": tong_ket.get("hanh_kiem"),
        "academic": tong_ket.get("hoc_luc"),
        "promotion": tong_ket.get("len_lop"),
        "homeroom_comment": so_diem.get("nhan_xet_gvcn"),
        "overall_gpa": tong_ket.get("diem_tk"),
        "raw_path": raw_path,
    }

    mark_docs: List[Dict[str, Any]] = []

    def emit_mark(subject_name: str, mh: Dict[str, Any]) -> None:
        tx_vals = _to_floats(mh.get("TX", []))
        gk_vals = _to_floats(mh.get("GK", []))
        ck_vals = _to_floats(mh.get("CK", []))
        tk_vals = _to_floats(mh.get("TK", []))
        scores = {
            "TX": _avg(tx_vals),
            "GK": _avg(gk_vals),
            "CK": _avg(ck_vals),
            "TK": tk_vals[-1] if tk_vals else None,
        }
        mark_docs.append({
            "doc_type": "mark",
            "id": f"mark::{student_id}::{subject_name}::sem{sem_int}::year{year_str}",
            "student_id": str(student_id),
            "full_name": full_name,
            "class_name": class_name,
            "year": year_str,
            "semester": sem_int,
            "subject": subject_name,
            "scores": scores,
            "subject_comment": mh.get("nhan_xet", "") or "",
            "raw_path": raw_path,
        })

    for _, mh in mon_diem.items():
        ten = mh.get("ten_mon_hoc")
        if ten:
            emit_mark(ten, mh)
    for _, mh in mon_nhan_xet.items():
        ten = mh.get("ten_mon_hoc")
        if ten:
            emit_mark(ten, mh)

    return student_doc, mark_docs


def read_last_run_timestamp() -> float:
    try:
        return float(config.TIMESTAMP_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def write_current_timestamp() -> None:
    config.TIMESTAMP_FILE.write_text(str(time.time()))


def bulk_index_from_dir(
    data_dir: str = config.DATA_DIR,
    index_name: str = config.ES_INDEX,
    full_refresh: bool = False,
) -> int:
    last_run_ts = 0.0 if full_refresh else read_last_run_timestamp()
    if full_refresh:
        log.info("Full-refresh: index lại toàn bộ.")
    elif last_run_ts:
        log.info("Incremental từ %s", datetime.fromtimestamp(last_run_ts))
    else:
        log.info("Chạy lần đầu, index toàn bộ.")

    actions: List[Dict[str, Any]] = []
    scanned = processed = indexed = 0

    if not os.path.isdir(data_dir):
        log.error("DATA_DIR không tồn tại: %s", data_dir)
        return 0

    for root, _, files in os.walk(data_dir):
        for fn in files:
            if not fn.lower().endswith(".json"):
                continue
            scanned += 1
            path = os.path.join(root, fn)
            if not full_refresh and os.path.getmtime(path) < last_run_ts:
                continue
            processed += 1
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                student_doc, mark_docs = extract_docs_from_json(data, raw_path=path)
                if not student_doc:
                    continue
                actions.append({
                    "_index": index_name,
                    "_id": student_doc["id"],
                    "_op_type": "index",
                    "_source": student_doc,
                })
                for md in mark_docs:
                    actions.append({
                        "_index": index_name,
                        "_id": md["id"],
                        "_op_type": "index",
                        "_source": md,
                    })
                if len(actions) >= config.BULK_BATCH_SIZE:
                    helpers.bulk(es, actions)
                    indexed += len(actions)
                    log.info("Đã index batch (%d docs, tổng %d).", len(actions), indexed)
                    actions.clear()
            except Exception as ex:
                log.warning("Bỏ qua %s: %s", path, ex)

    if actions:
        helpers.bulk(es, actions)
        indexed += len(actions)
        log.info("Đã index batch cuối (%d docs, tổng %d).", len(actions), indexed)

    log.info("Hoàn thành: quét %d file, xử lý %d, index %d docs.", scanned, processed, indexed)

    if processed > 0:
        write_current_timestamp()

    return indexed


def main() -> int:
    args = set(sys.argv[1:])
    if "--delete" in args:
        delete_index()
        return 0
    if "--full-refresh" in args:
        create_index()
        bulk_index_from_dir(full_refresh=True)
        return 0
    if "--ensure" in args:
        ensure_index()
        return 0

    if not es.indices.exists(index=config.ES_INDEX):
        log.warning("Index %s chưa tồn tại — chạy full-refresh lần đầu.", config.ES_INDEX)
        create_index()
        bulk_index_from_dir(full_refresh=True)
    else:
        bulk_index_from_dir(full_refresh=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
