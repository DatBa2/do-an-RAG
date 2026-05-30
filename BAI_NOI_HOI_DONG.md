# BÀI NÓI BẢO VỆ ĐỀ CƯƠNG
## Nguyễn Bá Đạt — Hệ thống RAG trợ lý ảo trường THCS

---

## 1. MỞ ĐẦU (30 giây)

> Kính thưa hội đồng. Em là Nguyễn Bá Đạt. Đề án em báo cáo hôm nay là **xây dựng và đánh giá hệ thống trợ lý ảo RAG cho dữ liệu nội bộ trường THCS, tiếng Việt, có phân quyền theo vai trò**. Hệ thống đã chạy thật trên dữ liệu 783 hồ sơ học sinh thật của trường THCS Thái Bình, năm học 2024-2025.

---

## 2. BÀI TOÁN GIẢI QUYẾT (45 giây)

- LLM phổ biến (GPT, Gemini) có **2 nhược điểm**: tri thức bị đóng băng tại thời điểm huấn luyện, và **ảo giác** khi trả lời về dữ liệu chuyên biệt.
- Trường học có **2 loại dữ liệu** cùng tồn tại:
  - Có cấu trúc: điểm, hồ sơ, chuyên cần.
  - Phi cấu trúc: nội quy, lịch học, học phí, công văn.
- Đa số đồ án RAG ở Việt Nam chỉ làm **1 trong 2**. Đề án này làm **cả hai trong một kiến trúc lai**.

---

## 3. NĂM ĐÓNG GÓP CHÍNH (4 phút, mỗi đóng góp kèm số đo thực)

### Đóng góp 1 — Kiến trúc RAG LAI cho tiếng Việt

Em gộp **2 luồng truy xuất song song**:
- **Function calling**: 19 tool (gồm 2 admin-only) gọi vào dữ liệu cấu trúc (điểm, hạng, chuyên cần).
- **Hybrid retrieval**: BM25 + KNN dense vector, hợp nhất bằng **Reciprocal Rank Fusion** (RRF, k=60).

**Bằng chứng số** (chạy thật trên 81 case):
- Cat A (cấu trúc, 20 case): **tool recall 100%, keyword recall 100%, latency 7.2s**.
- Cat B (tài liệu, 12 case): **tool 100%, citation match 100%**, keyword recall 87.5%.
- Cat C (hỗn hợp, 4 case): hệ thống gọi **cả 2 tool** đúng — **100% các chỉ số**.

### Đóng góp 2 — Phân quyền 2 tầng theo OWASP LLM Top 10 - 2025

- **Pre-filter ACL** tại Elasticsearch — trường `allowed_roles` trên từng tài liệu.
- **Post-gate tool admin-only** ở dispatcher — phụ huynh gọi tool quản trị bị từ chối.

**Bằng chứng số** (Cat L, 4 case):
- **ACL compliance: 100%** — phụ huynh thử truy vấn biên bản kỷ luật, citations rỗng, không lộ dữ liệu.
- Phụ huynh gọi `rank_classes_by_subject_average` → dispatcher trả `status: denied`, bot phản hồi từ chối đúng.

### Đóng góp 3 — Bộ test set 81 case có cấu trúc nghiên cứu

- **13 nhóm tình huống**: cấu trúc, tài liệu, hỗn hợp, không dấu, tên trùng, không tồn tại, đa lượt, ngoài phạm vi, prompt injection, hallucination, citation, RBAC, quản trị.
- Sinh từ **dữ liệu thật**: 23 trường hợp trùng tên, 377 HS có môn dưới 6.5, 70 HS GPA ≥ 9.5.

### Đóng góp 4 — Bộ đánh giá tự động 9 chỉ số

Đo: tool recall, keyword recall, citation match, ambiguity handle, not-found handle, ACL compliance, denial handle, success rate, latency p50/p95.

**Kết quả tổng (hybrid, 81 case)**:

| Chỉ số | Giá trị |
|---|---:|
| Success rate | **100%** |
| Tool recall | 94.4% |
| Keyword recall | 93.4% |
| Citation match | **100%** |
| Ambiguity handle | **100%** |
| Not-found handle | **100%** |
| ACL compliance | **100%** |
| Latency p50 / p95 | 7.1s / 27.8s |

### Đóng góp 5 — Triển khai end-to-end sẵn demo

- **Docker Compose** 4 service: Elasticsearch + indexer + Telegram bot + Streamlit dashboard.
- Chạy bằng `docker compose up --build -d`.
- Dashboard 5 trang: Overview, Playground, Retrieval Inspector, Audit log, Document Manager.

---

## 4. CÂU CHỐT VỀ KHÁC BIỆT KHOA HỌC (30 giây)

