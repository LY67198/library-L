# profile_query（读者画像与借阅记录）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐最后一个 stub 意图 `profile_query`，新建 profile_subgraph 子图 + BorrowRecord 模型 + ProfileService。

**Architecture:** 参照 reservation_subgraph 模式实现 profile_subgraph（understand → query → format）。profile_query_node 通过 asyncio.run() 桥接 async DB 查询。ChatService 注入 session_factory 到 LibraryNodeContext。

**Tech Stack:** SQLAlchemy async, Alembic, LangGraph StateGraph, RealLLMClient (MiniMax + DeepSeek), RuleBasedLLMClient 模板兜底

---

### Task 1: BorrowRecord 数据模型

**Files:**
- Create: `app/models/borrow_record.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: 创建 BorrowRecord 模型**

```python
# app/models/borrow_record.py
"""借阅记录模型"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow


class BorrowStatus(str, enum.Enum):
    borrowed = "borrowed"
    returned = "returned"
    overdue = "overdue"


class BorrowRecord(Base):
    __tablename__ = "borrow_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("books.id"), nullable=False
    )
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[BorrowStatus] = mapped_column(
        Enum(BorrowStatus, name="borrow_status_enum"),
        default=BorrowStatus.borrowed,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    book: Mapped["Book"] = relationship("Book")
```

- [ ] **Step 2: 更新 models/__init__.py，导出新模型**

```python
# app/models/__init__.py — 在现有 import 块末尾追加：
from .borrow_record import BorrowRecord, BorrowStatus

# __all__ 列表末尾追加：
    "BorrowRecord",
    "BorrowStatus",
```

Edit `app/models/__init__.py`:
- 在 `from .book import Book` 后新增一行 `from .borrow_record import BorrowRecord, BorrowStatus`
- 在 `__all__` 列表中 `"Book",` 后追加 `"BorrowRecord", "BorrowStatus",`

- [ ] **Step 3: 运行现有测试确保模型导入不破坏任何已有测试**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/ -x -q --tb=short`
Expected: 所有已有测试通过（新模型不影响已有测试）

- [ ] **Step 4: Commit**

```bash
git add app/models/borrow_record.py app/models/__init__.py
git commit -m "feat: 新增 BorrowRecord 借阅记录模型

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Alembic 迁移

**Files:**
- Create: `migrations/versions/xxxx_borrow_records.py` (自动生成)

- [ ] **Step 1: 生成迁移文件**

Run: `cd D:\Agent-Project\deep_research_scaffold && alembic revision --autogenerate -m "add borrow_records table"`
Expected: 在 `migrations/versions/` 下生成迁移文件

- [ ] **Step 2: 检查生成的迁移文件，确认包含 `borrow_records` 表和 `borrow_status_enum`**

打开生成的迁移文件，验证 `upgrade()` 中包含：
- `sa.Enum(... name='borrow_status_enum')` 创建
- `op.create_table('borrow_records', ...)` 包含 user_id, book_id, borrowed_at, due_at, returned_at, status 列
- 如果 alembic 未自动检测到 enum，确保迁移中手动创建 enum 类型

- [ ] **Step 3: 运行迁移**

Run: `cd D:\Agent-Project\deep_research_scaffold && alembic upgrade head`
Expected: 输出 `INFO  [alembic.runtime.migration] Running upgrade ... -> ...`

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/xxxx_borrow_records.py
git commit -m "feat: alembic 迁移 — 新建 borrow_records 表

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: BorrowRecord 模型单元测试

**Files:**
- Create: `tests/test_borrow_model.py`

- [ ] **Step 1: 编写模型测试**

```python
# tests/test_borrow_model.py
"""BorrowRecord 模型单元测试"""
import pytest
from datetime import datetime, timezone
from models import (
    BorrowRecord, BorrowStatus, User, Book, Base,
)


@pytest.mark.asyncio
async def test_create_borrow_record(db_session):
    """测试创建借阅记录"""
    from sqlalchemy import text

    # 创建依赖数据
    user = User(
        username="testuser",
        password_hash="hash",
        display_name="测试用户",
        student_id="S001",
    )
    book = Book(
        title="测试图书",
        author="测试作者",
        total=3,
        available=2,
    )
    db_session.add_all([user, book])
    await db_session.commit()

    record = BorrowRecord(
        user_id=user.id,
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        status=BorrowStatus.borrowed,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    assert record.id is not None
    assert record.status == BorrowStatus.borrowed
    assert record.user_id == user.id
    assert record.book_id == book.id
    assert record.borrowed_at is not None
    assert record.returned_at is None


@pytest.mark.asyncio
async def test_borrow_record_relationship(db_session):
    """测试关联关系 loading"""
    user = User(
        username="testuser2",
        password_hash="hash",
        display_name="测试用户2",
        student_id="S002",
    )
    book = Book(
        title="测试图书2",
        author="测试作者2",
        total=1,
        available=1,
    )
    db_session.add_all([user, book])
    await db_session.commit()

    record = BorrowRecord(
        user_id=user.id,
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        status=BorrowStatus.borrowed,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record, ["user", "book"])

    assert record.user.username == "testuser2"
    assert record.book.title == "测试图书2"


@pytest.mark.asyncio
async def test_borrow_record_status_transition(db_session):
    """测试借阅状态转换"""
    user = User(
        username="testuser3",
        password_hash="hash",
        display_name="测试用户3",
        student_id="S003",
    )
    book = Book(
        title="测试图书3",
        author="测试作者3",
        total=1,
        available=1,
    )
    db_session.add_all([user, book])
    await db_session.commit()

    record = BorrowRecord(
        user_id=user.id,
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        status=BorrowStatus.borrowed,
    )
    db_session.add(record)
    await db_session.commit()

    # borrowed → returned
    record.status = BorrowStatus.returned
    record.returned_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(record)

    assert record.status == BorrowStatus.returned
    assert record.returned_at is not None

    # borrowed → overdue
    record.status = BorrowStatus.overdue
    record.returned_at = None
    await db_session.commit()
    await db_session.refresh(record)

    assert record.status == BorrowStatus.overdue
    assert record.returned_at is None


@pytest.mark.asyncio
async def test_borrow_record_cascade_user_not_found(db_session):
    """测试 user_id 外键约束"""
    import asyncpg
    from sqlalchemy import text

    book = Book(
        title="测试图书4",
        author="测试作者4",
        total=1,
        available=1,
    )
    db_session.add(book)
    await db_session.commit()

    record = BorrowRecord(
        user_id="nonexistent-uuid",
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
    )
    db_session.add(record)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: 运行测试验证**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_borrow_model.py -v --tb=short`
Expected: 4 tests passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_borrow_model.py
git commit -m "test: BorrowRecord 模型单元测试（4 tests）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: ProfileService

**Files:**
- Create: `app/backend/service/profile_service.py`

- [ ] **Step 1: 创建 ProfileService**

```python
# app/backend/service/profile_service.py
"""读者画像查询服务"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import User, Appointment, BorrowRecord
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

        if profile_type in ("personal_info", "all"):
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
                    .options(selectinload(Appointment.seat))
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
```

- [ ] **Step 2: Commit**

```bash
git add app/backend/service/profile_service.py
git commit -m "feat: 新建 ProfileService — 用户画像查询

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: ProfileService 单元测试

