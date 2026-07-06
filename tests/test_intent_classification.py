"""9 分类意图识别测试"""

import pytest
from agents.llm import RuleBasedLLMClient


@pytest.fixture
def llm():
    return RuleBasedLLMClient()


@pytest.mark.parametrize(
    "query,expected",
    [
        ("有没有《三体》这本书", "search_book"),
        ("帮我找一下Python编程的书", "search_book"),
        ("推荐几本小说看看", "recommend_book"),
        ("想看书但不知道看什么", "recommend_book"),
        ("图书馆几点开门", "policy_query"),
        ("借书能借多久", "policy_query"),
        ("我要预约座位", "book_seat"),
        ("帮我查一下我的预约", "query_appointment"),
        ("取消我的预约", "cancel_appointment"),
        ("我的借阅记录", "profile_query"),
        ("你好", "greeting"),
        ("今天天气怎么样", "other"),
    ],
)
def test_classify_library_intent(llm, query, expected):
    assert llm.classify_library_intent(query) == expected
