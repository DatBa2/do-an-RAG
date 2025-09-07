import os
import json
import re
import math
import time
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

from elasticsearch import Elasticsearch, helpers

# --- CẤU HÌNH ---
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
INDEX_NAME = os.getenv("ES_INDEX", "hs_records")
BULK_BATCH_SIZE = int(os.getenv("BULK_BATCH_SIZE", "1000"))
TIMESTAMP_FILE = ".last_run_timestamp" # Tên file để lưu dấu thời gian

# Kết nối ES
es = Elasticsearch(ES_HOST)

# --- CÁC HÀM TIỆN ÍCH ---

def create_index(index_name: str = INDEX_NAME) -> None:
    """Xóa index cũ (nếu có) và tạo một index mới với mapping đã định nghĩa."""
    if es.indices.exists(index=index_name):
        print(f"[INFO] Đang xóa index cũ: {index_name}...")
        es.indices.delete(index=index_name)
    print(f"[INFO] Đang tạo index mới: {index_name}...")
    body = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "vn_text": {"type": "custom", "tokenizer": "standard", "filter": ["lowercase", "asciifolding"]},
                },
                "normalizer": {
                    "vn_normalizer": {"type": "custom", "filter": ["lowercase", "asciifolding"]}
                }
            }
        },
        "mappings": {
            "dynamic": True,
            "properties": {
                "doc_type": {"type": "keyword"},
                "full_name": {"type": "text", "analyzer": "vn_text", "fields": {
                    "raw": {"type": "keyword", "normalizer": "vn_normalizer"}
                }},
                "class_name": {"type": "text", "analyzer": "vn_text", "fields": {
                    "raw": {"type": "keyword", "normalizer": "vn_normalizer"}
                }},
                "year": {"type": "keyword"},
                "semester": {"type": "integer"},
                "overall_gpa": {"type": "float"},
                "subject": {"type": "text", "analyzer": "vn_text", "fields": {
                    "raw": {"type": "keyword", "normalizer": "vn_normalizer"}
                }},
                "scores": {
                    "properties": {
                        "TX": {"type": "float"},
                        "GK": {"type": "float"},
                        "CK": {"type": "float"},
                        "TK": {"type": "float"},
                    }
                },
            }
        },
    }
    es.indices.create(index=index_name, settings=body["settings"], mappings=body["mappings"])
    print(f"[OK] Đã tạo index {index_name} thành công.")

def delete_index(index_name: str = INDEX_NAME) -> None:
    """Hàm xóa index với bước xác nhận để đảm bảo an toàn."""
    if not es.indices.exists(index=index_name):
        print(f"[INFO] Index '{index_name}' không tồn tại. Không có gì để xóa.")
        return

    print(f"!!! CẢNH BÁO !!!")
    print(f"Bạn có chắc chắn muốn XÓA TOÀN BỘ index '{index_name}' không?")
    print("Hành động này không thể hoàn tác và toàn bộ dữ liệu sẽ bị mất vĩnh viễn.")
    confirm = input("Nhập 'delete' để xác nhận: ")

    if confirm.strip().lower() == 'delete':
        try:
            es.indices.delete(index=index_name)
            print(f"[OK] Đã xóa thành công index '{index_name}'.")
            # Xóa cả file timestamp để lần chạy sau được sạch
            if os.path.exists(TIMESTAMP_FILE):
                os.remove(TIMESTAMP_FILE)
                print(f"[INFO] Đã xóa file timestamp '{TIMESTAMP_FILE}'.")
        except Exception as e:
            print(f"[ERROR] Xóa index thất bại: {e}")
    else:
        print("[INFO] Thao tác đã được hủy.")


