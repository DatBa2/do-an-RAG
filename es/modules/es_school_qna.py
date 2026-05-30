"""Tools cho LLM truy vấn dữ liệu học sinh trên Elasticsearch.

Mỗi tool trả về dict với key `status`: success | not_found | ambiguous | error,
giúp LLM quyết định hành động tiếp theo.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch

from modules import config

log = logging.getLogger("qna")

es = Elasticsearch(config.ES_HOST, request_timeout=30)
INDEX_NAME = config.ES_INDEX

# --- Synonyms ---
DEFAULT_SUBJECT_SYNONYMS = {
    "toan": ["toan", "toan hoc"],
    "ngu van": ["ngu van", "van"],
    "ngoai ngu": ["ngoai ngu", "tieng anh", "english", "anh van"],
    "lich su va dia li": ["lich su va dia li", "lich su", "dia li", "lsdl"],
    "khoa hoc tu nhien": ["khoa hoc tu nhien", "khtn", "khoa hoc"],
    "tin hoc": ["tin hoc", "tin"],
    "gdcd": ["gdcd"],
    "cong nghe": ["cong nghe", "cn"],
    "nghe thuat": ["nghe thuat", "am nhac", "mi thuat"],
    "giao duc the chat": ["giao duc the chat", "the duc", "gdtc"],
    "noi dung giao duc cua dia phuong": [
        "noi dung giao duc cua dia phuong",
        "ndgd dia phuong",
        "dia phuong",
    ],
    "hoat dong trai nghiem, huong nghiep": [
        "hdtn",
        "hoat dong trai nghiem",
        "huong nghiep",
    ],
}

try:
    with open(config.SYNONYMS_FILE, "r", encoding="utf-8") as f:
        SUBJECT_SYNONYMS = json.load(f)
except FileNotFoundError:
    log.warning("Không tìm thấy %s, dùng default.", config.SYNONYMS_FILE)
    SUBJECT_SYNONYMS = DEFAULT_SUBJECT_SYNONYMS

# --- Chuẩn hoá tiếng Việt ---
_ACCENT_LOWER = str.maketrans(
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
)
_ACCENT_UPPER = str.maketrans(
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ",
    "AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD",
)


def strip_accents(s: str) -> str:
    return s.translate(_ACCENT_LOWER).translate(_ACCENT_UPPER)


def norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", strip_accents(s).lower().strip())


def match_subject(subject_text: str) -> Optional[str]:
    if not subject_text:
        return None
    n = norm(subject_text)
    for canon, arr in SUBJECT_SYNONYMS.items():
        for a in arr:
            if n == a or n in a or a in n:
                return canon
    return n


def _subject_query_string(subject_name: str) -> str:
    canonical = match_subject(subject_name)
    if canonical and canonical in SUBJECT_SYNONYMS:
        return " ".join(SUBJECT_SYNONYMS[canonical])
    return subject_name


def _semester_year_filters(year: Optional[str], semester: Optional[int]) -> List[Dict]:
    filters: List[Dict] = []
    if year:
        filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester is not None:
        filters.append({"term": {"semester": int(semester)}})
    return filters


# --- Hàm lõi: tìm 1 học sinh duy nhất, xử lý nhập nhằng ---

def _find_unique_student_record(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """Tìm bản ghi học sinh phù hợp nhất.

    Quy tắc dedupe:
    - Cùng `student_id` qua nhiều học kỳ → không phải nhập nhằng, lấy bản ghi
      mới nhất (year desc, semester desc) làm mặc định.
    - Khác `student_id` (trùng tên) → trả về `ambiguous` với danh sách phân biệt.
    """
    must = [
        {"term": {"doc_type": "student"}},
        {"match_phrase": {"full_name": student_name}},
    ]
    if class_name:
        must.append({"match": {"class_name": class_name}})
    must.extend(_semester_year_filters(year, semester))

    body = {
        "query": {"bool": {"must": must}},
        "size": 50,
        "sort": [{"year": "desc"}, {"semester": "desc"}],
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])

    if not hits:
        return {
            "status": "not_found",
            "message": f"Không tìm thấy học sinh nào tên '{student_name}' khớp tiêu chí.",
        }

    by_sid: Dict[str, Dict[str, Any]] = {}
    for h in hits:
        src = h["_source"]
        sid = src.get("student_id")
        if sid and sid not in by_sid:
            by_sid[sid] = src  # đầu tiên = mới nhất nhờ sort

    if len(by_sid) > 1:
        options = [
            f"- {s.get('full_name')} (lớp {s.get('class_name','?')}, "
            f"học kỳ {s.get('semester','?')} năm {s.get('year','?')}, "
            f"mã HS {sid})"
            for sid, s in by_sid.items()
        ]
        return {
            "status": "ambiguous",
            "message": (
                f"Tìm thấy {len(by_sid)} học sinh khác nhau cùng tên '{student_name}'. "
                "Vui lòng cung cấp thêm lớp / mã học sinh."
            ),
            "options": "\n".join(options),
        }

    return {"status": "success", "data": next(iter(by_sid.values()))}


# --- Tools cho LLM ---

def get_student_overview(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """Tổng quan: học lực, hạnh kiểm, GPA, chuyên cần, nhận xét."""
    return _find_unique_student_record(student_name, class_name, year, semester)


def get_all_subject_scores_for_student(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """Bảng điểm tất cả môn của 1 học sinh trong 1 học kỳ."""
    found = _find_unique_student_record(student_name, class_name, year, semester)
    if found["status"] != "success":
        return found

    rec = found["data"]
    must = [
        {"term": {"doc_type": "mark"}},
        {"term": {"student_id": rec["student_id"]}},
        {"term": {"semester": rec["semester"]}},
        {"term": {"year": rec["year"]}},
    ]
    res = es.search(index=INDEX_NAME, body={"query": {"bool": {"must": must}}}, size=50)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {
            "status": "not_found",
            "message": f"Có học sinh {student_name} nhưng chưa có dữ liệu điểm chi tiết.",
        }
    return {
        "status": "success",
        "context": {
            "student_name": rec["full_name"],
            "class_name": rec["class_name"],
            "year": rec["year"],
            "semester": rec["semester"],
        },
        "data": [h["_source"] for h in hits],
    }


def get_subject_score(
    student_name: str,
    subject_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """Điểm chi tiết 1 môn của 1 học sinh."""
    found = _find_unique_student_record(student_name, class_name, year, semester)
    if found["status"] != "success":
        return found

    rec = found["data"]
    must = [
        {"term": {"doc_type": "mark"}},
        {"term": {"student_id": rec["student_id"]}},
        {"term": {"semester": rec["semester"]}},
        {"term": {"year": rec["year"]}},
        {"match": {"subject": {"query": _subject_query_string(subject_name), "operator": "or"}}},
    ]
    res = es.search(index=INDEX_NAME, body={"query": {"bool": {"must": must}}}, size=1)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {
            "status": "not_found",
            "message": f"Không tìm thấy điểm môn '{subject_name}' của {student_name}.",
        }
    return {"status": "success", "data": hits[0]["_source"]}


def get_attendance_details(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """Chuyên cần: nghỉ có phép, không phép, bỏ tiết."""
    found = _find_unique_student_record(student_name, class_name, year, semester)
    if found["status"] != "success":
        return found
    rec = found["data"]
    att = rec.get("attendance") or {}
    if not any(v is not None for v in att.values()):
        return {"status": "not_found", "message": "Không có dữ liệu chuyên cần."}
    return {
        "status": "success",
        "context": {"student_name": rec["full_name"], "year": rec["year"], "semester": rec["semester"]},
        "data": att,
    }


def get_student_strengths_and_weaknesses(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    res = get_all_subject_scores_for_student(student_name, class_name, year, semester)
    if res["status"] != "success":
        return res
    valid = [s for s in res["data"] if s.get("scores", {}).get("TK") is not None]
    if not valid:
        return {"status": "not_found", "message": "Không đủ điểm tổng kết để phân tích."}
    best = max(valid, key=lambda s: s["scores"]["TK"])
    worst = min(valid, key=lambda s: s["scores"]["TK"])
    return {
        "status": "success",
        "context": res["context"],
        "best_subject": {"subject": best["subject"], "score": best["scores"]["TK"]},
        "worst_subject": {"subject": worst["subject"], "score": worst["scores"]["TK"]},
    }


# --- Class-level tools ---

def get_class_size(
    class_name: str,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    must.extend(_semester_year_filters(year, semester))
    body = {"query": {"bool": {"must": must}}}
    count = es.count(index=INDEX_NAME, body=body).get("count", 0)
    if count == 0:
        return {"status": "not_found", "message": f"Không có dữ liệu cho lớp {class_name}."}
    return {"status": "success", "class_name": class_name, "count": count}


def list_all_classes(year: Optional[str] = None) -> Dict[str, Any]:
    body = {
        "size": 0,
        "query": {"bool": {"must": [{"term": {"doc_type": "student"}}]}},
        "aggs": {"unique_classes": {"terms": {"field": "class_name.raw", "size": 500}}},
    }
    if year:
        body["query"]["bool"]["must"].append({"wildcard": {"year": f"*{year}*"}})
    res = es.search(index=INDEX_NAME, body=body)
    buckets = res.get("aggregations", {}).get("unique_classes", {}).get("buckets", [])
    if not buckets:
        return {"status": "not_found", "message": "Không có dữ liệu lớp học."}
    classes = sorted(b["key"] for b in buckets)
    return {"status": "success", "total_classes": len(classes), "class_list": classes}


def get_top_n_students(
    class_name: str,
    n: int = 5,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    must.extend(_semester_year_filters(year, semester))
    body = {
        "query": {"bool": {"must": must}},
        "sort": [{"overall_gpa": "desc"}],
        "size": min(int(n), 50),
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {"status": "not_found", "message": f"Không có dữ liệu lớp {class_name}."}
    return {"status": "success", "data": [h["_source"] for h in hits]}


def list_students_in_class(
    class_name: str,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    must.extend(_semester_year_filters(year, semester))
    body = {
        "query": {"bool": {"must": must}},
        "sort": [{"full_name.raw": "asc"}],
        "size": config.MAX_CLASS_SIZE,
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {"status": "not_found", "message": f"Lớp {class_name} không có dữ liệu."}
    return {"status": "success", "data": [h["_source"] for h in hits]}


def get_class_average_for_subject(
    class_name: str,
    subject_name: str,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [
        {"term": {"doc_type": "mark"}},
        {"match": {"class_name": class_name}},
        {"match": {"subject": {"query": _subject_query_string(subject_name), "operator": "or"}}},
    ]
    must.extend(_semester_year_filters(year, semester))
    body = {
        "query": {"bool": {"must": must}},
        "aggs": {"average_score": {"avg": {"field": "scores.TK"}}},
        "size": 0,
    }
    res = es.search(index=INDEX_NAME, body=body)
    avg = res.get("aggregations", {}).get("average_score", {}).get("value")
    if avg is None:
        return {
            "status": "not_found",
            "message": f"Không đủ dữ liệu môn {subject_name} cho lớp {class_name}.",
        }
    return {
        "status": "success",
        "class_name": class_name,
        "subject_name": subject_name,
        "average_score": round(avg, 2),
    }


def get_student_rank(
    student_name: str,
    class_name: str,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    must.extend(_semester_year_filters(year, semester))
    body = {
        "query": {"bool": {"must": must}},
        "sort": [{"overall_gpa": "desc"}],
        "size": config.MAX_CLASS_SIZE,
    }
    res = es.search(index=INDEX_NAME, body=body)
    students = [h["_source"] for h in res.get("hits", {}).get("hits", [])]
    if not students:
        return {"status": "not_found", "message": f"Không có dữ liệu lớp {class_name}."}
    target = norm(student_name)
    for idx, s in enumerate(students, start=1):
        if target in norm(s.get("full_name", "")):
            return {
                "status": "success",
                "rank": idx,
                "total": len(students),
                "gpa": s.get("overall_gpa"),
                "full_name": s.get("full_name"),
            }
    return {"status": "not_found", "message": f"Không thấy {student_name} trong lớp {class_name}."}


def get_student_rank_by_subject(
    student_name: str,
    class_name: str,
    subject_name: str,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    must = [
        {"term": {"doc_type": "mark"}},
        {"match": {"class_name": class_name}},
        {"match": {"subject": {"query": _subject_query_string(subject_name), "operator": "or"}}},
    ]
    must.extend(_semester_year_filters(year, semester))
    body = {
        "query": {"bool": {"must": must}},
        "sort": [{"scores.TK": {"order": "desc", "missing": "_last"}}],
        "size": config.MAX_CLASS_SIZE,
    }
    res = es.search(index=INDEX_NAME, body=body)
    marks = [h["_source"] for h in res.get("hits", {}).get("hits", [])]
    if not marks:
        return {
            "status": "not_found",
            "message": f"Không có dữ liệu môn {subject_name} của lớp {class_name}.",
        }
    target = norm(student_name)
    for idx, m in enumerate(marks, start=1):
        if target in norm(m.get("full_name", "")):
            return {
                "status": "success",
                "rank": idx,
                "total": len(marks),
                "subject_score": m.get("scores", {}).get("TK"),
                "full_name": m.get("full_name"),
            }
    return {
        "status": "not_found",
        "message": f"Không thấy điểm môn {subject_name} của {student_name} trong lớp {class_name}.",
    }


def get_at_risk_subjects(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
    threshold: float = 6.5,
) -> Dict[str, Any]:
    res = get_all_subject_scores_for_student(student_name, class_name, year, semester)
    if res["status"] != "success":
        return res
    at_risk = [
        s for s in res["data"]
        if s.get("scores", {}).get("TK") is not None and s["scores"]["TK"] < threshold
    ]
    if not at_risk:
        return {
            "status": "success",
            "context": res["context"],
            "at_risk_subjects": [],
            "message": f"Không có môn nào dưới {threshold}.",
        }
    return {"status": "success", "context": res["context"], "at_risk_subjects": at_risk}


def analyze_subject_strengths_by_group(
    student_name: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    res = get_all_subject_scores_for_student(student_name, class_name, year, semester)
    if res["status"] != "success":
        return res

    natural = {"toan", "khoa hoc tu nhien"}
    social = {"ngu van", "lich su va dia li", "gdcd"}

    nat_scores, soc_scores = [], []
    for s in res["data"]:
        tk = s.get("scores", {}).get("TK")
        if tk is None:
            continue
        canon = match_subject(s.get("subject", ""))
        if canon in natural:
            nat_scores.append(tk)
        elif canon in social:
            soc_scores.append(tk)

    if not nat_scores and not soc_scores:
        return {"status": "not_found", "message": "Không đủ dữ liệu phân tích."}

    avg_n = round(sum(nat_scores) / len(nat_scores), 2) if nat_scores else None
    avg_s = round(sum(soc_scores) / len(soc_scores), 2) if soc_scores else None

    conclusion = None
    if avg_n is not None and avg_s is not None:
        if avg_n > avg_s + 0.3:
            conclusion = f"{student_name} có thế mạnh nhóm Tự nhiên."
        elif avg_s > avg_n + 0.3:
            conclusion = f"{student_name} có thế mạnh nhóm Xã hội."
        else:
            conclusion = f"{student_name} học đồng đều hai nhóm."

    return {
        "status": "success",
        "context": res["context"],
        "natural_sciences_avg": avg_n,
        "social_sciences_avg": avg_s,
        "conclusion": conclusion,
    }


# --- Tools mới ---

def list_available_semesters(
    student_name: str,
    class_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Liệt kê các (year, semester) đã có dữ liệu cho học sinh."""
    must = [
        {"term": {"doc_type": "student"}},
        {"match_phrase": {"full_name": student_name}},
    ]
    if class_name:
        must.append({"match": {"class_name": class_name}})
    body = {
        "query": {"bool": {"must": must}},
        "size": 50,
        "sort": [{"year": "desc"}, {"semester": "desc"}],
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {"status": "not_found", "message": f"Không có dữ liệu cho {student_name}."}
    periods = [
        {
            "student_id": h["_source"].get("student_id"),
            "year": h["_source"].get("year"),
            "semester": h["_source"].get("semester"),
            "class_name": h["_source"].get("class_name"),
            "overall_gpa": h["_source"].get("overall_gpa"),
        }
        for h in hits
    ]
    return {"status": "success", "data": periods}


def get_score_trend(
    student_name: str,
    subject_name: Optional[str] = None,
    class_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Xu hướng điểm qua các học kỳ.

    - subject_name None → trả GPA tổng kết từng kỳ.
    - subject_name có → trả điểm TK môn đó từng kỳ.
    """
    # Tìm student_id qua bản ghi mới nhất
    base = _find_unique_student_record(student_name, class_name)
    if base["status"] != "success":
        return base
    sid = base["data"]["student_id"]

    if not subject_name:
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"doc_type": "student"}},
                        {"term": {"student_id": sid}},
                    ]
                }
            },
            "size": 50,
            "sort": [{"year": "asc"}, {"semester": "asc"}],
        }
        res = es.search(index=INDEX_NAME, body=body)
        hits = res.get("hits", {}).get("hits", [])
        return {
            "status": "success",
            "kind": "gpa",
            "student_name": base["data"]["full_name"],
            "data": [
                {
                    "year": h["_source"].get("year"),
                    "semester": h["_source"].get("semester"),
                    "overall_gpa": h["_source"].get("overall_gpa"),
                    "academic": h["_source"].get("academic"),
                }
                for h in hits
            ],
        }

    body = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"doc_type": "mark"}},
                    {"term": {"student_id": sid}},
                    {"match": {"subject": {"query": _subject_query_string(subject_name), "operator": "or"}}},
                ]
            }
        },
        "size": 100,
        "sort": [{"year": "asc"}, {"semester": "asc"}],
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {
            "status": "not_found",
            "message": f"Không có dữ liệu môn {subject_name} cho {student_name}.",
        }
    return {
        "status": "success",
        "kind": "subject",
        "subject_name": subject_name,
        "student_name": base["data"]["full_name"],
        "data": [
            {
                "year": h["_source"].get("year"),
                "semester": h["_source"].get("semester"),
                "TK": h["_source"].get("scores", {}).get("TK"),
                "GK": h["_source"].get("scores", {}).get("GK"),
                "CK": h["_source"].get("scores", {}).get("CK"),
            }
            for h in hits
        ],
    }


# --- Admin / teacher-only tools (chỉ được gọi khi role thuộc admin/teacher) ---

def rank_classes_by_subject_average(
    subject_name: str,
    n: int = 10,
    year: Optional[str] = None,
    semester: Optional[int] = None,
    grade_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Top N lớp theo điểm TB của 1 môn. Tool quản trị.

    grade_level (6/7/8/9) — chỉ tính các lớp khối đó (class_name bắt đầu bằng '<grade>A').
    """
    query_string = _subject_query_string(subject_name)
    must: List[Dict[str, Any]] = [
        {"term": {"doc_type": "mark"}},
        {"match": {"subject": {"query": query_string, "operator": "or"}}},
    ]
    must.extend(_semester_year_filters(year, semester))
    if grade_level:
        must.append({"prefix": {"class_name.raw": f"{int(grade_level)}a"}})

    body = {
        "query": {"bool": {"must": must}},
        "size": 0,
        "aggs": {
            "by_class": {
                "terms": {"field": "class_name.raw", "size": 100},
                "aggs": {"avg_tk": {"avg": {"field": "scores.TK"}}},
            }
        },
    }
    res = es.search(index=INDEX_NAME, body=body)
    buckets = res.get("aggregations", {}).get("by_class", {}).get("buckets", [])
    if not buckets:
        return {"status": "not_found", "message": f"Không có dữ liệu môn {subject_name}."}

    ranked = sorted(
        ((b["key"], round(b["avg_tk"]["value"] or 0, 2), b["doc_count"]) for b in buckets),
        key=lambda x: x[1],
        reverse=True,
    )[: int(n)]
    return {
        "status": "success",
        "subject_name": subject_name,
        "data": [
            {"class_name": k, "average_score": v, "num_records": c}
            for k, v, c in ranked
        ],
    }


def find_students_with_criteria(
    conduct: Optional[str] = None,
    academic: Optional[str] = None,
    grade_level: Optional[int] = None,
    class_name: Optional[str] = None,
    min_gpa: Optional[float] = None,
    max_gpa: Optional[float] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Tìm học sinh theo bộ tiêu chí kết hợp. Tool quản trị (admin/teacher).

    Ví dụ: conduct='Khá', grade_level=7 → mọi HS khối 7 có hạnh kiểm Khá.
    """
    must: List[Dict[str, Any]] = [{"term": {"doc_type": "student"}}]
    must.extend(_semester_year_filters(year, semester))
    if conduct:
        must.append({"term": {"conduct": conduct}})
    if academic:
        must.append({"term": {"academic": academic}})
    if class_name:
        must.append({"match": {"class_name": class_name}})
    if grade_level:
        must.append({"prefix": {"class_name.raw": f"{int(grade_level)}a"}})

    range_clause: Dict[str, float] = {}
    if min_gpa is not None:
        range_clause["gte"] = float(min_gpa)
    if max_gpa is not None:
        range_clause["lte"] = float(max_gpa)
    if range_clause:
        must.append({"range": {"overall_gpa": range_clause}})

    body = {
        "query": {"bool": {"must": must}},
        "size": min(int(limit), 200),
        "sort": [{"overall_gpa": {"order": "desc", "missing": "_last"}}],
    }
    res = es.search(index=INDEX_NAME, body=body)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {"status": "not_found", "message": "Không có học sinh khớp tiêu chí."}
    students = [
        {
            "full_name": h["_source"].get("full_name"),
            "class_name": h["_source"].get("class_name"),
            "overall_gpa": h["_source"].get("overall_gpa"),
            "conduct": h["_source"].get("conduct"),
            "academic": h["_source"].get("academic"),
            "year": h["_source"].get("year"),
            "semester": h["_source"].get("semester"),
        }
        for h in hits
    ]
    return {"status": "success", "count": len(students), "data": students}


def compare_students(
    student_name_a: str,
    student_name_b: str,
    class_name: Optional[str] = None,
    year: Optional[str] = None,
    semester: Optional[int] = None,
) -> Dict[str, Any]:
    """So sánh tổng quan + GPA 2 học sinh trong 1 kỳ."""
    a = _find_unique_student_record(student_name_a, class_name, year, semester)
    b = _find_unique_student_record(student_name_b, class_name, year, semester)
    if a["status"] != "success":
        return {"status": a["status"], "which": "A", **a}
    if b["status"] != "success":
        return {"status": b["status"], "which": "B", **b}
    return {
        "status": "success",
        "student_a": {
            "full_name": a["data"].get("full_name"),
            "class_name": a["data"].get("class_name"),
            "year": a["data"].get("year"),
            "semester": a["data"].get("semester"),
            "overall_gpa": a["data"].get("overall_gpa"),
            "academic": a["data"].get("academic"),
            "conduct": a["data"].get("conduct"),
        },
        "student_b": {
            "full_name": b["data"].get("full_name"),
            "class_name": b["data"].get("class_name"),
            "year": b["data"].get("year"),
            "semester": b["data"].get("semester"),
            "overall_gpa": b["data"].get("overall_gpa"),
            "academic": b["data"].get("academic"),
            "conduct": b["data"].get("conduct"),
        },
    }
