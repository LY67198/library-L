"""读者画像 REST 接口"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.profile import (
    BorrowRecordItem,
    ProfileResponse,
    UserInfo,
)
from backend.service.profile_service import ProfileService
from core.database import get_db
from core.deps import get_required_user
from models import User

router = APIRouter(tags=["profile"])


@router.get("/api/v1/profile", response_model=ProfileResponse)
async def get_profile(
    type: str = Query(default="all", pattern="^(all|personal_info|borrowing_history)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_required_user),
):
    service = ProfileService(db)
    data = await service.get_profile(user.id, type)

    user_info = None
    if data["user"] is not None:
        u = data["user"]
        user_info = UserInfo(
            display_name=u.display_name,
            student_id=u.student_id,
            username=u.username,
        )

    from backend.schemas.seat import AppointmentItem

    appointments = [
        AppointmentItem(
            appointment_id=a.id,
            seat_id=a.seat_id,
            floor_name=a.seat.zone.floor.name if a.seat else "",
            zone_name=a.seat.zone.name if a.seat else "",
            seat_number=a.seat.seat_number if a.seat else "",
            date=a.date.isoformat(),
            slot=a.slot.value if hasattr(a.slot, "value") else str(a.slot),
            status=a.status.value if hasattr(a.status, "value") else str(a.status),
        )
        for a in data["appointments"]
    ]

    borrow_records = [
        BorrowRecordItem(
            id=r.id,
            book_title=r.book.title if r.book else "",
            borrowed_at=r.borrowed_at.isoformat() if r.borrowed_at else "",
            due_at=r.due_at.isoformat() if r.due_at else "",
            returned_at=r.returned_at.isoformat() if r.returned_at else None,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in data["borrow_records"]
    ]

    return ProfileResponse(
        user=user_info,
        appointments=appointments,
        borrow_records=borrow_records,
    )
