"""AI 问答接口 — 同步 + SSE 流式"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.schemas.chat import ChatRequest, ChatResponse
from backend.service.chat_service import ChatService, get_chat_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """同步问答 — 返回完整结果"""
    result = await service.chat(
        query=payload.query,
        user_id=payload.user_id,
        history=payload.history,
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """SSE 流式问答 — 实时推送意图、Token、完成事件"""

    async def event_stream():
        async for event in service.chat_stream(
            query=payload.query,
            user_id=payload.user_id,
            history=payload.history,
        ):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: dict) -> str:
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"
