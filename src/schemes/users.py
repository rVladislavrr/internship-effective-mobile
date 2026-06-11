import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator, model_validator, Field, UUID4

TOKEN_TYPE_FIELD = "type"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

class Token(BaseModel):
    token_type: str = 'Bearer'
    accessToken: str


class UserInfo(BaseModel):
    sub: str
    active: bool
    scopes: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=500)
    last_name: str | None = Field(default=None, max_length=500)
    middle_name: str | None = Field(default=None, max_length=500)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    password_confirm: str = Field(min_length=6, max_length=100)

    @field_validator("first_name", "last_name", "middle_name", mode="before")
    @classmethod
    def strip_spaces(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self

class UserRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str | None
    middle_name: str | None
    email: EmailStr
    is_active: bool
    create_at: datetime
    update_at: datetime

    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=500)
    last_name: str | None = Field(default=None, max_length=500)
    middle_name: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = None

    password: str | None = Field(default=None, min_length=6, max_length=100)
    password_confirm: str | None = Field(default=None, min_length=6, max_length=100)

    @field_validator("first_name", "last_name", "middle_name", mode="before")
    @classmethod
    def strip_spaces(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "UserUpdate":
        if self.password is not None or self.password_confirm is not None:
            if self.password != self.password_confirm:
                raise ValueError("Пароли не совпадают")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str