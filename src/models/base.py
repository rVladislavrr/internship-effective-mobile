from sqlalchemy import func
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    create_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment='Время создания'
    )

    update_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        server_onupdate=func.now(),
        onupdate=func.now(),
        comment='Время обновления'
    )

    delete_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment='Время удаления'
    )

    def __repr__(self) -> str:
        cols = [f"{col}={getattr(self, col)}" for col in self.__table__.columns.keys()]
        return f"<{self.__class__.__name__}: {', '.join(cols)}>"
