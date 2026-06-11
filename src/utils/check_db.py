from src.db.connection import engine
from sqlalchemy import inspect, text

from src.models.base import Base


async def ping_database():
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        async with engine.begin() as conn:
            available_tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        expected_tables = Base.metadata.tables.keys()

        if not expected_tables:
            raise ValueError("Нет ни одной таблицы")

        missing_tables = []
        for table_name in expected_tables:
            if table_name not in available_tables:
                missing_tables.append(table_name)

        if missing_tables:
            raise ConnectionError(
                f"Недоступны таблицы: {', '.join(missing_tables)}"
            )

        return True

    except Exception as e:
        if isinstance(e, (TimeoutError, ConnectionError, ValueError)):
            raise e
        raise TimeoutError(f'Нет соединения с бд: {str(e)}')