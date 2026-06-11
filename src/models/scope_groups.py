from sqlalchemy.dialects.mysql import VARCHAR, TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class ScopeGroups(Base):
    __tablename__ = 'scope_groups'

    id: Mapped[int] = mapped_column(
        primary_key=True,
        unique=True,
    )

    name: Mapped[str] = mapped_column(VARCHAR(50), unique=True)

    description: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    scopes: Mapped[list["ScopeGroupScopes"]] = relationship(
        "ScopeGroupScopes",
        back_populates="group",
        cascade="all, delete-orphan",
    )