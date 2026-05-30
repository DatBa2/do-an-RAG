"""Query rewriting để tăng chất lượng retrieval.

Trước khi gọi vector search, dùng LLM viết lại câu hỏi để:
- Bổ sung context từ turn trước ("điểm em nó" → "điểm Toán của Lê Nguyễn Minh Trí lớp 7A10")
- Mở rộng câu hỏi mơ hồ thành câu hỏi tìm kiếm rõ ràng
- Diễn đạt lại theo ngữ vựng văn bản (từ "nó" → tên đầy đủ, "vắng học" → "nghỉ học")

Để rẻ và nhanh, dùng cùng model Gemini nhưng tắt tool, prompt ngắn.
"""
import logging
from typing import List, Optional

import google.generativeai as genai

from modules import config

log = logging.getLogger("query_rewrite")

REWRITE_INSTRUCTION = """\
Bạn là bộ viết lại câu hỏi cho hệ thống tìm kiếm tài liệu.
Dựa vào câu hỏi hiện tại và lịch sử hội thoại, viết lại thành 1 câu hỏi tìm kiếm rõ nghĩa,
có đầy đủ tên riêng và thực thể được nhắc tới. Không thêm thông tin mới.
KHÔNG giải thích, chỉ trả về câu đã viết lại trên 1 dòng.
"""

_rewriter: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    global _rewriter
    if _rewriter is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY chưa đặt.")
        genai.configure(api_key=config.GEMINI_API_KEY)
        _rewriter = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=REWRITE_INSTRUCTION,
        )
    return _rewriter


def rewrite_query(
    question: str,
    history: Optional[List[dict]] = None,
    max_history: int = 4,
) -> str:
    """Trả về câu hỏi đã viết lại. Fallback về câu gốc nếu lỗi."""
    history = history or []
    if not history:
        return question
    try:
        recent = history[-max_history * 2:]
        ctx = "\n".join(
            f"{turn.get('role','?')}: {turn.get('parts',[''])[0]}"
            for turn in recent
        )
        prompt = f"Lịch sử:\n{ctx}\n\nCâu hỏi hiện tại: {question}\n\nCâu đã viết lại:"
        model = _get_model()
        resp = model.generate_content(prompt)
        rewritten = (resp.text or "").strip().splitlines()[0] if resp.text else ""
        if not rewritten or len(rewritten) > 500:
            return question
        log.debug("Rewrite: %r → %r", question, rewritten)
        return rewritten
    except Exception as e:
        log.warning("Rewrite lỗi, dùng câu gốc: %s", e)
        return question
