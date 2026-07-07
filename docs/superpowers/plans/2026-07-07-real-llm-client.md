# 真实 LLMClient 接入 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 MiniMax + DeepSeek 真实 LLM 替换 `RuleBasedLLMClient` 的 5 个图书馆核心方法（意图分类、参数提取、回复格式化），MiniMax 主力、DeepSeek 兜底、规则引擎终极兜底。

**Architecture:** 新建 `app/agents/llm/client.py` 包含 `RealLLMClient` 类，内部通过 openai SDK 同步 API 调用 LLM，失败自动降级。`ChatService` 改为优先使用 `RealLLMClient`，API Key 缺失时回退 `RuleBasedLLMClient`。

**Tech Stack:** Python, openai SDK (已安装), MiniMax API (OpenAI 兼容), DeepSeek API (OpenAI 兼容)

---

## 文件结构

```
app/agents/
├── llm.py                  ← 不动（LLMClient Protocol + RuleBasedLLMClient）
├── llm/                     ← 新增包
│   ├── __init__.py          ← 导出 RealLLMClient
│   ├── client.py            ← RealLLMClient + prompts
app/backend/
├── config/
│   └── settings.py          ← 修改：新增 MINIMAX/DEEPSEEK 配置字段
└── service/
    └── chat_service.py      ← 修改：优先实例化 RealLLMClient
tests/
└── test_real_llm_client.py  ← 新增：RealLLMClient 单元测试
```

---

### Task 1: 在 AppSettings 中新增 MiniMax/DeepSeek 配置字段

**Files:**
- Modify: `app/backend/config/settings.py`

- [ ] **Step 1: 新增字段**

在 `AppSettings` 类中添加 6 个字段，紧跟 `embedding_model` 之后：

```python
# settings.py:29 之后新增
minimax_api_key: str = ""
minimax_base_url: str = "https://api.minimax.chat/v1"
minimax_model: str = "MiniMax-M3"
deepseek_api_key: str = ""
deepseek_base_url: str = "https://api.deepseek.com"
deepseek_model: str = "deepseek-v4-flash"
```

- [ ] **Step 2: 验证配置加载**

```bash
cd D:/Agent-Project/deep_research_scaffold
uv run python -c "from backend.config.settings import get_settings; s=get_settings(); print(s.minimax_model, s.deepseek_model)"
```

Expected: `MiniMax-M3 deepseek-v4-flash`

- [ ] **Step 3: 提交**

```bash
git add app/backend/config/settings.py
git commit -m "feat: add MiniMax/DeepSeek config fields to AppSettings"
```

---

### Task 2: 编写 RealLLMClient 测试（mock 驱动）

**Files:**
- Create: `tests/test_real_llm_client.py`

- [ ] **Step 1: 编写测试文件**

