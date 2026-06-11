# Система аутентификации и авторизации

Для запуска приложения

```commandline
docker-compose up -d --build
```

Так же само приложение можно запустить и не через докер, но тогда всё равно надо поднять базу данных и редис через компост

```commandline
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Прогон базовых тестов

```commandline
pytest -v
```

Некоторые ендпоинты также можно было кешировать в редис, но редис использовался показательно только для ограничения токена в блеклист после выхода из аккаунта

## Аутентификация

Система использует JWT токены.

### Как работает

```
Клиент                          Сервер
  |                               |
  |  POST /auth/login             |
  |  { email, password }  ──────► |  1. Проверяем email + bcrypt(password)
  |                               |  2. Достаём скоупы пользователя из БД
  |                               |  3. Создаём access token (15 мин)
  |                               |  4. Создаём refresh token (7 дней)
  |  Set-Cookie: access_token ◄── |
  |  Set-Cookie: refresh_token    |
  |                               |
  |  GET /products                |
  |  Cookie: access_token ──────► |  Middleware:
  |                               |  1. Читает токен из куки
  |                               |  2. Декодирует и проверяет подпись
  |                               |  3. Проверяет Redis blacklist
  |                               |  4. Кладёт UserInfo в request.state.user
  |  200 OK  ◄────────────────── |  Router: берёт request.state.user
```

### Токены

**Access token** — содержит:
```json
{
  "type": "access",
  "sub": "user-uuid",
  "active": true,
  "scopes": ["products:read", "orders:read", "orders:write"],
  "exp": 1718000900,
  "iat": 1718000000
}
```

**Refresh token** (7 дней) — содержит только `sub`, хранится в httpOnly куки.
Используется для получения новой пары токенов без повторного ввода пароля.

### Logout и blacklist

При выходе (sub:iat) токена записывается в **Redis** с TTL = остаток жизни токена.
Middleware проверяет blacklist при каждом запросе — O(1), ~0.1ms.
После истечения TTL Redis сам удаляет запись — никакого мусора.

```
Logout на 3-й минуте жизни 15-минутного токена
→ Redis.set("blacklist:uuid:iat", "1", ex=720)  # 12 минут
→ Через 12 минут Redis сам удаляет запись
→ Токен и так мёртв по exp — blacklist больше не нужен
```

### Мягкое удаление

При удалении аккаунта пользователь **не удаляется из БД**:
- `is_active = False`
- `delete_at = now()`
- Текущий токен отзывается через blacklist
- Куки удаляются

Повторный логин невозможен — `verify_password` проверяет `is_active`.

---

## Авторизация
### Принцип

Права — это строки вида `объект:действие`. Каждому пользователю назначается
набор таких строк. Проверка права — просто `scope in user.scopes`.

Основное подразделение на объект и действие, и от этого строится получение своих товаров или заказов от всех товаров и заказов в системе.


```python
"products:read"       # читать свои товары
"products:read_all"   # читать все товары
"orders:write"        # создавать заказы
"admin:*"             # полный доступ ко всему
```

---

## Скоупы системы

| Скоуп | Описание |
|-------|----------|
| `admin:*` | Полный доступ ко всему |
| `users:read_all` | Читать всех пользователей |
| `users:update_all` | Редактировать любого пользователя |
| `users:delete_all` | Удалять любого пользователя |
| `products:read` | Читать свои товары |
| `products:read_all` | Читать все товары |
| `products:write` | Создавать товары |
| `products:update` | Редактировать свои товары |
| `products:update_all` | Редактировать любой товар |
| `products:delete` | Удалять свои товары |
| `products:delete_all` | Удалять любой товар |
| `orders:read` | Читать свои заказы |
| `orders:read_all` | Читать все заказы |
| `orders:write` | Создавать заказы |
| `orders:update` | Редактировать свои заказы |
| `orders:update_all` | Редактировать любой заказ |
| `orders:delete_all` | Удалять любой заказ |
| `scopes:manage` | Управлять правами доступа |

---

## Группы

### Администратор
Полный доступ ко всему. Все скоупы включая `admin:*` и `scopes:manage`.

### Менеджер
Управление товарами и заказами:
`products:read_all`, `products:write`, `products:update_all`,
`orders:read_all`, `orders:update_all`, `users:read_all`

### Пользователь (по умолчанию при регистрации)
Базовый доступ — только свои объекты:
`products:read`, `orders:read`, `orders:write`, `orders:update`

### Гость
Только просмотр товаров: `products:read`

---

## Поток запроса

```
HTTP Request
    │
    ▼
AuthMiddleware
    ├── Публичный путь? (/auth/*, /docs) ──► пропускаем
    ├── Нет токена в куки ──────────────────► 401
    ├── Токен невалиден / истёк ────────────► 401
    ├── Токен в Redis blacklist ────────────► 401 (logout)
    └── OK → request.state.user = UserInfo
    │
    ▼
Router
    ├── require_scope("products:read_all") → нет скоупа ──► 403
    └── OK → выполняем логику роута
    │
    ▼
Response
```
