from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    student = "student"
    faculty = "faculty"
    librarian = "librarian"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    graduated = "graduated"


class BookStatus(str, enum.Enum):
    available = "available"
    borrowed = "borrowed"
    reserved = "reserved"
    lost = "lost"


class SeatStatus(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"
    disabled = "disabled"


class SeatZone(str, enum.Enum):
    silent = "silent"
    group = "group"
    individual = "individual"
    computer = "computer"


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


class AppointmentResource(str, enum.Enum):
    seat = "seat"
    book = "book"
    room = "room"


class TenantStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
