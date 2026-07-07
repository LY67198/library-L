"""数据模型层"""

from .appointment import Appointment, AppointmentStatus
from .base import Base, new_uuid, utcnow
from .book import Book
from .borrow_record import BorrowRecord, BorrowStatus
from .document import DocSourceType, Document
from .floor import Floor
from .seat import Seat, SeatStatus
from .seat_time_slot import SeatTimeSlot, TimeSlot
from .user import User
from .zone import Zone, ZoneType

__all__ = [
    "Base",
    "new_uuid",
    "utcnow",
    "User",
    "Book",
    "BorrowRecord",
    "BorrowStatus",
    "Document",
    "DocSourceType",
    "Floor",
    "Zone",
    "ZoneType",
    "Seat",
    "SeatStatus",
    "SeatTimeSlot",
    "TimeSlot",
    "Appointment",
    "AppointmentStatus",
]
