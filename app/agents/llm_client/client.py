"""RealLLMClient — MiniMax 主力 + DeepSeek 兜底 + 规则引擎终极兜底"""

from __future__ import annotations

import json
import logging
import time as _time
from typing import Any, Callable, TypeVar

from agents.llm import RuleBasedLLMClient
from observability.middleware import get_trace_id

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
            start = _time.monotonic()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = int((_time.monotonic() - start) * 1000)
            raw = resp.choices[0].message.content
            result = parser(raw)
            logger.info(
                "LLM call completed: model=%s, latency_ms=%d, trace_id=%s",
                model, latency_ms, get_trace_id() or "-",
            )
            return result
        except Exception as exc:
            logger.warning(
                "LLM call failed: model=%s, error=%s, trace_id=%s",
                model, exc, get_trace_id() or "-",
            )

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
    """将 LLM 输出解析为 dict，解析失败向上抛异常以触发 fallback 链路"""
    raw = raw.strip()
    # 处理 ```json ... ``` 包裹的情况
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON from LLM output: {raw[:200]}")
        raise  # 重新抛出，让 _call_with_fallback 切换到下一个 LLM
