import logging

from fastapi import APIRouter, Request, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.adminManager import admin_manager
from src.db.connection import get_async_session
from src.schemes.scopes import (
    ScopeRead,
    ScopeGroupWithScopes,
    AssignScopeRequest,
    RevokeScopeRequest,
    AssignGroupRequest,
    RevokeGroupRequest,
)
from src.utils.permissions import require_scope

log = logging.getLogger(__name__)

router = APIRouter(
    tags=["Admin"],
    dependencies=[Depends(require_scope("scopes:manage"))],
)


def _check_not_self(user_inf, target_user_id) -> None:
    from fastapi import HTTPException, status
    if str(user_inf.sub) == str(target_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"msg": "Нельзя изменять свои собственные скоупы"},
        )


@router.get("/scopes",
            response_model=list[ScopeRead],
            summary="Все скоупы")
async def get_all_scopes(session: AsyncSession = Depends(get_async_session)):
    return await admin_manager.get_all_scopes(session)


@router.get("/groups",
            response_model=list[ScopeGroupWithScopes],
            summary="Все группы со скоупами")
async def get_all_groups(session: AsyncSession = Depends(get_async_session)):
    return await admin_manager.get_all_groups(session)


@router.get("/users/{user_id}/scopes",
            response_model=list[ScopeRead],
            summary="Скоупы пользователя")
async def get_user_scopes(user_id: UUID4, session: AsyncSession = Depends(get_async_session)):
    return await admin_manager.get_user_scopes(user_id, session)


@router.post("/scopes/assign",
             response_model=list[ScopeRead],
             summary="Выдать скоуп")
async def assign_scope(
        request: Request,
        data: AssignScopeRequest,
        session: AsyncSession = Depends(get_async_session),
):
    _check_not_self(request.state.user, data.user_id)
    return await admin_manager.assign_scope(
        user_id=data.user_id,
        scope_id=data.scope_id,
        granted_by=request.state.user.sub,
        session=session,
    )


@router.delete("/scopes/revoke",
               response_model=list[ScopeRead],
               summary="Забрать скоуп")
async def revoke_scope(
        request: Request,
        data: RevokeScopeRequest,
        session: AsyncSession = Depends(get_async_session),
):
    _check_not_self(request.state.user, data.user_id)
    return await admin_manager.revoke_scope(
        user_id=data.user_id,
        scope_id=data.scope_id,
        session=session,
    )


@router.post("/groups/assign",
             response_model=list[ScopeRead],
             summary="Выдать все скоупы группы")
async def assign_group(
        request: Request,
        data: AssignGroupRequest,
        session: AsyncSession = Depends(get_async_session),
):
    _check_not_self(request.state.user, data.user_id)
    return await admin_manager.assign_group(
        user_id=data.user_id,
        group_id=data.group_id,
        granted_by=request.state.user.sub,
        session=session,
    )


@router.delete("/groups/revoke",
               response_model=list[ScopeRead],
               summary="Забрать все скоупы группы")
async def revoke_group(
        request: Request,
        data: RevokeGroupRequest,
        session: AsyncSession = Depends(get_async_session),
):
    _check_not_self(request.state.user, data.user_id)
    return await admin_manager.revoke_group(
        user_id=data.user_id,
        group_id=data.group_id,
        session=session,
    )