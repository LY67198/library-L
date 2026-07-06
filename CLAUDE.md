# 图书馆智能服务系统 — 项目进度

## 项目概述

基于 `deep_research_scaffold`（FastAPI + LangGraph 脚手架）的图书馆智能服务系统。Phase 1 聚焦 AI 智能问答 + 馆藏检索。

## 仓库

- GitHub: https://github.com/LY67198/library-L.git
- Gitee: https://gitee.com/lingering-yesterday/library-l.git
- 分支: `main`（主分支）、`dev`（开发分支）

## 当前进度

**已完成:**

- [x] 脚手架导入（`deep_research_scaffold` 全部文件）
- [x] 清理脚手架冗余文件（`LEARNING_PATH.md`、`SCAFFOLD.md`、`*.egg-info/`）
- [x] Phase 1 设计文档 → `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- [x] Phase 1 实现计划 → `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
- [x] Phase 1 代码实现（32 tests passed）
- [x] README 重写为图书馆项目说明
- [x] `.env.example` 完善（DeepSeek + MiniMax + Qwen 嵌入/重排序）
- [x] Docker 部署配置

## LLM / 模型配置

| 厂商 | 用途 | 模型 |
|------|------|------|
| DeepSeek | 对话 | `deepseek-v4-flash` |
| MiniMax | 对话 | `MiniMax-M3` |
| Qwen (DashScope) | 嵌入 | `text-embedding-v2` (1024d) |
| Qwen (DashScope) | 重排序 | `qwen3-rerank` |

API Key 都在 `.env` 中配置（已 gitignore），模板见 `.env.example`。

## 核心设计决策

| 决策 | 选择 |
|------|------|
| Agent 编排 | LangGraph 显式编排，1 主图 + 1 检索子图 |
| LLM | 当前 `RuleBasedLLMClient` 扩展 9 分类，后续换 DeepSeek/MiniMax |
| 检索 | `Retriever` Protocol 插件化 — `ChromaDBRetriever` + `SQLBookLookup`（当前用 StubRetriever） |
| State | 新包 `agents/`，不侵入 `research_agents/` |
| 前端 | 脚手架 Vue 3 前端重写为对话界面 |
| 部署 | Docker Compose（FastAPI + PostgreSQL + Redis） |
| 依赖管理 | `uv`（pyproject.toml） |

## 9 种用户意图

`search_book` `recommend_book` `policy_query` `book_seat` `query_appointment` `cancel_appointment` `profile_query` `greeting` `other`

## 项目结构

```
app/
├── agents/               ← Phase 1 新建
│   ├── state.py          ← LibraryState
│   ├── graph.py          ← 主图 + retrieval 子图
│   ├── nodes.py          ← 9 节点 + LibraryNodeContext
│   ├── config.py         ← ChatConfig
│   └── retrieval/
│       ├── protocol.py   ← Retriever Protocol + StubRetriever
│       ├── chroma_retriever.py
│       └── sql_book_lookup.py
├── research_agents/      ← 脚手架原有（llm.py 扩展）
│   └── adapters/llm.py   ← LLMClient Protocol + RuleBasedLLMClient（9 分类）
└── backend/
    ├── router/
    │   ├── chat_router.py   ← 新增
    │   └── book_router.py   ← 新增
    ├── schemas/
    │   └── chat.py          ← 新增
    └── service/
        └── chat_service.py  ← 新增
tests/
├── test_intent_classification.py  ← 12 tests
├── test_library_graph.py          ← 14 tests
└── test_chat_api.py               ← 6 tests
```

## 下一步

1. 实现真实 LLMClient（接入 DeepSeek/MiniMax，替换 `RuleBasedLLMClient`）
2. 初始化 ChromaDB 知识库 + PostgreSQL 图书数据
3. Phase 2：用户系统 + 座位预约（Redis 分布式锁 + Celery）

## 关键文档

- 设计文档: `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- 实现计划: `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