def extract_docs_from_json(data: Dict[str, Any], raw_path: str = "") -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Trích xuất student_doc và mark_docs từ dữ liệu JSON gốc."""
    user = data.get("data", {}).get("user", {})
    soDiem = data.get("data", {}).get("soDiem", {})
    mon_diem = soDiem.get("mon_hoc_tinh_diem", {})
    mon_nhan_xet = soDiem.get("mon_hoc_nhan_xet", {})
    tong_ket = soDiem.get("tong_ket", {})
    
    if not user.get("full_name") or not user.get("ma_hoc_sinh"):
        return None, []

    full_name = user.get("full_name")
    class_name = user.get("ten_lop")
    year = user.get("nam_hoc_text") or user.get("nam_hoc")
    semester = data.get("data", {}).get("hocKyID") or soDiem.get("hoc_ky")
    student_id = user.get("ma_hoc_sinh") or user.get("hoc_sinh_id")
    aChuyenCan = data.get("data", {}).get("aChuyenCan", {})

    student_doc = {
        "doc_type": "student", "id": f"student::{student_id}::sem{semester}::year{year}",
        "student_id": student_id, "full_name": full_name, "class_name": class_name,
        "year": str(year) if year is not None else None,
        "semester": int(semester) if semester is not None else None,
        "attendance": {"phep": aChuyenCan.get("phep"), "khong_phep": aChuyenCan.get("khong_phep"), "bo_tiet": aChuyenCan.get("bo_tiet")},
        "conduct": tong_ket.get("hanh_kiem"), "academic": tong_ket.get("hoc_luc"),
        "promotion": tong_ket.get("len_lop"), "homeroom_comment": soDiem.get("nhan_xet_gvcn"),
        "overall_gpa": tong_ket.get("diem_tk"), "raw_path": raw_path,
    }
    mark_docs = []
    def _avg(values: List[float]) -> Optional[float]:
        return sum(values) / len(values) if values else None
        
    def _emit_mark(subject_name: str, mh: Dict[str, Any]):
        def _to_floats(xs):
            out = []
            for x in xs:
                if x.get("diem") is not None:
                    try: out.append(float(x['diem']))
                    except (ValueError, TypeError): pass
            return out
            
        scores = {
            "TX": _avg(_to_floats(mh.get("TX", []))),
            "GK": _avg(_to_floats(mh.get("GK", []))),
            "CK": _avg(_to_floats(mh.get("CK", []))),
            "TK": _to_floats(mh.get("TK", []))[-1] if _to_floats(mh.get("TK", [])) else None,
        }
        mark_docs.append({
            "doc_type": "mark", "id": f"mark::{student_id}::{subject_name}::sem{semester}::year{year}",
            "student_id": student_id, "full_name": full_name, "class_name": class_name,
            "year": str(year) if year is not None else None,
            "semester": int(semester) if semester is not None else None,
            "subject": subject_name, "scores": scores,
            "subject_comment": mh.get("nhan_xet", ""), "raw_path": raw_path,
        })
        
    for _, mh in mon_diem.items():
        if ten := mh.get("ten_mon_hoc"): _emit_mark(ten, mh)
    for _, mh in mon_nhan_xet.items():
        if ten := mh.get("ten_mon_hoc"): _emit_mark(ten, mh)
        
    return student_doc, mark_docs

def read_last_run_timestamp() -> float:
    try:
        with open(TIMESTAMP_FILE, "r") as f: return float(f.read().strip())
    except (FileNotFoundError, ValueError): return 0.0

def write_current_timestamp() -> None:
    with open(TIMESTAMP_FILE, "w") as f: f.write(str(time.time()))

def bulk_index_from_dir(data_dir: str = "./organized_results", index_name: str = INDEX_NAME, full_refresh: bool = False) -> None:
    last_run_ts = 0.0
    if not full_refresh:
        last_run_ts = read_last_run_timestamp()
        if last_run_ts > 0: print(f"[INFO] Bắt đầu cập nhật tăng trưởng từ lần chạy lúc: {datetime.fromtimestamp(last_run_ts)}")
        else: print("[INFO] File timestamp không tìm thấy. Chạy như lần đầu tiên...")
    else: print("[INFO] Bắt đầu index lại toàn bộ (full refresh)...")

    actions, count_files_processed, total_files_scanned = [], 0, 0
    for root, _, files in os.walk(data_dir):
        for fn in files:
            if not fn.lower().endswith(".json"): continue
            total_files_scanned += 1
            path = os.path.join(root, fn)
            file_mod_time = os.path.getmtime(path)
            if not full_refresh and file_mod_time < last_run_ts: continue
            count_files_processed += 1
            try:
                with open(path, "r", encoding="utf-8") as f: data = json.load(f)
                student_doc, mark_docs = extract_docs_from_json(data, raw_path=path)
                if not student_doc: continue
                actions.append({"_index": index_name, "_id": student_doc["id"], "_op_type": "index", "_source": student_doc})
                for md in mark_docs: actions.append({"_index": index_name, "_id": md["id"], "_op_type": "index", "_source": md})
                if len(actions) >= BULK_BATCH_SIZE:
                    helpers.bulk(es, actions); actions.clear()
                    print(f"[Bulk] Đã index ~{BULK_BATCH_SIZE} văn bản...")
            except Exception as ex: print(f"[WARN] Bỏ qua file {path}: {ex}")
    if actions:
        helpers.bulk(es, actions)
        print(f"[Bulk] Đã index {len(actions)} văn bản cuối cùng.")
    if total_files_scanned > 0: print(f"[OK] Hoàn thành. Đã quét {total_files_scanned} file, xử lý {count_files_processed} file mới/thay đổi.")
    else: print("[INFO] Không tìm thấy file JSON nào trong thư mục được chỉ định.")
    if count_files_processed > 0 and not full_refresh: write_current_timestamp()

# --- ĐIỂM KHỞI CHẠY SCRIPT ---

if __name__ == "__main__":
    args = sys.argv
    if '--delete' in args:
        delete_index()
    elif '--full-refresh' in args:
        create_index()
        bulk_index_from_dir(full_refresh=True)
        write_current_timestamp()
    else:
        if not es.indices.exists(index=INDEX_NAME):
            print(f"[WARN] Index '{INDEX_NAME}' không tồn tại. Tự động chạy chế độ full-refresh lần đầu.")
            create_index()
            bulk_index_from_dir(full_refresh=True)
            write_current_timestamp()
        else:
            bulk_index_from_dir(full_refresh=False)