# Phase 4: profile_query（读者画像与借阅记录）— 设计文档

## 概述

补齐最后一个 stub 意图 `profile_query`，新建 `profile_subgraph` 子图（understand → query → format），新建 `BorrowRecord` 模型记录借阅流水，新建 `ProfileService` 统一查询用户信息、预约记录、借阅记录。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 子图 | `profile_subgraph`：3 节点子图，参照 `reservation_subgraph` 模式 |
| 数据模型 | 新建 `BorrowRecord`（借阅流水），不新建借阅/归还 API |
| 服务层 | 新建 `ProfileService`，注入 `LibraryNodeContext` |
| LLM | `RealLLMClient` 新增 2 方法 + `RuleBasedLLMClient` 新增模板兜底 |
| 主图 | `profile_stub` 升级为 `profile_subgraph` |
| 测试 | ~16 tests（单元 + 集成 + E2E） |

## 数据模型

### BorrowRecord

```python
class BorrowStatus(str, enum.Enum):
    borrowed = "borrowed"
    returned = "returned"
    overdue = "overdue"

class BorrowRecord(Base):
    __tablename__ = "borrow_records"

    id: str              # UUID
    user_id: str         # FK → users.id
    book_id: str         # FK → books.id
    borrowed_at: datetime
    due_at: datetime
    returned_at: datetime | None   # NULL = 未还
    status: BorrowStatus           # borrowed / returned / overdue
```

**图书库存联动**：`BorrowRecord` 创建时 `books.available -= 1`，归还时 `+= 1`。由管理员后台/种子数据触发，本期不实现对话借阅/归还 API。

### Alembic 迁移

- 新建 `borrow_records` 表
- `books.available` 现有字段不变（已存在）

### 种子数据

新增 3-5 条样例借阅记录（含已还、未还、逾期各状态），关联 admin 用户和示例图书。

## Agent 层：profile_subgraph

### 子图结构

```
START
  → profile_understand   (解析用户意图)
    → profile_query      (查询 DB)
  → profile_format       (LLM 格式化回复)
  → END
```

### 节点职责

| 节点 | 职责 |
|------|------|
| `profile_understand` | 调用 `llm.extract_profile_params(query)` 判断用户想查什么，返回 `{profile_type: "personal_info" | "borrowing_history" | "all"}` |
| `profile_query` | 通过 `ProfileService` 查询：User 信息、当前有效预约（Appointment）、借阅记录（BorrowRecord） |
| `profile_format` | 调用 `llm.format_profile_response(user, appointments, borrows)` 生成自然语言回复 |

### LibraryNodeContext 变更

```python
@dataclass(frozen=True)
class LibraryNodeContext:
    # ... 现有字段不变 ...
    profile_service: object | None = None    # 新增
```

### 主图变更

`graph.py` 中：
- `profile_stub` → `profile_subgraph`（编译后的子图）
- `_build_profile_subgraph(context)` 新增构造方法
- 路由不变（`profile_query` → `subgraph="profile"` → `profile_subgraph`）

## LLM 层

`RealLLMClient` 新增 2 个方法，`RuleBasedLLMClient` 新增对应兜底模板：

| 方法 | 职责 | 兜底策略 |
|------|------|---------|
| `extract_profile_params(query)` | 解析用户消息，返回 `{profile_type}` | 关键词匹配："借阅/借了/还了/借过"→borrowing_history，其余→all |
| `format_profile_response(user, appointments, borrows)` | 结构化数据 → 自然语言回复 | 固定模板拼接（三段式：个人信息 + 当前预约 + 借阅记录） |

## 服务层

### ProfileService

```python
class ProfileService:
    def __init__(self, db: AsyncSession):
        ...

    async def get_profile(self, user_id: str, profile_type: str) -> dict:
        """返回 {user, appointments, borrow_records}"""
        user = await self._db.get(User, user_id)
        appointments = ...  # 当前有效预约
        borrow_records = ...  # 借阅记录（按 borrowed_at 倒序）
        return {"user": user, "appointments": appointments, "borrow_records": borrow_records}
```

## 测试策略

| 层级 | 数量 | 测什么 | 依赖 |
|------|------|--------|------|
| 单元 | ~8 | `BorrowRecord` 模型创建/状态转换、`ProfileService.get_profile`（mock db）、`extract_profile_params` 关键词兜底、`format_profile_response` 模板拼接 | mock |
| 集成 | ~5 | `profile_subgraph` 三节点链路、LLM 兜底、无认证拒绝、空记录处理 | TestClient + SQLite |
| E2E | ~3 | 完整对话：查个人信息、查借阅记录、查全部 | TestClient |

## 文件变更清单

```
新增:
  app/models/borrow_record.py              ← BorrowRecord + BorrowStatus
  app/backend/service/profile_service.py   ← ProfileService
  tests/test_borrow_model.py               ← 模型单元测试
  tests/test_profile_service.py            ← 服务单元测试
  tests/test_profile_graph.py              ← 子图集成测试
  migrations/versions/xxxx_borrow_records.py ← Alembic 迁移

修改:
  app/models/__init__.py                   ← 导出 BorrowRecord, BorrowStatus
  app/agents/graph.py                      ← profile_stub → profile_subgraph
  app/agents/nodes.py                      ← 新增 3 个 profile 节点，LibraryNodeContext 加 profile_service
  app/agents/llm_client/client.py          ← 新增 2 个 LLM 方法 + prompts
  app/agents/llm.py                        ← RuleBasedLLMClient 新增模板兜底
  app/backend/service/chat_service.py      ← 注入 ProfileService
  scripts/seed.py                          ← 新增借阅记录种子数据
  tests/test_library_graph.py              ← 更新 stub 测试为真实断言
```

## 扩展路径

- **借阅/归还 API**：对话式借阅可新增 `borrow_book` / `return_book` 意图，在 reservation_subgraph 旁扩展 borrow_subgraph
- **阅读统计**：`profile_query` 可扩展返回阅读量排行、偏好类别等聚合数据
- **催还通知**：Celery Beat 定时扫描 `overdue` 记录，通过对话推送催还消息
