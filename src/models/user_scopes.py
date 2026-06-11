from sqlalchemy import UUID, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class UserScopes(Base):
    __tablename__ = 'user_scopes'

    __table_args__ = (
        UniqueConstraint('user_id', 'scope_id', name='uq_user_scope'),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        unique=True,
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)

    scope_id: Mapped[int] = mapped_column(ForeignKey('scopes.id'))

    granted_by: Mapped[UUID | None] = mapped_column(
        ForeignKey('users.id'),
        nullable=True,
        index=True,
        comment='Кто выдал'
    )

    # Связи
    user: Mapped["Users"] = relationship(
        "Users",
        back_populates="scopes",
        foreign_keys=[user_id],
    )

    scope: Mapped["Scopes"] = relationship(
        "Scopes",
        back_populates="user_scopes",
    )