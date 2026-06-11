import logging

from fastapi import APIRouter, Request, status, Depends
from pydantic import BaseModel

from src.schemes.users import UserInfo
from src.utils.permissions import require_scope

log = logging.getLogger(__name__)

router = APIRouter(tags=["Продукты"])

class Product(BaseModel):
    id: int
    name: str
    price: float
    owner_id: str


class Order(BaseModel):
    id: int
    product: str
    amount: int
    status: str
    owner_id: str

PRODUCTS = [
    Product(id=1, name="Ноутбук",    price=85000.0, owner_id="*"),   # где * это мой подходящий под мой айди
    Product(id=2, name="Мышь",       price=1500.0,  owner_id="*"),
    Product(id=3, name="Монитор",    price=35000.0, owner_id="other-user-1"),
    Product(id=4, name="Клавиатура", price=5000.0,  owner_id="other-user-2"),
]

ORDERS = [
    Order(id=1, product="Ноутбук",    amount=1, status="delivered", owner_id="*"),
    Order(id=2, product="Мышь",       amount=2, status="pending",   owner_id="*"),
    Order(id=3, product="Монитор",    amount=1, status="shipping",  owner_id="other-user-1"),
    Order(id=4, product="Клавиатура", amount=3, status="delivered", owner_id="other-user-2"),
]


@router.get(
    "/products",
    response_model=list[Product],
    summary="Мои товары [products:read]",
    dependencies=[Depends(require_scope("products:read"))],
)
async def get_my_products(request: Request):
    return [p for p in PRODUCTS if p.owner_id == "*" or p.owner_id == request.state.user.sub]


@router.get(
    "/products/all",
    response_model=list[Product],
    summary="Все товары [products:read_all]",
    description="Возвращает товары всех пользователей. Требует повышенных прав.",
    dependencies=[Depends(require_scope("products:read_all"))],
)
async def get_all_products():
    return PRODUCTS


@router.post(
    "/products",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар [products:write]",
    dependencies=[Depends(require_scope("products:write"))],
)
async def create_product(request: Request, name: str, price: float):
    user: UserInfo = request.state.user
    new_product = Product(
        id=len(PRODUCTS) + 1,
        name=name,
        price=price,
        owner_id=user.sub,
    )
    PRODUCTS.append(new_product)
    log.info(f"Создан товар '{name}' owner={user.sub}")
    return new_product


@router.get(
    "/orders",
    response_model=list[Order],
    summary="Мои заказы [orders:read]",
    dependencies=[Depends(require_scope("orders:read"))],
)
async def get_my_orders(request: Request):
    return [o for o in ORDERS if o.owner_id == "*" or o.owner_id == request.state.user.sub]


@router.get(
    "/orders/all",
    response_model=list[Order],
    summary="Все заказы [orders:read_all]",
    description="Возвращает заказы всех пользователей. Требует повышенных прав.",
    dependencies=[Depends(require_scope("orders:read_all"))],
)
async def get_all_orders():
    return ORDERS


@router.post(
    "/orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    summary="Создать заказ [orders:write]",
    dependencies=[Depends(require_scope("orders:write"))],
)
async def create_order(request: Request, product: str, amount: int):
    user: UserInfo = request.state.user
    new_order = Order(
        id=len(ORDERS) + 1,
        product=product,
        amount=amount,
        status="pending",
        owner_id=user.sub,
    )
    ORDERS.append(new_order)
    log.info(f"[Создан заказ '{product}' owner={user.sub}")
    return new_order