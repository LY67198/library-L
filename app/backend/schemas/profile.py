"""读者画像相关 Pydantic 模型"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.seat import AppointmentItem


class UserInfo(BaseModel):
    display_name: str
    student_id: str
    username: str


class BorrowRecordItem(BaseModel):
    id: str
    book_title: str
    borrowed_at: str
    due_at: str
    returned_at: str | None
    status: str


class ProfileResponse(BaseModel):
    user: UserInfo | None
    appointments: list[AppointmentItem]
    borrow_records: list[BorrowRecordItem]
