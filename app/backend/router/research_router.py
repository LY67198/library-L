from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.schemas.research import ResearchRequest, ResearchResponse
from backend.service.workflow_service import WorkflowService, get_workflow_service


router = APIRouter(prefix="/api/v1/research", tags=["research"])


@router.post("/run", response_model=ResearchResponse)
async def run_research(
    payload: ResearchRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> ResearchResponse:
    final = await workflow_service.run(payload)
    return ResearchResponse.from_request(payload, final=final)


@router.post("/stream")
async def stream_research(
    payload: ResearchRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> StreamingResponse:
    async def event_stream():
        yield _sse({"type": "status", "message": "request accepted"})
        async for event in workflow_service.stream_events(payload):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