**Files:**
- Create: `tests/test_profile_service.py`

- [ ] **Step 1: 编写 ProfileService 测试**

```python
# tests/test_profile_service.py
"""ProfileService 单元测试"""
import pytest
from datetime import datetime, timezone
from backend.service.profile_service import ProfileService
from models import (
    User, Book, BorrowRecord, BorrowStatus, Appointment, AppointmentStatus,
    Floor, Zone, Seat, SeatStatus, SeatTimeSlot, TimeSlot,
)


@pytest.mark.asyncio
async def test_get_profile_user_only(db_session):
    """测试仅查询用户信息"""
    user = User(
        username="reader1",
        password_hash="hash",
        display_name="读者一号",
        student_id="R001",
    )
    db_session.add(user)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "personal_info")

    assert result["user"] is not None
    assert result["user"].display_name == "读者一号"
    assert result["user"].student_id == "R001"
    assert result["appointments"] == []
    assert result["borrow_records"] == []


@pytest.mark.asyncio
async def test_get_profile_with_appointments(db_session):
    """测试查询用户信息 + 预约记录"""
    user = User(
        username="reader2",
        password_hash="hash",
        display_name="读者二号",
        student_id="R002",
    )
    floor = Floor(name="1F", sort_order=1)
    zone = Zone(floor_id=floor.id, name="自习区", zone_type="open", sort_order=1)
    seat = Seat(zone_id=zone.id, seat_number="A01")

    db_session.add_all([user, floor, zone, seat])
    await db_session.flush()

    slot = SeatTimeSlot(
        seat_id=seat.id,
        date=datetime(2026, 7, 8).date(),
        slot=TimeSlot.morning,
        user_id=user.id,
        is_available=False,
    )
    appt = Appointment(
        user_id=user.id,
        seat_id=seat.id,
        date=datetime(2026, 7, 8).date(),
        slot=TimeSlot.morning,
        status=AppointmentStatus.booked,
    )
    db_session.add_all([slot, appt])
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "all")

    assert result["user"].display_name == "读者二号"
    assert len(result["appointments"]) == 1
    assert result["appointments"][0].status == AppointmentStatus.booked


@pytest.mark.asyncio
async def test_get_profile_with_borrow_history(db_session):
    """测试查询借阅记录"""
    user = User(
        username="reader3",
        password_hash="hash",
        display_name="读者三号",
        student_id="R003",
    )
    book = Book(
        title="百年孤独",
        author="加西亚·马尔克斯",
        total=2,
        available=1,
    )
    db_session.add_all([user, book])
    await db_session.commit()

    record = BorrowRecord(
        user_id=user.id,
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        status=BorrowStatus.borrowed,
    )
    db_session.add(record)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "borrowing_history")

    assert result["user"].display_name == "读者三号"
    assert len(result["borrow_records"]) == 1
    assert result["borrow_records"][0].book.title == "百年孤独"
    assert result["borrow_records"][0].status == BorrowStatus.borrowed
    assert result["appointments"] == []


@pytest.mark.asyncio
async def test_get_profile_nonexistent_user(db_session):
    """测试查询不存在的用户"""
    service = ProfileService(db_session)
    result = await service.get_profile("nonexistent-id", "all")

    assert result["user"] is None
    assert result["appointments"] == []
    assert result["borrow_records"] == []


@pytest.mark.asyncio
async def test_get_profile_empty_history(db_session):
    """测试查询没有借阅记录的用户"""
    user = User(
        username="reader5",
        password_hash="hash",
        display_name="读者五号",
        student_id="R005",
    )
    db_session.add(user)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "all")

    assert result["user"].display_name == "读者五号"
    assert result["appointments"] == []
    assert result["borrow_records"] == []
```

