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
- [x] Phase 1 设计文档 → `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- [x] README 汉化
- [x] Phase 1 实现计划 → `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`（18 个 Task）
- [x] 代码实现（Phase 1 完成，32 tests passed）

## 核心设计决策

| 决策 | 选择 |
|------|------|
| Agent 编排 | LangGraph 显式编排，3 子图（检索域完整 + 预约/画像 stub） |
| LLM | `RuleBasedLLMClient` 扩展 9 分类，后续换真 LLM |
| 检索 | `Retriever` Protocol 插件化 — `ChromaDBRetriever` + `SQLBookLookup` |
| State | 新包 `library_agents/`，不侵入 `research_agents/` |
| 前端 | 基于脚手架 Vue 3 前端扩展对话界面 |
| 部署 | Docker Compose（FastAPI + PostgreSQL + Redis） |

## 9 种用户意图

`search_book` `recommend_book` `policy_query` `book_seat` `query_appointment` `cancel_appointment` `profile_query` `greeting` `other`

## 项目结构

```
app/
├── agents/                   ← Phase 1 新建（多 Agent 协作）
│   ├── state.py              ← LibraryState
│   ├── graph.py              ← 主图 + retrieval 子图
│   ├── nodes.py              ← 节点实现 + LibraryNodeContext
│   ├── config.py             ← ChatConfig
│   └── retrieval/
│       ├── protocol.py       ← Retriever Protocol + StubRetriever
│       ├── chroma_retriever.py
│       └── sql_book_lookup.py
├── research_agents/          ← 脚手架原有（llm.py 扩展 9 分类）
└── backend/
    ├── router/
    │   ├── chat_router.py   ← 新增（同步 + SSE 流式）
    │   └── book_router.py   ← 新增（馆藏检索）
    ├── schemas/
    │   └── chat.py          ← 新增（ChatRequest/Response）
    └── service/
        └── chat_service.py  ← 新增（Agent 组装 + SSE 桥接）
```

## 下一步

执行实现计划 `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`，按 18 个 Task 逐步落实代码。

## 关键文档

- 设计文档: `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- 实现计划: `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
- 脚手架学习: `LEARNING_PATH.md`
- 脚手架详解: `SCAFFOLD.md`
