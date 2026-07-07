"""RealLLMClient 单元测试 — mock OpenAI SDK"""

import json
from unittest.mock import MagicMock, patch

import pytest
from agents.llm import RuleBasedLLMClient
from agents.llm_client import RealLLMClient
from agents.llm_client.client import _call_with_fallback


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
