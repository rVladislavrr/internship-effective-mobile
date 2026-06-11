import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UUID, VARCHAR, CHAR

from src.models import Base


class Users(Base):
    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        comment='Public user UUID'
    )

    first_name: Mapped[str] = mapped_column(VARCHAR(500),
                                            comment='Имя')

    last_name: Mapped[str | None] = mapped_column(VARCHAR(500),
                                                  nullable=True,
                                                  comment='Фамилия')

    middle_name: Mapped[str | None] = mapped_column(VARCHAR(500),
                                                    nullable=True,
                                                    comment='Отчество')

    email: Mapped[str] = mapped_column(VARCHAR(500),
                                       unique=True,
                                       index=True, comment='Почта')

    is_active: Mapped[bool] = mapped_column(default=True,
                                            index=True,
                                            comment='Активен ли')

    hash_password: Mapped[str] = mapped_column(
        VARCHAR(255),
        comment='Hash password'
    )

    scopes: Mapped[list["UserScopes"]] = relationship(
        "UserScopes",
        back_populates="user",
        foreign_keys="UserScopes.user_id",
        cascade="all, delete-orphan",
    )