- [ ] **Step 2: 运行测试验证**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_profile_service.py -v --tb=short`
Expected: 5 tests passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_profile_service.py
git commit -m "test: ProfileService 单元测试（5 tests）

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: LLM 层 — extract_profile_params + format_profile_response

**Files:**
- Modify: `app/agents/llm_client/client.py`
- Modify: `app/agents/llm.py`

- [ ] **Step 1: 在 client.py 中新增 System Prompt 和两个方法**

在 `client.py` 中，在 `FORMAT_RESERVATION_RESPONSE_PROMPT` 之后追加：

```python
EXTRACT_PROFILE_PARAMS_PROMPT = """你是一个图书馆读者画像参数提取器。从用户消息中提取查询意图，只输出 JSON（不要输出其他文字）。

参数说明：
- profile_type: "personal_info"（查个人信息）/ "borrowing_history"（借阅记录）/ "all"（全部）

输出格式示例：
{"profile_type": "all"}
{"profile_type": "borrowing_history"}"""

FORMAT_PROFILE_RESPONSE_PROMPT = """你是一个友好的图书馆助手。根据用户信息和借阅记录，用自然语言回复用户。
要求：
- 用中文回复
- 语气友好、自然
- 个人信息段：姓名、学号
- 预约段：列出当前有效预约（楼层、座位号、日期、时段）
- 借阅段：列出借阅记录（书名、借阅日期、到期日期、状态）
- 如果某段无数据，简洁说明"""
```

在 `RealLLMClient` 类的 `stub_message` 方法之前插入：

```python
    def extract_profile_params(self, query: str) -> dict:
        try:
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=EXTRACT_PROFILE_PARAMS_PROMPT,
                user_message=query,
                parser=_parse_json_or_empty,
                temperature=0.1,
            )
        except RuntimeError:
            logger.warning("Profile params extraction LLM failed, using rule-based fallback")
            return self._fallback.extract_profile_params(query)

    def format_profile_response(
        self, user_info: dict, appointments: list[dict], borrow_records: list[dict]
    ) -> str:
        try:
            data = json.dumps({
                "user": user_info,
                "appointments": appointments,
                "borrow_records": borrow_records,
            }, ensure_ascii=False, default=str)
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=FORMAT_PROFILE_RESPONSE_PROMPT,
                user_message=f"以下是与用户相关的数据：\n{data}",
                parser=str.strip,
                temperature=0.3,
                max_tokens=512,
            )
        except RuntimeError:
            logger.warning("Format profile response LLM failed, using rule-based fallback")
            return self._fallback.format_profile_response(user_info, appointments, borrow_records)