```python
"""RealLLMClient 单元测试 — mock OpenAI SDK"""

import json
from unittest.mock import MagicMock, patch

import pytest
from agents.llm import RuleBasedLLMClient
from agents.llm.client import RealLLMClient, _call_with_fallback


# ─── mock factory helpers ───

def _mock_openai_client(**kwargs):
    """Create a mock OpenAI client whose .chat.completions.create() returns kwargs."""
    mock = MagicMock()
    mock.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=kwargs.get("content", "")))],
    )
    return mock


def _failing_mock():
    """Create a mock that always raises."""
    mock = MagicMock()
    mock.chat.completions.create.side_effect = RuntimeError("API down")
    return mock


# ─── _call_with_fallback ───

class TestCallWithFallback:
    """测试 MiniMax → DeepSeek → raise 的切换链路"""

    def test_primary_succeeds_returns_parsed(self):
        primary = _mock_openai_client(content="search_book")
        secondary = _mock_openai_client(content="should_not_be_used")

        result = _call_with_fallback(
            primary=primary,
            primary_model="MiniMax-M3",
            secondary=secondary,
            secondary_model="deepseek-v4-flash",
            system_prompt="classify",
            user_message="有没有《三体》",
            parser=str.strip,
        )
        assert result == "search_book"
        primary.chat.completions.create.assert_called_once()
        secondary.chat.completions.create.assert_not_called()

    def test_primary_fails_secondary_succeeds(self):
        primary = _failing_mock()
        secondary = _mock_openai_client(content="search_book")

        result = _call_with_fallback(
            primary=primary,
            primary_model="MiniMax-M3",
            secondary=secondary,
            secondary_model="deepseek-v4-flash",
            system_prompt="classify",
            user_message="有没有《三体》",
            parser=str.strip,
        )
        assert result == "search_book"
        primary.chat.completions.create.assert_called_once()
        secondary.chat.completions.create.assert_called_once()

    def test_both_fail_raises_runtime_error(self):
        primary = _failing_mock()
        secondary = _failing_mock()

        with pytest.raises(RuntimeError, match="All LLM backends failed"):
            _call_with_fallback(
                primary=primary,
                primary_model="MiniMax-M3",
                secondary=secondary,
                secondary_model="deepseek-v4-flash",
                system_prompt="classify",
                user_message="test",
                parser=str.strip,
            )

    def test_parser_transforms_output(self):
        """验证 parser 函数的转换作用"""
        primary = _mock_openai_client(content='{"date":"today","slot":"morning"}')

        result = _call_with_fallback(
            primary=primary,
            primary_model="MiniMax-M3",
            secondary=MagicMock(),
            secondary_model="deepseek-v4-flash",
            system_prompt="extract",
            user_message="今天上午有座位吗",
            parser=json.loads,
        )
        assert result == {"date": "today", "slot": "morning"}


# ─── RealLLMClient 方法测试 ───

@pytest.fixture
def fallback():
    return RuleBasedLLMClient()


class TestClassifyLibraryIntent:
    """意图分类 — 走 LLM，失败回退规则引擎"""

    def test_llm_succeeds(self, fallback):
        primary = _mock_openai_client(content="search_book")
        secondary = MagicMock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.classify_library_intent("有没有《三体》")
        assert result == "search_book"

    def test_llm_fails_reverts_to_fallback(self, fallback):
        primary = _failing_mock()
        secondary = _failing_mock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.classify_library_intent("有没有《三体》")
        # 规则引擎输出
        assert result == "search_book"


class TestExtractBookingParams:
    """参数提取 — 走 LLM，失败回退规则引擎"""

    def test_llm_succeeds(self, fallback):
        primary = _mock_openai_client(content='{"date":"today","slot":"morning","floor":2}')
        secondary = MagicMock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.extract_booking_params("今天上午2楼有座位吗")
        assert result == {"date": "today", "slot": "morning", "floor": 2}

    def test_llm_returns_bad_json_reverts_to_fallback(self, fallback):
        """LLM 返回非 JSON → parser 抛异常 → 整个链路失败 → 走 fallback"""
        primary = _mock_openai_client(content="not json")
        secondary = _failing_mock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.extract_booking_params("今天上午2楼")
        # fallback 返回的 dict
        assert isinstance(result, dict)


class TestExtractCancelParams:
    """取消参数提取 — 走 LLM，失败回退规则引擎"""

    def test_llm_succeeds(self, fallback):
        primary = _mock_openai_client(content='{"query":"取消座位"}')
        secondary = MagicMock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.extract_cancel_params("取消我的预约")
        assert result == {"query": "取消座位"}

    def test_llm_fails_reverts_to_fallback(self, fallback):
        primary = _failing_mock()
        secondary = _failing_mock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.extract_cancel_params("取消")
        assert isinstance(result, dict)


class TestFormatLibraryResponse:
    """检索结果格式化 — 走 LLM"""

    def test_llm_succeeds(self, fallback):
        primary = _mock_openai_client(content="为您找到《三体》，位于3楼A区")
        secondary = MagicMock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        docs = [{"content": "三体", "metadata": {"title": "三体", "source": "book"}}]
        result = client.format_library_response("search_book", "有没有《三体》", docs)
        assert len(result) > 0

    def test_llm_fails_reverts_to_fallback(self, fallback):
        primary = _failing_mock()
        secondary = _failing_mock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        docs = [{"content": "三体", "metadata": {"title": "三体"}}]
        result = client.format_library_response("search_book", "有没有《三体》", docs)
        assert "三体" in result


class TestFormatReservationResponse:
    """预约结果格式化 — 走 LLM"""

    def test_llm_succeeds(self, fallback):
        primary = _mock_openai_client(content="预约成功！您已预约2楼A区座位3，时段：上午")
        secondary = MagicMock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.format_reservation_response(
            "book_seat",
            {"floor_name": "2楼", "zone_name": "A区", "seat_number": "3", "date": "今天", "slot": "morning"},
        )
        assert len(result) > 0

    def test_llm_fails_reverts_to_fallback(self, fallback):
        primary = _failing_mock()
        secondary = _failing_mock()
        client = RealLLMClient(
            primary_client=primary,
            primary_model="MiniMax-M3",
            secondary_client=secondary,
            secondary_model="deepseek-v4-flash",
            fallback=fallback,
        )
        result = client.format_reservation_response(
            "book_seat",
            {"floor_name": "2楼", "zone_name": "A区", "seat_number": "3", "date": "今天", "slot": "morning"},
        )
        assert "预约成功" in result


class TestDelegatedMethods:
    """非替换方法委托给 RuleBasedLLMClient"""

    def test_classify_intent_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.classify_intent("compare market trends")
        assert result == "research"

    def test_answer_direct_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.answer_direct("hello")
        assert "hello" in result

    def test_plan_research_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.plan_research("AI trends")
        assert "sub_questions" in result

    def test_judge_evidence_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.judge_evidence("test", [{"a": 1}])
        assert len(result) == 1
        assert result[0]["relevance_score"] == 0.75

    def test_analyze_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.analyze("test", [])
        assert result["findings"]

    def test_reflect_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.reflect("test", ["gap1"])
        assert len(result) == 1

    def test_write_report_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.write_report("test", [], [])
        assert "# Research Result" in result

    def test_stub_message_delegates(self, fallback):
        client = RealLLMClient(
            primary_client=MagicMock(),
            primary_model="M",
            secondary_client=MagicMock(),
            secondary_model="D",
            fallback=fallback,
        )
        result = client.stub_message("profile_query")
        assert "开发中" in result
```

