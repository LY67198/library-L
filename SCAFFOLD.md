# Deep Research Scaffold — 深度调研脚手架模板

## 概述

Deep Research Scaffold 是从 `deep_research` 项目中提取的**干净架构模板**。它保留了完整的多智能体调研工作流骨架，但移除了特定 LLM provider（千问/DashScope）、外部服务依赖（Bocha Web Search、Milvus）和教学注释，使开发者可以快速替换为自己的 LLM、搜索引擎和向量数据库。

技术栈：**Python 3.10+ / FastAPI / LangGraph / Pydantic / Vue 3 + Vite**

---

## 核心功能

1. **完整的工作流骨架**：包含 intent → plan → web_search → local_rag → evidence_judge → analyze → reflect → write 全流程
2. **可插拔的 LLM 适配器**：通过 `LLMClient` 协议接口，替换为任何 LLM provider
3. **可插拔的检索工具**：通过 `SearchTools` 接口，接入任何搜索引擎和知识库
4. **可插拔的记忆存储**：通过 `MemoryStore` 接口，支持任意后端
5. **SSE 流式推送**：保留实时进度推送的前后端架构
6. **默认确定性实现**：无需 API Key 即可运行，使用规则引擎模拟各节点行为

---

## 架构

```
front/                       -- Vue 3 + Vite 前端
  └── src/                   -- 提交研究请求 & SSE 消费

app/
  ├── app_main.py            -- FastAPI 入口
  ├── backend/               -- Web 层
  │   ├── config/            -- 运行时设置
  │   ├── router/            -- health / research 端点
  │   ├── schemas/           -- 请求 & 响应模型
  │   └── service/           -- 工作流服务 & SSE 桥接
  └── research_agents/       -- 核心 Agent 引擎
      ├── config.py          -- 工作流配置加载
      ├── state.py           -- ResearchState 状态契约
      ├── graph.py           -- LangGraph 节点连线 & 路由
      ├── nodes.py           -- 节点实现
      ├── tools.py           -- 可插拔检索/搜索工具
      ├── adapters/          -- LLM 适配器协议 & 默认实现
      │   └── llm.py         -- LLMClient 接口 + RuleBasedLLMClient
      └── memory/            -- 记忆接口 & 内存实现
          └── store.py       -- MemoryStore 接口 + InMemoryMemoryStore
```

---

## 模块详解

### 1. 配置模块 (`backend/config/settings.py`)

FastAPI 运行时设置，包括应用名称、CORS 来源、host、port 等。

### 2. 状态定义 (`research_agents/state.py`)

定义了 LangGraph 工作流的共享状态结构 `ResearchState`，是跨所有节点传递数据的契约：

```
query, intent, plan, outline, sub_questions, research_questions
search_plan, web_search, local_rag, web_evidence, local_evidence
evidence_pool, audit_flags, analysis, needs_more_research
findings, source_index, draft, final, iteration, max_iterations
```

### 3. 工作流编排 (`research_agents/graph.py`)

基于 LangGraph `StateGraph` 构建完整工作流：

```
START
  → intent
    ├── direct_answer → END
    └── plan
        ├── web_search ──┐
        ├── local_rag  ──┤
        └────────→ evidence_judge
                     → analyze
                       ├── needs_more → reflect → web_search/local_rag ...
                       └── done → write → END
```

**路由条件**：
- `route_after_intent`: 根据意图路由到 direct_answer 或 plan
- `should_continue_research`: 根据迭代次数和证据完备性决定继续或写报告

### 4. 节点实现 (`research_agents/nodes.py`)

各个节点的具体实现，包含：
- `intent_node`: 意图识别
- `direct_answer_node`: 直接回答
- `plan_node`: 任务拆解与规划
- `web_search_node` / `local_rag_node`: 双通道证据采集
- `evidence_judge_node`: 证据审计与裁判
- `analyze_node`: 结论分析
- `reflect_node`: 补搜规划
- `write_node`: 报告撰写

默认实现使用 `RuleBasedLLMClient` 提供确定性输出，可通过替换适配器接入真实 LLM。

### 5. 工作流配置 (`research_agents/config.py`)