```

同时更新 `LLMClient` Protocol 和 `RuleBasedLLMClient`。

- [ ] **Step 2: 更新 LLMClient Protocol（llm.py）**

在 `LLMClient` Protocol 中，`format_reservation_response` 方法后追加：

```python
    # --- 读者画像方法（Phase 4 新增） ---
    def extract_profile_params(self, query: str) -> dict: ...

    def format_profile_response(
        self, user_info: dict, appointments: list[dict], borrow_records: list[dict]
    ) -> str: ...
```

- [ ] **Step 3: 更新 RuleBasedLLMClient（llm.py）**

在 `RuleBasedLLMClient` 中 `stub_message` 方法之前追加：

```python
    def extract_profile_params(self, query: str) -> dict:
        """关键词兜底：借阅/借了/还了/借过 → borrowing_history，其余 → all"""
        lowered = query.lower()
        if any(w in lowered for w in ["借阅", "借了", "还了", "借过", "借书记录",
                                        "借了哪些", "借过什么", "在借"]):
            return {"profile_type": "borrowing_history"}
        return {"profile_type": "all"}

    def format_profile_response(
        self, user_info: dict, appointments: list[dict], borrow_records: list[dict]
    ) -> str:
        """固定模板拼接：个人信息 + 当前预约 + 借阅记录"""
        lines = []
        u = user_info or {}
        lines.append(f"**个人信息**\n- 姓名：{u.get('display_name', '-')}\n- 学号：{u.get('student_id', '-')}")

        lines.append("\n**当前预约**")
        if appointments:
            for a in appointments:
                slot_label = (
                    "上午" if a.get("slot") == "morning"
                    else "下午" if a.get("slot") == "afternoon"
                    else "晚上"
                )
                lines.append(
                    f"- {a.get('floor_name', '')}-{a.get('zone_name', '')}-"
                    f"{a.get('seat_number', '')} | {a.get('date', '')} {slot_label}"
                )
        else:
            lines.append("- 暂无有效预约")

        lines.append("\n**借阅记录**")
        if borrow_records:
            for br in borrow_records:
                status_map = {"borrowed": "在借", "returned": "已还", "overdue": "逾期"}
                status = status_map.get(br.get("status", ""), br.get("status", ""))
                lines.append(
                    f"- 《{br.get('book_title', '-')}》 "
                    f"借阅：{br.get('borrowed_at', '-')[:10]} "
                    f"到期：{br.get('due_at', '-')[:10]} "
                    f"状态：{status}"
                )
        else:
            lines.append("- 暂无借阅记录")

        return "\n".join(lines)
```

- [ ] **Step 4: 运行已有测试确认无回归**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_real_llm_client.py tests/test_library_graph.py -v --tb=short`
Expected: 所有已有测试通过

- [ ] **Step 5: Commit**

```bash
git add app/agents/llm_client/client.py app/agents/llm.py
git commit -m "feat: LLM 层新增 extract_profile_params + format_profile_response

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Agent 层 — profile_subgraph 3 节点 + 主图升级

**Files:**
- Modify: `app/agents/nodes.py`
- Modify: `app/agents/graph.py`

- [ ] **Step 1: 更新 LibraryNodeContext，新增 session_factory 字段**

在 `app/agents/nodes.py` 中，修改 `LibraryNodeContext`：

```python
@dataclass(frozen=True)
class LibraryNodeContext:
    """节点依赖注入容器"""

    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever
    auth_service: object | None = None
    seat_service: object | None = None
    session_factory: object | None = None  # Phase 4: async sessionmaker
