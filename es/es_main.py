"""Gemini function-calling orchestrator với hybrid retrieval, RBAC và verify."""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import google.generativeai as genai
from google.generativeai.protos import Part
from google.generativeai.types import FunctionDeclaration, Tool

from modules import config
from modules.doc_search import search_documents
from modules.es_school_qna import (
    analyze_subject_strengths_by_group,
    compare_students,
    find_students_with_criteria,
    get_all_subject_scores_for_student,
    get_at_risk_subjects,
    get_attendance_details,
    get_class_average_for_subject,
    get_class_size,
    get_score_trend,
    get_student_overview,
    get_student_rank,
    get_student_rank_by_subject,
    get_student_strengths_and_weaknesses,
    get_subject_score,
    get_top_n_students,
    list_all_classes,
    list_available_semesters,
    list_students_in_class,
    rank_classes_by_subject_average,
)
from modules.query_rewrite import rewrite_query

config.configure_logging()
log = logging.getLogger("es_main")
config.require_gemini()
genai.configure(api_key=config.GEMINI_API_KEY)


# --- Tool declarations ---
_OPT_CTX = {
    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tuỳ chọn)."},
    "year": {"type": "STRING", "description": "Năm học, ví dụ '2024-2025' hoặc '2024' (tuỳ chọn)."},
    "semester": {"type": "INTEGER", "description": "Học kỳ 1 hoặc 2 (tuỳ chọn)."},
}

