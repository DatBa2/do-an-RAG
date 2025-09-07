import os
import re
import json
from typing import Optional, Dict, Any, List
from elasticsearch import Elasticsearch

# --- Cấu hình và kết nối ES ---
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")
INDEX_NAME = os.getenv("ES_INDEX", "hs_records")
es = Elasticsearch(ES_HOST)

# --- Các hàm tiện ích chuẩn hóa & Từ đồng nghĩa ---
try:
    with open('synonyms.json', 'r', encoding='utf-8') as f:
        SUBJECT_SYNONYMS = json.load(f)
except FileNotFoundError:
    print("[WARN] File 'synonyms.json' không tìm thấy. Sử dụng danh sách mặc định.")
    SUBJECT_SYNONYMS = {
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
        "noi dung giao duc cua dia phuong": ["noi dung giao duc cua dia phuong", "ndgd dia phuong", "dia phuong"],
        "hoat dong trai nghiem, huong nghiep": ["hdtn", "hoat dong trai nghiem", "huong nghiep"]
    }

ACCENT_MAP = str.maketrans(
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
)
ACCENT_MAP.update(
    str.maketrans(
        "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ",
        "AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIoooooooooooooooooUUUUUUUUUUUYYYYYD"
    )
)

def strip_accents(s: str) -> str:
    """Bỏ dấu tiếng Việt."""
    return s.translate(ACCENT_MAP)

def norm(s: Optional[str]) -> str:
    """Chuẩn hóa chuỗi: bỏ dấu, chuyển chữ thường, xóa khoảng trắng thừa."""
    if not s: return ""
    s2 = strip_accents(s).lower().strip()
    return re.sub(r"\s+", " ", s2)

def match_subject(subject_text: str) -> Optional[str]:
    """Tìm tên môn học chuẩn hóa từ một chuỗi bất kỳ."""
    if not subject_text: return None
    n = norm(subject_text)
    for canon, arr in SUBJECT_SYNONYMS.items():
        for a in arr:
            if n == a or n in a or a in n:
                return canon
    return n