```

- [ ] **Step 2: 新增 3 个 profile 节点**

在 `app/agents/nodes.py` 中，`reservation_format_node` 之后追加。

确保文件顶部已有 `import asyncio`（如无则添加到顶部 import 区）。

```python
# --- Profile 子图节点（Phase 4） ---

def profile_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """解析用户消息，判断用户想查什么"""
    query = state["query"]
    params = context.llm.extract_profile_params(query)
    return {"context": {"profile_type": params.get("profile_type", "all")}}


def profile_query_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """查询 DB：User + Appointment + BorrowRecord"""
    user_id = state.get("user_id")
    if not user_id:
        return {
            "response": "请先登录后查看个人信息。",
            "sources": [],
            "error": "unauthenticated",
        }

    session_factory = context.session_factory
    if session_factory is None:
        return {
            "response": "个人信息查询服务暂不可用。",
            "sources": [],
            "error": "no_db",
        }

    profile_type = state.get("context", {}).get("profile_type", "all")

    async def _query():
        from backend.service.profile_service import ProfileService

        async with session_factory() as db:
            service = ProfileService(db)
            return await service.get_profile(user_id, profile_type)

    try:
        result = asyncio.run(_query())
    except Exception:
        return {
            "response": "查询个人信息时出错，请稍后重试。",
            "sources": [],
            "error": "profile_query_failed",
        }

    user = result["user"]
    if user is None:
        return {
            "response": "未找到用户信息。",
            "sources": [],
            "error": None,
        }

    # 序列化 appointment 数据
    appointments = []
    for a in result["appointments"]:
        seat = getattr(a, "seat", None)
        floor_name = getattr(seat, "floor_name", "") if seat else ""
        zone_name = getattr(seat, "zone_name", "") if seat else ""
        seat_number = getattr(seat, "seat_number", "") if seat else ""
        appointments.append({
            "appointment_id": a.id,
            "date": str(a.date),
            "slot": a.slot.value if hasattr(a.slot, "value") else str(a.slot),
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "floor_name": floor_name,
            "zone_name": zone_name,
            "seat_number": seat_number,
        })

    # 序列化 borrow_record 数据
    borrow_records = []
    for br in result["borrow_records"]:
        book = getattr(br, "book", None)
        borrow_records.append({
            "id": br.id,
            "book_title": book.title if book else "-",
            "borrowed_at": str(br.borrowed_at),
            "due_at": str(br.due_at),
            "returned_at": str(br.returned_at) if br.returned_at else None,
            "status": br.status.value if hasattr(br.status, "value") else str(br.status),
        })

    user_info = {
        "display_name": user.display_name,
        "student_id": user.student_id,
        "username": user.username,
    }

    return {
        "context": {
            "profile_type": profile_type,
            "user_info": user_info,
            "appointments": appointments,
            "borrow_records": borrow_records,
        },
        "error": None,
    }


def profile_format_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """LLM 格式化回复"""
    error = state.get("error")
    if error:
        fallback = state.get("fallback_response", "服务异常，请稍后重试。")
        return {"response": fallback, "sources": []}

    ctx = state.get("context", {})
    user_info = ctx.get("user_info", {})
    appointments = ctx.get("appointments", [])
    borrow_records = ctx.get("borrow_records", [])

    response = context.llm.format_profile_response(user_info, appointments, borrow_records)
    return {"response": response, "sources": []}
```

- [ ] **Step 3: 更新主图 — profile_stub 升级为 profile_subgraph**

在 `app/agents/graph.py` 中：

修改 `build_library_graph`：
```python
# 将:
    graph.add_node("profile_stub", lambda s: profile_stub_node(s, context))
# 替换为:
    graph.add_node("profile_subgraph", _build_profile_subgraph(context))
```

```python
# 将:
            "profile": "profile_stub",
# 替换为:
            "profile": "profile_subgraph",
```

```python
# 将:
    graph.add_edge("profile_stub", END)