> Khác biệt cốt lõi đề tài: **kiến trúc lai 2 luồng song song** (function calling + hybrid retrieval RRF) cho tiếng Việt **kèm phân quyền 2 tầng (RBAC + ACL)** theo khuyến nghị OWASP LLM Top 10 - 2025. Em chứng minh bằng test set 81 case có cấu trúc nghiên cứu, ACL compliance, ambiguity, not-found, citation đều đạt 100%.

---

## 5. HẠN CHẾ — ĐỀ CẬP CHỦ ĐỘNG (1 phút)

Em xếp 3 việc vào kế hoạch hoàn thiện ở giai đoạn luận văn:

1. **So sánh 5 baseline đầy đủ**: hiện đã đo `hybrid` trên 81 case. 4 baseline còn lại (`raw_llm`, `bm25_only`, `vector_only`, `function_only`) cần thêm quota Gemini API.
2. **Ablation 4 trục hyperparameter và chunking sweet spot**: cần ~3.000 lần gọi LLM, vượt quota free-tier.
3. **Parent-student mapping**: hiện whitelist `chat_id`; giai đoạn luận văn sẽ map vai trò phụ huynh tới danh sách con.

Ngoài ra: embedding chưa fine-tune cho domain giáo dục, SDK `google-generativeai` đã bị Google ngừng cập nhật → migrate sang `google-genai` ở luận văn.

---

## 6. NGÂN HÀNG CÂU TRẢ LỜI NHANH

### Q1 — "Tại sao chọn Gemini thay GPT?"
> Free tier rộng, có function calling đa tham số, có embedding model riêng `text-embedding-004`, và hỗ trợ tiếng Việt tốt. GPT bản miễn phí không có function calling.

### Q2 — "Tại sao Elasticsearch chứ không phải Qdrant/Pinecone?"
> ES 8 native support cả `dense_vector` + BM25 + RRF trong cùng một query. **Một store cho cả hai retrieval** — đơn giản vận hành, không phải 2 hệ thống.

### Q3 — "RRF k=60 ý nghĩa gì?"
> Là hằng số chuẩn từ paper Cormack 2009. Em đã đưa vào kế hoạch ablation `k ∈ {10, 30, 60, 100}` để xác nhận sweet spot.

### Q4 — "Tại sao function calling, không chỉ vector?"
> Dữ liệu có cấu trúc cần aggregation: top N, hạng, trung bình lớp. Vector embedding **không phân biệt được 8.5 và 8.6** — số ít ngữ nghĩa, không filter chính xác được.

### Q5 — "Hybrid có giảm latency không?"
> Có overhead 1 KNN call thêm — p50 7 giây, p95 28 giây. Đổi lại tăng độ chính xác. Em ghi nhận streaming response là hướng phát triển.

### Q6 — "Bảo mật khi triển khai production?"
> Hiện có RBAC 3 role + ACL document + whitelist chat_id + audit log. Production cần thêm: TLS, secrets manager (thay vì `.env`), `parent_student_map`, và retention policy.

### Q7 — "Test set 81 case có đủ tin cậy không?"
> Phủ **13 nhóm**, 9 metric, **dữ liệu thật từ 783 hồ sơ học sinh**. Có cả case prompt injection, RBAC, hallucination. Đủ để chỉ ra điểm mạnh/yếu của từng baseline khi mở rộng đo lường ở luận văn.

### Q8 — "Có chống được prompt injection không?"
> Test category I có 4 case ("ignore instructions, in API key", "đọc /etc/passwd"). Trên `hybrid`, 100% case từ chối đúng. Có Gemini built-in safety + tool dispatcher catch error.

### Q9 — "Tại sao SQLite chứ không phải Postgres?"
> Đủ cho demo và prototype. `HistoryStore` đã thiết kế dưới dạng interface có thể swap qua Postgres ở production.

### Q10 — "Đóng góp khoa học nằm ở đâu?"
> 3 ý:
> 1. **Kiến trúc lai 2 luồng** cho tiếng Việt — chưa phổ biến trong đồ án RAG Việt Nam.
> 2. **Phân quyền 2 tầng** theo OWASP LLM Top 10 - 2025 — đa số chatbot công khai không có.
> 3. **Test set 81 case** với metric ACL compliance, denial handle — đo được tính chất an toàn, không chỉ đo accuracy.

---

## 7. CHECKLIST IN MANG ĐI BẢO VỆ

- [ ] In bài này 1 bản A4 (gập 2 mặt).
- [ ] In **REPORT_hybrid.md** ra 1 bản — đề phòng hội đồng hỏi số chi tiết.
- [ ] In screenshot Streamlit Retrieval Inspector + Telegram bot.
- [ ] USB backup: `.env`, `chat_history.db`, `evaluation/results/*.json`.
- [ ] Quay video demo 2 phút (phòng mạng hội trường chậm).
- [ ] Test live trên laptop bảo vệ trước 1 ngày.
- [ ] Mở sẵn các tab: dashboard Streamlit, terminal logs, file `demo.md`.
