from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.clients.embedding_client import EmbeddingClient
from app.core.exceptions import Forbidden
from app.models import User
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate
from app.services.policy_service import PolicyService

router = APIRouter(prefix="/admin/policies", tags=["admin"])


def _require_librarian(user: User) -> None:
    if user.role not in ("librarian", "admin"):
        raise Forbidden("Librarian role required")


def _get_rag_deps(request: Request) -> tuple[WhooshIndexManager, ChromaStore, EmbeddingClient]:
    """Pull RAG singletons from app.state (initialized in lifespan)."""
    return (
        request.app.state.bm25_index,
        request.app.state.chroma_store,
        request.app.state.embedding_client,
    )


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[PolicyResponse]:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    items = await service.list_all(tenant_id)
    return [PolicyResponse.model_validate(p) for p in items]


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    request: Request,
    payload: PolicyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.create(tenant_id=tenant_id, data=payload.model_dump())
    return PolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    payload: PolicyUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.update(policy_id, tenant_id, payload.model_dump(exclude_unset=True))
    return PolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if user.role != "admin":
        raise Forbidden("Admin role required")
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    await service.delete(policy_id, tenant_id)


@router.post("/{policy_id}/reindex", response_model=PolicyResponse)
async def reindex_policy(
    policy_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    if user.role != "admin":
        raise Forbidden("Admin role required")
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.reindex(policy_id, tenant_id)
    return PolicyResponse.model_validate(policy)