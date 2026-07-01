from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserRoadmapTaskProgress(Base):
    """Weekly mock tasks & phase-3 virtual revision items."""

    __tablename__ = "user_roadmap_tasks"
    __table_args__ = (UniqueConstraint("user_id", "week_number", "task_key", name="uq_user_roadmap_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_number: Mapped[int] = mapped_column(Integer, index=True)
    task_key: Mapped[str] = mapped_column(String(80), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_taken_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weak_areas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="roadmap_tasks")