# 替换为:
    graph.add_edge("profile_subgraph", END)
```

新增 `_build_profile_subgraph` 函数（放在 `_build_reservation_subgraph` 之后）：

```python
def _build_profile_subgraph(context: LibraryNodeContext):
    """构建读者画像子图：understand → query → format"""
    sub = StateGraph(LibraryState)

    sub.add_node("profile_understand", lambda s: profile_understand_node(s, context))
    sub.add_node("profile_query", lambda s: profile_query_node(s, context))
    sub.add_node("profile_format", lambda s: profile_format_node(s, context))

    sub.add_edge(START, "profile_understand")
    sub.add_edge("profile_understand", "profile_query")
    sub.add_edge("profile_query", "profile_format")
    sub.add_edge("profile_format", END)

    return sub.compile()
```

同时更新 nodes.py 的 import（在 graph.py 顶部添加对新节点的引用）：
```python
# graph.py 顶部 import 中添加:
    profile_understand_node,
    profile_query_node,
    profile_format_node,
```

- [ ] **Step 4: 运行已有测试确认无回归**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_library_graph.py -v --tb=short`
Expected: 当前 profile_query stub 测试会 FAIL（因为不再返回 stub message），其他测试 PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/nodes.py app/agents/graph.py
git commit -m "feat: profile_subgraph 三节点 + 主图升级

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: ChatService 注入 session_factory

**Files:**
- Modify: `app/backend/service/chat_service.py`

- [ ] **Step 1: 修改 ChatService 以支持 session_factory**

```python
# app/backend/service/chat_service.py

# 在文件顶部 import 块中添加：
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# 修改 ChatService.__init__:
class ChatService:
    """图书馆聊天服务 — 懒初始化 + 线程安全"""

    def __init__(self):
        self._lock = Lock()
        self._initialized = False
        self._app = None
        self._config = ChatConfig()
        self._session_factory = None

    def set_session_factory(self, factory) -> None:
        """注入 async session factory，供 Profile Service 使用"""
        self._session_factory = factory

    # 修改 _ensure_initialized，在 context 创建时注入 session_factory:
    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            context = LibraryNodeContext(
                config=self._config,
                llm=_create_llm_client(),
                retriever=StubRetriever(),
                book_lookup=StubRetriever(),
                session_factory=self._session_factory,
            )
            self._app = build_library_graph(context)
            self._initialized = True

    # 修改 _invoke_sync: 在 state 中携带 user_id:
    # （已存在，不需要改动 — create_initial_library_state 已接受 user_id 参数）
```

- [ ] **Step 2: 在模块中创建 session_factory 并注入**

在 `chat_service.py` 中，修改 `get_chat_service` 函数：

```python
def get_chat_service() -> ChatService:
    """全局单例 — 懒初始化"""
    global _CHAT_SERVICE
    if _CHAT_SERVICE is None:
        _CHAT_SERVICE = ChatService()
        # 注入 session_factory（使用项目数据库配置）
        try:
            from backend.config.settings import get_settings
            settings = get_settings()
            engine = create_async_engine(settings.database_url, echo=False)
            _CHAT_SERVICE.set_session_factory(
                async_sessionmaker(engine, expire_on_commit=False)
            )
        except Exception:
            pass  # session_factory 注入失败时，profile_query 会返回错误提示
    return _CHAT_SERVICE
```

- [ ] **Step 3: 运行已有测试确认无回归**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_chat_api.py tests/test_auth_api.py -v --tb=short`
Expected: 所有已有测试通过

- [ ] **Step 4: Commit**

```bash
git add app/backend/service/chat_service.py
git commit -m "feat: ChatService 注入 session_factory 支持 ProfileService

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: profile_subgraph 集成测试

**Files:**
- Create: `tests/test_profile_graph.py`
- Modify: `tests/test_library_graph.py`

- [ ] **Step 1: 编写 profile_subgraph 集成测试**

