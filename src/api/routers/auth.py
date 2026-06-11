import logging

from fastapi import APIRouter, Response, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.connection import get_async_session
from src.db.userManager import user_manager
from src.schemes.users import UserRead, UserCreate, UserLogin
from src.utils.auth_jwt import create_tokens, build_access_payload, get_payload_refresh, blacklist_token

router_logger = logging.getLogger('Роутер Subjects')

router = APIRouter(tags=["Auth"])


@router.post(
    "/register",
    response_model=UserRead,
    summary="Регистрация нового пользователя",
)
async def register(
        user_data: UserCreate,
        response: Response,
        session: AsyncSession = Depends(get_async_session),
) -> UserRead:
    user = await user_manager.create_user(
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        middle_name=user_data.middle_name,
        email=user_data.email,
        password=user_data.password,
        group_name="Пользователь",
        session=session,
    )

    scopes = await user_manager.get_user_scopes(user.id, session=session)

    payload = build_access_payload(user, scopes)
    create_tokens(payload, response)

    return UserRead.model_validate(user, from_attributes=True)


@router.post(
    "/login",
    response_model=UserRead,
    summary="Вход по email и паролю",
)
async def login(
        user_data: UserLogin,
        response: Response,
        session: AsyncSession = Depends(get_async_session)
) -> UserRead:
    user = await user_manager.verify_password(
        email=user_data.email,
        password=user_data.password,
        session=session,
    )
    scopes = await user_manager.get_user_scopes(user.id, session=session)

    payload = build_access_payload(user, scopes)
    create_tokens(payload, response)
    return UserRead.model_validate(user, from_attributes=True)


@router.post(
    "/refresh",
    response_model=UserRead,
    summary="Обновить токены по refresh токену из куки",
)
async def refresh(
        response: Response,
        refresh_payload=Depends(get_payload_refresh),
        session: AsyncSession = Depends(get_async_session)
) -> UserRead:
    user_id = refresh_payload["sub"]

    user = await user_manager.get(entity_id=user_id, session=session)

    if not user.is_active:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"msg": "Пользователь деактивирован"},
        )
    scopes = await user_manager.get_user_scopes(user.id, session=session)

    payload = build_access_payload(user, scopes)
    create_tokens(payload, response)
    return UserRead.model_validate(user, from_attributes=True)


@router.post(
    "/logout",
    summary="Выход — отзывает токены",
)
async def logout(
        request: Request,
        response: Response,
):

    access_token = request.cookies.get(settings.auth_jwt.key_cookie_access)

    if access_token:
        await blacklist_token(access_token)

    response.delete_cookie(settings.auth_jwt.key_cookie_access)
    response.delete_cookie(settings.auth_jwt.key_cookie_refresh)

    return {"msg": "Выход выполнен"}
