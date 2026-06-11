import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError, InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.connection import async_session_maker
from src.models.base import Base

TCreate = TypeVar("TCreate", bound=BaseModel)
TRead = TypeVar("TRead", bound=BaseModel)
TUpdate = TypeVar("TUpdate", bound=BaseModel)
TModel = TypeVar("TModel", bound=Base)

database_logger = logging.getLogger("Бд")


#TODO: уже понял что некоторые функции не будут рааботать если не передавать в них сессию,
# брал с прошлого своего проекта,
# и такая работа с сессиями неправильная и уже исправлена в некоторых роутах

class BaseManager(Generic[TCreate, TRead, TUpdate, TModel]):
    create_schema: type[TCreate]
    read_schema: type[TRead]
    update_schema: type[TUpdate]
    model: type[TModel]

    async def __create_entity(self, data: dict, session: AsyncSession) -> TModel:
        instance = self.model(**data)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance

    async def get(self, entity_id: int,
                  session: AsyncSession | None = None,
                  request_id: str | None = None) -> TRead:
        database_logger.debug(f"{request_id} | Начало получения {self.model.__name__}")

        try:
            if session is None:

                async with async_session_maker() as session:
                    entity = await session.get(self.model, entity_id)

            else:
                entity = await session.get(self.model, entity_id)

            if entity is None:
                database_logger.debug(f"{request_id} | Не найден {self.model.__name__} id: {entity_id}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, )

            database_logger.debug(f"{request_id} | Успешно получен {self.model.__name__} id: {entity_id}")
            return self.read_schema.model_validate(entity, from_attributes=True)

        except HTTPException:
            raise
        except (OperationalError, InterfaceError) as e:
            database_logger.critical(
                f"{request_id} | База данных недоступна {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise ConnectionError(f"{request_id} | База данных недоступна: {e}") from e

        except SQLAlchemyError as e:
            database_logger.error(
                f"{request_id} | Ошибка БД при получении {self.model.__name__}, Ошибка: {e}",
                exc_info=True,
            )
            raise

        except Exception as e:
            database_logger.error(
                f"Ошибка при получении {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise

    async def create(self, create_data: TCreate,
                     session: AsyncSession | None = None,
                     request_id: str | None = None) -> TRead:
        database_logger.debug(f"{request_id} | Начало создания {self.model.__name__}")

        data = create_data.model_dump(exclude_unset=True)

        try:
            if session is None:

                async with async_session_maker() as session:
                    entity = await self.__create_entity(data, session)

            else:
                entity = await self.__create_entity(data, session)

            await session.commit()

            database_logger.debug(f"{request_id} | Успешно создан {self.model.__name__}: {entity}")

            return self.read_schema.model_validate(entity, from_attributes=True)

        except (OperationalError, InterfaceError) as e:
            database_logger.critical(
                f"{request_id} | База данных недоступна {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise ConnectionError(f"{request_id} | База данных недоступна: {e}") from e

        except SQLAlchemyError as e:
            database_logger.error(
                f"{request_id} | Ошибка БД при создании {self.model.__name__}: {data}, Ошибка: {e}",
                exc_info=True,
            )
            raise

        except Exception as e:
            database_logger.error(
                f"Ошибка при создании {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, index_entity: str,
                     session: AsyncSession | None = None,
                     request_id: str | None = None) -> TRead:
        database_logger.debug(f"{request_id} | Начало удаления {self.model.__name__} с индексом: {index_entity}")

        try:
            if session is None:

                async with async_session_maker() as session:
                    entity: type[TModel] = await session.get(self.model, index_entity)

            else:
                entity: type[TModel] = await session.get(self.model, index_entity)

            if entity is None:
                database_logger.debug(
                    f"{request_id} | Объект {self.model.__name__} с индексом: {index_entity} не найден")

                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Object not found')

            if not entity.is_active:
                database_logger.debug(
                    f"{request_id} | Объект {self.model.__name__} с индексом: {index_entity} уже удалён")

                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Object already deleted')

            entity.is_active = False
            entity.delete_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()

            database_logger.debug(
                f"{request_id} | Объект {self.model.__name__} с индексом: {index_entity} удалён")

            return self.read_schema.model_validate(entity, from_attributes=True)

        except HTTPException:
            raise

        except (OperationalError, InterfaceError) as e:
            database_logger.critical(
                f"{request_id} | База данных недоступна {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise ConnectionError(f"{request_id} | База данных недоступна: {e}") from e

        except Exception as e:
            database_logger.error(
                f"Ошибка при удалении {self.model.__name__}: {e}",
                exc_info=True,
            )
            raise

    @property
    def __name__(self):
        return self.__class__.__name__
