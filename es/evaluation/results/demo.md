# Demo RAG Trợ lý ảo - 6 câu hỏi đại diện

Kết quả 6 câu demo đại diện (artifact từ lần chạy trước). Để chạy nhanh hiện tại dùng `evaluation/test_set_mini.json` qua `run_eval --testset`.


## A04 - Tra cứu điểm môn (function-calling)

- **Role**: `parent`
- **Đóng góp minh hoạ**: Function-calling cho dữ liệu có cấu trúc (UC01)
- **Latency**: 6067 ms
- **Tools called**: `['get_subject_score']`
- **Citations**: (không)

**Q**: Điểm Toán của Lê Nguyễn Minh Trí lớp 7A10 học kỳ 2

**A**:

> Chào bạn, dưới đây là kết quả học tập môn Toán của em Lê Nguyễn Minh Trí, học sinh lớp 7A10 trong học kỳ 2 năm học 2024-2025:

*   **Điểm thường xuyên (TX):** 8.75
*   **Điểm giữa kỳ (GK):** 7.3
*   **Điểm cuối kỳ (CK):** 9.0
*   **Điểm tổng kết (TK):** 8.5

Nếu cần hỗ trợ thêm bất kỳ thông tin nào khác về kết quả học tập của em, bạn vui lòng cho tôi biết nhé!


## B11 - Tra cứu tài liệu (hybrid BM25+KNN+RRF)

- **Role**: `parent`
- **Đóng góp minh hoạ**: Hybrid retrieval phi cấu trúc + citation (UC08)
- **Latency**: 17222 ms
- **Tools called**: `['search_documents']`
- **Citations**:
  - `documents/06_hoc_phi_dong_gop.md` - 1. Học phí
  - `documents/04_lich_hoc_lich_thi.md` - 2. Lịch kiểm tra giữa kỳ
  - `documents/04_lich_hoc_lich_thi.md` - 1. Thời gian năm học
  - `documents/06_hoc_phi_dong_gop.md` - 3. Miễn giảm học phí
  - `documents/08_thong_tin_lien_he.md` - 5. Đội ngũ giáo viên chủ nhiệm

**Q**: Học phí lớp 7 năm 2024-2025 là bao nhiêu một tháng?

**A**:

> Chào quý phụ huynh,

Về mức học phí dành cho học sinh cấp THCS (trong đó có lớp 7) trong năm học 2024-2025, thông tin cụ thể như sau:

*   **Mức học phí:** 70.000 đồng/tháng/học sinh (áp dụng từ tháng 09/2024).
*   **Hình thức đóng:** Đóng theo học kỳ (Học kỳ 1 đóng vào tháng 10/2024, học kỳ 2 đóng vào tháng 03/2025).

Ngoài ra, nhà trường cũng có các chính sách miễn, giảm học phí cho các trường hợp cụ thể:
*   **Miễn 100% học phí:** Dành cho con liệt sĩ, con thương binh, học sinh khuyết tật và học sinh thuộc hộ nghèo.
*   **Giảm 50% học phí:** Dành cho học sinh thuộc hộ cận nghèo.
*   **Lưu ý:** Hồ sơ miễn giảm cần được nộp tại Phòng Tài vụ trước ngày 15/09 hàng năm.

Nguồn: 06 Hoc Phi Dong Gop — 1. Học phí (documents/06_hoc_phi_dong_gop.md)
Nguồn: 06 Hoc Phi Dong Gop — 3. Miễn giảm học phí (documents/06_hoc_phi_dong_gop.md)


## C01 - Câu hỏi hỗn hợp (structured + docs)

- **Role**: `parent`
- **Đóng góp minh hoạ**: Kiến trúc lai: gọi cả function-calling và search_documents (UC09)
- **Latency**: 17922 ms
- **Tools called**: `['get_student_overview', 'search_documents']`
- **Citations**:
  - `documents/05_khen_thuong_ky_luat.md` - 1.1. Danh hiệu cuối học kỳ
  - `documents/05_khen_thuong_ky_luat.md` - 1.2. Mức thưởng
  - `documents/03_chuong_trinh_lop_7.md` - 7. Tài liệu tham khảo
  - `documents/01_noi_quy_hoc_sinh.md` - 5. Học tập
  - `documents/01_noi_quy_hoc_sinh.md` - 8. Hiệu lực

