from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.revision_history import RevisionHistory
    from app.models.user import User


class RevisionItem(Base):
    __tablename__ = "revision_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=3)
    next_revision_date: Mapped[date] = mapped_column(Date, index=True)
    last_revised: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="revision_items")
    history_entries: Mapped[List["RevisionHistory"]] = relationship(
        back_populates="revision_item", cascade="all, delete-orphan"
    )
