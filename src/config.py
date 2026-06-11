from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent


class AuthJWT(BaseModel):
    private_key_path: Path = BASE_DIR / "certs" / "jwt-private.pem"
    public_key_path: Path = BASE_DIR / "certs" / "jwt-public.pem"
    algorithm: str = 'RS256'
    access_token_expire_minutes: int = 5
    refresh_token_expire_days: int = 7
    key_cookie_access: str = "access_token"
    key_cookie_refresh: str = "refresh_token"


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_USER: str
    DB_PASS: str

    APP_HOST: str
    APP_PORT: int

    REDIS_HOST: str = '127.0.0.1'
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str
    REDIS_DB_SESSIONS: int = 0

    # Бд тест
    DB_HOST_TEST: str
    DB_PORT_TEST: str
    DB_NAME_TEST: str
    DB_USER_TEST: str
    DB_PASS_TEST: str

    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str

    LOG_LEVEL: str = 'DEBUG'

    auth_jwt: AuthJWT = AuthJWT()

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env",
                                      extra="ignore")

    @property
    def DATABASE_URL(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_TEST(self):
        return f"postgresql+asyncpg://{self.DB_USER_TEST}:{self.DB_PASS_TEST}@{self.DB_HOST_TEST}:{self.DB_PORT_TEST}/{self.DB_NAME_TEST}"

    @property
    def DATABASE_URL_ALEMBIC(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"

settings = Settings()
