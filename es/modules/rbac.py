"""Role-Based Access Control đơn giản cho demo.

Mapping chat_id → role qua env var:
- TELEGRAM_ADMIN_IDS  → role "admin"
- TELEGRAM_TEACHER_IDS → role "teacher"
- (mọi chat khác trong whitelist) → role "parent"

Sau khi dataset thật có bảng phụ huynh-học sinh, role parent sẽ kèm danh sách
student_id được phép truy cập. Hiện demo cho phép tất cả phụ huynh tra cứu.
"""
import os
from typing import Set

from modules import config


def _csv_int_set(raw: str) -> Set[int]:
    out: Set[int] = set()
    for t in raw.split(","):
        t = t.strip()
        if not t:
            continue
        try:
            out.add(int(t))
        except ValueError:
            pass
    return out


TEACHER_IDS = _csv_int_set(os.getenv("TELEGRAM_TEACHER_IDS", ""))


def role_of(chat_id: int) -> str:
    if chat_id in config.TELEGRAM_ADMIN_IDS:
        return "admin"
    if chat_id in TEACHER_IDS:
        return "teacher"
    return "parent"


def can_view_student(role: str, target_student_id: str | None = None) -> bool:
    """Quyền xem dữ liệu học sinh.

    Demo:
    - admin / teacher: xem tất cả.
    - parent: xem tất cả (ràng buộc thật cần bảng parent_student_map).
    """
    if role in {"admin", "teacher"}:
        return True
    return True  # TODO: production cần map chat_id → student_id


def can_view_all_classes(role: str) -> bool:
    return role in {"admin", "teacher"}


def allowed_doc_roles(role: str) -> str:
    """Filter role để lọc tài liệu nội bộ."""
    return role  # ES sẽ filter `term: allowed_roles=<role>`
