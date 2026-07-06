# Scaffold 学习路线

## 总览

Scaffold 核心代码共 **7 个文件，约 300 行**，按以下顺序学习即可掌握 LangGraph 的核心模式。

```
graph.py   ← 编排层，定义节点顺序和路由规则
  ├── state.py     ← 数据契约，定义所有节点共享的字段
  ├── nodes.py     ← 执行层，每个节点的具体逻辑
  │     ├── adapters/llm.py  ← LLM 接口（可替换）
  │     ├── tools.py          ← 检索工具接口（可替换）
  │     └── memory/store.py   ← 记忆存储接口（可替换）
  └── config.py    ← 配置加载

workflow_service.py  ← 组装 + 启动
```

---

## 第 1 步：`research_agents/state.py` — 理解"共享状态"

**知识点**：LangGraph 中所有节点通过一个共享字典 `ResearchState` 传递数据。每个节点读 state 中的字段，返回要更新的字段，LangGraph 自动合并。

**关键细节**：

- 普通字段（如 `intent: str`）是**覆盖更新**
- `Annotated[list[str], operator.add]` 标记的字段是**追加更新**，用于 `messages`
- `create_initial_state()` 工厂函数为所有字段提供初始值

**文件**：`app/research_agents/state.py`

---

## 第 2 步：`research_agents/graph.py` — 理解"编排"

**知识点**：`StateGraph` = 节点集合 + 边集合 + 条件路由函数。这是整个系统最重要的文件（58 行）。

**核心概念**：

| 概念 | 代码 | 含义 |
|------|------|------|
| 创建图 | `StateGraph(ResearchState)` | 指定共享状态的类型 |
| 添加节点 | `graph.add_node("name", func)` | 注册一个执行节点 |
| 固定边 | `graph.add_edge(A, B)` | A 执行完一定去 B |
| 条件边 | `graph.add_conditional_edges(A, fn, mapping)` | A 执行完，调用 fn(state) 决定去哪个节点 |
| 编译 | `graph.compile()` | 生成可执行的图 |

**图结构**：

```
START
  │
  ▼
[intent] ── "direct" ──→ [direct_answer] ──→ END
  │
  "research"
  ▼
[plan] ──┬──→ [web_search] ──┐
          │                    │
          └──→ [local_rag]  ──┤
                               ▼
                      [evidence_judge]
                               │
                               ▼
                          [analyze] ── has gaps ──→ [reflect] ──→ web_search + local_rag
                               │
                           no gaps
                               │
                               ▼
                           [write] ──→ END
```

**两个路由函数（理解条件分支的关键）**：

```python
# 路由 1：意图决定走直接回答还是深度调研
def _route_after_intent(state):
    return "direct" if state.get("intent") == "direct" else "research"

# 路由 2：有缺口 + 未超迭代上限 → 补搜；否则 → 写报告
def _route_after_analysis(state):
    if state.get("missing_gaps") and state.get("iteration", 0) < state.get("max_iterations", 1):
        return "reflect"
    return "write"
```

**文件**：`app/research_agents/graph.py`

---

## 第 3 步：`research_agents/nodes.py` — 理解"节点怎么读/写状态"

**知识点**：每个节点函数签名都是 `(state: ResearchState, context: NodeContext) → 部分状态更新`。

**所有 9 个节点遵循相同模式**：读 state 的输入字段 → 调用 LLM/工具 → 返回要更新的字段字典。

**`NodeContext`**（依赖注入容器）：把 config、llm、tools、memory 打包传入，避免在每个节点里硬编码依赖。

**值得关注的两个细节**：

1. **`reflect_node` 的迭代保护**：`iteration + 1` + `missing_gaps = []`，防止死循环
2. **`_queries_for_source`**：补搜轮次优先用 `supplementary_queries`，否则用初始 `search_plan`

**文件**：`app/research_agents/nodes.py`

---

## 第 4 步：`research_agents/adapters/llm.py` — 理解"可插拔 LLM"

**知识点**：`LLMClient` 是一个 **Protocol**（鸭子类型），不要求继承，只要实现了 7 个方法就能替换。

**7 个方法对应 7 个节点的 LLM 调用**：

| 方法 | 对应节点 | 做什么 |
|------|---------|--------|
| `classify_intent(query)` | intent | 判断是闲聊还是调研 |
| `answer_direct(query)` | direct_answer | 直接回答 |
| `plan_research(query)` | plan | 拆解问题、生成搜索计划 |
| `judge_evidence(query, records)` | evidence_judge | 证据评分去重 |
| `analyze(query, evidence)` | analyze | 形成结论、找出缺口 |
| `reflect(query, gaps)` | reflect | 生成补搜计划 |
| `write_report(query, findings, sources)` | write | 撰写最终报告 |

**默认 `RuleBasedLLMClient`**：纯规则引擎，不调任何 API，保证零依赖可运行。

