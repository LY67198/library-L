from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    # --- 深度调研方法（原有） ---
    def classify_intent(self, query: str) -> str: ...

    def answer_direct(self, query: str, memory_context: str = "") -> str: ...

    def plan_research(self, query: str) -> dict: ...

    def judge_evidence(self, query: str, records: list[dict]) -> list[dict]: ...

    def analyze(self, query: str, evidence: list[dict]) -> dict: ...

    def reflect(self, query: str, missing_gaps: list[str]) -> list[dict]: ...

    def write_report(self, query: str, findings: list[dict], sources: list[dict]) -> str: ...

    # --- 图书馆问答方法（Phase 1 新增） ---
    def classify_library_intent(self, query: str) -> str: ...

    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str: ...

    def stub_message(self, intent: str) -> str: ...

    # --- 图书馆预约方法（Phase 2a 新增） ---
    def extract_booking_params(self, query: str) -> dict: ...

    def extract_cancel_params(self, query: str) -> dict: ...

    def format_reservation_response(self, intent: str, result: dict) -> str: ...

    # --- 读者画像方法（Phase 4 新增） ---
    def extract_profile_params(self, query: str) -> dict: ...

    def format_profile_response(
        self, user_info: dict, appointments: list[dict], borrow_records: list[dict]
    ) -> str: ...


