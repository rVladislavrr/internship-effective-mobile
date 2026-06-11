from .auth import router as auth_router  # noqa: F401
from .users import router as users_router  # noqa: F401
from .admin import router as admin_router  # noqa: F401
from .product import router as product_router  # noqa: F401

from fastapi import APIRouter

router = APIRouter()

router.include_router(auth_router, prefix='/auth')
router.include_router(users_router, prefix='/users')
router.include_router(admin_router, prefix='/admin')
router.include_router(product_router,)