**迁移时只需**：保持方法签名不变，内部换成 `openai.chat.completions.create(...)`。graph 和 nodes 完全不用改。

**文件**：`app/research_agents/adapters/llm.py`

---

## 第 5 步：`research_agents/tools.py` — 理解"可插拔检索"

**知识点**：`SearchTools` 是一个 dataclass，封装 `search_web()` 和 `search_local()` 两个检索接口。

默认 stub 实现返回假数据，替换时接入 Bocha API / Google Search / Milvus。

**文件**：`app/research_agents/tools.py`

---

## 第 6 步：`research_agents/config.py` — 理解"配置加载"

**知识点**：`ResearchConfig` 是 frozen dataclass，`from_file()` 支持 config.json + 环境变量双重加载，`with_overrides()` 支持请求级参数覆盖。

**文件**：`app/research_agents/config.py`

---

## 第 7 步：`backend/service/workflow_service.py` — 理解"怎么跑起来"

**知识点**：FastAPI 和 LangGraph 之间的桥梁。展示了完整的执行流程：

```
1. 组装 NodeContext（把所有可插拔组件拼一起）
2. build_graph(context) → 构建 StateGraph
3. create_initial_state(...) → 创建初始状态
4. app.invoke(state, config) → 执行图
5. result["final"] → 拿最终报告
```

**两种执行模式**：

| 模式 | 方法 | 适用场景 |
|------|------|---------|
| 同步 | `app.invoke(state, config)` | 一次性执行，返回完整结果 |
| 流式 | `app.stream(state, config, stream_mode="updates")` | 逐个节点推送进度，用于 SSE |

**文件**：`app/backend/service/workflow_service.py`

---

## 进阶：对比学习

掌握 scaffold 后，对比学习另外两个项目：

| 项目 | LangGraph 模式 | 新增知识点 |
|------|---------------|-----------|
| **scaffold** | 线性流水线 + 条件循环 | 基础 StateGraph |
| **deep_research** | 同样的图结构 | 真实 LLM、PostgreSQL/Redis/Milvus 三级记忆、checkpointer 断点续传 |
| **cloud_agent** | 中心路由 + 子 Agent 分发 | ReAct Agent、MCP 协议、跨 Agent State Handoff |

---

## 核心公式

```
LangGraph 应用 = StateGraph(共享State)
               + add_node(name, fn) × N   ← 节点：读 state → 处理 → 返回更新
               + add_edge(A, B)           ← 固定边
               + add_conditional_edges    ← 条件边：fn(state) → next_node
               + compile()                ← 编译
               + invoke(state, config)    ← 执行
```

---

## 补充：深入理解"可插拔"

### LLM 可插拔

`LLMClient` 是一个 **Protocol**（鸭子类型），定义"做什么"，不定义"怎么做"：

```
          ┌──────────────────────────┐
          │  LLMClient (Protocol)    │  ← 接口约定：7 个方法签名
          └──────┬───────────────────┘
                 │
    ┌────────────┼────────────────┐
    ▼            ▼                ▼
RuleBased    QwenClient     OpenAIClient    ← 随便换，graph/nodes 一行不改
(当前默认)   (你写)           (你写)
```

**RuleBasedLLMClient 怎么工作的？** 纯关键词匹配，零 API 依赖：

```python
# 判断意图：query 里含 research/compare/trend → 走调研流程，否则直接回答
def classify_intent(self, query: str) -> str:
    research_markers = {"research", "compare", "market", "trend", ...}
    return "research" if any(marker in query.lower() for marker in research_markers) else "direct"

# 生成搜索计划：返回固定的模板结构
def plan_research(self, query: str) -> dict:
    return {"summary": f"Research plan for: {query}", "sub_questions": [...], "search_plan": [...]}

# 写报告：拼字符串，不调任何 LLM
def write_report(self, query, findings, sources) -> str:
    lines = [f"# Research Result: {query}", "", "## Findings", ...]
    return "\n".join(lines)
```

**迁移到真实 LLM 时**：保持方法名和参数不变，内部改成 `openai.chat.completions.create(...)` 或 `qwen.call(...)`。graph 和 nodes **一行不改**。

### Tools 可插拔

同样模式，`SearchTools` 当前返回假数据：

```python
def search_web(self, query: str, limit: int = 5) -> list[dict]:
    # 不调任何搜索引擎，直接返回占位数据
    return [{"source_id": f"WEB-{idx}", "snippet": f"Placeholder for: {query}"} for idx in range(1, limit+1)]
```

替换时接入 Tavily API / Bocha API / Google Search / Milvus 向量库——只要保持 `search_web(query, limit) → list[dict]` 签名不变即可。

### 一句话总结

> **定义好"做什么"（Protocol / 方法签名），具体"怎么做"可以随时换，系统其余部分不受影响。**

这就是为什么 scaffold 不需要任何 API Key 也能跑通——所有外部依赖都是可插拔的 stub 实现。
