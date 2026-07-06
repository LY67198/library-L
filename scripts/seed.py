"""种子数据：通过 ORM 初始化楼层、区域、座位"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config.settings import get_settings
from models import Floor, Seat, Zone
from models.seat import SeatStatus
from models.zone import ZoneType


async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        # 清空已有数据（注意外键顺序）
        await db.execute(delete(Seat))
        await db.execute(delete(Zone))
        await db.execute(delete(Floor))
        await db.commit()

        # 楼层
        f1 = Floor(name="1F", sort_order=1)
        f2 = Floor(name="2F", sort_order=2)
        db.add_all([f1, f2])
        await db.flush()

        # 区域
        z1 = Zone(floor_id=f1.id, name="自习区", zone_type=ZoneType.open, sort_order=1)
        z2 = Zone(floor_id=f2.id, name="阅览区", zone_type=ZoneType.open, sort_order=1)
        z3 = Zone(floor_id=f2.id, name="电子阅览室", zone_type=ZoneType.electronic, sort_order=2)
        db.add_all([z1, z2, z3])
        await db.flush()

        # 座位
        seats = []
        for i in range(1, 13):
            seats.append(Seat(zone_id=z1.id, seat_number=f"A{i:02d}"))
        for i in range(1, 9):
            seats.append(Seat(zone_id=z2.id, seat_number=f"B{i:02d}"))
        for i in range(1, 7):
            status = SeatStatus.disabled if i == 3 else SeatStatus.available
            seats.append(Seat(zone_id=z3.id, seat_number=f"C{i:02d}", status=status))
        db.add_all(seats)
        await db.commit()

    # 验证
    async with factory() as db:
        floor_count = (await db.execute(select(Floor))).scalars().all()
        zone_count = (await db.execute(select(Zone))).scalars().all()
        seat_count = (await db.execute(select(Seat))).scalars().all()
        print(f"已插入: {len(floor_count)} 楼层, {len(zone_count)} 区域, {len(seat_count)} 座位")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
