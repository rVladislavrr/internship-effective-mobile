import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.userManager import user_manager
from src.models import Scopes, ScopeGroups, ScopeGroupScopes, Users

SCOPE_GROUPS = {
    "Администратор": {
        "description": "Полный доступ ко всему",
        "scopes": [
            ("admin:*",              "Полный доступ ко всему"),
            ("users:read_all",       "Читать всех пользователей"),
            ("users:update_all",     "Редактировать любого пользователя"),
            ("users:delete_all",     "Удалять любого пользователя"),
            ("products:read_all",    "Читать все товары"),
            ("products:write",       "Создавать товары"),
            ("products:update_all",  "Редактировать любой товар"),
            ("products:delete_all",  "Удалять любой товар"),
            ("orders:read_all",      "Читать все заказы"),
            ("orders:update_all",    "Редактировать любой заказ"),
            ("orders:delete_all",    "Удалять любой заказ"),
            ("scopes:manage",        "Управлять правами доступа"),
        ],
    },
    "Менеджер": {
        "description": "Управление товарами и заказами",
        "scopes": [
            ("products:read_all",    "Читать все товары"),
            ("products:write",       "Создавать товары"),
            ("products:update_all",  "Редактировать любой товар"),
            ("orders:read_all",      "Читать все заказы"),
            ("orders:update_all",    "Редактировать любой заказ"),
            ("users:read_all",       "Читать всех пользователей"),
        ],
    },
    "Пользователь": {
        "description": "Базовый доступ — только свои объекты",
        "scopes": [
            ("products:read",        "Читать товары"),
            ("orders:read",          "Читать свои заказы"),
            ("orders:write",         "Создавать заказы"),
            ("orders:update",        "Редактировать свои заказы"),
        ],
    },
    "Гость": {
        "description": "Только просмотр публичных товаров",
        "scopes": [
            ("products:read",        "Читать товары"),
        ],
    },
}

log = logging.getLogger(__name__)


async def seed_scope_groups(session: AsyncSession) -> None:
    created_scopes = 0
    created_groups = 0
    created_links = 0

    try:
        for group_name, config in SCOPE_GROUPS.items():

            result = await session.execute(
                select(ScopeGroups).where(ScopeGroups.name == group_name)
            )
            group = result.scalar_one_or_none()

            if group is None:
                group = ScopeGroups(
                    name=group_name,
                    description=config["description"],
                )
                session.add(group)
                await session.flush()
                created_groups += 1

            for scope_name, scope_desc in config["scopes"]:

                result = await session.execute(
                    select(Scopes).where(Scopes.name == scope_name)
                )
                scope = result.scalar_one_or_none()

                if scope is None:
                    scope = Scopes(
                        name=scope_name,
                        description=scope_desc,
                    )
                    session.add(scope)
                    await session.flush()
                    created_scopes += 1

                result = await session.execute(
                    select(ScopeGroupScopes).where(
                        ScopeGroupScopes.group_id == group.id,
                        ScopeGroupScopes.scope_id == scope.id,
                    )
                )
                if result.scalar_one_or_none() is None:
                    session.add(ScopeGroupScopes(
                        group_id=group.id,
                        scope_id=scope.id,
                    ))
                    created_links += 1

        await session.commit()

    except Exception as e:
        await session.rollback()
        log.error(f"Ошибка при создании изначальных групп {e}")
        raise

async def seed_admin(session: AsyncSession) -> None:

    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD

    result = await session.execute(
        select(Users).where(Users.email == email)
    )
    admin = result.scalar_one_or_none()

    if admin is not None:
        log.info(f"Админ уже существует")
        admin.is_active = True
        admin.delete_at = None
        await session.commit()
        return

    await user_manager.create_user(
        first_name="Admin",
        last_name=None,
        middle_name=None,
        email=email,
        password=password,
        group_name="Администратор",
        granted_by=None,
        session=session,
    )
    log.info(f"Создан админ: {email}")