# --- HÀM LÕI MỚI ĐỂ TÌM KIẾM VÀ CHỐNG NHẬP NHẰNG ---
def _find_unique_student_record(student_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """
    Hàm lõi để tìm kiếm MỘT học sinh duy nhất, có khả năng xử lý nhập nhằng.
    Sử dụng 'match_phrase' để tăng độ chính xác.
    """
    must_filters = [{"term": {"doc_type": "student"}}, {"match_phrase": {"full_name": student_name}}]
    
    if class_name: must_filters.append({"match": {"class_name": class_name}})
    if year: must_filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester: must_filters.append({"term": {"semester": semester}})
        
    query = {"query": {"bool": {"must": must_filters}}}
    
    # Tìm kiếm với size=10 để phát hiện các trường hợp nhập nhằng
    res = es.search(index=INDEX_NAME, body=query, size=10)
    hits = res.get("hits", {}).get("hits", [])
    
    if not hits:
        return {"status": "not_found", "message": f"Không tìm thấy học sinh nào có tên '{student_name}' khớp với các tiêu chí đã cho."}
    
    # Lấy danh sách các bản ghi duy nhất
    unique_students = [h['_source'] for h in hits]

    if len(unique_students) > 1:
        # TRẢ VỀ TRẠNG THÁI NHẬP NHẰNG ĐỂ GEMINI HỎI LẠI NGƯỜI DÙNG
        clarification_options = [
            f"- {s.get('full_name')} (Lớp {s.get('class_name', 'N/A')}, HK {s.get('semester', 'N/A')} năm {s.get('year', 'N/A')})"
            for s in unique_students
        ]
        return {
            "status": "ambiguous", 
            "message": f"Tìm thấy nhiều học sinh tên '{student_name}'. Vui lòng cung cấp thêm thông tin hoặc chọn một trong các học sinh sau:",
            "options": "\n".join(clarification_options)
        }
    
    # TÌM THẤY DUY NHẤT 1 KẾT QUẢ -> THÀNH CÔNG
    return {"status": "success", "data": unique_students[0]}

# --- BỘ CÔNG CỤ (TOOLS) DÀNH CHO LLM ---
# --- CÁC HÀM NÀY ĐÃ ĐƯỢC CẬP NHẬT ĐỂ AN TOÀN HƠN ---

def get_student_overview(student_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy thông tin tổng quan (hạnh kiểm, học lực, điểm tổng kết) của một học sinh."""
    return _find_unique_student_record(student_name, class_name, year, semester)

def get_all_subject_scores_for_student(student_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy bảng điểm chi tiết TẤT CẢ các môn của một học sinh."""
    find_result = _find_unique_student_record(student_name, class_name, year, semester)
    
    if find_result["status"] != "success":
        return find_result

    student_record = find_result["data"]
    student_id = student_record.get("student_id")
    sem = student_record.get("semester")
    yr = student_record.get("year")

    must_filters = [
        {"term": {"doc_type": "mark"}},
        {"term": {"student_id.keyword": student_id}}, # Dùng .keyword để khớp chính xác
        {"term": {"semester": sem}},
        {"term": {"year.keyword": yr}}
    ]
    
    query = {"query": {"bool": {"must": must_filters}}, "size": 50}
    res = es.search(index=INDEX_NAME, body=query)
    hits = res.get("hits", {}).get("hits", [])

    if not hits:
        return {"status": "not_found", "message": f"Đã tìm thấy học sinh {student_name} nhưng không tìm thấy dữ liệu điểm chi tiết."}
        
    scores_list = [hit['_source'] for hit in hits]
    return {"status": "success", "data": scores_list}

def get_subject_score(student_name: str, subject_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy điểm chi tiết của MỘT môn học cụ thể cho một học sinh."""
    find_result = _find_unique_student_record(student_name, class_name, year, semester)
    
    if find_result["status"] != "success":
        return find_result

    student_record = find_result["data"]
    student_id = student_record.get("student_id")
    sem = student_record.get("semester")
    yr = student_record.get("year")
    
    canonical_subject = match_subject(subject_name)
    query_string = " ".join(SUBJECT_SYNONYMS.get(canonical_subject, [canonical_subject])) if canonical_subject else subject_name

    must_filters = [
        {"term": {"doc_type": "mark"}},
        {"term": {"student_id.keyword": student_id}},
        {"term": {"semester": sem}},
        {"term": {"year.keyword": yr}},
        {"match": {"subject": {"query": query_string, "operator": "or"}}}
    ]
    
    query = {"query": {"bool": {"must": must_filters}}}
    res = es.search(index=INDEX_NAME, body=query, size=1)
    hits = res.get("hits", {}).get("hits", [])
    
    if not hits:
        return {"status": "not_found", "message": f"Không tìm thấy điểm môn '{subject_name}' cho học sinh {student_name}."}
        
    return {"status": "success", "data": hits[0]['_source']}

def get_attendance_details(student_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy thông tin chuyên cần chi tiết của học sinh."""
    find_result = _find_unique_student_record(student_name, class_name, year, semester)
    
    if find_result['status'] != 'success':
        return find_result
        
    attendance_data = find_result.get('data', {}).get('attendance')
    if attendance_data:
        return {"status": "success", "data": attendance_data}
        
    return {"status": "not_found", "message": "Không tìm thấy dữ liệu chuyên cần."}

def get_student_strengths_and_weaknesses(student_name: str, class_name: Optional[str] = None, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Phân tích điểm số để tìm ra môn học mạnh nhất và yếu nhất của học sinh."""
    all_scores_result = get_all_subject_scores_for_student(student_name, class_name, year, semester)
    
    if all_scores_result['status'] != 'success':
        return all_scores_result
        
    scores_list = all_scores_result['data']
    valid_scores = [s for s in scores_list if s.get('scores', {}).get('TK') is not None]
    
    if not valid_scores:
        return {"status": "not_found", "message": "Không có đủ dữ liệu điểm tổng kết môn học để phân tích."}
        
    best_subject = max(valid_scores, key=lambda s: s['scores']['TK'])
    worst_subject = min(valid_scores, key=lambda s: s['scores']['TK'])
    
    return {
        "status": "success",
        "best_subject": {"subject": best_subject['subject'], "score": best_subject['scores']['TK']},
        "worst_subject": {"subject": worst_subject['subject'], "score": worst_subject['scores']['TK']}
    }
    
# --- CÁC HÀM ÍT BỊ ẢNH HƯỞNG BỞI TÊN HỌC SINH (GIỮ NGUYÊN HOẶC ÍT THAY ĐỔI) ---

def get_class_size(class_name: str, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy sĩ số của một lớp học cụ thể."""
    must_filters = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    if year: must_filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester: must_filters.append({"term": {"semester": semester}})
    query = {"query": {"bool": {"must": must_filters}}}
    count = es.count(index=INDEX_NAME, body=query).get("count", 0)
    if count > 0:
        return {"status": "success", "class_name": class_name, "count": count}
    return {"status": "not_found", "message": f"Không tìm thấy dữ liệu cho lớp {class_name}."}

def list_all_classes(year: Optional[str] = None) -> Dict[str, Any]:
    """Liệt kê tất cả các lớp học có trong trường và đếm tổng số lớp."""
    query = {"size": 0, "query": {"bool": {"must": [{"term": {"doc_type": "student"}}]}}, "aggs": {"unique_classes": {"terms": {"field": "class_name.raw", "size": 200}}}}
    if year: query["query"]["bool"]["must"].append({"wildcard": {"year": f"*{year}*"}})
    res = es.search(index=INDEX_NAME, body=query)
    buckets = res.get("aggregations", {}).get("unique_classes", {}).get("buckets", [])
    if not buckets:
        return {"status": "not_found", "message": "Không tìm thấy dữ liệu về lớp học nào."}
    class_names = [bucket['key'] for bucket in buckets]
    return {"status": "success", "total_classes": len(class_names), "class_list": sorted(class_names)}

def get_top_n_students(class_name: str, n: int = 5, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Liệt kê top N học sinh có điểm tổng kết (GPA) cao nhất lớp."""
    must_filters = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    if year: must_filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester: must_filters.append({"term": {"semester": semester}})
    query = {"query": {"bool": {"must": must_filters}}, "sort": [{"overall_gpa": "desc"}], "size": n}
    res = es.search(index=INDEX_NAME, body=query)
    hits = res.get("hits", {}).get("hits", [])
    if not hits:
        return {"status": "not_found", "message": f"Không có dữ liệu học sinh cho lớp {class_name}."}
    top_students = [hit['_source'] for hit in hits]
    return {"status": "success", "data": top_students}

# Các hàm rank cần class_name làm tham số bắt buộc nên ít bị ảnh hưởng,
# tuy nhiên, chúng vẫn có thể được cải tiến thêm bằng hàm helper nếu cần.
# Tạm thời giữ nguyên để tập trung vào các hàm tra cứu chính.

def get_student_rank(student_name: str, class_name: str, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy thứ hạng của một học sinh trong lớp dựa trên ĐIỂM TỔNG KẾT (GPA)."""
    # ... (giữ nguyên logic cũ vì đã có class_name)
    class_query_must = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    if year: class_query_must.append({"wildcard": {"year": f"*{year}*"}})
    if semester: class_query_must.append({"term": {"semester": semester}})
    class_query = {"query": {"bool": {"must": class_query_must}}, "sort": [{"overall_gpa": "desc"}], "size": 200}
    res = es.search(index=INDEX_NAME, body=class_query)
    all_students = [h["_source"] for h in res.get("hits", {}).get("hits", [])]
    if not all_students:
        return {"status": "not_found", "message": f"Không có dữ liệu cho lớp {class_name}."}
    student_name_norm = norm(student_name)
    for i, student in enumerate(all_students, start=1):
        if student_name_norm in norm(student.get("full_name", "")):
            return {"status": "success", "rank": i, "total": len(all_students), "gpa": student.get("overall_gpa")}
    return {"status": "not_found", "message": f"Không tìm thấy học sinh {student_name} trong lớp {class_name}."}


def get_student_rank_by_subject(student_name: str, class_name: str, subject_name: str, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Lấy thứ hạng của một học sinh trong lớp dựa trên điểm của MỘT MÔN HỌC CỤ THỂ."""
    # ... (giữ nguyên logic cũ vì đã có class_name)
    canonical_subject = match_subject(subject_name)
    query_string = " ".join(SUBJECT_SYNONYMS.get(canonical_subject, [canonical_subject])) if canonical_subject else subject_name
    class_query_must = [{"term": {"doc_type": "mark"}}, {"match": {"class_name": class_name}}, {"match": {"subject": {"query": query_string, "operator": "or"}}}]
    if year: class_query_must.append({"wildcard": {"year": f"*{year}*"}})
    if semester: class_query_must.append({"term": {"semester": semester}})
    class_query = {"query": {"bool": {"must": class_query_must}}, "sort": [{"scores.TK": "desc"}], "size": 200}
    res = es.search(index=INDEX_NAME, body=class_query)
    all_marks_in_class = [h["_source"] for h in res.get("hits", {}).get("hits", [])]
    if not all_marks_in_class:
        return {"status": "not_found", "message": f"Không có dữ liệu điểm môn {subject_name} cho lớp {class_name}."}
    student_name_norm = norm(student_name)
    for i, mark_data in enumerate(all_marks_in_class, start=1):
        if student_name_norm in norm(mark_data.get("full_name", "")):
            return {"status": "success", "rank": i, "total": len(all_marks_in_class), "subject_score": mark_data.get("scores", {}).get("TK")}
    return {"status": "not_found", "message": f"Không tìm thấy điểm môn {subject_name} của học sinh {student_name} trong lớp {class_name}."}

# Thêm hàm này vào cuối file es_school_qna.py

def list_students_in_class(class_name: str, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Liệt kê danh sách tất cả học sinh trong một lớp học cụ thể."""
    must_filters = [{"term": {"doc_type": "student"}}, {"match": {"class_name": class_name}}]
    if year: must_filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester: must_filters.append({"term": {"semester": semester}})
    
    query = {
        "query": {"bool": {"must": must_filters}},
        "sort": [{"full_name.raw": "asc"}], # Sắp xếp theo tên cho danh sách gọn gàng
        "size": 200 # Giới hạn cao để lấy hết học sinh trong một lớp
    }
    
    res = es.search(index=INDEX_NAME, body=query)
    hits = res.get("hits", {}).get("hits", [])
    
    if not hits:
        return {"status": "not_found", "message": f"Không tìm thấy học sinh nào trong lớp {class_name} khớp với tiêu chí."}
        
    student_list = [hit['_source'] for hit in hits]
    return {"status": "success", "data": student_list}

def get_class_average_for_subject(class_name: str, subject_name: str, year: Optional[str] = None, semester: Optional[int] = None) -> Dict[str, Any]:
    """Tính điểm trung bình của một môn học cụ thể cho toàn bộ một lớp."""
    canonical_subject = match_subject(subject_name)
    query_string = " ".join(SUBJECT_SYNONYMS.get(canonical_subject, [canonical_subject])) if canonical_subject else subject_name

    must_filters = [
        {"term": {"doc_type": "mark"}},
        {"match": {"class_name": class_name}},
        {"match": {"subject": {"query": query_string, "operator": "or"}}}
    ]
    if year: must_filters.append({"wildcard": {"year": f"*{year}*"}})
    if semester: must_filters.append({"term": {"semester": semester}})

    # Sử dụng aggregation của Elasticsearch để tính trung bình
    query = {
        "query": {"bool": {"must": must_filters}},
        "aggs": {
            "average_score": {
                "avg": {"field": "scores.TK"}
            }
        },
        "size": 0
    }
    
    res = es.search(index=INDEX_NAME, body=query)
    avg_score = res.get("aggregations", {}).get("average_score", {}).get("value")

    if avg_score is not None:
        return {"status": "success", "class_name": class_name, "subject_name": subject_name, "average_score": round(avg_score, 2)}
    
    return {"status": "not_found", "message": f"Không có đủ dữ liệu để tính điểm trung bình môn {subject_name} cho lớp {class_name}."}

def get_at_risk_subjects(student_name: str, class_name: Optional[str] = None, threshold: float = 6.5) -> Dict[str, Any]:
    """Liệt kê các môn học có điểm tổng kết dưới một ngưỡng nhất định (mặc định là 6.5)."""
    all_scores_result = get_all_subject_scores_for_student(student_name, class_name)
    
    if all_scores_result['status'] != 'success':
        return all_scores_result
        
    scores_list = all_scores_result['data']
    at_risk_list = [
        s for s in scores_list 
        if s.get('scores', {}).get('TK') is not None and s['scores']['TK'] < threshold
    ]
    
    if not at_risk_list:
        return {"status": "success", "at_risk_subjects": [], "message": f"Chúc mừng! Em {student_name} không có môn nào dưới ngưỡng {threshold} điểm."}
        
    return {"status": "success", "at_risk_subjects": at_risk_list}

def analyze_subject_strengths_by_group(student_name: str, class_name: Optional[str] = None) -> Dict[str, Any]:
    """Phân tích điểm số để xem học sinh có thế mạnh về nhóm môn Tự nhiên hay Xã hội."""
    all_scores_result = get_all_subject_scores_for_student(student_name, class_name)
    
    if all_scores_result['status'] != 'success':
        return all_scores_result
    
    scores_list = all_scores_result['data']
    
    natural_sciences = ['toan', 'khoa hoc tu nhien']
    social_sciences = ['ngu van', 'lich su va dia li', 'gdcd']
    
    natural_scores = [s['scores']['TK'] for s in scores_list if match_subject(s['subject']) in natural_sciences and s.get('scores', {}).get('TK') is not None]
    social_scores = [s['scores']['TK'] for s in scores_list if match_subject(s['subject']) in social_sciences and s.get('scores', {}).get('TK') is not None]
    
    if not natural_scores and not social_scores:
        return {"status": "not_found", "message": "Không có đủ dữ liệu điểm các môn Tự nhiên hoặc Xã hội để phân tích."}
        
    avg_natural = round(sum(natural_scores) / len(natural_scores), 2) if natural_scores else None
    avg_social = round(sum(social_scores) / len(social_scores), 2) if social_scores else None

    result = {
        "status": "success",
        "natural_sciences_avg": avg_natural,
        "social_sciences_avg": avg_social
    }
    
    if avg_natural is not None and avg_social is not None:
        if avg_natural > avg_social:
            result["conclusion"] = f"Em {student_name} có thế mạnh hơn về các môn Tự nhiên."
        elif avg_social > avg_natural:
            result["conclusion"] = f"Em {student_name} có thế mạnh hơn về các môn Xã hội."
        else:
            result["conclusion"] = f"Em {student_name} học đồng đều ở cả hai nhóm môn Tự nhiên và Xã hội."
            
    return result