- [ ] **Step 2: 运行测试验证全红（`module not found`）**

```bash
cd D:/Agent-Project/deep_research_scaffold
uv run pytest tests/test_real_llm_client.py -v 2>&1
```

Expected: `ModuleNotFoundError: No module named 'agents.llm.client'`

- [ ] **Step 3: 提交（仅测试文件）**

```bash
git add tests/test_real_llm_client.py
git commit -m "test: add RealLLMClient unit tests (red)"
```

---

### Task 3: 实现 RealLLMClient

**Files:**
- Create: `app/agents/llm/__init__.py`
- Create: `app/agents/llm/client.py`

- [ ] **Step 1: 创建包 `__init__.py`**

```python
from .client import RealLLMClient

__all__ = ["RealLLMClient"]
```

- [ ] **Step 2: 编写 `client.py`**

```python
"""RealLLMClient — MiniMax 主力 + DeepSeek 兜底 + 规则引擎终极兜底"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypeVar

from agents.llm import LLMClient, RuleBasedLLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ─── System Prompts ───

CLASSIFY_INTENT_PROMPT = """你是一个图书馆智能助手的意图分类器。根据用户输入，判断用户意图，只输出以下标签之一（不要输出任何其他文字）：

标签说明及示例：
- search_book: 检索/查找某本具体图书（如 "有没有《三体》"、"帮我找一下Python入门"）
- recommend_book: 请求推荐图书（如 "推荐几本小说"、"有什么好书"）
- policy_query: 咨询图书馆政策/规则（如 "几点开门"、"借书规则是什么"）
- book_seat: 预约座位（如 "我要预约座位"、"帮我订个座"）
- query_appointment: 查询已有预约（如 "我的预约记录"、"查一下我的预约"）
- cancel_appointment: 取消预约（如 "取消我的预约"、"把预约删了"）
- profile_query: 查询个人记录/画像（如 "我的借阅记录"、"我借了哪些书"）
- greeting: 问候/寒暄（如 "你好"、"早上好"）
- other: 以上都不匹配"""

EXTRACT_BOOKING_PROMPT = """你是一个图书馆座位预约参数提取器。从用户消息中提取预约参数，只输出 JSON（不要输出其他文字）。

参数说明：
- date: "today" / "tomorrow" / "day_after_tomorrow"，未提到默认 "today"
- slot: "morning" / "afternoon" / "evening"，未提到不填
- floor: 楼层数字，如 1、2、3，未提到不填

输出格式示例：
{"date": "today", "slot": "morning", "floor": 2}
{"date": "tomorrow", "slot": "afternoon"}"""

EXTRACT_CANCEL_PROMPT = """你是一个图书馆预约取消参数提取器。从用户消息中提取取消相关参数，只输出 JSON（不要输出其他文字）。

输出格式示例：
{"appointment_id": "uuid-if-present", "seat_info": "if-mentioned"}"""

FORMAT_LIBRARY_RESPONSE_PROMPT = """你是一个友好的图书馆助手。根据检索到的图书/政策信息，用自然语言回答用户的问题。
要求：
- 用中文回复
- 语气友好、自然
- 如果检索结果为空，礼貌地告知用户并建议换关键词
- 如果有多条结果，列出前几条并引导用户进一步筛选"""

FORMAT_RESERVATION_RESPONSE_PROMPT = """你是一个友好的图书馆助手。根据预约操作结果，用自然语言回复用户。
要求：
- 用中文回复
- 预约成功时：恭喜并重申关键信息（楼层、区域、座位号、日期、时段）
- 取消成功时：确认已取消
- 查询时：列出预约记录"""


# ─── 核心函数 ───

def _call_with_fallback(
    *,
    primary: Any,
    primary_model: str,
    secondary: Any,
    secondary_model: str,
    system_prompt: str,
    user_message: str,
    parser: Callable[[str], T],
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> T:
    """MiniMax → DeepSeek → raise RuntimeError"""
    for client, model in [(primary, primary_model), (secondary, secondary_model)]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content
            return parser(raw)
        except Exception as exc:
            logger.warning(f"LLM call failed ({model}): {exc}")

    raise RuntimeError("All LLM backends failed")


# ─── RealLLMClient ───

class RealLLMClient:
    """真实 LLM 客户端 — MiniMax 主力 + DeepSeek 兜底 + RuleBasedLLMClient 终极兜底

    实例化需要两个已配置的 OpenAI client 对象。
    未被替换的 8 个方法委托给 RuleBasedLLMClient。
    """

    def __init__(
        self,
        *,
        primary_client: Any,
        primary_model: str,
        secondary_client: Any,
        secondary_model: str,
        fallback: RuleBasedLLMClient,
    ):
        self._primary = primary_client
        self._primary_model = primary_model
        self._secondary = secondary_client
        self._secondary_model = secondary_model
        self._fallback = fallback

    # === 图书馆方法（替换为 LLM） ===

    def classify_library_intent(self, query: str) -> str:
        try:
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=CLASSIFY_INTENT_PROMPT,
                user_message=query,
                parser=lambda s: s.strip().lower(),
                temperature=0.1,
                max_tokens=16,
            )
        except RuntimeError:
            logger.warning("Intent classification LLM failed, using rule-based fallback")
            return self._fallback.classify_library_intent(query)

    def extract_booking_params(self, query: str) -> dict:
        try:
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=EXTRACT_BOOKING_PROMPT,
                user_message=query,
                parser=_parse_json_or_empty,
                temperature=0.1,
            )
        except RuntimeError:
            logger.warning("Booking param extraction LLM failed, using rule-based fallback")
            return self._fallback.extract_booking_params(query)

    def extract_cancel_params(self, query: str) -> dict:
        try:
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=EXTRACT_CANCEL_PROMPT,
                user_message=query,
                parser=_parse_json_or_empty,
                temperature=0.1,
            )
        except RuntimeError:
            logger.warning("Cancel param extraction LLM failed, using rule-based fallback")
            return self._fallback.extract_cancel_params(query)

    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str:
        try:
            docs_text = json.dumps(
                [
                    {
                        "content": d.get("content", ""),
                        "title": d.get("metadata", {}).get("title", ""),
                        "source": d.get("metadata", {}).get("source", ""),
                    }
                    for d in docs
                ],
                ensure_ascii=False,
            )
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=FORMAT_LIBRARY_RESPONSE_PROMPT,
                user_message=f"用户问题：{query}\n\n检索结果：\n{docs_text}",
                parser=str.strip,
                temperature=0.3,
                max_tokens=512,
            )
        except RuntimeError:
            logger.warning("Format library response LLM failed, using rule-based fallback")
            return self._fallback.format_library_response(intent, query, docs)

    def format_reservation_response(self, intent: str, result: dict) -> str:
        try:
            result_text = json.dumps(result, ensure_ascii=False)
            return _call_with_fallback(
                primary=self._primary,
                primary_model=self._primary_model,
                secondary=self._secondary,
                secondary_model=self._secondary_model,
                system_prompt=FORMAT_RESERVATION_RESPONSE_PROMPT,
                user_message=f"意图：{intent}\n\n操作结果：\n{result_text}",
                parser=str.strip,
                temperature=0.3,
                max_tokens=512,
            )
        except RuntimeError:
            logger.warning("Format reservation response LLM failed, using rule-based fallback")
            return self._fallback.format_reservation_response(intent, result)

    # === 委托给 RuleBasedLLMClient 的方法 ===

    def classify_intent(self, query: str) -> str:
        return self._fallback.classify_intent(query)

    def answer_direct(self, query: str, memory_context: str = "") -> str:
        return self._fallback.answer_direct(query, memory_context)

    def plan_research(self, query: str) -> dict:
        return self._fallback.plan_research(query)

    def judge_evidence(self, query: str, records: list[dict]) -> list[dict]:
        return self._fallback.judge_evidence(query, records)

    def analyze(self, query: str, evidence: list[dict]) -> dict:
        return self._fallback.analyze(query, evidence)

    def reflect(self, query: str, missing_gaps: list[str]) -> list[dict]:
        return self._fallback.reflect(query, missing_gaps)

    def write_report(self, query: str, findings: list[dict], sources: list[dict]) -> str:
        return self._fallback.write_report(query, findings, sources)

    def stub_message(self, intent: str) -> str:
        return self._fallback.stub_message(intent)


# ─── 内部辅助 ───

def _parse_json_or_empty(raw: str) -> dict:
    """将 LLM 输出解析为 dict，失败返回空 dict"""
    raw = raw.strip()
    # 处理 ```json ... ``` 包裹的情况
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON from LLM output: {raw[:200]}")
        return {}
```

