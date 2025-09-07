import os
import time
import google.generativeai as genai
from google.generativeai.protos import Part
from google.generativeai.types import FunctionDeclaration, Tool

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCM9BL3FkNcpf0aimQCUTnGuTvhhG6zw3Q")
if not GEMINI_API_KEY:
    raise ValueError("Vui lòng thiết lập GEMINI_API_KEY trong file .env hoặc biến môi trường")
genai.configure(api_key=GEMINI_API_KEY)

from modules.es_school_qna import (
    get_class_size, get_student_overview, get_student_rank,
    get_subject_score, get_student_rank_by_subject, list_all_classes,
    get_all_subject_scores_for_student, get_top_n_students,
    get_student_strengths_and_weaknesses, get_attendance_details, list_students_in_class,
    get_class_average_for_subject,
    get_at_risk_subjects,
    analyze_subject_strengths_by_group)

# --- KHAI BÁO CÔNG CỤ THEO CÁCH CHUẨN ---
# Đây là bước quan trọng nhất. Chúng ta mô tả rõ từng hàm cho Gemini.
tools = Tool(
    function_declarations=[
        FunctionDeclaration(
            name="get_student_overview",
            description="Lấy thông tin tổng quan (hạnh kiểm, học lực, điểm tổng kết) của một học sinh.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên đầy đủ của học sinh cần tra cứu."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name"]
            }
        ),
        FunctionDeclaration(
            name="get_subject_score",
            description="Lấy điểm chi tiết của MỘT môn học cụ thể cho một học sinh.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên đầy đủ của học sinh."},
                    "subject_name": {"type": "STRING", "description": "Tên môn học cần xem điểm, ví dụ: 'Toán'."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name", "subject_name"]
            }
        ),
        FunctionDeclaration(
            name="get_all_subject_scores_for_student",
            description="Lấy bảng điểm chi tiết TẤT CẢ các môn của một học sinh.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần xem bảng điểm."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name"]
            }
        ),
        FunctionDeclaration(
            name="get_attendance_details",
            description="Lấy thông tin chuyên cần chi tiết (số ngày nghỉ có phép và không phép) của học sinh.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần xem thông tin chuyên cần."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name"]
            }
        ),
        FunctionDeclaration(
            name="get_student_strengths_and_weaknesses",
            description="Phân tích điểm số để tìm ra môn học mạnh nhất và yếu nhất của học sinh.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần phân tích."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name"]
            }
        ),
        FunctionDeclaration(
            name="get_student_rank",
            description="Lấy thứ hạng của một học sinh trong lớp dựa trên điểm tổng kết (GPA).",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần xem hạng."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (bắt buộc)."}
                },
                "required": ["student_name", "class_name"]
            }
        ),
        FunctionDeclaration(
            name="get_student_rank_by_subject",
            description="Lấy thứ hạng của một học sinh trong lớp dựa trên điểm của một môn học cụ thể.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần xem hạng."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (bắt buộc)."},
                    "subject_name": {"type": "STRING", "description": "Tên môn học dùng để xếp hạng."}
                },
                "required": ["student_name", "class_name", "subject_name"]
            }
        ),
        FunctionDeclaration(
            name="get_top_n_students",
            description="Liệt kê top N học sinh có điểm tổng kết (GPA) cao nhất lớp.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "class_name": {"type": "STRING", "description": "Tên lớp cần xem xếp hạng."},
                    "n": {"type": "INTEGER", "description": "Số lượng học sinh cần hiển thị, mặc định là 5."}
                },
                "required": ["class_name"]
            }
        ),
        FunctionDeclaration(
            name="get_class_size",
            description="Lấy sĩ số (tổng số học sinh) của một lớp học.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "class_name": {"type": "STRING", "description": "Tên lớp cần đếm sĩ số."}
                },
                "required": ["class_name"]
            }
        ),
        FunctionDeclaration(
            name="list_all_classes",
            description="Liệt kê tất cả các lớp học hiện có trong trường.",
            parameters={"type": "OBJECT", "properties": {}} # Không cần tham số
        ),
        # <-- KHAI BÁO TOOL MỚI
        FunctionDeclaration(
            name="list_students_in_class",
            description="Liệt kê danh sách tên của tất cả học sinh trong một lớp học cụ thể.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "class_name": {"type": "STRING", "description": "Tên lớp cần xem danh sách."}
                },
                "required": ["class_name"]
            }
        ),
        FunctionDeclaration(
            name="get_class_average_for_subject",
            description="Tính và lấy điểm trung bình của một môn học cụ thể cho cả một lớp. Dùng để so sánh điểm của một học sinh với trung bình lớp.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "class_name": {"type": "STRING", "description": "Tên lớp cần tính điểm trung bình."},
                    "subject_name": {"type": "STRING", "description": "Tên môn học cần tính điểm trung bình."}
                },
                "required": ["class_name", "subject_name"]
            }
        ),
        FunctionDeclaration(
            name="get_at_risk_subjects",
            description="Tìm và liệt kê các môn học của một học sinh đang có điểm dưới một ngưỡng nhất định (mặc định là 6.5), để đưa ra cảnh báo.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần kiểm tra."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."},
                    "threshold": {"type": "NUMBER", "description": "Ngưỡng điểm để cảnh báo, mặc định là 6.5."}
                },
                "required": ["student_name"]
            }
        ),
        FunctionDeclaration(
            name="analyze_subject_strengths_by_group",
            description="Phân tích xem một học sinh có thế mạnh về nhóm môn Khoa học Tự nhiên (Toán, KHTN) hay Khoa học Xã hội (Văn, Sử-Địa, GDCD).",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "student_name": {"type": "STRING", "description": "Tên học sinh cần phân tích."},
                    "class_name": {"type": "STRING", "description": "Tên lớp của học sinh (tùy chọn)."}
                },
                "required": ["student_name"]
            }
        ),
    ]
)

