from fastapi import HTTPException, status, Request
from src.schemes.users import UserInfo

def require_scope(scope: str):
    async def dependency(request: Request):
        user: UserInfo = getattr(request.state, "user", None)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"msg": "Не авторизован"},
            )

        if "admin:*" not in user.scopes and scope not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"msg": f"Недостаточно прав. Требуется: {scope}"},
            )

    return dependency