```python
# tests/test_profile_graph.py
"""profile_subgraph 集成测试 — 验证子图三节点链路"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from agents.llm import RuleBasedLLMClient
from agents.config import ChatConfig
from agents.graph import build_library_graph
from agents.nodes import LibraryNodeContext
from agents.retrieval.protocol import StubRetriever
from agents.state import create_initial_library_state


def _build_context():
    return LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
        session_factory=None,
    )


def test_profile_query_unauthenticated():
    """未登录时返回提示"""
    context = _build_context()
    app = build_library_graph(context)
    state = create_initial_library_state(query="我的个人信息", user_id=None)
    result = app.invoke(state)
    assert "请先登录" in result["response"]


def test_profile_query_returns_response_with_mock():
    """mock asyncio.run 返回预置数据，验证完整链路"""
    context = _build_context()
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "测试读者"
    canned_user.student_id = "R010"
    canned_user.username = "reader10"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我的个人信息", user_id="test-user-id")
        result = app.invoke(state)

    assert "测试读者" in result["response"]
    assert "R010" in result["response"]


def test_profile_query_with_borrow_history_mock():
    """mock 返回含借阅记录的数据"""
    context = _build_context()
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "借阅读者"
    canned_user.student_id = "R011"
    canned_user.username = "reader11"

    mock_book = MagicMock()
    mock_book.title = "三体"

    mock_br = MagicMock()
    mock_br.id = "br-1"
    mock_br.book = mock_book
    mock_br.borrowed_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    mock_br.due_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    mock_br.returned_at = None
    mock_br.status = MagicMock()
    mock_br.status.value = "borrowed"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [mock_br],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我的借阅记录", user_id="test-user-id")
        result = app.invoke(state)

    assert "三体" in result["response"]


def test_profile_query_empty_history_mock():
    """mock 空借阅记录，验证不出现开发中提示"""
    context = _build_context()
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "空记录读者"
    canned_user.student_id = "R012"
    canned_user.username = "reader12"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我借过什么书", user_id="test-user-id")
        result = app.invoke(state)

    assert len(result["response"]) > 0
    assert "开发中" not in result["response"]


def test_profile_query_db_unavailable():
    """session_factory 为 None 时返回错误提示"""
    context = _build_context()
    app = build_library_graph(context)
    state = create_initial_library_state(query="我的借阅记录", user_id="test-user-id")
    result = app.invoke(state)
    assert "暂不可用" in result["response"] or "请先登录" in result["response"]
```

- [ ] **Step 2: 更新 test_library_graph.py**

修改 `test_intent_routing` 参数化测试中 profile_query 的预期值：

```python
# 将:
        ("我的借阅记录", "profile_query", "profile"),
# 保持不变 — 意图和子图路由不变

# 删除或修改 test_profile_stub 相关测试（如果存在）：
# 当前 test_library_graph.py 中无 profile_stub 专项测试，无需修改
```

检查 `test_library_graph.py` 是否需要更新：确认 profile_query 在路由测试中仍然正确（`"profile_query"` → subgraph `"profile"`），路由逻辑不变。

- [ ] **Step 3: 运行测试验证**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/test_profile_graph.py tests/test_library_graph.py -v --tb=short`
Expected: 所有测试通过

- [ ] **Step 4: Commit**

```bash
git add tests/test_profile_graph.py tests/test_library_graph.py
git commit -m "test: profile_subgraph 集成测试（4 tests）+ 更新路由测试

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: 种子数据 — 新增借阅记录

**Files:**
- Modify: `scripts/seed.py`

- [ ] **Step 1: 在 seed.py 中追加借阅记录种子数据**

在 `scripts/seed.py` 中，在 `from models import Book, Floor, Seat, User, Zone` 后添加 `BorrowRecord, BorrowStatus` 导入：

```python
from models import Book, Floor, Seat, User, Zone, BorrowRecord, BorrowStatus
```

在图书插入之后、验证之前，追加：

```python
        # 借阅记录种子数据
        from datetime import datetime, timezone, timedelta

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
            if b.status == BorrowStatus.borrowed or b.status == BorrowStatus.overdue:
                book = await db.get(Book, b.book_id)
                if book and book.available > 0:
                    book.available -= 1

        await db.commit()
        print(f"借阅记录: {len(borrows)} 条")
```

- [ ] **Step 2: Commit**

