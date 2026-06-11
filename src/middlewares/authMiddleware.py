import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from starlette.responses import JSONResponse

from src.config import settings
from src.utils.auth_jwt import get_users_payload, is_blacklisted

api_logger = logging.getLogger("api")

PUBLIC_PATHS = {"/docs", "/openapi.json", "/redoc"}
PUBLIC_PREFIXES = ("/auth/",)


def _is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _401(request: Request, msg: str = "Invalid token") -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": {"msg": msg, "request_id": _get_request_id(request)}},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("OPTIONS", "HEAD"):
            return await call_next(request)

        if _is_public(request.url.path):
            return await call_next(request)

        token = request.cookies.get(settings.auth_jwt.key_cookie_access)
        if not token:
            return _401(request, "Access токен не найден")

        try:
            user, payload = await get_users_payload(token)
        except Exception:
            return _401(request)

        if await is_blacklisted(payload):
            return _401(request, "Токен отозван")

        request.state.user = user
        return await call_next(request)