class RuleBasedLLMClient:
    """Small deterministic adapter so the scaffold works without API keys."""

    def classify_intent(self, query: str) -> str:
        lowered = query.lower()
        research_markers = {
            "research",
            "compare",
            "market",
            "trend",
            "evidence",
            "sources",
            "report",
            "analysis",
            "strategy",
        }
        return "research" if any(marker in lowered for marker in research_markers) else "direct"

    def answer_direct(self, query: str, memory_context: str = "") -> str:
        context = f"\n\nMemory context:\n{memory_context}" if memory_context else ""
        return f"Direct scaffold response for: {query}{context}"

    def plan_research(self, query: str) -> dict:
        return {
            "summary": f"Research plan for: {query}",
            "sub_questions": [
                f"What is the current context for {query}?",
                f"What evidence supports the main claims about {query}?",
                f"What risks or tradeoffs should be considered for {query}?",
            ],
            "search_plan": [
                {"query": query, "source": "hybrid", "reason": "original user question"},
                {"query": f"{query} evidence sources", "source": "web", "reason": "external evidence"},
                {"query": f"{query} internal notes", "source": "local", "reason": "local knowledge"},
            ],
        }

    def judge_evidence(self, query: str, records: list[dict]) -> list[dict]:
        judged = []
        for idx, record in enumerate(records, 1):
            item = dict(record)
            item.setdefault("source_id", f"SRC-{idx}")
            item["relevance_score"] = 0.75
            item["supports"] = [query]
            judged.append(item)
        return judged

    def analyze(self, query: str, evidence: list[dict]) -> dict:
        findings = [
            {
                "claim": f"Initial scaffold finding for: {query}",
                "supporting_source_ids": [item.get("source_id") for item in evidence[:3]],
                "confidence": "medium" if evidence else "low",
            }
        ]
        missing_gaps = [] if evidence else ["No evidence was collected"]
        return {"findings": findings, "missing_gaps": missing_gaps}

    def reflect(self, query: str, missing_gaps: list[str]) -> list[dict]:
        if not missing_gaps:
            return []
        return [
            {
                "query": f"{query} missing evidence",
                "source": "hybrid",
                "reason": "; ".join(missing_gaps),
            }
        ]

    def write_report(self, query: str, findings: list[dict], sources: list[dict]) -> str:
        lines = [f"# Research Result: {query}", ""]
        lines.append("## Findings")
        if findings:
            for idx, finding in enumerate(findings, 1):
                source_ids = ", ".join(str(item) for item in finding.get("supporting_source_ids", []) if item)
                suffix = f" [{source_ids}]" if source_ids else ""
                lines.append(f"{idx}. {finding.get('claim', 'Finding')}{suffix}")
        else:
            lines.append("- No findings were produced.")
        lines.extend(["", "## Sources"])
        if sources:
            for source in sources:
                lines.append(f"- {source.get('source_id')}: {source.get('label')} ({source.get('locator')})")
        else:
            lines.append("- No sources.")
        return "\n".join(lines)

    # --- 图书馆问答方法（Phase 1 新增） ---

    def classify_library_intent(self, query: str) -> str:
        """9 分类关键词规则引擎"""
        lowered = query.lower()
        # 注意：顺序很重要——更具体的关键词必须排在前面，
        # 避免被较宽泛的关键词（如 search_book 的 "查一下"）先匹配到。
        intent_rules = [
            ("cancel_appointment", ["取消预约", "删除预约", "取消"]),
            ("query_appointment", ["我的预约", "预约记录", "预约查询", "查一下我的预约"]),
            ("profile_query", ["借阅记录", "我的记录", "借了哪些", "借过什么", "读者画像", "个人信息"]),
            ("book_seat", ["预约座位", "占座", "订座", "选座", "座位预约"]),
            ("recommend_book", ["推荐几本", "不知道看什么", "有什么好书", "推荐一下", "推荐"]),
            ("search_book", ["有没有", "找一下", "找一本", "查一下", "检索", "搜索", "在哪"]),
            ("policy_query", ["几点", "开门", "关门", "借书", "借多久", "罚款", "规则", "规定", "怎么借"]),
            ("greeting", ["你好", "hi", "hello", "嗨", "早上好", "下午好", "晚上好"]),
        ]
        for intent, markers in intent_rules:
            if any(marker in lowered for marker in markers):
                return intent
        return "other"

    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str:
        """将检索结果格式化为用户可读的回复"""
        if not docs:
            return f"未找到与「{query}」相关的结果，请尝试其他关键词。"
        lines = ["为您找到以下结果：", ""]
        for idx, doc in enumerate(docs, 1):
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            source = meta.get("source", meta.get("title", ""))
            loc = meta.get("location", meta.get("locator", ""))
            line = f"{idx}. {content}"
            if source:
                line += f"  [{source}]"
            if loc:
                line += f" — {loc}"
            lines.append(line)
        return "\n".join(lines)

    def extract_profile_params(self, query: str) -> dict:
        """关键词兜底：借阅/借了/还了/借过 → borrowing_history，其余 → all"""
        lowered = query.lower()
        if any(w in lowered for w in ["借阅", "借了", "还了", "借过", "借书记录",
                                        "借了哪些", "借过什么", "在借"]):
            return {"profile_type": "borrowing_history"}
        return {"profile_type": "all"}

    def format_profile_response(
        self, user_info: dict, appointments: list[dict], borrow_records: list[dict]
    ) -> str:
        """固定模板拼接：个人信息 + 当前预约 + 借阅记录"""
        lines = []
        u = user_info or {}
        lines.append(f"**个人信息**\n- 姓名：{u.get('display_name', '-')}\n- 学号：{u.get('student_id', '-')}")

        lines.append("\n**当前预约**")
        if appointments:
            for a in appointments:
                slot_label = (
                    "上午" if a.get("slot") == "morning"
                    else "下午" if a.get("slot") == "afternoon"
                    else "晚上"
                )
                lines.append(
                    f"- {a.get('floor_name', '')}-{a.get('zone_name', '')}-"
                    f"{a.get('seat_number', '')} | {a.get('date', '')} {slot_label}"
                )
        else:
            lines.append("- 暂无有效预约")

        lines.append("\n**借阅记录**")
        if borrow_records:
            for br in borrow_records:
                status_map = {"borrowed": "在借", "returned": "已还", "overdue": "逾期"}
                status = status_map.get(br.get("status", ""), br.get("status", ""))
                lines.append(
                    f"- 《{br.get('book_title', '-')}》 "
                    f"借阅：{br.get('borrowed_at', '-')[:10]} "
                    f"到期：{br.get('due_at', '-')[:10]} "
                    f"状态：{status}"
                )
        else:
            lines.append("- 暂无借阅记录")

        return "\n".join(lines)

    def stub_message(self, intent: str) -> str:
        """占位消息 — 未实现功能的友好提示"""
        messages = {
            "book_seat": "座位预约功能正在开发中，敬请期待。",
            "query_appointment": "预约查询功能正在开发中，敬请期待。",
            "cancel_appointment": "取消预约功能正在开发中，敬请期待。",
            "profile_query": "读者画像功能正在开发中，敬请期待。",
        }
        return messages.get(intent, "该功能正在开发中，敬请期待。")

    # --- 图书馆预约方法（Phase 2a 新增） ---

    def extract_booking_params(self, query: str) -> dict:
        """从用户消息中提取预约参数 — 关键词规则版"""
        lowered = query.lower()
        params = {}

        if "今天" in lowered:
            params["date"] = "today"
        elif "明天" in lowered:
            params["date"] = "tomorrow"
        elif "后天" in lowered:
            params["date"] = "day_after_tomorrow"

        if any(w in lowered for w in ["上午", "早上"]):
            params["slot"] = "morning"
        elif any(w in lowered for w in ["下午", "中午"]):
            params["slot"] = "afternoon"
        elif any(w in lowered for w in ["晚上", "傍晚"]):
            params["slot"] = "evening"

        for i in range(1, 10):
            if f"{i}楼" in query or f"{i}层" in query:
                params["floor"] = i
                break

        return params

    def extract_cancel_params(self, query: str) -> dict:
        """从用户消息中提取取消参数"""
        return {"query": query}

    def format_reservation_response(self, intent: str, result: dict) -> str:
        """格式化预约操作结果为自然语言回复"""
        if intent == "book_seat":
            return (
                f"预约成功！座位：{result.get('floor_name', '')}-"
                f"{result.get('zone_name', '')}-{result.get('seat_number', '')}，"
                f"日期：{result.get('date', '')}，时段：{result.get('slot', '')}"
            )
        elif intent == "query_appointment":
            appts = result.get("appointments", [])
            if not appts:
                return "您目前没有预约记录。"
            lines = ["您的预约记录："]
            for a in appts:
                slot_label = (
                    "上午" if a["slot"] == "morning"
                    else "下午" if a["slot"] == "afternoon"
                    else "晚上"
                )
                lines.append(
                    f"- {a['floor_name']}-{a['zone_name']}-{a['seat_number']} "
                    f"({a['date']} {slot_label}) "
                    f"[{a['appointment_id']}]"
                )
            return "\n".join(lines)
        elif intent == "cancel_appointment":
            return f"预约已取消（{result.get('appointment_id', '')}）。"
        return "操作完成。"

