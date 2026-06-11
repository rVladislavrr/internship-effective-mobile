from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, UniqueConstraint

from src.models import Base


class ScopeGroupScopes(Base):
    __tablename__ = 'scope_group_scopes'

    __table_args__ = (
        UniqueConstraint('group_id', 'scope_id', name='uq_group_scope'),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        unique=True,
    )

    group_id: Mapped[int] = mapped_column(ForeignKey('scope_groups.id'))
    scope_id: Mapped[int] = mapped_column(ForeignKey('scopes.id'))

    group: Mapped["ScopeGroups"] = relationship(
        "ScopeGroups",
        back_populates="scopes",
    )
    scope: Mapped["Scopes"] = relationship(
        "Scopes",
        back_populates="group_scopes",
    )