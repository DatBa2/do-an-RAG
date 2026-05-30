# RAG School Advisor

**Đồ án tốt nghiệp** — Nghiên cứu và ứng dụng hệ thống RAG (Retrieval-Augmented Generation) làm trợ lý ảo AI cho tìm kiếm dữ liệu nội bộ.

Hệ thống cung cấp một chatbot tiếng Việt giúp phụ huynh / giáo viên / quản trị viên truy vấn:
- **Dữ liệu học sinh có cấu trúc**: điểm số, hạnh kiểm, chuyên cần, xếp hạng, xu hướng học tập.
- **Tài liệu nội bộ phi cấu trúc**: nội quy, quy định nghỉ học, lịch học, học phí, an toàn trường học…

Hệ thống minh hoạ **mô hình RAG lai (hybrid)**: kết hợp _function-calling_ trên dữ liệu có cấu trúc (Elasticsearch BM25 + filters + aggregations) với _vector retrieval_ trên tài liệu phi cấu trúc (Gemini embedding + KNN), gộp kết quả bằng **Reciprocal Rank Fusion**.

---

## Mục lục

1. [Kiến trúc](#kiến-trúc)
2. [Tính năng nổi bật](#tính-năng-nổi-bật)
3. [Stack công nghệ](#stack-công-nghệ)
4. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
5. [Khởi chạy nhanh (Docker)](#khởi-chạy-nhanh-docker)
6. [Khởi chạy thủ công](#khởi-chạy-thủ-công)
7. [Cấu hình `.env`](#cấu-hình-env)
8. [Cách sử dụng](#cách-sử-dụng)
9. [Bộ tool LLM (20 tool)](#bộ-tool-llm)
10. [Phân quyền RBAC](#phân-quyền-rbac)
11. [Chi tiết kỹ thuật](#chi-tiết-kỹ-thuật)
12. [Đánh giá thực nghiệm](#đánh-giá-thực-nghiệm)
13. [Bảo mật](#bảo-mật)
14. [Hạn chế và hướng phát triển](#hạn-chế-và-hướng-phát-triển)
15. [Tham khảo](#tham-khảo)

---

## Kiến trúc

```
                                 ┌────────────────────────┐
                                 │  Gemini 2.5 Flash      │
                                 │  (function calling)    │
   ┌────────────┐                ├────────────────────────┤
   │ Telegram   │────┐           │  Advisor orchestrator  │
   │ bot        │    │           │  - tool dispatcher     │
   └────────────┘    │           │  - query rewriting     │
                    ─┼──────────▶│  - self-RAG verify     │
   ┌────────────┐    │           │  - citation collector  │
   │ Streamlit  │────┤           └─────────┬──────────────┘
   │ chat UI    │    │                     │
   └────────────┘    │      ┌──────────────┼────────────────┐
                    ─┘      │              │                │
   ┌────────────┐           ▼              ▼                ▼
   │ Eval CLI   │──┘   17 tool      search_documents   verify
   └────────────┘      structured    (hybrid RRF)       (LLM)
                            │              │
                            ▼              ▼
                      ┌──────────────────────────┐
                      │  Elasticsearch 8.13      │
                      │  - hs_records (BM25)     │
                      │  - internal_docs         │
                      │    (BM25 + dense_vector) │
                      └──────────────────────────┘
                            ▲              ▲
                 ┌──────────┘              └──────────┐
            JSON học sinh                    MD / PDF tài liệu
            (es_index.py)                    (modules/ingest_docs.py)
```

Ba luồng xử lý chính:

1. **Câu hỏi về dữ liệu học sinh** → LLM gọi 1 trong 17 tool structured → query Elasticsearch index `hs_records` → trả lời có số liệu xác thực.
2. **Câu hỏi về chính sách / quy định** → LLM gọi `search_documents` → hybrid retrieval (BM25 + KNN, RRF fuse) trên index `internal_docs` → LLM tổng hợp + trích nguồn.
3. **Câu hỏi hỗn hợp** → LLM gọi cả hai loại tool trong cùng một lượt.

---

## Tính năng nổi bật

| Nhóm | Chi tiết |
|---|---|
| **Retrieval** | Hybrid BM25 + KNN trên cùng index ES, fuse bằng RRF (rank_constant = 60) |
| **Generation** | Gemini 2.5 Flash với 20 tool function-calling, system instruction tiếng Việt |
| **Quality** | Query rewriting để bổ sung context multi-turn; Self-RAG verify (tuỳ chọn) để kiểm tra grounding |
| **Citation** | Mỗi câu trả lời từ tài liệu kèm `Nguồn: <title> — <section> (<source_path>)` |
| **Security** | RBAC 3 vai trò (parent / teacher / admin), ACL cấp document, whitelist `chat_id` cho Telegram |
| **Observability** | Audit log SQLite (timestamp, chat_id, role, question, tools_called, answer, latency); embedding cache; lệnh `/stats` cho admin |
| **Evaluation** | Bộ test 81 case (13 nhóm) + bộ mini 17 case (test_set_mini.json); 5 baseline (raw / bm25 / vector / function / hybrid); metrics: tool recall, keyword recall, citation match, latency p50/p95 |
| **Deployment** | Docker Compose 4 service (Elasticsearch + indexer + bot + dashboard) khởi chạy bằng 1 lệnh |
| **Vietnamese NLP** | Analyzer `asciifolding` + accent stripping; từ điển synonyms môn học; prompt tiếng Việt |

---

## Stack công nghệ

- **Ngôn ngữ**: Python 3.10+
- **Vector & search store**: Elasticsearch 8.13.4 (BM25 + `dense_vector` cosine, native KNN)
- **LLM**: Google Gemini 2.5 Flash (function calling), Gemini Embedding `text-embedding-004` (768 chiều)
- **Front-end**: python-telegram-bot 21; Streamlit ≥ 1.30 (chat UI + admin dashboard)
- **Persistence**: SQLite (chat history, audit log, embedding cache)
- **Document parsing**: `pdfplumber` (PDF), parser markdown tự viết (đọc front-matter ACL)
- **Container**: Docker, docker-compose

---

## Cấu trúc thư mục

```
do-an-RAG/
├── README.md
├── .gitignore
└── es/
    ├── documents/                # 8 tài liệu nội bộ mẫu (.md)
    ├── organized_results/        # ~780 JSON dữ liệu học sinh
    ├── evaluation/
    │   ├── test_set.json         # 81 test case, 13 category nghiên cứu
    │   ├── test_set_mini.json    # 17 case (mỗi nhóm 1-2) — chạy nhanh / LLM local
    │   └── run_eval.py           # eval runner cho 5 baseline (hỗ trợ --testset)
    ├── modules/
    │   ├── config.py             # config tập trung + helper RBAC
    │   ├── es_school_qna.py      # 19 tool dữ liệu HS (gồm 2 admin-only)
    │   ├── doc_search.py         # hybrid retrieval (BM25 + KNN + RRF)
    │   ├── ingest_docs.py        # parse + chunk + embed + index tài liệu
    │   ├── embeddings.py         # Gemini embedding + SQLite cache
    │   ├── query_rewrite.py      # query rewriting (Gemini)
    │   ├── rbac.py               # role mapping từ chat_id
    │   ├── audit.py              # audit log SQLite
    │   └── synonyms.json         # từ điển môn học
    ├── es_index.py               # ETL JSON học sinh → ES
    ├── es_main.py                # class Advisor (orchestrator)
    ├── es_tele_bot.py            # Telegram bot
    ├── admin_dashboard.py        # Streamlit dashboard + chat UI
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    └── .env.example
```

---

## Khởi chạy nhanh (Docker)

Yêu cầu: Docker Desktop hoặc Docker Engine ≥ 20.10, có RAM cấp tối thiểu 2 GB cho Elasticsearch.

```bash
git clone <repo>
cd do-an-RAG/es

cp .env.example .env
# Mở .env, điền GEMINI_API_KEY và TELEGRAM_TOKEN

docker compose up --build -d
docker compose logs -f bot
```

Compose tự động chạy tuần tự:
1. Elasticsearch + healthcheck `green`/`yellow`.
2. **indexer** (one-shot): chạy `es_index.py` để index `hs_records` + `python -m modules.ingest_docs` để index `internal_docs`.
3. **bot**: Telegram bot polling.
4. **dashboard**: Streamlit ở http://localhost:8501

Sau khi bot khởi động, mở Telegram tìm bot, gõ `/start`. Nếu thấy thông báo "Chat ID chưa được cấp quyền", copy chat ID vào `TELEGRAM_ADMIN_IDS` trong `.env`, restart:

```bash
docker compose restart bot
```

---

## Khởi chạy thủ công

Phù hợp khi muốn debug từng phần.

```bash
cd es
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # điền GEMINI_API_KEY, TELEGRAM_TOKEN

# 1. Khởi động Elasticsearch (qua Docker)
docker compose up -d elasticsearch

# 2. Index dữ liệu
python es_index.py --full-refresh             # index học sinh
python -m modules.ingest_docs --recreate      # index tài liệu

# 3. Test CLI (không cần Telegram)
python es_main.py

# 4. Chạy bot Telegram
python es_tele_bot.py

# 5. Chạy dashboard Streamlit
streamlit run admin_dashboard.py
```

---

## Cấu hình `.env`

| Biến | Bắt buộc | Mặc định | Mô tả |
|---|:-:|---|---|
| `GEMINI_API_KEY` | ✅ | — | Lấy tại https://aistudio.google.com/apikey |
| `TELEGRAM_TOKEN` | ✅ | — | Tạo bot qua @BotFather |
| `TELEGRAM_ADMIN_IDS` | ✅* | — | Danh sách `chat_id` admin (csv) |
| `TELEGRAM_TEACHER_IDS` |  | — | Danh sách `chat_id` giáo viên (csv) |
| `TELEGRAM_ALLOWED_IDS` |  | — | Danh sách `chat_id` phụ huynh (csv) |
| `TELEGRAM_ALLOW_ALL` |  | `false` | Đặt `true` để demo công khai (bỏ whitelist) |
| `ES_HOST` |  | `http://localhost:9200` | Endpoint Elasticsearch |
| `ES_INDEX` |  | `hs_records` | Tên index học sinh |
| `BULK_BATCH_SIZE` |  | `1000` | Batch size khi index |
| `GEMINI_MODEL` |  | `gemini-2.5-flash` | Model Gemini dùng cho generation |
| `HISTORY_TURNS` |  | `20` | Số turn hội thoại được giữ |
| `LOG_LEVEL` |  | `INFO` | DEBUG / INFO / WARNING |

\* Hoặc bật `TELEGRAM_ALLOW_ALL=true` (không khuyến nghị với dữ liệu thật).

Cách lấy `chat_id`: thêm bot vào Telegram và gõ bất kỳ tin nhắn nào → bot phản hồi kèm chat ID, hoặc gõ `/whoami` để xem.

---

## Cách sử dụng

### Qua Telegram

| Lệnh | Mô tả |
|---|---|
| `/start` | Thông tin chào mừng + role hiện tại |
| `/help` | Danh sách lệnh + ví dụ câu hỏi |
| `/whoami` | Xem `chat_id`, `user_id`, role, trạng thái cấp quyền |
| `/clear` | Xoá lịch sử hội thoại của bạn |
| `/stats` | Audit stats (chỉ admin) |

Ví dụ câu hỏi:

```
Điểm Toán của Lê Nguyễn Minh Trí lớp 7A10 học kỳ 2
Top 5 học sinh lớp 7A10 học kỳ 2
Em Trí thế mạnh môn nào?
So sánh Trí với Nam lớp 7A10

Học sinh nghỉ học không phép quá 5 buổi bị xử lý thế nào?
Học phí lớp 7 năm 2024-2025 bao nhiêu?
Lịch kiểm tra cuối kỳ 2 khi nào?
Tiêu chí xếp loại Xuất sắc là gì?
```

### Qua Streamlit Dashboard

Mở http://localhost:8501. Có 5 trang:

- **Overview**: trạng thái ES, số documents, embedding cache, audit stats.
- **Playground** — chat multi-turn với bot, có sidebar chọn role / bật-tắt query rewriting / self-RAG verify, hiển thị tools chain, citations và rewritten query của mỗi lượt.
- **Retrieval Inspector**: so sánh trực tiếp 3 strategy `bm25` / `vector` / `hybrid` trên cùng câu hỏi, hiển thị hits và score.
- **Audit log**: filter theo `chat_id`, xem chi tiết từng query.
- **Documents**: liệt kê tài liệu, upload tài liệu mới và re-index trực tiếp từ giao diện.

---

## Bộ tool LLM

### 17 tool dữ liệu học sinh (structured)

| Tool | Tham số | Trả về |
|---|---|---|
| `get_student_overview` | student_name, [class_name, year, semester] | Tổng quan: học lực, hạnh kiểm, GPA, chuyên cần |
| `get_subject_score` | student_name, subject_name, [...] | Điểm TX / GK / CK / TK 1 môn |
| `get_all_subject_scores_for_student` | student_name, [...] | Bảng điểm tất cả môn 1 học kỳ |
| `get_attendance_details` | student_name, [...] | Phép / không phép / bỏ tiết |
| `get_student_strengths_and_weaknesses` | student_name, [...] | Môn TK cao nhất / thấp nhất |
| `get_student_rank` | student_name, class_name, [...] | Thứ hạng GPA trong lớp |
| `get_student_rank_by_subject` | student_name, class_name, subject_name | Thứ hạng 1 môn trong lớp |
| `get_top_n_students` | class_name, [n=5] | Top N GPA |
| `get_class_size` | class_name, [...] | Sĩ số lớp |
| `list_all_classes` | [year] | Danh sách lớp |
| `list_students_in_class` | class_name, [...] | Danh sách học sinh |
| `get_class_average_for_subject` | class_name, subject_name | Điểm TB môn cho cả lớp |
| `get_at_risk_subjects` | student_name, [threshold=6.5] | Môn có TK dưới ngưỡng |
| `analyze_subject_strengths_by_group` | student_name | So sánh nhóm tự nhiên vs xã hội |
| `list_available_semesters` | student_name | Các (năm, học kỳ) đã có dữ liệu |
| `get_score_trend` | student_name, [subject_name] | Xu hướng GPA hoặc điểm môn |
| `compare_students` | student_name_a, student_name_b | So sánh 2 học sinh |

### 2 tool quản trị (admin-only, gating qua RBAC)

| Tool | Tham số | Mô tả |
|---|---|---|
| `rank_classes_by_subject_average` | subject_name, [n, grade_level, year, semester] | Top N lớp theo điểm TB 1 môn |
| `find_students_with_criteria` | conduct, academic, grade_level, class_name, min_gpa, max_gpa, year, semester | Tìm HS theo bộ tiêu chí kết hợp |

Hai tool này **bị từ chối với role=parent** ngay tại dispatcher (`es_main.py:ADMIN_ONLY_TOOLS`) — căn cứ cho bằng chứng RBAC trong báo cáo.

### 1 tool tài liệu nội bộ (unstructured)

| Tool | Tham số | Cơ chế |
|---|---|---|
| `search_documents` | query, [k=5] | Hybrid retrieval BM25 + KNN với RRF, **tự động filter theo `allowed_roles` của caller** |

---

## Phân quyền RBAC

| Quyền | parent | teacher | admin |
|---|:-:|:-:|:-:|
| Tra cứu điểm học sinh | ✅ (sẽ cần parent_student_map) | ✅ | ✅ |
| Liệt kê / top lớp | ⚠ | ✅ | ✅ |
| Tài liệu nội bộ | ✅ (public docs) | ✅ | ✅ (all) |
| `/stats` (audit) | ❌ | ❌ | ✅ |

Mapping `chat_id` → role qua env:
- Có trong `TELEGRAM_ADMIN_IDS` → `admin`
- Có trong `TELEGRAM_TEACHER_IDS` → `teacher`
- Còn lại trong whitelist → `parent`

ACL tài liệu được khai báo qua front-matter trong file `.md`:

```markdown
---
title: Báo cáo nội bộ giáo viên
acl_roles: teacher,admin
---
...nội dung...
```

Tài liệu không có front-matter mặc định mở cho cả 3 role. Cấu trúc tài liệu hiện tại:

| File | ACL | Mục đích |
|---|---|---|
| `01_noi_quy_hoc_sinh.md` ... `08_thong_tin_lien_he.md` | parent, teacher, admin | Tài liệu công khai |
| `09_huong_dan_giao_vien.md` | teacher, admin | Hướng dẫn nội bộ cho GV |
| `10_bien_ban_hop_hoi_dong.md` | admin | Biên bản Hội đồng kỷ luật — nhạy cảm |

---

## Chi tiết kỹ thuật

### Hai Elasticsearch index

**`hs_records`** — dữ liệu học sinh. Mỗi học sinh / học kỳ có 1 doc `student` + nhiều doc `mark` (một / môn).

```
student::<student_id>::sem<n>::year<YYYY-YYYY>
mark::<student_id>::<subject>::sem<n>::year<YYYY-YYYY>
```

Mapping nổi bật:
- `full_name`, `class_name`, `subject`: text với analyzer `vn_text` (lowercase + asciifolding) + subfield `.raw` keyword normalizer.
- `student_id`, `year`, `conduct`, `academic`: keyword.
- `semester`: integer.
- `scores.TK`, `overall_gpa`: float.

**`internal_docs`** — chunk tài liệu nội bộ:

```python
{
  "doc_id": "02_quy_dinh_nghi_hoc",
  "chunk_id": "02_quy_dinh_nghi_hoc::chunk_003",
  "title": "Quy định nghỉ học và xin phép",
  "section": "4. Giới hạn nghỉ học",
  "source_path": "es/documents/02_quy_dinh_nghi_hoc.md",
  "content": "Nghỉ có phép không quá 10 buổi...",
  "content_tokens": 76,
  "allowed_roles": ["parent", "teacher", "admin"],
  "embedding": [768 chiều],
  "indexed_at": "2025-05-15T..."
}
```

### Chunking strategy

`modules/ingest_docs.py`:

1. **Parse front-matter** YAML-like cho metadata + ACL.
2. **Split theo heading** (`#` `##` `###` …): mỗi section trở thành 1 chunk tự nhiên.
3. Nếu section dài hơn `max_tokens = 320` thì cắt thành nhiều chunk bằng cách:
   - Tách câu theo dấu `.`, `!`, `?`, `\n`.
   - Đóng chunk khi vượt `max_tokens`.
   - Giữ `overlap_tokens = 64` từ cuối chunk trước sang đầu chunk sau để tránh đứt câu.
4. Token đếm xấp xỉ `len(words) / 0.75` (tiếng Việt).

Trên bộ tài liệu hiện tại, mỗi file sinh **5–8 chunk** với 33–121 token / chunk, mỗi chunk = đúng 1 section.

### Embedding + cache

`modules/embeddings.py`:

- Model: `models/text-embedding-004` (768 chiều).
- `task_type`: `retrieval_document` lúc index, `retrieval_query` lúc search — Gemini phân biệt để tăng chất lượng matching.
- Cache SQLite (`data/embed_cache.db`) keyed bằng `sha256(model | task | text)`. Re-ingest không tốn token API; chạy evaluation nhiều lần cũng nhanh hơn.

### Hybrid retrieval với RRF

`modules/doc_search.py`:

```
                            ┌──────────────┐
                  ┌────────▶│  BM25 hits   │──┐
   Câu hỏi ──────┤         └──────────────┘  │
                  │         ┌──────────────┐  ├─▶ RRF fuse ─▶ Top-K
                  └────────▶│  KNN hits    │──┘    score = Σ 1/(60+rank_i)
                            └──────────────┘
```

**Reciprocal Rank Fusion** (Cormack et al. 2009, công thức chuẩn `k = 60`):

```python
score(doc) = Σ_i  1 / (60 + rank_i(doc))
```

RRF không cần normalize score giữa hai hệ BM25/cosine — chỉ cần rank. Đây là lựa chọn an toàn và phổ biến cho hybrid search hiện đại.

Filter `allowed_roles` được áp dụng đồng thời ở cả BM25 và KNN branch để đảm bảo ACL.

### Query rewriting

`modules/query_rewrite.py`:

- Trước khi search vector, dùng Gemini viết lại câu hỏi mang theo context.
- Ví dụ: `"điểm em nó"` (sau khi đã hỏi về Trí) → `"điểm Toán của Lê Nguyễn Minh Trí lớp 7A10"`.
- Hint được gắn vào câu hỏi gốc (`Tóm tắt context để tìm kiếm: ...`) để LLM chính dùng khi cần.
- Fallback an toàn về câu gốc nếu lỗi API.

### Self-RAG verify (tuỳ chọn)

`Advisor._verify()`:

- Sau khi sinh câu trả lời cuối + có citations, gọi Gemini lần 2 với prompt verifier.
- Verifier so câu trả lời với evidence (chunk citations), trả `OK` hoặc `FAIL: <lý do>`.
- Nếu `FAIL`: append cảnh báo `⚠ Lưu ý: câu trả lời chưa được kiểm chứng đầy đủ`.
- Bật qua flag `AdvisorContext(verify=True)`. Mặc định tắt vì +1 round trip Gemini.

### Audit log

`modules/audit.py` ghi mọi query vào SQLite:

```sql
CREATE TABLE audit (
  id INTEGER PRIMARY KEY,
  ts REAL,
  chat_id INTEGER,
  role TEXT,
  question TEXT,
  tools_called TEXT,  -- JSON
  answer TEXT,
  latency_ms INTEGER,
  success INTEGER
);
```

Dùng cho dashboard, `/stats`, và phân tích sử dụng. Trong production có thể chuyển sang Postgres / OpenSearch.

---

## Đánh giá thực nghiệm

Đồ án xây dựng bộ test set v2 dựa **trên dữ liệu thật của trường** (783 file JSON, 32 lớp khối 6-9, 23 trường hợp trùng tên giữa các lớp) cùng 8 tài liệu nội bộ được tạo từ thực tế Trường THCS Thái Bình. Mục tiêu là cung cấp bằng chứng định lượng đủ chiều để bảo vệ luận văn.

### Test set v2.1

`evaluation/test_set.json` — **81 test case chia 13 category nghiên cứu**, hỗ trợ `role` per-case để kiểm thử RBAC:

| Cat | Tên | n | Mục tiêu kiểm thử |
|---|---|---:|---|
| A | structured | 20 | Mỗi tool dữ liệu HS được kích hoạt đúng ít nhất 1 lần |
| B | docs | 12 | Phủ cả 8 tài liệu công khai, ít nhất 1 câu / tài liệu |
| C | mixed | 4 | Câu hỏi cần kết hợp dữ liệu HS + quy định |
| D | robustness | 10 | Không dấu, viết tắt (KHTN, GDCD), synonym (Anh văn ↔ Ngoại ngữ, Văn ↔ Ngữ văn), casing, paraphrase |
| E | ambiguity | 4 | Tên trùng (Nguyễn Đăng Khôi 3 HS, Lê Minh Thái 3 HS) — kiểm tra logic dedupe `_find_unique_student_record` |
| F | not_found | 4 | HS không tồn tại, lớp không tồn tại, sai năm/lớp |
| G | multi-turn | 4 | 2-3 turn / case → kiểm tra query rewriting có thực sự giúp |
| H | out_of_scope | 4 | Thời tiết, toán cơ bản, ngoài giáo dục — bot phải không gọi tool, không bịa |
| I | security | 4 | Prompt injection, SQL injection, path traversal, leak token |
| J | hallucination | 4 | Câu hỏi data không có (môn Vật lý, năm 2030, học phí lớp 10) — bot phải nói không có |
| K | citation | 4 | Kiểm tra `expected_source` xuất hiện trong citations |
| **L** | **rbac** | **4** | **Tài liệu role-restricted (parent không xem được admin doc), tool admin-only (parent gọi bị từ chối)** |
| **M** | **admin** | **3** | **Use case quản trị thuần (tìm HS theo tiêu chí, xếp hạng lớp theo môn)** |

Mỗi case có schema giàu: `role`, `expected_tools[]`, `expected_keywords[]`, `expected_source`, `expected_denied_source`, `expected_status` (`ambiguous` / `not_found` / `denied`), `note`.

### Baselines (5 mode)

| Baseline | Mô tả |
|---|---|
| `raw_llm` | Gemini không có tool, không có context — chứng minh tác hại hallucination khi không retrieval |
| `bm25_only` | Chỉ BM25 trên tài liệu nội bộ + LLM tổng hợp |
| `vector_only` | Chỉ KNN trên embedding + LLM tổng hợp |
| `function_only` | Chỉ function-calling cho dữ liệu HS (bỏ `search_documents`) — đánh giá đóng góp của vector retrieval |
| `hybrid` | Hệ thống đầy đủ — kết hợp tất cả |

### Metrics (9 trục)

| Metric | Định nghĩa |
|---|---|
| **Tool recall** | % case có ít nhất 1 trong `expected_tools` được gọi (1.0 nếu không yêu cầu tool) |
| **Keyword recall** | % keyword kỳ vọng có trong câu trả lời (cho fuzzy correctness check) |
| **Citation match** | % case có `expected_source` trong danh sách citations |
| **Ambiguity handle** | Với case `expected_status=ambiguous`: bot có hỏi lại / liệt kê options không |
| **Not-found handle** | Với case `expected_status=not_found`: bot KHÔNG được trả về con số điểm bịa |
| **ACL compliance** | Với case có `expected_denied_source`: nguồn cấm KHÔNG được xuất hiện trong citations (đo độ kín của ACL) |
| **Denial handle** | Với case `expected_status=denied`: bot phải trả thông báo từ chối, không tự thử workaround |
| **Success rate** | % không bị error / tool loop overflow |
| **Latency** | avg / p50 / p95 (ms) — tính tổng tất cả turn với multi-turn |

### Ablation studies (research-grade)

Mỗi trục thay đổi 1 hyperparameter, các param khác giữ default — cho phép luận văn có bảng "ảnh hưởng của X đến Y".

| Trục | Giá trị | Lệnh |
|---|---|---|
| Retrieval `k` | 1, 3, 5, 10 | `python -m evaluation.run_ablation --axis k` |
| RRF constant `k` | 10, 30, 60, 100 | `python -m evaluation.run_ablation --axis rrf` |
| Query rewriting | on / off | `python -m evaluation.run_ablation --axis rewrite` |
| Self-RAG verify | on / off | `python -m evaluation.run_ablation --axis verify` |
| Chunk size × overlap | 8 cấu hình | `python -m evaluation.run_chunking_ablation` |

Chunking grid (re-index mỗi cấu hình, embedding cache hit lần sau):

| chunk_size | overlap |
|---:|---:|
| 128 | 0, 32 |
| 256 | 0, 64 |
| 320 | 64 (default) |
| 512 | 64, 128 |
| 1024 | 128 |

### Quy trình chạy đầy đủ

```bash
# 1. Baselines comparison (5 mode × 81 case)
python -m evaluation.run_eval --all --out evaluation/results/baselines.json

# (tuỳ chọn) chạy nhanh / thử LLM local: bộ mini 17 case phủ đủ 13 nhóm
python -m evaluation.run_eval --all --testset evaluation/test_set_mini.json --out evaluation/results/mini.json

# 2. Hyperparameter ablation (4 trục)
python -m evaluation.run_ablation --all --out evaluation/results/ablation.json

# 3. Chunking ablation (8 cấu hình — chậm hơn vì re-index)
python -m evaluation.run_chunking_ablation --out evaluation/results/chunking.json

# 4. Tổng hợp markdown report cho luận văn
python -m evaluation.gen_report \
  --baselines evaluation/results/baselines.json \
  --ablation evaluation/results/ablation.json \
  --chunking evaluation/results/chunking.json \
  --out evaluation/results/REPORT.md
```

Kết quả `REPORT.md` sẽ chứa 4 bảng có thể copy thẳng vào báo cáo:
- Bảng 1: So sánh 5 baseline + breakdown theo category + cross-mode comparison.
- Bảng 2: Ablation theo 4 trục hyperparameter.
- Bảng 3: Ablation chunking strategy.
- Bảng 4: Ví dụ định tính (raw_llm vs hybrid) cho 5 case đầu.

### Các tuỳ chọn khác

```bash
# Chạy 1 baseline cụ thể
python -m evaluation.run_eval --mode hybrid

# Filter theo category để debug nhanh
python -m evaluation.run_eval --all --category structured,docs --limit 10

# Bật self-RAG verify cho hybrid
python -m evaluation.run_eval --mode hybrid --verify

# Quick chunking ablation (chỉ 3 cấu hình)
python -m evaluation.run_chunking_ablation --quick
```

### Câu chuyện trình bày khi bảo vệ

Với bộ dữ liệu kết quả trên, luận văn có thể bám 5 luận điểm chính được chứng minh bằng số:

1. **RAG vs raw LLM**: bảng 1 cho thấy `hybrid` cao hơn `raw_llm` ở mọi metric, đặc biệt citation match và not-found handle.
2. **Hybrid vs single-strategy**: `hybrid` outperform cả `bm25_only` và `vector_only` ở docs category, chứng minh RRF có ích.
3. **Function-calling là cần thiết**: `function_only` đạt cao hơn `vector_only` cho structured category — vector RAG không phù hợp dữ liệu có cấu trúc.
4. **Tham số hybrid có sweet spot**: ablation `k` và `rrf_k` cho thấy không phải lớn hơn là tốt hơn.
5. **Chunking có trade-off**: ablation chunking cho thấy chunk quá nhỏ → mất context, quá lớn → noise → giảm precision.

---

## Bảo mật

- `.env` đã được đưa vào `.gitignore`. **Nếu lỡ commit token thật vào git, hãy rotate ngay** tại @BotFather (Telegram) và Google AI Studio (Gemini), rồi `git rm --cached .env`.
- Bot mặc định **chặn** mọi `chat_id` không có trong `TELEGRAM_ALLOWED_IDS / TELEGRAM_ADMIN_IDS / TELEGRAM_TEACHER_IDS`. Bật `TELEGRAM_ALLOW_ALL=true` chỉ cho demo nội bộ.
- ACL document được kiểm tra ở cả 2 nhánh BM25 và KNN qua `allowed_roles` filter — không có đường tắt.
- Elasticsearch trong `docker-compose.yml` chạy không TLS / không xác thực; phù hợp môi trường local. Triển khai thật cần bật `xpack.security.enabled=true`, cấu hình TLS và network isolation.
- Audit log lưu toàn bộ câu hỏi và câu trả lời — cân nhắc retention policy nếu nội dung nhạy cảm.

---

## Hạn chế và hướng phát triển

### Hạn chế hiện tại

- `parent` role chưa giới hạn chỉ xem dữ liệu của con mình (thiếu bảng `parent_student_map`).
- Chunking dạng heuristic; chưa thử các phương pháp semantic chunking nâng cao.
- `google-generativeai` SDK đã được Google thông báo ngừng cập nhật, cần di chuyển sang `google-genai` trong tương lai.
- Chưa hỗ trợ OCR; PDF scan sẽ trả về văn bản trống.
- Chưa có streaming response; người dùng phải đợi đến khi câu trả lời hoàn chỉnh.

### Hướng phát triển

- **OCR pipeline** với VietOCR / Tesseract cho học bạ scan và biên bản giấy.
- **Fine-tune embedding** tiếng Việt domain-specific (giáo dục) để cải thiện retrieval.
- **GraphRAG** mô hình hoá quan hệ học sinh ↔ lớp ↔ giáo viên ↔ tài liệu.
- **Migrate SDK**: `google-generativeai` → `google-genai` (Google đã thông báo ngừng hỗ trợ).
- **Streaming**: dùng `generate_content_async` để phản hồi từng phần.
- **Production hardening**: ES có TLS + auth, secrets manager, observability stack (Prometheus + Grafana), rate limiting.
- **Multi-modal**: nhận diện ảnh học bạ / kết quả thi.

---

## Tham khảo

Các kỹ thuật và mô hình đã áp dụng trong đồ án này dựa trên các công trình sau:

1. Lewis, P. et al. (2020). _Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks_. NeurIPS.
2. Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). _Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods_. SIGIR.
3. Asai, A. et al. (2023). _Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection_. arXiv:2310.11511.
4. Gao, Y. et al. (2024). _Retrieval-Augmented Generation for Large Language Models: A Survey_. arXiv:2312.10997.
5. Gemini Team, Google (2024). _Gemini: A Family of Highly Capable Multimodal Models_.
6. Bộ Giáo dục và Đào tạo (2021). Thông tư 22/2021/TT-BGDĐT về đánh giá học sinh THCS và THPT.
7. Elastic (2024). _Elasticsearch Guide — kNN search, dense_vector field, Reciprocal Rank Fusion_.

---

## License

Mã nguồn được phát triển cho mục đích đồ án tốt nghiệp. Dữ liệu học sinh trong thư mục `organized_results/` là dữ liệu mẫu phục vụ minh hoạ.