STRUCTURED_TOOLS = Tool(function_declarations=[
    FunctionDeclaration(
        name="get_student_overview",
        description="Tổng quan học sinh: học lực, hạnh kiểm, GPA, chuyên cần. Mặc định kỳ mới nhất.",
        parameters={
            "type": "OBJECT",
            "properties": {"student_name": {"type": "STRING"}, **_OPT_CTX},
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="get_subject_score",
        description="Điểm chi tiết 1 môn (TX/GK/CK/TK) của 1 học sinh.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "subject_name": {"type": "STRING"},
                **_OPT_CTX,
            },
            "required": ["student_name", "subject_name"],
        },
    ),
    FunctionDeclaration(
        name="get_all_subject_scores_for_student",
        description="Bảng điểm tất cả môn của 1 học sinh trong 1 học kỳ.",
        parameters={
            "type": "OBJECT",
            "properties": {"student_name": {"type": "STRING"}, **_OPT_CTX},
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="get_attendance_details",
        description="Chuyên cần chi tiết.",
        parameters={
            "type": "OBJECT",
            "properties": {"student_name": {"type": "STRING"}, **_OPT_CTX},
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="get_student_strengths_and_weaknesses",
        description="Môn mạnh nhất / yếu nhất theo điểm TK.",
        parameters={
            "type": "OBJECT",
            "properties": {"student_name": {"type": "STRING"}, **_OPT_CTX},
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="get_student_rank",
        description="Thứ hạng GPA trong lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "class_name": {"type": "STRING"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["student_name", "class_name"],
        },
    ),
    FunctionDeclaration(
        name="get_student_rank_by_subject",
        description="Thứ hạng 1 môn trong lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "class_name": {"type": "STRING"},
                "subject_name": {"type": "STRING"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["student_name", "class_name", "subject_name"],
        },
    ),
    FunctionDeclaration(
        name="get_top_n_students",
        description="Top N học sinh có GPA cao nhất lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "class_name": {"type": "STRING"},
                "n": {"type": "INTEGER"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["class_name"],
        },
    ),
    FunctionDeclaration(
        name="get_class_size",
        description="Sĩ số lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "class_name": {"type": "STRING"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["class_name"],
        },
    ),
    FunctionDeclaration(
        name="list_all_classes",
        description="Danh sách tất cả lớp.",
        parameters={"type": "OBJECT", "properties": {"year": _OPT_CTX["year"]}},
    ),
    FunctionDeclaration(
        name="list_students_in_class",
        description="Danh sách học sinh trong lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "class_name": {"type": "STRING"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["class_name"],
        },
    ),
    FunctionDeclaration(
        name="get_class_average_for_subject",
        description="Điểm TB 1 môn cho cả lớp.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "class_name": {"type": "STRING"},
                "subject_name": {"type": "STRING"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["class_name", "subject_name"],
        },
    ),
    FunctionDeclaration(
        name="get_at_risk_subjects",
        description="Các môn có điểm TK dưới ngưỡng (mặc định 6.5).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "threshold": {"type": "NUMBER"},
                **_OPT_CTX,
            },
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="analyze_subject_strengths_by_group",
        description="So sánh thế mạnh nhóm Tự nhiên vs Xã hội.",
        parameters={
            "type": "OBJECT",
            "properties": {"student_name": {"type": "STRING"}, **_OPT_CTX},
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="list_available_semesters",
        description="Các (năm, học kỳ) đã có dữ liệu của 1 học sinh.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "class_name": _OPT_CTX["class_name"],
            },
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="get_score_trend",
        description="Xu hướng điểm qua nhiều học kỳ (GPA hoặc 1 môn).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name": {"type": "STRING"},
                "subject_name": {"type": "STRING"},
                "class_name": _OPT_CTX["class_name"],
            },
            "required": ["student_name"],
        },
    ),
    FunctionDeclaration(
        name="compare_students",
        description="So sánh tổng quan 2 học sinh.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "student_name_a": {"type": "STRING"},
                "student_name_b": {"type": "STRING"},
                **_OPT_CTX,
            },
            "required": ["student_name_a", "student_name_b"],
        },
    ),
    FunctionDeclaration(
        name="search_documents",
        description=(
            "Tìm kiếm trong tài liệu nội bộ của trường (nội quy, quy định, học phí, "
            "chương trình giáo dục, lịch học, an toàn...). Dùng khi câu hỏi liên quan "
            "tới chính sách / quy định / thông tin trường, KHÔNG phải điểm số/xếp hạng."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Câu hỏi tìm kiếm."},
                "k": {"type": "INTEGER", "description": "Số tài liệu trả về, mặc định 5."},
            },
            "required": ["query"],
        },
    ),
    FunctionDeclaration(
        name="rank_classes_by_subject_average",
        description=(
            "Xếp hạng các lớp theo điểm trung bình của 1 môn. CHỈ DÀNH CHO ADMIN/GIÁO VIÊN. "
            "Dùng cho các câu hỏi quản trị như 'lớp nào có điểm Toán cao nhất khối 7'."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "subject_name": {"type": "STRING"},
                "n": {"type": "INTEGER", "description": "Số lớp, mặc định 10."},
                "grade_level": {"type": "INTEGER", "description": "Khối 6/7/8/9 (tuỳ chọn)."},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
            },
            "required": ["subject_name"],
        },
    ),
    FunctionDeclaration(
        name="find_students_with_criteria",
        description=(
            "Tìm danh sách học sinh theo tổ hợp tiêu chí (hạnh kiểm, học lực, khối, lớp, "
            "khoảng GPA). CHỈ DÀNH CHO ADMIN/GIÁO VIÊN. Dùng cho thống kê quản trị."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "conduct": {"type": "STRING", "description": "Hạnh kiểm: Tốt/Khá/Đạt/Chưa đạt"},
                "academic": {"type": "STRING", "description": "Học lực: Tốt/Khá/Đạt/Chưa đạt"},
                "grade_level": {"type": "INTEGER", "description": "Khối 6/7/8/9"},
                "class_name": _OPT_CTX["class_name"],
                "min_gpa": {"type": "NUMBER"},
                "max_gpa": {"type": "NUMBER"},
                "year": _OPT_CTX["year"],
                "semester": _OPT_CTX["semester"],
                "limit": {"type": "INTEGER", "description": "Tối đa, mặc định 50."},
            },
        },
    ),
])

STRUCTURED_FUNCTIONS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "get_student_overview": get_student_overview,
    "get_subject_score": get_subject_score,
    "get_all_subject_scores_for_student": get_all_subject_scores_for_student,
    "get_top_n_students": get_top_n_students,
    "get_class_size": get_class_size,
    "get_student_rank": get_student_rank,
    "get_student_rank_by_subject": get_student_rank_by_subject,
    "list_all_classes": list_all_classes,
    "get_student_strengths_and_weaknesses": get_student_strengths_and_weaknesses,
    "get_attendance_details": get_attendance_details,
    "list_students_in_class": list_students_in_class,
    "get_class_average_for_subject": get_class_average_for_subject,
    "get_at_risk_subjects": get_at_risk_subjects,
    "analyze_subject_strengths_by_group": analyze_subject_strengths_by_group,
    "list_available_semesters": list_available_semesters,
    "get_score_trend": get_score_trend,
    "compare_students": compare_students,
    "rank_classes_by_subject_average": rank_classes_by_subject_average,
    "find_students_with_criteria": find_students_with_criteria,
}