```bash
git add scripts/seed.py
git commit -m "feat: 种子数据新增 3 条样例借阅记录

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 11: 全量测试回归 + 最终验证

- [ ] **Step 1: 运行全量测试**

Run: `cd D:\Agent-Project\deep_research_scaffold && python -m pytest tests/ -v --tb=short`
Expected: 所有已有测试 + 新增测试全部通过（~152 tests）

- [ ] **Step 2: 运行前端构建验证**

Run: `cd D:\Agent-Project\deep_research_scaffold\front && npm run build`
Expected: 构建成功（前端不受影响）

- [ ] **Step 3: 服务启动验证**

Run: `cd D:\Agent-Project\deep_research_scaffold && timeout 10 python -m uvicorn app_main:app --host 0.0.0.0 --port 8000 2>&1 || true`
Expected: 服务正常启动，无 import 错误

- [ ] **Step 4: 端点验证**

```bash
# 健康检查
curl http://localhost:8000/api/v1/health
# 无认证 chat 请求（验证 profile_query 返回提示登录）
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "我的借阅记录"}'
# 验证响应中 intent=profile_query，response 包含"请先登录"
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: 全量测试回归验证通过

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 12: 更新 CLAUDE.md 项目进度

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新进度状态**

在 CLAUDE.md 中：
- 将 `profile_query` 状态从 `🔜 最后一个待实现（当前 stub）` 改为 `✅ Phase 4`
- 将 `profile_subgraph` 状态从 `🔜 stub → 待升级` 改为 `✅ Phase 4`
- 更新 "已实现" 计数：9/9 意图，3/3 子图
- 在关键文档列表追加新的设计文档和计划文档引用

```markdown
## 断点续接 — 2026-07-07（profile_query ✅ 已完成）

**当前状态:** profile_query + profile_subgraph 已实现，9/9 意图全部完成，3/3 子图全部实现。

### profile_query — 已全部完成

- [x] 设计文档 → `docs/superpowers/specs/2026-07-07-profile-query-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-07-profile-query.md`
- [x] BorrowRecord 模型 + BorrowStatus 枚举
- [x] Alembic 迁移（borrow_records 表）
- [x] ProfileService（用户画像查询）
- [x] LLM 层新增 extract_profile_params + format_profile_response
- [x] profile_subgraph 三节点（understand → query → format）
- [x] ChatService 注入 session_factory
- [x] 种子数据新增借阅记录
- [x] 测试：模型 4 + 服务 5 + 子图集成 4 = ~13 new tests
- [x] 全量 ~152 tests passed + 前端构建通过

### 新文件

```
app/models/borrow_record.py                  ← BorrowRecord + BorrowStatus
app/backend/service/profile_service.py       ← ProfileService
tests/test_borrow_model.py                   ← 模型测试（4 tests）
tests/test_profile_service.py                ← 服务测试（5 tests）
tests/test_profile_graph.py                  ← 子图集成测试（4 tests）
migrations/versions/xxxx_borrow_records.py   ← Alembic 迁移
```

### 项目完成度总览

**9 种用户意图：9/9 全部实现** ✅

**子图：3/3 全部实现** ✅

**基础设施：全部完成** ✅
```

- [ ] **Step 2: 更新项目结构图**

在 CLAUDE.md 项目结构中追加新文件路径。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 更新 CLAUDE.md — profile_query Phase 4 完成

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Plan Summary

| Task | 内容 | 文件 | 测试 |
|------|------|------|------|
| 1 | BorrowRecord 模型 | `app/models/borrow_record.py`, `__init__.py` | — |
| 2 | Alembic 迁移 | `migrations/versions/` | — |
| 3 | 模型单元测试 | `tests/test_borrow_model.py` | 4 |
| 4 | ProfileService | `app/backend/service/profile_service.py` | — |
| 5 | 服务单元测试 | `tests/test_profile_service.py` | 5 |
| 6 | LLM 层扩展 | `llm_client/client.py`, `llm.py` | — |
| 7 | profile_subgraph + 主图 | `nodes.py`, `graph.py` | — |
| 8 | ChatService 注入 | `chat_service.py` | — |
| 9 | 子图集成测试 | `tests/test_profile_graph.py`, `test_library_graph.py` | 4 |
| 10 | 种子数据 | `scripts/seed.py` | — |
| 11 | 全量回归 | — | ~152 |
| 12 | 更新 CLAUDE.md | `CLAUDE.md` | — |

**总计: ~13 new tests, 全量 ~152 tests**
