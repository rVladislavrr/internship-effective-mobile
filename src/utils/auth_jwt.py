import logging
import jwt

from datetime import timedelta, datetime, timezone
from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer

from src.config import settings
from src.redis_conn import redis_client
from src.schemes.users import UserInfo, TOKEN_TYPE_FIELD, ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE, UserRead

logger = logging.getLogger(__name__)
http_bearer = HTTPBearer(auto_error=False)

BLACKLIST_PREFIX = "blacklist:"

def encode_jwt(
        payload: dict,
        private_key: str = settings.auth_jwt.private_key_path.read_text(),
        algorithm: str = settings.auth_jwt.algorithm,
        expire_minutes: int = settings.auth_jwt.access_token_expire_minutes,
        expire_timedelta: timedelta | None = None,
) -> str:
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expire_timedelta or timedelta(minutes=expire_minutes))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, private_key, algorithm=algorithm)


def decode_jwt(
        token: str | bytes,
        public_key: str = settings.auth_jwt.public_key_path.read_text(),
        algorithm: str = settings.auth_jwt.algorithm,
) -> dict:
    return jwt.decode(token, public_key, algorithms=[algorithm])

def create_jwt(
        token_type: str,
        token_data: dict,
        expire_minutes: int = settings.auth_jwt.access_token_expire_minutes,
        expire_timedelta: timedelta | None = None,
) -> str:
    payload = {TOKEN_TYPE_FIELD: token_type}
    payload.update(token_data)
    return encode_jwt(payload=payload, expire_minutes=expire_minutes, expire_timedelta=expire_timedelta)


def create_access_token(user_inf: dict) -> str:
    return create_jwt(
        token_type=ACCESS_TOKEN_TYPE,
        token_data=user_inf,
        expire_minutes=settings.auth_jwt.access_token_expire_minutes,
    )


def create_refresh_token(user: dict) -> str:
    return create_jwt(
        token_type=REFRESH_TOKEN_TYPE,
        token_data={"sub": user["sub"]},
        expire_timedelta=timedelta(days=settings.auth_jwt.refresh_token_expire_days),
    )


def create_tokens(user_inf: UserInfo, response: Response) -> None:

    data = user_inf.model_dump()
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    response.set_cookie(
        key=settings.auth_jwt.key_cookie_access,
        value=access_token,
        max_age=settings.auth_jwt.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
    )

    response.set_cookie(
        key=settings.auth_jwt.key_cookie_refresh,
        value=refresh_token,
        max_age=settings.auth_jwt.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )

def validate_token_type(payload: dict, token_type: str) -> None:
    if payload.get(TOKEN_TYPE_FIELD) != token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": f"Ожидался '{token_type}', получен '{payload.get(TOKEN_TYPE_FIELD)}'"},
        )


def decode_and_validate(token: str, token_type: str) -> dict:
    try:
        payload = decode_jwt(token=token)
        validate_token_type(payload, token_type)
        return payload
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Токен истёк"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Невалидный токен"},
        )

def _make_jti(payload: dict) -> str:
    return f"{payload['sub']}:{payload['iat']}"


def _remaining_seconds(payload: dict) -> int:
    exp = payload.get("exp", 0)
    now = int(datetime.now(timezone.utc).timestamp())
    return max(exp - now, 0)


async def blacklist_token(token: str) -> None:
    try:
        payload = decode_jwt(token)
    except jwt.InvalidTokenError:
        return

    ttl = _remaining_seconds(payload)
    if ttl > 0:
        jti = _make_jti(payload)
        await redis_client.blacklist_token(jti, ttl)
        logger.info(f"[blacklist] sub={payload.get('sub')} ttl={ttl}s")


async def is_blacklisted(payload: dict) -> bool:
    jti = _make_jti(payload)
    return await redis_client.is_blacklisted(jti)

async def get_payload_access(request: Request) -> UserInfo:
    token = request.cookies.get(settings.auth_jwt.key_cookie_access)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Access токен не найден"},
        )
    payload = decode_and_validate(token, ACCESS_TOKEN_TYPE)
    return UserInfo.model_validate(payload)


async def get_payload_refresh(request: Request) -> dict:
    token = request.cookies.get(settings.auth_jwt.key_cookie_refresh)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"msg": "Refresh токен не найден"},
        )
    return decode_and_validate(token, REFRESH_TOKEN_TYPE)


async def get_active_payload(
        user_inf: UserInfo = Depends(get_payload_access),
) -> UserInfo:
    if not user_inf.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"msg": "Пользователь неактивен"},
        )
    return user_inf


async def get_users_payload(token: str) -> tuple[UserInfo, dict]:
    payload = decode_and_validate(token, ACCESS_TOKEN_TYPE)
    user_info = UserInfo.model_validate(payload)
    return user_info, payload

def build_access_payload(user: UserRead, scopes: list[str]) -> UserInfo:
    return UserInfo(
        sub=str(user.id),
        active=user.is_active,
        scopes=scopes,
    )
