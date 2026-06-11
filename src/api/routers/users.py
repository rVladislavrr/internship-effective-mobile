import logging

from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.connection import get_async_session
from src.db.userManager import user_manager
from src.schemes.scopes import ScopeRead
from src.schemes.users import UserRead, UserInfo, UserUpdate
from src.utils.auth_jwt import blacklist_token

log = logging.getLogger(__name__)

router = APIRouter(tags=["Users"])


@router.get("/me",
            response_model=UserRead,
            summary="Получить свой профиль")
async def get_me(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
):
    user_inf: UserInfo = request.state.user
    return await user_manager.get_me(user_inf.sub, session)


@router.get("/me/scopes",
            response_model=list[ScopeRead],
            summary="Получить свои скоупы")
async def get_my_scopes(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
):
    user_inf: UserInfo = request.state.user
    return await user_manager.get_my_scopes(user_inf.sub, session)


@router.patch("/me",
              response_model=UserRead,
              summary="Обновление своего профиля")
async def update_me(
        request: Request,
        data: UserUpdate,
        session: AsyncSession = Depends(get_async_session),
):
    user_inf: UserInfo = request.state.user
    return await user_manager.update_me(user_inf.sub, data, session)


@router.delete("/me",
               response_model=UserRead,
               summary="Удаление своего аккаунта")
async def delete_me(
        request: Request,
        response: Response,
        session: AsyncSession = Depends(get_async_session),
):
    user_inf: UserInfo = request.state.user

    user = await user_manager.delete_me(user_inf.sub, session)

    access_token = request.cookies.get(settings.auth_jwt.key_cookie_access)
    if access_token:
        await blacklist_token(access_token)

    response.delete_cookie(settings.auth_jwt.key_cookie_access)
    response.delete_cookie(settings.auth_jwt.key_cookie_refresh)

    return user