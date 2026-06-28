"""业务枚举类型 — 定义用户/图书/座位/预约/租户状态等域枚举,值使用英文以保证序列化稳定。"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """用户角色:学生、教职工、馆员、管理员。"""

    student = "student"
    faculty = "faculty"
    librarian = "librarian"
    admin = "admin"


class UserStatus(str, enum.Enum):
    """用户账号状态:正常、已停用、已毕业。"""

    active = "active"
    suspended = "suspended"
    graduated = "graduated"


class BookStatus(str, enum.Enum):
    """图书状态:在馆、借出、已被预约、丢失。"""

    available = "available"
    borrowed = "borrowed"
    reserved = "reserved"
    lost = "lost"


class SeatStatus(str, enum.Enum):
    """座位状态:空闲、占用、维护中、停用。"""

    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"
    disabled = "disabled"


class SeatZone(str, enum.Enum):
    """座位所在分区:静音区、小组区、个人区、电脑区。"""

    silent = "silent"
    group = "group"
    individual = "individual"
    computer = "computer"


class AppointmentStatus(str, enum.Enum):
    """预约生命周期状态:待确认、已确认、进行中、已完成、已取消、已过期。"""

    pending = "pending"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


class AppointmentResource(str, enum.Enum):
    """预约资源类型:座位、图书、研讨间。"""

    seat = "seat"
    book = "book"
    room = "room"


class TenantStatus(str, enum.Enum):
    """租户(机构)状态:正常、已停用。"""

    active = "active"
    suspended = "suspended"
