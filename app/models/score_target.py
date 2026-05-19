from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserScoreTarget(Base):
    """Overall and subject-wise mock score targets (SSC CGL Tier-1 style)."""

    __tablename__ = "user_score_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    overall_max_marks: Mapped[float] = mapped_column(Float, default=200.0)
    overall_target_marks: Mapped[float] = mapped_column(Float, default=170.0)
    reasoning_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    reasoning_target_marks: Mapped[float] = mapped_column(Float, default=45.0)
    quant_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    quant_target_marks: Mapped[float] = mapped_column(Float, default=48.0)
    english_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    english_target_marks: Mapped[float] = mapped_column(Float, default=47.0)
    gk_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    gk_target_marks: Mapped[float] = mapped_column(Float, default=35.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="score_target")
