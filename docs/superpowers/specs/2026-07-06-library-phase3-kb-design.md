# Phase 3 — 知识库管理 设计文档

**日期:** 2026-07-06
**状态:** 待实施

## 概述

为图书馆智能服务系统建立真实可用的知识库，结束所有检索走 stub 的历史。

- **图书管理**: PostgreSQL `books` 表 + REST CRUD + 批量导入，供 `SQLBookLookup` 消费
- **政策文档管理**: Markdown 上传 → chunk → embed → ChromaDB，供 `ChromaDBRetriever` 消费
- **管理员权限**: User 模型新增 `is_admin` 字段，JWT 携带，Depends 校验

## 架构

```
app/
├── models/
│   ├── book.py              ← 新增：Book 模型
│   ├── document.py          ← 新增：Document 模型（追踪已上传政策文档）
│   └── user.py              ← 改造：新增 is_admin 字段
├── agents/
│   └── retrieval/
│       ├── chroma_retriever.py  ← 改造：补全写入 + 删除 chunk 方法
│       └── embedder.py          ← 新增：Qwen text-embedding-v2 嵌入客户端
├── backend/
│   ├── router/
│   │   ├── admin_book_router.py ← 新增：图书 CRUD + 批量导入
│   │   ├── admin_doc_router.py  ← 新增：文档上传/删除/重新索引
│   │   └── book_router.py       ← 改造：从 stub 改为真实 DB 查询
│   ├── schemas/
│   │   ├── book.py              ← 新增：Book 相关 Pydantic 模型
│   │   └── document.py          ← 新增：Document 相关 Pydantic 模型
│   └── service/
│       ├── book_service.py      ← 新增：图书业务逻辑
│       └── doc_service.py       ← 新增：文档索引/删除逻辑
├── core/
│   ├── security.py          ← 改造：JWT encode 增加 is_admin claim
│   └── deps.py              ← 改造：新增 require_admin Depends
└── migrations/              ← 新增 migration
```

### 数据流

```
管理员 → POST /api/v1/admin/books → book_service → PostgreSQL
管理员 → POST /api/v1/admin/books/import → book_service → PostgreSQL (批量)
管理员 → POST /api/v1/admin/documents → doc_service → embedder → ChromaDB
用户提问 → Agent → SQLBookLookup → PostgreSQL（图书检索）
用户提问 → Agent → ChromaDBRetriever → ChromaDB（政策检索）
```

## 数据模型

### Book 表（PostgreSQL）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键，默认 `uuid4` |
| `title` | String(256) | 书名，NOT NULL |
| `author` | String(128) | 作者，NOT NULL |
| `isbn` | String(20) | ISBN，唯一索引，可空 |
| `publisher` | String(128) | 出版社，可空 |
| `publish_year` | Integer | 出版年份，可空 |
| `category` | String(64) | 分类标签，可空 |
| `location` | String(128) | 馆藏位置，可空 |
| `total` | Integer | 总册数，默认 1 |
| `available` | Integer | 可借数，默认 1 |
| `created_at` | DateTime(tz=True) | 创建时间 |
| `updated_at` | DateTime(tz=True) | 更新时间 |

### Document 表（PostgreSQL — 仅追踪元数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `title` | String(256) | 文档标题 |
| `filename` | String(256) | 原始文件名 |
| `source_type` | Enum(`policy`, `rule`, `faq`, `other`) | 文档分类 |
| `chunk_count` | Integer | 切分 chunk 数 |
| `created_at` | DateTime(tz=True) | 上传时间 |

### ChromaDB Collection（`library_policies`）

每条记录为一个 chunk：

```
{
  "id": "<doc_id>_<chunk_index>",
  "document": "<chunk 文本>",
  "embedding": [...],  # Qwen text-embedding-v2, 1024d
  "metadata": {
    "doc_id": "<document.id>",
    "title": "<文档标题>",
    "source_type": "policy|rule|faq|other",
    "chunk_index": 0,
    "chunk_total": 10
  }
}
```

### User 表改造

新增 `is_admin` 列：`sa.Column('is_admin', sa.Boolean(), nullable=False, default=False)`

JWT payload 新增 `"is_admin": true/false`。

