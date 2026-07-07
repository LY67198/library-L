# 真实 LLMClient 接入 — 设计文档

## 概述

用 MiniMax + DeepSeek 提供的真实 LLM 替换 `RuleBasedLLMClient` 中 5 个图书馆核心方法，保留关键词规则引擎作为最终兜底。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 主力模型 | MiniMax（`MiniMax-M3`），OpenAI 兼容 API |
| 兜底模型 | DeepSeek（`deepseek-v4-flash`），OpenAI 兼容 API |
| 最终兜底 | `RuleBasedLLMClient` 关键词规则引擎 |
| SDK | `openai` Python SDK（已安装，与 `/llm.py` 一起使用） |
| 替换范围 | 5 个图书馆核心方法，深度调研 7 个方法保留规则引擎 |
| 协议兼容 | `LLMClient` Protocol 保持不变，节点代码无需修改 |

## 调用链

```
RealLLMClient.classify_library_intent(query)
  → MiniMax (Chat Completions)
  → 失败? → DeepSeek (Chat Completions)
  → 失败? → RuleBasedLLMClient（关键词/模板兜底）
```

## 代码结构变更

```
app/agents/
├── llm.py              ← 现有（LLMClient Protocol + RuleBasedLLMClient，不动）
├── llm/                 ← 新增包
│   ├── __init__.py      ← 导出 RealLLMClient
│   └── client.py        ← RealLLMClient + 内部辅助函数
```

## 替换的 5 个方法

| 方法 | 返回类型 | 策略 |
|------|----------|------|
| `classify_library_intent` | `str`（9 分类标签） | System prompt 定义 9 分类 + few-shot 示例，返回单个 intent 字符串 |
| `extract_booking_params` | `dict` | System prompt 说明 slot/date/floor 参数，返回 JSON |
| `extract_cancel_params` | `dict` | System prompt，返回 JSON |
| `format_library_response` | `str` | System prompt + 检索结果 doc list，格式化为用户可读文本 |
| `format_reservation_response` | `str` | System prompt + intent + result dict，格式化为自然语言回复 |

未被替换的 8 个方法（深度调研 7 个 + `answer_direct`）继续走 `RuleBasedLLMClient`。

## 核心接口

### `RealLLMClient`

```python
class RealLLMClient:
    """真实 LLM 客户端 — MiniMax 主力 + DeepSeek 兜底 + 规则引擎终极兜底"""

    def __init__(self, minimax_client, deepseek_client, fallback: RuleBasedLLMClient):
        self._primary = minimax_client       # OpenAI client (MiniMax)
        self._secondary = deepseek_client    # OpenAI client (DeepSeek)
        self._fallback = fallback            # RuleBasedLLMClient
        self._primary_model: str
        self._secondary_model: str

    # 被替换的 5 个方法：
    def classify_library_intent(self, query: str) -> str: ...
    def extract_booking_params(self, query: str) -> dict: ...
    def extract_cancel_params(self, query: str) -> dict: ...
    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str: ...
    def format_reservation_response(self, intent: str, result: dict) -> str: ...

    # 委托给 fallback 的方法（8 个）：
    def classify_intent(self, query: str) -> str: ...
    def answer_direct(self, query: str, memory_context: str = "") -> str: ...
    # ... 其余深度调研方法
```

### 内部执行层

`LLMClient` Protocol 所有方法均为同步，节点代码同步调用，因此 `real_llm_client` 内部使用 openai SDK 的**同步 API**。

```python
def _call_with_fallback(
    self,
    system_prompt: str,
    user_message: str,
    parser: Callable[[str], T],
    temperature: float = 0.1,
) -> T:
    """MiniMax → DeepSeek → raise RuntimeError"""

    for client, model in [(self._primary, self._primary_model),
                           (self._secondary, self._secondary_model)]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=1024,
            )
            return parser(resp.choices[0].message.content)
        except Exception:
            continue

    raise RuntimeError("All LLM backends failed")
```

格式类方法（`format_library_response`、`format_reservation_response`）传 `temperature=0.3`，分类/提取类传默认 `0.1`。

## System Prompts 设计要点

### classify_library_intent

- 定义 9 个意图标签：`search_book`, `recommend_book`, `policy_query`, `book_seat`, `query_appointment`, `cancel_appointment`, `profile_query`, `greeting`, `other`
- 每个标签附简短说明和 2 个示例
- 要求只输出标签名，不要额外文字

### extract_booking_params

- 说明输出 JSON 格式：`{"date": "...", "slot": "...", "floor": N}`
- date 字段要求返回 `today`/`tomorrow`/`day_after_tomorrow`，不解析具体日期
- slot 字段：`morning`/`afternoon`/`evening`

### extract_cancel_params

- 说明输出 JSON 格式，尝试提取 appointment_id 或座位信息

### format_library_response / format_reservation_response

- temperature 可以略高（0.3），让回复不千篇一律
- 强调用中文、友好语气

## 配置

复用现有 `.env` 变量，无需新增：

```
MINIMAX_API_KEY=sk-xxxxx
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-M3
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

`RealLLMClient` 的实例化在 `chat_service.py` 或 `ChatConfig` 初始化时完成，具体位置待实现计划确定。

## 不变的部分

- `LLMClient` Protocol — 不动
- `RuleBasedLLMClient` — 不动
- `LibraryNodeContext` — 不动，只需将 `llm` 字段指向 `RealLLMClient` 实例
- `nodes.py` — 不动，所有节点代码无需修改
- 深度调研 7 个方法 — 不动，`RealLLMClient` 委托给 `RuleBasedLLMClient`

## 测试策略

| 层级 | 测什么 | 怎么测 |
|------|--------|--------|
| 单元 | `_call_with_fallback` 链路切换 | mock OpenAI client，验证 MiniMax 失败→切 DeepSeek→切 fallback |
| 单元 | 5 个方法各自的 prompt 输入/解析输出 | mock `_call_with_fallback`，验证参数传递和返回值解析 |
| 单元 | LLM 全部失败时 fallback 生效 | mock 两个 client 都抛异常，验证返回 rule_based 结果 |
| 集成 | 意图分类准确性 | 选 10 条典型中文问句，断言 intent 标签匹配 |
| 不测 | MiniMax/DeepSeek 服务端行为 | 第三方服务，不测 |

## 不清算的内容

- 通用 LLM 重试/超时配置（不加复杂化，openai SDK 默认行为足够）
- 流式 LLM 调用（Phase 1 的 `/chat/stream` 暂不接入真实 LLM）
- Token 计数 / 成本监控（Phase 3 可观测性统一做）
- 深度调研 7 个方法的 LLM 替换（当前项目不需要）
