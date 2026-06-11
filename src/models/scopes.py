from sqlalchemy import VARCHAR, TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Scopes(Base):
    __tablename__ = 'scopes'

    id: Mapped[int] = mapped_column(
        primary_key=True,
        unique=True,
    )

    name: Mapped[str] = mapped_column(VARCHAR(50), unique=True)

    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    user_scopes: Mapped[list["UserScopes"]] = relationship(
        "UserScopes",
        back_populates="scope",
    )

    group_scopes: Mapped[list["ScopeGroupScopes"]] = relationship(
        "ScopeGroupScopes",
        back_populates="scope",
    )