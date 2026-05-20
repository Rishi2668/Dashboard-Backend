from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.revision import RevisionItem
    from app.models.user import User


class RevisionHistory(Base):
    __tablename__ = "revision_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revision_item_id: Mapped[int] = mapped_column(
        ForeignKey("revision_items.id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(50))
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    completed_on: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    revision_item: Mapped["RevisionItem"] = relationship(back_populates="history_entries")
    user: Mapped["User"] = relationship()