## API 设计

### 图书管理（需 admin 权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/admin/books` | 分页列表，支持 `?q=&category=&offset=&limit=` |
| `GET` | `/api/v1/admin/books/{id}` | 单条详情 |
| `POST` | `/api/v1/admin/books` | 新增图书 |
| `PUT` | `/api/v1/admin/books/{id}` | 更新图书 |
| `DELETE` | `/api/v1/admin/books/{id}` | 删除图书 |
| `POST` | `/api/v1/admin/books/import` | 批量导入 |

批量导入支持两种格式：
- `Content-Type: application/json` — `{"items": [{...}, {...}]}`
- `Content-Type: multipart/form-data` — CSV 文件上传，自动解析

### 文档管理（需 admin 权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/admin/documents` | 文档列表 |
| `POST` | `/api/v1/admin/documents` | 上传 Markdown → chunk → embed → ChromaDB |
| `DELETE` | `/api/v1/admin/documents/{id}` | 删除文档 + ChromaDB 对应 chunks |

Chunk 策略：按 `\n## ` 分节，每节作为一个 chunk；超过 2000 字符的节再按 1000 字符重叠切割。

### 改造现有接口

| 方法 | 路径 | 变化 |
|------|------|------|
| `GET` | `/api/v1/books` | 从 stub → 真实 DB 查询，支持 `?q=&category=&offset=&limit=` |

### Auth 改造

- JWT `encode` 从 User 对象读取 `is_admin`，写入 payload
- JWT `decode` 提取 `is_admin` claim
- 新增 `require_admin` → 检查 `current_user.is_admin`，非 admin 返回 403

## Embedder 设计

`app/agents/retrieval/embedder.py`：

```python
class QwenEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-v2"):
        ...
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """调用 DashScope API，返回 1024d 向量"""
    async def embed_single(self, text: str) -> list[float]:
        """单个文本嵌入便捷方法"""
```

配置从 `.env` 读取 `DASHSCOPE_API_KEY`。

## 改造 ChromaDBRetriever

新增方法：

```python
def add_documents(self, chunks: list[dict]):
    """写入 chunks 到 collection — 每个 chunk 含 id/document/metadata"""

def delete_by_doc_id(self, doc_id: str):
    """按 doc_id 前缀删除对应 chunks"""
```

`add_documents` 用 `collection.upsert()`，方便重新索引覆盖。

## 种子数据

`scripts/seed.py` 扩展：
- 创建默认 admin 用户（`admin/admin123`）
- 按顺序：user → floor → zone → seat → book（插入 20 条示例图书）
- 可选：调用 `doc_service` 或 `chroma_retriever.add_documents` 初始化示例政策文档

## 测试

| 模块 | 测试内容 | 预估数量 |
|------|----------|----------|
| `test_book_model` | Book 模型 CRUD | 3 |
| `test_book_service` | 分页、搜索、批量导入逻辑 | 6 |
| `test_admin_book_api` | admin CRUD + 批量导入 API + 权限校验 | 8 |
| `test_admin_doc_api` | 文档上传/删除 API | 4 |
| `test_book_router` | 公开图书搜索（真实数据） | 3 |
| `test_security_admin` | JWT is_admin claim + deps 校验 | 3 |
| `test_embedder` | embed 调用 mock | 2 |
| `test_chroma_retriever` | add_documents + delete + search 联动 | 4 |
| `test_seed_books` | seed 脚本输出验证 | 1 |
| **合计** | | **~34 tests** |

## 已知依赖

- `chromadb` 已在 `pyproject.toml` 中
- `openai` SDK（DashScope 兼容接口）用于 embedding
- 新增 Alembic migration（`books` + `documents` 表 + `users.is_admin` 列）
- 不需要新增外部服务，ChromaDB 用 `PersistentClient` 本地持久化

## 不在范围内

- 真实 LLMClient（对话用 MiniMax/DeepSeek）— 仍用 RuleBasedLLMClient
- 读者画像（`profile_query`）— Phase 3 后续子阶段
- MCP Server — Phase 3 后续子阶段
- 可观测性（OpenTelemetry）— Phase 3 后续子阶段
- Ragas 评估 — Phase 3 后续子阶段
