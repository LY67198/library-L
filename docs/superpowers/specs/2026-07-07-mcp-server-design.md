# MCP Server — 设计文档

## 概述

将图书馆系统的 5 个核心能力封装为 MCP（Model Context Protocol）Tool，通过 SSE + HTTP 传输暴露给外部 AI 客户端（如 Claude Desktop）。使用官方 `mcp` Python SDK，嵌入现有 FastAPI 进程。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| Tool 数量 | 5 个（search_books, list_seats, book_seat, list_appointments, cancel_appointment） |
| 传输协议 | SSE + HTTP（嵌入 FastAPI） |
| 认证 | API Key（User 表新增 `api_key` 字段，Bearer token 方式传入） |
| SDK | `mcp`（官方 Python SDK） |
| Tool 参数 | 细粒度 JSON Schema（标准 input_schema） |
| 实现方式 | 直接调用现有 services（不经过 REST 路由器） |

## 调用链

```
外部 AI 客户端 → POST/GET /api/v1/mcp（SSE）
  → MCP Server 解析 JSON-RPC，匹配 Tool
  → tools.py 调用 SeatService / BookService
  → DB 查询/写入
  → 结构化 JSON 返回给外部 AI
```

## 代码结构变更

```
app/mcp_server/               ← 新建包
├── __init__.py               ← 导出
├── server.py                 ← MCP Server 实例 + SSE 传输 + FastAPI 挂载
├── tools.py                  ← 5 个 Tool 实现（调用现有 services）
└── auth.py                   ← API Key 依赖（Bearer token → User 查询）

app/
├── app_main.py               ← 修改：注册 /mcp 路由
├── models/user.py            ← 修改：新增 api_key 字段
├── backend/service/          ← 不动（复用）
└── core/                     ← 不动（复用 database, deps）

migrations/                   ← 新增：api_key 列迁移

pyproject.toml                ← 修改：新增 mcp 依赖
```

## 5 个 Tool 定义

### `search_books` — 馆藏检索

| 属性 | 值 |
|------|-----|
| 描述 | 检索图书馆馆藏图书，支持书名/作者/ISBN 模糊搜索 + 分类筛选 |
| 输入 | `query: string`（搜索关键词），`category?: string`（分类代码 A-T），`offset?: int`（默认 0），`limit?: int`（默认 10，最大 50） |
| 输出 | `{ items: [{ title, author, isbn, category, location, available }], total: int }` |

### `list_seats` — 座位浏览

| 属性 | 值 |
|------|-----|
| 描述 | 查询图书馆可预约座位，支持按楼层/区域/日期/时段筛选 |
| 输入 | `floor_id?: int`，`zone_id?: int`，`date?: string`（YYYY-MM-DD），`slot?: string`（morning/afternoon/evening），`offset?: int`，`limit?: int`（默认 100） |
| 输出 | `{ seats: [{ seat_id, floor_id, zone_id, seat_number, status, slot_status }], total: int }` |

### `book_seat` — 预约座位

| 属性 | 值 |
|------|-----|
| 描述 | 预约指定座位，需要提供座位ID、日期和时段 |
| 输入 | `seat_id: string (required)`，`date: string (required, YYYY-MM-DD)`，`slot: string (required, morning/afternoon/evening)` |
| 输出 | 成功：`{ appointment_id, seat_id, date, slot, status: "booked" }`；失败：`{ error: str, detail?: str }` |

### `list_appointments` — 查询预约

| 属性 | 值 |
|------|-----|
| 描述 | 查询当前用户的预约记录 |
| 输入 | `offset?: int`，`limit?: int`（默认 100） |
| 输出 | `{ appointments: [{ appointment_id, seat_id, date, slot, status }], total: int }` |

### `cancel_appointment` — 取消预约

| 属性 | 值 |
|------|-----|
| 描述 | 取消指定的预约记录 |
| 输入 | `appointment_id: string (required)` |
| 输出 | 成功：`{ success: true, cancelled_id: str }`；失败：`{ error: str }` |

## 认证设计

### User 模型改动

```python
# app/models/user.py — 新增字段
api_key: Mapped[str] = mapped_column(
    String(64), unique=True, nullable=False, index=True,
    default=lambda: uuid.uuid4().hex
)
```

### API Key 认证流

```
MCP 客户端 → Authorization: Bearer <api_key>
  → auth.get_user_by_api_key(api_key)
  → 找到 User → 注入 Tool 调用上下文
  → 未找到 → 返回 MCP error，拒绝连接
```

- API Key 在用户注册时自动生成
- 管理员后续可扩展 regenerate / revoke 操作
- MCP 的 SSE 生命周期内绑定一个用户身份

## SSE 传输 & FastAPI 集成

### 端点

```
GET  /api/v1/mcp/sse      → SSE 事件流（服务端推送 JSON-RPC 消息，含 ping 保活）
POST /api/v1/mcp/messages → 客户端 JSON-RPC 请求
```

### 挂载方式

```python
# app_main.py
from mcp.server.sse import SseServerTransport

sse = SseServerTransport("/api/v1/mcp/messages")
app.mount("/api/v1/mcp", create_sse_app(sse, api_key_auth))
```

MCP Server 作为 starlette ASGI app 挂载到 FastAPI 的 `/api/v1/mcp` 路径下。

### 认证时机

SSE 握手阶段（GET /sse）提取 `Authorization` header → 校验 API Key → 查用户 → 存入 session 上下文。后续每个 Tool 调用自动关联到此用户。

## 不变的部分

- 现有 REST API（`/api/v1/books`、`/api/v1/seats/*`、`/api/v1/appointments/*`）— 不动
- `SeatService`、`BookService` — 不动
- `AppSettings` — 不动（MCP 不需要额外配置）
- 前端 — 不动
- Docker Compose — 不动（MCP 端点复用 FastAPI 容器）

## 测试策略

| 层级 | 测什么 | 怎么测 |
|------|--------|--------|
| 单元 | API Key 认证逻辑 | mock DB，验证有效 key 返回用户、无效 key 拒绝 |
| 单元 | 5 个 Tool 函数（核心逻辑） | mock services，验证参数传递和返回值格式 |
| 集成 | MCP SSE 端点握手 | HTTPX async client 连 `/mcp/sse` + `/mcp/messages`，验证 JSON-RPC 响应 |
| 集成 | 无认证时拒绝连接 | 不带 Authorization header，验证返回认证错误 |
| 集成 | 端到端 Tool 调用（含 DB） | 测试数据库，真实 service 调用，验证返回值完整 |
| 不测 | `mcp` SDK 内部行为 | 第三方库，不测 |

## 不清算的内容

- AI 智能问答（`POST /api/v1/chat`）的 MCP 化 — chat 本身是 SSE 流式，复杂度高，先不加
- stdio 传输 — 先只做 SSE + HTTP
- API Key 的 regenerate / revoke 管理端点 — 后续管理功能扩展
- 速率限制 — Phase 4 可观测性统一做
- MCP Resources / Prompts 能力 — 只用 Tool，保持简单
