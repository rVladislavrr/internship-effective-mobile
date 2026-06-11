from fastapi import status


async def register_user(client, email: str, password: str = "password123"):
    response = await client.post("/auth/register", json={
        "first_name": "Тест",
        "email": email,
        "password": password,
        "password_confirm": password,
    })
    return response


class TestAccess:

    async def test_user_can_read_own_products(self, async_client):
        await register_user(async_client, "user_products@example.com")

        response = await async_client.get("/products")
        assert response.status_code == status.HTTP_200_OK
        for product in response.json():
            assert product["owner_id"] == "*"

    async def test_user_cannot_read_all_products(self, async_client):
        await register_user(async_client, "user_no_all@example.com")

        response = await async_client.get("/products/all")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_user_can_read_own_orders(self, async_client):
        await register_user(async_client, "user_orders@example.com")

        response = await async_client.get("/orders")
        assert response.status_code == status.HTTP_200_OK
        for order in response.json():
            assert order["owner_id"] == "*"

    async def test_user_cannot_read_all_orders(self, async_client):
        await register_user(async_client, "user_no_orders_all@example.com")

        response = await async_client.get("/orders/all")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_user_can_create_order(self, async_client):
        await register_user(async_client, "user_create_order@example.com")

        response = await async_client.post("/orders", params={
            "product": "Тестовый",
            "amount": 2,
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["product"] == "Тестовый"

    async def test_user_cannot_create_product(self, async_client):
        await register_user(async_client, "user_no_product@example.com")

        response = await async_client.post("/products", params={
            "name": "Товар",
            "price": 100.0,
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_unauthorized_cannot_access_products(self, async_client):
        response = await async_client.get("/products")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_unauthorized_cannot_access_orders(self, async_client):
        response = await async_client.get("/orders")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_admin_can_read_all_products(self, async_client):
        from src.config import settings
        await async_client.post("/auth/login", json={
            "email": settings.ADMIN_EMAIL,
            "password": settings.ADMIN_PASSWORD,
        })

        response = await async_client.get("/products/all")
        assert response.status_code == status.HTTP_200_OK
        owner_ids = {p["owner_id"] for p in response.json()}
        assert len(owner_ids) > 1

    async def test_admin_can_read_all_orders(self, async_client):
        from src.config import settings
        await async_client.post("/auth/login", json={
            "email": settings.ADMIN_EMAIL,
            "password": settings.ADMIN_PASSWORD,
        })

        response = await async_client.get("/orders/all")
        assert response.status_code == status.HTTP_200_OK
        owner_ids = {o["owner_id"] for o in response.json()}
        assert len(owner_ids) > 1

    async def test_admin_can_create_product(self, async_client):
        from src.config import settings
        await async_client.post("/auth/login", json={
            "email": settings.ADMIN_EMAIL,
            "password": settings.ADMIN_PASSWORD,
        })

        response = await async_client.post("/products", params={
            "name": "Новый товар",
            "price": 9999.0,
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Новый товар"