# Tool chỉ dành cho admin/teacher — parent gọi sẽ bị tool dispatcher từ chối.
ADMIN_ONLY_TOOLS = {
    "rank_classes_by_subject_average",
    "find_students_with_criteria",
}

SYSTEM_INSTRUCTION = """\
Bạn là Cố vấn học tập ảo, trả lời phụ huynh / giáo viên bằng tiếng Việt chuyên nghiệp.

Nguyên tắc:
1. Khi câu hỏi liên quan tới ĐIỂM SỐ / HẠNH KIỂM / XẾP HẠNG / DANH SÁCH LỚP → gọi tool dữ liệu học sinh tương ứng.
2. Khi câu hỏi liên quan tới CHÍNH SÁCH / NỘI QUY / QUY ĐỊNH / LỊCH / HỌC PHÍ / THÔNG TIN TRƯỜNG → gọi `search_documents`.
3. Không tự bịa số liệu hoặc quy định khi không có trong tool result.
4. Mặc định trả dữ liệu MỚI NHẤT nếu phụ huynh không nói rõ học kỳ/năm.
5. status='ambiguous' → hỏi lại bằng options.
6. status='not_found' → thông báo lịch sự là chưa có dữ liệu.
7. KHI dùng `search_documents`, BẮT BUỘC trích nguồn ở cuối câu trả lời theo format:
   "Nguồn: <title> — <section> (<source_path>)"
   Nếu có nhiều nguồn, liệt kê tất cả.
8. Trình bày kết quả gọn gàng (gạch đầu dòng nếu nhiều mục), KHÔNG dán JSON thô.
9. Khi tool trả về status='denied': KHÔNG thử lại tool khác, KHÔNG bịa kết quả. Trả lời nguyên văn rằng người dùng không có quyền và đề nghị liên hệ quản trị.
"""

MAX_TOOL_LOOPS = 8


@dataclass
class AdvisorContext:
    """Context truyền cho 1 lượt hỏi: role, có rewrite query hay không."""
    role: str = "parent"
    rewrite: bool = True
    verify: bool = False  # bật self-RAG verify


@dataclass
class AdvisorResult:
    answer: str
    tools_called: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    rewritten_query: Optional[str] = None
    elapsed_ms: int = 0
    success: bool = True


