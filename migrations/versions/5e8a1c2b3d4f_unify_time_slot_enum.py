"""统一 time_slot_enum — 合并 appointment_slot_enum → time_slot_enum

Revision ID: 5e8a1c2b3d4f
Revises: d11085afd4d2
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e8a1c2b3d4f"
down_revision: Union[str, None] = "d11085afd4d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """appointments.slot 改用 time_slot_enum，删除 appointment_slot_enum"""
    op.execute(
        "ALTER TABLE appointments ALTER COLUMN slot TYPE time_slot_enum USING slot::text::time_slot_enum"
    )
    op.execute("DROP TYPE appointment_slot_enum")


def downgrade() -> None:
    """恢复 appointment_slot_enum，回退 column type"""
    op.execute("CREATE TYPE appointment_slot_enum AS ENUM ('morning', 'afternoon', 'evening')")
    op.execute(
        "ALTER TABLE appointments ALTER COLUMN slot TYPE appointment_slot_enum USING slot::text::appointment_slot_enum"
    )
