"""种子数据：管理员用户 + 楼层/区域/座位 + 示例图书"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config.settings import get_settings
from core.security import hash_password
from models import Book, BorrowRecord, BorrowStatus, Floor, Seat, User, Zone
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
        await db.execute(delete(Book))
        await db.execute(delete(User))
        await db.commit()

        # 管理员用户
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="管理员",
            student_id="ADMIN001",
            is_admin=True,
        )
        db.add(admin)
        await db.commit()
        print(f"管理员用户: admin / admin123 (id={admin.id})")

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
        await db.flush()

        # 示例图书
        sample_books = [
            Book(title="三体", author="刘慈欣", isbn="9787536692930", publisher="重庆出版社",
                 publish_year=2008, category="科幻", location="I247.5", total=3, available=2),
            Book(title="数据结构与算法分析", author="Mark Allen Weiss", isbn="9787111539241",
                 publisher="机械工业出版社", publish_year=2016, category="计算机", location="TP311.12", total=2, available=2),
            Book(title="百年孤独", author="加西亚·马尔克斯", isbn="9787544253994",
                 publisher="南海出版公司", publish_year=2011, category="文学", location="I775.45", total=2, available=1),
            Book(title="深入理解计算机系统", author="Randal E. Bryant", isbn="9787111544937",
                 publisher="机械工业出版社", publish_year=2016, category="计算机", location="TP3", total=1, available=1),
            Book(title="红楼梦", author="曹雪芹", isbn="9787020002207",
                 publisher="人民文学出版社", publish_year=1996, category="文学", location="I242.4", total=4, available=3),
            Book(title="设计模式", author="Erich Gamma", isbn="9787111618331",
                 publisher="机械工业出版社", publish_year=2019, category="计算机", location="TP311.5", total=2, available=2),
            Book(title="平凡的世界", author="路遥", isbn="9787530212004",
                 publisher="北京十月文艺出版社", publish_year=2012, category="文学", location="I247.5", total=3, available=3),
            Book(title="人工智能", author="Stuart Russell", isbn="9787111631058",
                 publisher="机械工业出版社", publish_year=2020, category="计算机", location="TP18", total=1, available=1),
            Book(title="活着", author="余华", isbn="9787530215319",
                 publisher="北京十月文艺出版社", publish_year=2017, category="文学", location="I247.5", total=3, available=1),
            Book(title="算法导论", author="Thomas H. Cormen", isbn="9787111407010",
                 publisher="机械工业出版社", publish_year=2013, category="计算机", location="TP301.6", total=2, available=2),
            Book(title="围城", author="钱锺书", isbn="9787020024759",
                 publisher="人民文学出版社", publish_year=1991, category="文学", location="I246.5", total=2, available=2),
            Book(title="编译原理", author="Alfred V. Aho", isbn="9787111551218",
                 publisher="机械工业出版社", publish_year=2018, category="计算机", location="TP314", total=1, available=1),
            Book(title="小王子", author="圣埃克苏佩里", isbn="9787020042494",
                 publisher="人民文学出版社", publish_year=2003, category="文学", location="I565.88", total=2, available=2),
            Book(title="数据库系统概念", author="Abraham Silberschatz", isbn="9787111573524",
                 publisher="机械工业出版社", publish_year=2019, category="计算机", location="TP311.13", total=2, available=2),
            Book(title="白夜行", author="东野圭吾", isbn="9787544242516",
                 publisher="南海出版公司", publish_year=2008, category="推理", location="I313.45", total=2, available=1),
            Book(title="计算机网络", author="James F. Kurose", isbn="9787111599714",
                 publisher="机械工业出版社", publish_year=2019, category="计算机", location="TP393", total=3, available=3),
            Book(title="嫌疑人X的献身", author="东野圭吾", isbn="9787544241694",
                 publisher="南海出版公司", publish_year=2008, category="推理", location="I313.45", total=2, available=2),
            Book(title="操作系统概念", author="Abraham Silberschatz", isbn="9787111604367",
                 publisher="机械工业出版社", publish_year=2018, category="计算机", location="TP316", total=1, available=1),
            Book(title="时间简史", author="史蒂芬·霍金", isbn="9787535732309",
                 publisher="湖南科学技术出版社", publish_year=2001, category="科普", location="P159", total=2, available=2),
            Book(title="图解HTTP", author="上野宣", isbn="9787115351531",
                 publisher="人民邮电出版社", publish_year=2014, category="计算机", location="TN915.04", total=2, available=2),
        ]
        db.add_all(sample_books)
        await db.commit()

        # 借阅记录种子数据
        books = (await db.execute(select(Book).limit(10))).scalars().all()
        now = datetime.now(timezone.utc)

        borrows = [
            BorrowRecord(
                user_id=admin.id,
                book_id=books[0].id,
                borrowed_at=now - timedelta(days=30),
                due_at=now + timedelta(days=30),
                status=BorrowStatus.borrowed,
            ),
            BorrowRecord(
                user_id=admin.id,
                book_id=books[1].id,
                borrowed_at=now - timedelta(days=60),
                due_at=now - timedelta(days=30),
                status=BorrowStatus.overdue,
            ),
            BorrowRecord(
                user_id=admin.id,
                book_id=books[2].id,
                borrowed_at=now - timedelta(days=90),
                due_at=now - timedelta(days=60),
                returned_at=now - timedelta(days=55),
                status=BorrowStatus.returned,
            ),
        ]
        db.add_all(borrows)

        # 更新对应图书的 available 数量
        for b in borrows:
            if b.status in (BorrowStatus.borrowed, BorrowStatus.overdue):
                book = await db.get(Book, b.book_id)
                if book and book.available > 0:
                    book.available -= 1

        await db.commit()
        print(f"借阅记录: {len(borrows)} 条")

    # 验证
    async with factory() as db:
        floor_count = (await db.execute(select(Floor))).scalars().all()
        zone_count = (await db.execute(select(Zone))).scalars().all()
        seat_count = (await db.execute(select(Seat))).scalars().all()
        book_count = (await db.execute(select(Book))).scalars().all()
        user_count = (await db.execute(select(User))).scalars().all()
        print(
            f"已插入: {len(user_count)} 用户, {len(floor_count)} 楼层, "
            f"{len(zone_count)} 区域, {len(seat_count)} 座位, {len(book_count)} 图书"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