class Advisor:
    """Wrapper sạch quanh Gemini chat. Có thể tái sử dụng cho bot + eval."""

    def __init__(self) -> None:
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            tools=[STRUCTURED_TOOLS],
            system_instruction=SYSTEM_INSTRUCTION,
        )
        self._verifier: Optional[genai.GenerativeModel] = None

    # --- Tool dispatcher ---
    def _run_tool(
        self, name: str, args: Dict[str, Any], ctx: AdvisorContext
    ) -> Dict[str, Any]:
        # RBAC gate: tool admin-only chỉ chạy khi role thuộc admin/teacher
        if name in ADMIN_ONLY_TOOLS and ctx.role not in {"admin", "teacher"}:
            log.info("Từ chối %s cho role=%s", name, ctx.role)
            return {
                "status": "denied",
                "message": (
                    f"Tính năng '{name}' chỉ dành cho giáo viên/quản trị. "
                    "Phụ huynh không có quyền truy cập."
                ),
            }

        if name == "search_documents":
            try:
                return search_documents(
                    query=args.get("query", ""),
                    k=int(args.get("k", 5)),
                    role=ctx.role,
                )
            except Exception as e:
                log.exception("search_documents lỗi")
                return {"status": "error", "message": str(e)}

        fn = STRUCTURED_FUNCTIONS.get(name)
        if not fn:
            return {"status": "error", "message": f"Unknown tool: {name}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"status": "error", "message": f"Tham số không hợp lệ: {e}"}
        except Exception as e:
            log.exception("Tool %s raised", name)
            return {"status": "error", "message": str(e)}

    # --- Verify (Self-RAG lite) ---
    def _verify(self, question: str, answer: str, citations: List[Dict[str, Any]]) -> bool:
        if not self._verifier:
            self._verifier = genai.GenerativeModel(
                model_name=config.GEMINI_MODEL,
                system_instruction=(
                    "Bạn là bộ kiểm tra grounding. Cho câu hỏi, câu trả lời và bằng chứng, "
                    "chỉ trả về 'OK' nếu câu trả lời được bằng chứng chứng minh, "
                    "hoặc 'FAIL: <lý do ngắn>' nếu không."
                ),
            )
        ev = "\n".join(
            f"- {c.get('title')} / {c.get('section')}: {c.get('content','')[:300]}"
            for c in citations
        )
        prompt = (
            f"Câu hỏi: {question}\n\n"
            f"Câu trả lời:\n{answer}\n\n"
            f"Bằng chứng:\n{ev or '(không có)'}\n\n"
            "Phán xét:"
        )
        try:
            r = self._verifier.generate_content(prompt)
            verdict = (r.text or "").strip()
            return verdict.upper().startswith("OK")
        except Exception as e:
            log.warning("Verify lỗi: %s", e)
            return True

    # --- Main entry ---
    def answer(
        self,
        question: str,
        history: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[AdvisorContext] = None,
    ) -> AdvisorResult:
        ctx = ctx or AdvisorContext()
        history = history or []
        result = AdvisorResult(answer="")
        t0 = time.time()

        # Query rewrite (chỉ dùng cho vector retrieval, nhưng đưa luôn câu rewritten vào lịch sử)
        effective_q = question
        if ctx.rewrite and history:
            rewritten = rewrite_query(question, history)
            if rewritten != question:
                result.rewritten_query = rewritten
                # Không thay câu hỏi gốc, vì LLM cần nguyên văn intent.
                # Câu rewrite chỉ dùng nội bộ; với LLM ta gắn vào prompt như hint.

        chat = self.model.start_chat(history=history)
        hint = f"\n(Tóm tắt context để tìm kiếm: {result.rewritten_query})" if result.rewritten_query else ""
        response = chat.send_message(question + hint)

        for _ in range(MAX_TOOL_LOOPS):
            try:
                part = response.candidates[0].content.parts[0]
            except (IndexError, AttributeError):
                result.answer = getattr(response, "text", "") or "Xin lỗi, tôi chưa thể trả lời."
                break

            fc = getattr(part, "function_call", None)
            if not fc or not fc.name:
                result.answer = (part.text or "").strip() or "Xin lỗi, tôi chưa thể trả lời."
                break

            args = {k: v for k, v in fc.args.items()}
            result.tools_called.append(fc.name)
            tool_result = self._run_tool(fc.name, args, ctx)

            if fc.name == "search_documents" and tool_result.get("status") == "success":
                for d in tool_result.get("data", []):
                    result.citations.append({
                        "title": d.get("title"),
                        "section": d.get("section"),
                        "source_path": d.get("source_path"),
                        "content": d.get("content"),
                    })

            response = chat.send_message(
                Part(function_response={"name": fc.name, "response": tool_result})
            )
        else:
            log.warning("Đạt giới hạn tool loop (%d)", MAX_TOOL_LOOPS)
            try:
                result.answer = response.text or "Xin lỗi, câu hỏi quá phức tạp."
            except Exception:
                result.answer = "Xin lỗi, câu hỏi quá phức tạp."
            result.success = False

        if ctx.verify and result.citations:
            ok = self._verify(question, result.answer, result.citations)
            if not ok:
                result.answer += "\n\n⚠ Lưu ý: câu trả lời chưa được kiểm chứng đầy đủ từ tài liệu nội bộ."

        result.elapsed_ms = int((time.time() - t0) * 1000)
        return result


# --- Singleton + backward-compatible function ---
_DEFAULT_ADVISOR: Optional[Advisor] = None


def get_advisor() -> Advisor:
    global _DEFAULT_ADVISOR
    if _DEFAULT_ADVISOR is None:
        _DEFAULT_ADVISOR = Advisor()
    return _DEFAULT_ADVISOR


def answer_question(
    question: str,
    history_chat: List[Dict[str, Any]],
    role: str = "parent",
) -> str:
    """Backward-compat wrapper for older callers."""
    ctx = AdvisorContext(role=role)
    return get_advisor().answer(question, history_chat, ctx).answer


# --- CLI ---
if __name__ == "__main__":
    print("🤖 Cố vấn học tập sẵn sàng. Gõ 'exit' để thoát.")
    advisor = get_advisor()
    history: List[Dict[str, Any]] = []
    while True:
        try:
            q = input("Hỏi: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in {"exit", "quit", "thoát"}:
            break
        r = advisor.answer(q, history)
        history.append({"role": "user", "parts": [q]})
        history.append({"role": "model", "parts": [r.answer]})
        history = history[-config.HISTORY_TURNS * 2:]
        print(f"\n👩‍🏫 {r.answer}")
        print(f"⏱  {r.elapsed_ms}ms  •  tools={r.tools_called}  •  citations={len(r.citations)}\n")