- [ ] **Step 3: 运行测试看多少变绿**

```bash
cd D:/Agent-Project/deep_research_scaffold
uv run pytest tests/test_real_llm_client.py -v 2>&1
```

Expected: 15+ tests PASS (all unit tests with mocks should pass)

- [ ] **Step 4: 提交**

```bash
git add app/agents/llm/
git commit -m "feat: add RealLLMClient with MiniMax+DeepSeek fallback chain"
```

---

### Task 4: 修改 ChatService 使用 RealLLMClient

**Files:**
- Modify: `app/backend/service/chat_service.py`

- [ ] **Step 1: 修改 `_ensure_initialized` 方法**

将 `llm=RuleBasedLLMClient()` 改为工厂函数，API Key 存在时优先使用 `RealLLMClient`：

```python
# chat_service.py 顶部新增 import
from agents.llm.client import RealLLMClient
from agents.llm import RuleBasedLLMClient
from backend.config.settings import get_settings
from openai import OpenAI


def _create_llm_client() -> RuleBasedLLMClient | RealLLMClient:
    """工厂：API Key 存在时创建 RealLLMClient，否则回退 RuleBasedLLMClient"""
    settings = get_settings()
    if settings.minimax_api_key and settings.deepseek_api_key:
        try:
            primary = OpenAI(
                api_key=settings.minimax_api_key,
                base_url=settings.minimax_base_url,
            )
            secondary = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            return RealLLMClient(
                primary_client=primary,
                primary_model=settings.minimax_model,
                secondary_client=secondary,
                secondary_model=settings.deepseek_model,
                fallback=RuleBasedLLMClient(),
            )
        except Exception:
            pass  # 配置有问题，回退规则引擎
    return RuleBasedLLMClient()
```

然后将 `ChatService._ensure_initialized` 中的：

```python
llm=RuleBasedLLMClient(),
```

改为：

```python
llm=_create_llm_client(),
```

- [ ] **Step 2: 验证现有测试仍通过**

```bash
cd D:/Agent-Project/deep_research_scaffold
uv run pytest tests/test_library_graph.py tests/test_chat_api.py -v 2>&1
```

Expected: All tests pass (ChatService 在没有 API Key 时自动回退 RuleBasedLLMClient)

- [ ] **Step 3: 提交**

```bash
git add app/backend/service/chat_service.py
git commit -m "feat: use RealLLMClient in ChatService with auto-fallback"
```

---

### Task 5: 运行全量测试

- [ ] **Step 1: 运行全部测试**

```bash
cd D:/Agent-Project/deep_research_scaffold
uv run pytest tests/ -v 2>&1
```

Expected: All tests pass (real LLM tests + existing tests)

- [ ] **Step 2: 如有失败，修复问题后重新验证**

确认 `git status` 没有遗漏的修改。

- [ ] **Step 3: 提交（如有修改）**

```bash
git add -A
git commit -m "chore: final adjustments for RealLLMClient integration"
```
