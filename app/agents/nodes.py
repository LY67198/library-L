"""图书馆 Agent 节点实现 — 意图分类、检索、Stub、直接回答"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from agents.llm import LLMClient
from .config import ChatConfig
from .retrieval.protocol import Retriever
from .state import LibraryState


@dataclass(frozen=True)
class LibraryNodeContext:
    """节点依赖注入容器"""

    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever
    auth_service: object | None = None    # Phase 2a: AuthService
    seat_service: object | None = None    # Phase 2a: SeatService
    session_factory: object | None = None  # Phase 4: async sessionmaker


# --- 主图节点 ---

def intent_classifier_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """9 分类意图识别，LLM 失败时关键词兜底"""
    query = state["query"]
    try:
        intent = context.llm.classify_library_intent(query)
    except Exception:
        intent = _fallback_classify(query)
    subgraph = _intent_to_subgraph(intent)
    return {"intent": intent, "subgraph": subgraph}


# --- 检索子图节点 ---

def retrieval_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """提取查询条件，确定检索类型"""
    return {"context": {"original_query": state["query"], "intent": state["intent"]}}


def policy_retrieval_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """ChromaDB 向量检索政策文档"""
    query = state["query"]
    try:
        docs = context.retriever.search(query, top_k=context.config.retriever_top_k)
        return {"retrieved_docs": docs, "error": None}
    except Exception:
        return {
            "retrieved_docs": [],
            "error": "retriever_unavailable",
            "fallback_response": "抱歉，政策检索服务暂时不可用，请稍后重试。",
        }


def book_lookup_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """PostgreSQL 图书字段查询"""
    query = state["query"]
    try:
        docs = context.book_lookup.search(query, top_k=context.config.retriever_top_k)
        return {"retrieved_docs": docs, "error": None}
    except Exception:
        return {
            "retrieved_docs": [],
            "error": "book_lookup_unavailable",
            "fallback_response": "抱歉，图书检索服务暂时不可用，请稍后重试。",
        }


def recommend_retrieve_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """推荐检索 — Phase 1 复用图书检索"""
    return book_lookup_node(state, context)


def format_response_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """格式化检索结果为用户可读回复"""
    error = state.get("error")
    if error:
        fallback = state.get("fallback_response", "服务异常，请稍后重试。")
        return {"response": fallback, "sources": []}
    docs = state.get("retrieved_docs", [])
    response = context.llm.format_library_response(state["intent"], state["query"], docs)
    sources = [
        {
            "type": doc.get("metadata", {}).get("source", "unknown"),
            "title": doc.get("metadata", {}).get("title", ""),
            "id": doc.get("metadata", {}).get("id", ""),
        }
        for doc in docs
    ]
    return {"response": response, "sources": sources, "error": None}


# --- Stub 节点 ---

def reservation_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """座位预约 Stub — 返回开发中提示"""
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def profile_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """读者画像 Stub — 返回开发中提示"""
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def direct_answer_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """问候和兜底直接回答"""
    intent = state["intent"]
    if intent == "greeting":
        return {
            "response": "您好！我是图书馆智能助手，可以帮您检索图书、查询政策、推荐书籍。请问有什么可以帮您的？",
            "sources": [],
        }
    return {"response": "抱歉，我没有理解您的问题，请换个方式描述一下？", "sources": []}


# --- 内部辅助函数 ---

def _intent_to_subgraph(intent: str) -> str:
    """意图 → 子图路由映射"""
    mapping = {
        "search_book": "retrieval",
        "recommend_book": "retrieval",
        "policy_query": "retrieval",
        "book_seat": "reservation",
        "query_appointment": "reservation",
        "cancel_appointment": "reservation",
        "profile_query": "profile",
        "greeting": "direct",
        "other": "direct",
    }
    return mapping.get(intent, "direct")


def _fallback_classify(query: str) -> str:
    """LLM 不可用时的关键词兜底分类"""
    lowered = query.lower()
    if any(w in lowered for w in ["书", "book", "找", "推荐", "检索"]):
        return "search_book"
    if any(w in lowered for w in ["几点", "开门", "关门", "借", "罚款", "规则"]):
        return "policy_query"
    if any(w in lowered for w in ["座位", "预约", "取消"]):
        return "book_seat"
    return "other"


# --- Reservation 子图节点（Phase 2a） ---

def reservation_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """预约子图入口 — 解析用户消息，提取结构化参数"""
    intent = state["intent"]
    query = state["query"]

    if intent == "book_seat":
        params = context.llm.extract_booking_params(query)
    elif intent == "cancel_appointment":
        params = context.llm.extract_cancel_params(query)
    else:
        params = {"query": query}

    return {"context": {"intent": intent, "reservation_params": params}}


def reservation_book_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """预约座位节点 — 返回指引（实际预约通过 REST API）"""
    params = state.get("context", {}).get("reservation_params", {})
    date_hint = params.get("date", "请指定日期")
    slot_hint = params.get("slot", "请选择时段")
    floor_hint = f"{params['floor']}楼" if params.get("floor") else "请指定楼层"

    response = (
        f"根据您的需求：{floor_hint}，{date_hint}，{slot_hint}时段。"
        f"请在座位列表中选择具体座位进行预约。"
    )
    return {"response": response, "sources": []}


def reservation_query_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """查询预约节点 — 返回指引"""
    response = "请在「我的预约」页面查看您的预约记录。"
    return {"response": response, "sources": []}


def reservation_cancel_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """取消预约节点 — 返回指引"""
    response = "请在「我的预约」中找到对应预约，点击取消即可。"
    return {"response": response, "sources": []}


def reservation_format_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """格式化预约结果"""
    response = state.get("response", "")
    return {"response": response, "sources": state.get("sources", [])}


# --- Profile 子图节点（Phase 4） ---

def profile_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """解析用户消息，判断用户想查什么"""
    query = state["query"]
    params = context.llm.extract_profile_params(query)
    return {"context": {"profile_type": params.get("profile_type", "all")}}


def profile_query_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """查询 DB：User + Appointment + BorrowRecord"""
    user_id = state.get("user_id")
    if not user_id:
        return {
            "response": "请先登录后查看个人信息。",
            "sources": [],
        }

    session_factory = context.session_factory
    if session_factory is None:
        return {
            "response": "个人信息查询服务暂不可用。",
            "sources": [],
        }

    profile_type = state.get("context", {}).get("profile_type", "all")

    async def _query():
        from backend.service.profile_service import ProfileService

        async with session_factory() as db:
            service = ProfileService(db)
            return await service.get_profile(user_id, profile_type)

    try:
        result = asyncio.run(_query())
    except Exception:
        return {
            "response": "查询个人信息时出错，请稍后重试。",
            "sources": [],
        }

    user = result["user"]
    if user is None:
        return {
            "response": "未找到用户信息。",
            "sources": [],
            "error": None,
        }

    # 序列化 appointment 数据
    appointments = []
    for a in result["appointments"]:
        seat = getattr(a, "seat", None)
        floor_name = ""
        zone_name = ""
        seat_number = ""
        if seat:
            # Seat model has zone relationship, zone has floor relationship
            zone = getattr(seat, "zone", None)
            if zone:
                floor_name = getattr(zone, "floor_name", "") or ""
                zone_name = getattr(zone, "name", "") or ""
            seat_number = getattr(seat, "seat_number", "") or ""
        appointments.append({
            "appointment_id": a.id,
            "date": str(a.date),
            "slot": a.slot.value if hasattr(a.slot, "value") else str(a.slot),
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "floor_name": floor_name,
            "zone_name": zone_name,
            "seat_number": seat_number,
        })

    # 序列化 borrow_record 数据
    borrow_records = []
    for br in result["borrow_records"]:
        book = getattr(br, "book", None)
        borrow_records.append({
            "id": br.id,
            "book_title": book.title if book else "-",
            "borrowed_at": str(br.borrowed_at),
            "due_at": str(br.due_at),
            "returned_at": str(br.returned_at) if br.returned_at else None,
            "status": br.status.value if hasattr(br.status, "value") else str(br.status),
        })

    user_info = {
        "display_name": user.display_name,
        "student_id": user.student_id,
        "username": user.username,
    }

    return {
        "context": {
            "profile_type": profile_type,
            "user_info": user_info,
            "appointments": appointments,
            "borrow_records": borrow_records,
        },
        "error": None,
    }


def profile_format_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """LLM 格式化回复"""
    error = state.get("error")
    if error:
        fallback = state.get("fallback_response", "服务异常，请稍后重试。")
        return {"response": fallback, "sources": []}

    ctx = state.get("context", {})
    user_info = ctx.get("user_info")
    if user_info is None:
        # profile_query_node already set a terminal response (e.g. unauthenticated, no_db)
        return {}

    appointments = ctx.get("appointments", [])
    borrow_records = ctx.get("borrow_records", [])

    response = context.llm.format_profile_response(user_info, appointments, borrow_records)
    return {"response": response, "sources": []}