加载工作流参数：最大迭代轮数、预算限制、路由阈值等。

### 6. LLM 适配器 (`research_agents/adapters/llm.py`)

**扩展点 1**，定义了 `LLMClient` 协议接口：

```python
class LLMClient(Protocol):
    def invoke(self, prompt: str, **kwargs) -> str: ...
    async def ainvoke(self, prompt: str, **kwargs) -> str: ...
```

默认提供 `RuleBasedLLMClient`——不调用任何 API，使用规则引擎给出确定性输出。迁移时只需实现 `LLMClient` 协议，例如：

```python
class OpenAILLMClient:
    def invoke(self, prompt, **kwargs):
        return openai.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content
```

### 7. 可插拔搜索工具 (`research_agents/tools.py`)

**扩展点 2**，定义了 `SearchTools` 接口：

| 方法 | 说明 |
|------|------|
| `web_search(query, count)` | 网络搜索 |
| `local_rag(query, limit)` | 本地知识库/向量检索 |
| `get_tools()` | 返回 LangChain Tool 列表 |

默认提供基于内存的 stub 实现，替换时接入 Bocha API、Google Search、Milvus 等。

### 8. 记忆接口 (`research_agents/memory/store.py`)

**扩展点 3**，定义了 `MemoryStore` 接口：

| 方法 | 说明 |
|------|------|
| `save(user_id, key, data)` | 保存记忆 |
| `search(user_id, query, limit)` | 语义搜索记忆 |
| `get(user_id, key)` | 获取特定记忆 |

默认提供 `InMemoryMemoryStore`，可替换为 Redis、PostgreSQL、Milvus 等。

### 9. WorkflowService (`backend/service/workflow_service.py`)

FastAPI 应用与 LangGraph 工作流之间的桥梁：

- **run()**: 同步执行 → 返回最终报告
- **stream_events()**: 异步 SSE 流式推送 → 每个节点执行时发送进度事件

懒初始化 + 线程安全，首次请求时创建 Agent 实例。

### 10. API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/research/run` | POST | 同步执行调研 |
| `/api/v1/research/stream` | POST | SSE 流式调研 |

### 11. 前端 (`front/`)

Vue 3 + Vite 项目，Vite dev server 自动代理 `/api` 到后端 `http://127.0.0.1:8000`。

---

## 扩展指南

入手时按以下顺序替换默认实现：

| 优先级 | 扩展点 | 文件 | 工作内容 |
|--------|--------|------|----------|
| 1 | LLM | `adapters/llm.py` | 实现 `LLMClient`，替换 `RuleBasedLLMClient` |
| 2 | 搜索工具 | `tools.py` | 实现 `SearchTools`，接入真实搜索引擎 |
| 3 | 记忆存储 | `memory/store.py` | 实现 `MemoryStore`，接入 Redis/Postgres/Milvus |
| 4 | 状态字段 | `state.py` | 按需扩展 `ResearchState` |
| 5 | 路由逻辑 | `graph.py` | 调整条件路由条件 |

---

## 与 deep_research 的区别

| 维度 | deep_research | deep_research_scaffold |
|------|-------------|----------------------|
| LLM | 千问/DashScope (硬编码) | `LLMClient` 协议接口 |
| 搜索引擎 | Bocha Web Search | `SearchTools` 接口 |
| 向量数据库 | Milvus (硬编码) | `MemoryStore` 接口 |
| 记忆系统 | 完整的 Redis/PG/Milvus 三级记忆 | 简单的 InMemory 实现 |
| 工具集 | 20+ 工具函数 | 最小工具集 |
| 可运行性 | 需要 API Key + 多个外部服务 | 零依赖即可运行 |
| 代码量 | 大量（含业务逻辑） | 精简（仅骨架） |

---

## 快速启动

```bash
cd deep_research_scaffold
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 启动后端
cd app
uvicorn app_main:app --reload --port 8000

# 健康检查
curl http://127.0.0.1:8000/api/v1/health

# 测试调研
curl -X POST http://127.0.0.1:8000/api/v1/research/run \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare RAG and multi-agent research workflows"}'

# 启动前端
cd ../front
npm install && npm run dev
```
