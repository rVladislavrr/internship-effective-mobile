import logging

from fastapi import HTTPException, status
from pydantic import UUID4
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError, OperationalError, InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scopes import Scopes
from src.models.scope_groups import ScopeGroups
from src.models.scope_group_scopes import ScopeGroupScopes
from src.models.user_scopes import UserScopes
from src.models.users import Users
from src.schemes.scopes import ScopeRead, ScopeGroupWithScopes

log = logging.getLogger(__name__)


class AdminManager:

    @staticmethod
    def _db_critical(action: str, e: Exception) -> HTTPException:
        log.critical(f"БД недоступна при '{action}': {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"msg": "База данных недоступна"},
        )

    @staticmethod
    def _db_error(action: str, e: Exception) -> HTTPException:
        log.error(f"Ошибка БД при '{action}': {e}", exc_info=True)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"msg": f"Ошибка при выполнении операции '{action}'"},
        )

    @staticmethod
    async def _get_user_or_404(user_id: UUID4, session: AsyncSession) -> Users:
        user: Users | None = await session.get(Users, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"msg": "Пользователь не найден"},
            )
        return user

    @staticmethod
    async def _get_scope_or_404(scope_id: int, session: AsyncSession) -> Scopes:
        scope: Scopes | None = await session.get(Scopes, scope_id)
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"msg": f"Скоуп id={scope_id} не найден"},
            )
        return scope

    @staticmethod
    async def _get_group_or_404(group_id: int, session: AsyncSession) -> ScopeGroups:
        group: ScopeGroups | None = await session.get(ScopeGroups, group_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"msg": f"Группа id={group_id} не найдена"},
            )
        return group

    @staticmethod
    async def _get_user_scopes(
            user_id: UUID4,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        result = await session.execute(
            select(Scopes)
            .join(UserScopes, UserScopes.scope_id == Scopes.id)
            .where(UserScopes.user_id == user_id)
            .order_by(Scopes.name)
        )
        return [ScopeRead.model_validate(s, from_attributes=True)
                for s in result.scalars().all()]

    async def get_all_scopes(self, session: AsyncSession) -> list[ScopeRead]:
        try:
            result = await session.execute(select(Scopes).order_by(Scopes.id))
            return [ScopeRead.model_validate(s, from_attributes=True)
                    for s in result.scalars().all()]
        except (OperationalError, InterfaceError) as e:
            raise self._db_critical("get_all_scopes", e)
        except SQLAlchemyError as e:
            raise self._db_error("get_all_scopes", e)

    async def get_all_groups(self, session: AsyncSession) -> list[ScopeGroupWithScopes]:
        try:
            result = await session.execute(select(ScopeGroups).order_by(ScopeGroups.id))
            groups = result.scalars().all()

            response = []
            for group in groups:
                scopes_result = await session.execute(
                    select(Scopes)
                    .join(ScopeGroupScopes, ScopeGroupScopes.scope_id == Scopes.id)
                    .where(ScopeGroupScopes.group_id == group.id)
                )
                response.append(ScopeGroupWithScopes(
                    id=group.id,
                    name=group.name,
                    description=group.description,
                    scopes=[ScopeRead.model_validate(s, from_attributes=True)
                            for s in scopes_result.scalars().all()],
                ))
            return response
        except (OperationalError, InterfaceError) as e:
            raise self._db_critical("get_all_groups", e)
        except SQLAlchemyError as e:
            raise self._db_error("get_all_groups", e)

    async def get_user_scopes(
            self,
            user_id: UUID4,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            await self._get_user_or_404(user_id, session)
            return await self._get_user_scopes(user_id, session)
        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            raise self._db_critical("get_user_scopes", e)
        except SQLAlchemyError as e:
            raise self._db_error("get_user_scopes", e)

    async def assign_scope(
            self,
            user_id: UUID4,
            scope_id: int,
            granted_by: UUID4,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            await self._get_user_or_404(user_id, session)
            await self._get_scope_or_404(scope_id, session)

            exists = await session.execute(
                select(UserScopes).where(
                    UserScopes.user_id == user_id,
                    UserScopes.scope_id == scope_id,
                )
            )
            if exists.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"msg": "Скоуп уже выдан этому пользователю"},
                )

            session.add(UserScopes(
                user_id=user_id,
                scope_id=scope_id,
                granted_by=granted_by,
            ))
            await session.commit()
            log.info(f"assign scope_id={scope_id} user_id={user_id}  {granted_by}")

            return await self._get_user_scopes(user_id, session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("assign_scope", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("assign_scope", e)

    async def revoke_scope(
            self,
            user_id: UUID4,
            scope_id: int,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            await self._get_user_or_404(user_id, session)
            await self._get_scope_or_404(scope_id, session)

            deleted = await session.execute(
                delete(UserScopes).where(
                    UserScopes.user_id == user_id,
                    UserScopes.scope_id == scope_id,
                )
            )
            if deleted.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": "Скоуп не найден у пользователя"},
                )

            await session.commit()
            log.info(f"revoke scope_id={scope_id} user_id={user_id}")

            return await self._get_user_scopes(user_id, session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("revoke_scope", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("revoke_scope", e)

    async def assign_group(
            self,
            user_id: UUID4,
            group_id: int,
            granted_by: UUID4,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            await self._get_user_or_404(user_id, session)
            group = await self._get_group_or_404(group_id, session)

            scopes_result = await session.execute(
                select(Scopes)
                .join(ScopeGroupScopes, ScopeGroupScopes.scope_id == Scopes.id)
                .where(ScopeGroupScopes.group_id == group.id)
            )
            scopes = scopes_result.scalars().all()

            if not scopes:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": f"Группа id={group_id} не содержит скоупов"},
                )

            added = 0
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
                    added += 1

            await session.commit()
            log.info(f"group_id={group_id}user_id={user_id}, выдано: {added}")

            return await self._get_user_scopes(user_id, session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("assign_group", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("assign_group", e)

    async def revoke_group(
            self,
            user_id: UUID4,
            group_id: int,
            session: AsyncSession,
    ) -> list[ScopeRead]:
        try:
            await self._get_user_or_404(user_id, session)
            group = await self._get_group_or_404(group_id, session)

            scopes_result = await session.execute(
                select(Scopes)
                .join(ScopeGroupScopes, ScopeGroupScopes.scope_id == Scopes.id)
                .where(ScopeGroupScopes.group_id == group.id)
            )
            scope_ids = [s.id for s in scopes_result.scalars().all()]

            if not scope_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": f"Группа id={group_id} не содержит скоупов"},
                )

            deleted = await session.execute(
                delete(UserScopes).where(
                    UserScopes.user_id == user_id,
                    UserScopes.scope_id.in_(scope_ids),
                )
            )
            if deleted.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"msg": "У пользователя не было скоупов этой группы"},
                )

            await session.commit()
            log.info(f"group_id={group_id} user_id={user_id} удалено: {deleted.rowcount}")

            return await self._get_user_scopes(user_id, session)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            await session.rollback()
            raise self._db_critical("revoke_group", e)
        except SQLAlchemyError as e:
            await session.rollback()
            raise self._db_error("revoke_group", e)


admin_manager = AdminManager()