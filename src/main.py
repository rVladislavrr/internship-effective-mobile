import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from starlette.middleware.cors import CORSMiddleware

from src.config import settings
from src.db.connection import async_session_maker
from src.logger import setup_logging
from src.middlewares.authMiddleware import AuthMiddleware
from src.middlewares.loggingMiddleware import LoggingMiddleware
from src.redis_conn import redis_client
from src.utils.check_db import ping_database
from src.api.routers import router
from src.utils.create_bd import seed_scope_groups, seed_admin


@asynccontextmanager
async def lifespan(app_l: FastAPI):
    setup_logging()
    log = logging.getLogger(__name__)
    log.info('Начинается lifespan')

    await redis_client.connect()

    await ping_database()

    async with async_session_maker() as session:
        await seed_scope_groups(session)
        await seed_admin(session)

    log.info('Стартовый lifespan успешно прошёл')
    yield
    await redis_client.close()
    log.info('завершающий lifespan')


app = FastAPI(
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
    )