**Q**: Lê Nguyễn Minh Trí lớp 7A10 có đạt loại Xuất sắc theo quy định không?

**A**:

> Chào bạn, dựa trên dữ liệu học tập của em Lê Nguyễn Minh Trí (lớp 7A10, học kỳ 2 năm học 2024-2025), kết quả học tập của em như sau:

*   **Học lực:** Tốt
*   **Hạnh kiểm:** Tốt
*   **Điểm trung bình (GPA):** 8.8

Theo quy định của nhà trường, học sinh đạt danh hiệu **"Học sinh Xuất sắc"** cần đáp ứng các tiêu chí: học lực Tốt, hạnh kiểm Tốt và điểm trung bình các môn **từ 9.0 trở lên**.

Vì em Lê Nguyễn Minh Trí có điểm trung bình là 8.8 (chưa đạt ngưỡng 9.0), nên hiện tại em **chưa đạt danh hiệu Học sinh Xuất sắc** theo quy định này.

Nguồn: 05 Khen Thuong Ky Luat — 1.1. Danh hiệu cuối học kỳ (documents/05_khen_thuong_ky_luat.md)


## E01 - Tên trùng → hỏi lại (anti-hallucination)

- **Role**: `parent`
- **Đóng góp minh hoạ**: Dedupe ambiguity + UX hỏi lại (giảm hallucination)
- **Latency**: 12185 ms
- **Tools called**: `['get_all_subject_scores_for_student']`
- **Citations**: (không)

**Q**: Điểm tổng kết của Nguyễn Đăng Khôi học kỳ 2

**A**:

> Chào bạn, hiện tại hệ thống tìm thấy có 3 học sinh tên **Nguyễn Đăng Khôi** có dữ liệu điểm học kỳ 2 năm học 2024-2025. Để tôi có thể cung cấp chính xác thông tin bạn cần, vui lòng cho biết học sinh đó đang học lớp mấy trong các lớp sau:

*   **Nguyễn Đăng Khôi** (Lớp 6A9, Mã HS: 2405055502)
*   **Nguyễn Đăng Khôi** (Lớp 7A8, Mã HS: 2205987469)
*   **Nguyễn Đăng Khôi** (Lớp 7A2, Mã HS: 2207883574)

Rất mong nhận được phản hồi từ bạn.


## L03 - RBAC: phụ huynh gọi tool quản trị → từ chối

- **Role**: `parent`
- **Đóng góp minh hoạ**: RBAC gating tại dispatcher (tool ADMIN_ONLY)
- **Latency**: 4094 ms
- **Tools called**: `['rank_classes_by_subject_average']`
- **Citations**: (không)

**Q**: Top 5 lớp có điểm trung bình môn Toán cao nhất

**A**:

> Rất tiếc, tôi không thể cung cấp thông tin xếp hạng điểm trung bình các lớp vì đây là dữ liệu dành riêng cho giáo viên và quản trị nhà trường.

Nếu bạn là phụ huynh cần biết thông tin về kết quả học tập của con em mình, tôi rất sẵn lòng hỗ trợ. Bạn có thể cung cấp tên học sinh để tôi kiểm tra bảng điểm chi tiết hoặc thứ hạng cụ thể của học sinh đó trong lớp nhé.


## M02 - RBAC: admin gọi tool quản trị → cho phép

- **Role**: `admin`
- **Đóng góp minh hoạ**: Use case quản trị (UC11) - tool admin-only chạy thành công
- **Latency**: 2015 ms
- **Tools called**: `['rank_classes_by_subject_average']`
- **Citations**: (không)

**Q**: Top 5 lớp có điểm trung bình môn Toán cao nhất khối 7 học kỳ 2

**A**:

> Chào bạn, dưới đây là danh sách 5 lớp khối 7 có điểm trung bình môn Toán cao nhất trong học kỳ 2:

1. **Lớp 7a10**: 9.27 điểm
2. **Lớp 7a9**: 8.84 điểm
3. **Lớp 7a7**: 7.99 điểm
4. **Lớp 7a2**: 7.78 điểm
5. **Lớp 7a6**: 7.55 điểm

Hy vọng thông tin này hữu ích với bạn!
