# Phase 4.1: GET /api/v1/profile REST 端点 — 设计文档

## 概述

暴露 ProfileService 现有能力为 HTTP JSON API。用户通过 Bearer Token 认证后，可获取个人信息、当前预约、借阅记录。复用已有 `ProfileService.get_profile()`，无需修改服务层。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 认证 | `get_required_user` 强制认证，未登录返回 401 |
| 服务层 | 复用已有 `ProfileService.get_profile()` |
| 查询参数 | `type` 参数控制返回范围，默认 `all` |
| Schema | 新建 `ProfileResponse`，内嵌 `UserInfo` + `AppointmentItem` + `BorrowRecordItem` |
| 路由前缀 | `/api/v1/profile`，与 README 已公布的一致 |

## API 设计

```
GET /api/v1/profile?type=all
Authorization: Bearer <token>

Response 200:
{
  "user": {
    "display_name": "管理员",
    "student_id": "ADMIN001",
    "username": "admin"
  },
  "appointments": [
    {
      "appointment_id": "...",
      "floor_name": "1F",
      "zone_name": "自习区",
      "seat_number": "A01",
      "date": "2026-07-08",
      "slot": "morning",
      "status": "booked"
    }
  ],
  "borrow_records": [
    {
      "id": "...",
      "book_title": "三体",
      "borrowed_at": "2026-06-07T...",
      "due_at": "2026-08-06T...",
      "returned_at": null,
      "status": "borrowed"
    }
  ]
}
```

查询参数：
- `type=all`（默认）：用户信息 + 当前有效预约 + 借阅记录
- `type=personal_info`：仅用户信息，appointments 和 borrow_records 返回空数组
- `type=borrowing_history`：用户信息 + 借阅记录，appointments 返回空数组
- 无效 type 值 → 422（Pydantic 校验拒绝）

错误响应：
- 401：未提供有效 Token
- 200 + `"user": null`：用户不存在（Token 有效但用户已被删除）

## 文件变更清单

```
新增:
  app/backend/schemas/profile.py            ← Pydantic 响应模型
  app/backend/router/profile_router.py      ← REST 路由
  tests/test_profile_api.py                 ← API 测试（4 tests）

修改:
  app/app_main.py                           ← 注册 profile_router
```

## Schema 定义

`AppointmentItem` 复用 `backend.schemas.seat` 中已有定义，仅新增以下模型：

```python
# app/backend/schemas/profile.py

class UserInfo(BaseModel):
    display_name: str
    student_id: str
    username: str

class BorrowRecordItem(BaseModel):
    id: str
    book_title: str
    borrowed_at: str
    due_at: str
    returned_at: str | None
    status: str

class ProfileResponse(BaseModel):
    user: UserInfo | None
    appointments: list[AppointmentItem]   # 复用 seat.py
    borrow_records: list[BorrowRecordItem]
```

`AppointmentItem` 直接复用 `backend.schemas.seat.AppointmentItem`，不重复定义。

## 测试策略

| 测试 | 预期 |
|------|------|
| `test_get_profile_unauthenticated` | 401 |
| `test_get_profile_all` | 200，含 user + appointments + borrow_records |
| `test_get_profile_personal_info` | 200，仅 user，空数组 |
| `test_get_profile_borrowing_history` | 200，user + borrow_records |

测试使用 `TestClient` + 预先创建的用户和数据，需 PostgreSQL 运行。

## 不做什么

- 不新增 POST/PUT/DELETE — 读者画像是只读查询
- 不修改 ProfileService — 复用已有接口
- 不新增借阅统计/聚合 — 留给后续 Phase