# --- Ánh xạ tên hàm sang đối tượng hàm Python ---
available_functions = {
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
}

# --- CHỈ DẪN HỆ THỐNG CHO GEMINI ---
SYSTEM_INSTRUCTION = """
Bạn là một chatbot Cố vấn học tập chuyên nghiệp và thân thiện. Nhiệm vụ chính của bạn là trả lời các câu hỏi của phụ huynh về tình hình học tập của học sinh bằng cách sử dụng các công cụ (functions) đã được cung cấp.
1. Luôn ưu tiên sử dụng các công cụ khi câu hỏi liên quan đến việc tra cứu thông tin học sinh (điểm số, hạnh kiểm, xếp hạng...).
2. Khi một công cụ trả về trạng thái 'ambiguous', hãy sử dụng thông tin trong mục 'options' để hỏi lại phụ huynh một cách lịch sự nhằm làm rõ họ muốn xem thông tin của học sinh nào.
3. Khi một công cụ trả về trạng thái 'not_found', hãy thông báo cho phụ huynh rằng không tìm thấy thông tin một cách nhẹ nhàng.
4. Sau khi nhận được dữ liệu từ công cụ, hãy diễn giải và trình bày thông tin đó cho phụ huynh một cách rõ ràng, đầy đủ và dễ hiểu, không chỉ đơn thuần là liệt kê dữ liệu thô.
5. Nếu câu hỏi của phụ huynh không liên quan đến việc tra cứu, hãy trò chuyện một cách tự nhiên trong vai trò một cố vấn.
"""

# --- Khởi tạo Model ---
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    tools=[tools],
    system_instruction=SYSTEM_INSTRUCTION
)

def answer_question(question: str, history_chat: list) -> str:
    """
    Gửi câu hỏi tới model, xử lý chuỗi function call nếu có, và trả về câu trả lời cuối cùng.
    """
    chat = model.start_chat(history=history_chat)
    response = chat.send_message(question)

    try:
        # Lấy phần nội dung đầu tiên từ phản hồi của model
        part = response.candidates[0].content.parts[0]
        
        # Vòng lặp này sẽ chạy một cách an toàn miễn là model yêu cầu gọi hàm
        while hasattr(part, 'function_call') and part.function_call.name:
            function_call = part.function_call
            function_name = function_call.name
            
            if function_name not in available_functions:
                return f"Lỗi: Model muốn gọi một hàm không xác định: {function_name}"
            
            # Lấy hàm và các tham số
            function_to_call = available_functions[function_name]
            args = {key: value for key, value in function_call.args.items()}
            
            # print(f"🤖 (Bước trung gian) LLM gọi hàm: {function_name}({args})")
            
            # Gọi hàm Python và lấy kết quả
            tool_result = function_to_call(**args)
            
            # Gửi kết quả của hàm về cho model để nó quyết định bước tiếp theo
            response = chat.send_message(
                Part(function_response={"name": function_name, "response": tool_result})
            )
            # Cập nhật 'part' với phản hồi mới nhất từ model cho vòng lặp tiếp theo
            part = response.candidates[0].content.parts[0]

        # Sau khi vòng lặp kết thúc (không còn function_call), lấy câu trả lời cuối cùng
        final_answer = part.text

    except (IndexError, ValueError):
        final_answer = response.text

    history_chat.append({"role": "user", "parts": [question]})
    history_chat.append({"role": "model", "parts": [final_answer]})
    return final_answer.strip()

# --- Chạy thử ---
if __name__ == "__main__":
    print("🤖 Chatbot Cố vấn học tập đã sẵn sàng! (sử dụng Function Calling)")
    history_chat = [
        {"role": "user", "parts": ["Xin chào, bạn là ai?"]},
        {"role": "model", "parts": ["Xin chào! Tôi là Cố vấn học tập ảo, tôi có thể giúp bạn tra cứu thông tin về tình hình học tập của các em học sinh."]}
    ]
    
    while True:
        question = input("Phụ huynh: ")
        if question.lower() in ["exit", "quit", "thoát"]:
            break
        start_time = time.time()
        answer = answer_question(question, history_chat)
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"👩‍🏫 Cố vấn: {answer}")
        print(f"⏱️  Thời gian phản hồi: {elapsed:.2f} giây\n")