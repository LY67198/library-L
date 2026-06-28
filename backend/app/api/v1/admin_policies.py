"""策略管理路由 — 提供图书馆政策的 CRUD 与重新索引接口(写入限管理员角色)。"""

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
    """校验当前用户具备图书管理员权限(librarian / admin)。

    参数:
        user: 当前请求对应的已登录用户。

    返回值:
        None: 仅做权限校验,无返回。

    抛出:
        Forbidden: 当用户角色不在允许列表时抛出。
    """
    if user.role not in ("librarian", "admin"):
        raise Forbidden("Librarian role required")


def _get_rag_deps(request: Request) -> tuple[WhooshIndexManager, ChromaStore, EmbeddingClient]:
    """从 app.state 取出 lifespan 阶段初始化的 RAG 单例 — 避免在请求内重建索引。

    参数:
        request: FastAPI 请求对象,用于访问 app.state。

    返回值:
        tuple[WhooshIndexManager, ChromaStore, EmbeddingClient]: 三件套 RAG 依赖。
    """
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
    """查询当前租户的全部策略 — 仅图书管理员可访问。

    参数:
        request: FastAPI 请求对象,用于读取租户上下文与 RAG 单例。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        list[PolicyResponse]: 策略详情列表。
    """
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
    """创建策略 — 仅图书管理员可创建,创建后会自动同步到 RAG 索引。

    参数:
        request: FastAPI 请求对象,用于读取租户上下文与 RAG 单例。
        payload: 策略创建请求体。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        PolicyResponse: 新建后的策略详情。
    """
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
    """局部更新策略 — 仅图书管理员,只更新提供的字段,并同步 RAG 索引。

    参数:
        policy_id: 策略主键 ID(路径参数)。
        payload: 策略更新请求体。
        request: FastAPI 请求对象,用于读取租户上下文与 RAG 单例。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        PolicyResponse: 更新后的策略详情。
    """
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
    """删除策略 — 仅管理员(admin)角色可操作,会同步清理 RAG 索引。

    参数:
        policy_id: 策略主键 ID(路径参数)。
        request: FastAPI 请求对象,用于读取租户上下文与 RAG 单例。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        None: 成功删除后无返回体。

    抛出:
        Forbidden: 当用户不是 admin 角色时抛出。
    """
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
    """手动触发单条策略的 RAG 重新索引 — 仅管理员(admin)可操作。

    参数:
        policy_id: 策略主键 ID(路径参数)。
        request: FastAPI 请求对象,用于读取租户上下文与 RAG 单例。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        PolicyResponse: 重新索引后的策略详情。

    抛出:
        Forbidden: 当用户不是 admin 角色时抛出。
    """
    if user.role != "admin":
        raise Forbidden("Admin role required")
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.reindex(policy_id, tenant_id)
    return PolicyResponse.model_validate(policy)
