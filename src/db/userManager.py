import logging
from datetime import timezone, datetime

import bcrypt
from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, InterfaceError, SQLAlchemyError
from fastapi import HTTPException, status

from src.db.base import BaseManager
from src.models.users import Users
from src.models.user_scopes import UserScopes
from src.models.scopes import Scopes
from src.models.scope_groups import ScopeGroups
from src.models.scope_group_scopes import ScopeGroupScopes
from src.schemes.scopes import ScopeRead
from src.schemes.users import UserCreate, UserRead, UserUpdate

log = logging.getLogger(__name__)


class UserManager(BaseManager[UserCreate, UserRead, UserUpdate, Users]):
    create_schema = UserCreate
    read_schema = UserRead
    update_schema = UserUpdate
    model = Users


    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @staticmethod
    async def _get_by_email(email: str, session: AsyncSession) -> Users | None:
        result = await session.execute(
            select(Users).where(Users.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _assign_group_scopes(
        user_id: UUID4,
        group_name: str,
        granted_by: UUID4 | None,
        session: AsyncSession,
    ) -> None:
        result = await session.execute(
            select(ScopeGroups).where(ScopeGroups.name == group_name)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise ValueError(f"Группа '{group_name}' не найдена — запусти seed")

        result = await session.execute(
            select(Scopes)
            .join(ScopeGroupScopes, ScopeGroupScopes.scope_id == Scopes.id)
            .where(ScopeGroupScopes.group_id == group.id)
        )
        scopes = result.scalars().all()

        for scope in scopes:
            exists = await session.execute(
                select(UserScopes).where(
                    UserScopes.user_id == user_id,
                    UserScopes.scope_id == scope.id,
                )
            )
            if exists.scalar_one_or_none() is None:
                session.add(UserScopes(
                    user_id=user_id,
                    scope_id=scope.id,
                    granted_by=granted_by,
                ))

    async def create_user(
        self,
        first_name: str,
        last_name: str | None,
        middle_name: str | None,
        email: str,
        password: str,
        group_name: str = "Пользователь",
        granted_by: UUID4 | None = None,
        session: AsyncSession | None = None,
        request_id: str | None = None,
    ) -> UserRead:
        log.debug(f"{request_id} | Создание пользователя: {email}")

        async def _create(s: AsyncSession) -> UserRead:
            existing = await self._get_by_email(email, s)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"msg": "Пользователь с таким email уже существует"},
                )

            user = Users(
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                email=email,
                hash_password=self._hash_password(password),
                is_active=True,
            )
            s.add(user)
            await s.flush()

            await self._assign_group_scopes(user.id, group_name, granted_by, s)

            await s.commit()
            await s.refresh(user)

            log.debug(f"{request_id} | Пользователь создан: {user.id}")
            return UserRead.model_validate(user, from_attributes=True)

        try:
            if session is None:
                from src.db.connection import async_session_maker
                async with async_session_maker() as s:
                    return await _create(s)
            else:
                return await _create(session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            log.critical(f"{request_id} | БД недоступна: {e}", exc_info=True)
            raise ConnectionError(f"БД недоступна: {e}") from e
        except SQLAlchemyError as e:
            log.error(f"{request_id} | Ошибка БД: {e}", exc_info=True)
            raise
        except Exception as e:
            log.error(f"{request_id} | Неожиданная ошибка: {e}", exc_info=True)
            raise

    async def verify_password(
        self,
        email: str,
        password: str,
        session: AsyncSession | None = None,
        request_id: str | None = None,
    ) -> Users:
        log.debug(f"{request_id} | Проверка пароля: {email}")

        async def _verify(s: AsyncSession) -> Users:
            user = await self._get_by_email(email, s)

            if user is None or not self._verify_password(password, user.hash_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"msg": "Неверный email или пароль"},
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"msg": "Аккаунт деактивирован"},
                )
            return user

        try:
            if session is None:
                from src.db.connection import async_session_maker
                async with async_session_maker() as s:
                    return await _verify(s)
            else:
                return await _verify(session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            log.critical(f"{request_id} | БД недоступна: {e}", exc_info=True)
            raise ConnectionError(f"БД недоступна: {e}") from e
        except Exception as e:
            log.error(f"{request_id} | Ошибка: {e}", exc_info=True)
            raise

    @staticmethod
    async def get_user_scopes(
        user_id: UUID4,
        session: AsyncSession | None = None,
    ) -> list[str]:

        async def _get(s: AsyncSession) -> list[str]:
            result = await s.execute(
                select(Scopes.name)
                .join(UserScopes, UserScopes.scope_id == Scopes.id)
                .where(UserScopes.user_id == user_id)
            )
            return list(result.scalars().all())

        if session is None:
            from src.db.connection import async_session_maker
            async with async_session_maker() as s:
                return await _get(s)
        else:
            return await _get(session)

    @staticmethod
    def _db_critical(action: str, e: Exception) -> HTTPException:
        log.critical(f"[users] БД недоступна при '{action}': {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"msg": "База данных недоступна, попробуйте позже"},
        )

    @staticmethod
    def _db_error(action: str, e: Exception) -> HTTPException:
        log.error(f"[users] Ошибка БД при '{action}': {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"msg": f"Ошибка при выполнении операции"},
        )

    async def _get_or_404(self, user_id: UUID4, session: AsyncSession) -> Users:
        user = await session.get(Users, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"msg": "Пользователь не найден"},
            )
        return user

    async def get_me(
            self,
            user_id: UUID4,
            session: AsyncSession,
    ) -> UserRead:
        try:
            user = await self._get_or_404(user_id, session)
            return UserRead.model_validate(user, from_attributes=True)
        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            raise self._db_critical("get_me", e)
        except SQLAlchemyError as e:
            raise self._db_error("get_me", e)

    async def get_my_scopes(
            self,
            user_id: UUID4,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            result = await session.execute(
                select(Scopes)
                .join(UserScopes, UserScopes.scope_id == Scopes.id)
                .where(UserScopes.user_id ==user_id)
                .order_by(Scopes.name)
            )
            return [ScopeRead.model_validate(s, from_attributes=True)
                    for s in result.scalars().all()]
        except (OperationalError, InterfaceError) as e:
            raise self._db_critical("get_my_scopes", e)
        except SQLAlchemyError as e:
            raise self._db_error("get_my_scopes", e)

    async def update_me(
            self,
            user_id: UUID4,
            data: UserUpdate,
            session: AsyncSession,
    ) -> UserRead:
        try:
            user = await self._get_or_404(user_id, session)

            update_data = data.model_dump(exclude_none=True, exclude={"password_confirm"})

            if "password" in update_data:
                update_data["hash_password"] = self._hash_password(
                    update_data.pop("password")
                )

            if "email" in update_data and update_data["email"] != user.email:
                exists = await session.execute(
                    select(Users).where(Users.email == update_data["email"])
                )
                if exists.scalar_one_or_none() is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"msg": "Email уже занят"},
                    )

            for field, value in update_data.items():
                setattr(user, field, value)

            await session.commit()
            await session.refresh(user)

            log.info(f"[users] Обновлён профиль user_id={user_id}, поля: {list(update_data.keys())}")
            return UserRead.model_validate(user, from_attributes=True)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("update_me", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("update_me", e)

    async def delete_me(
            self,
            user_id: UUID4,
            session: AsyncSession,
    ) -> UserRead:
        try:
            user = await self._get_or_404(user_id, session)

            user.is_active = False
            user.delete_at = datetime.now(timezone.utc).replace(tzinfo=None)

            await session.commit()
            await session.refresh(user)

            log.info(f"[users] Мягкое удаление user_id={user_id}")
            return UserRead.model_validate(user, from_attributes=True)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("delete_me", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("delete_me", e)


user_manager = UserManager()