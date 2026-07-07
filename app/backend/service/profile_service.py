"""读者画像查询服务"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import User, Appointment, BorrowRecord, Seat, Zone
from models.appointment import AppointmentStatus
from models.borrow_record import BorrowStatus


class ProfileService:
    """查询用户个人信息、当前预约、借阅记录"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_profile(self, user_id: str, profile_type: str) -> dict:
        """返回 {user, appointments, borrow_records}

        profile_type:
          - "personal_info": 仅返回用户信息
          - "borrowing_history": 返回用户信息 + 借阅记录
          - "all": 返回全部（用户信息 + 预约 + 借阅记录）
        """
        # 查询用户
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        appointments = []
        borrow_records = []

        if profile_type == "all":
            # 查询当前有效预约
            if user:
                appt_result = await self._db.execute(
                    select(Appointment)
                    .where(
                        Appointment.user_id == user_id,
                        Appointment.status.in_([
                            AppointmentStatus.booked,
                            AppointmentStatus.checked_in,
                        ]),
                    )
                    .order_by(Appointment.created_at.desc())
                    .options(selectinload(Appointment.seat).selectinload(Seat.zone).selectinload(Zone.floor))
                )
                appointments = list(appt_result.scalars().all())

        if profile_type in ("borrowing_history", "all"):
            # 查询借阅记录
            if user:
                br_result = await self._db.execute(
                    select(BorrowRecord)
                    .where(BorrowRecord.user_id == user_id)
                    .order_by(BorrowRecord.borrowed_at.desc())
                    .options(selectinload(BorrowRecord.book))
                )
                borrow_records = list(br_result.scalars().all())

        return {
            "user": user,
            "appointments": appointments,
            "borrow_records": borrow_records,
        }
