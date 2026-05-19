from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class MockTest(Base):
    __tablename__ = "mock_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    test_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test_date: Mapped[date] = mapped_column(Date, index=True)
    test_type: Mapped[str] = mapped_column(String(20), default="full", index=True)
    section_subject: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=200.0)
    total_questions: Mapped[int] = mapped_column(Integer, default=100)
    attempted: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    negative_marks: Mapped[float] = mapped_column(Float, default=0.0)

    # Reasoning
    reasoning_score: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    reasoning_total_questions: Mapped[int] = mapped_column(Integer, default=25)
    reasoning_attempted: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_correct: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_wrong: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    # Quant
    quant_score: Mapped[float] = mapped_column(Float, default=0.0)
    quant_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    quant_total_questions: Mapped[int] = mapped_column(Integer, default=25)
    quant_attempted: Mapped[int] = mapped_column(Integer, default=0)
    quant_correct: Mapped[int] = mapped_column(Integer, default=0)
    quant_wrong: Mapped[int] = mapped_column(Integer, default=0)
    quant_accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    # English
    english_score: Mapped[float] = mapped_column(Float, default=0.0)
    english_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    english_total_questions: Mapped[int] = mapped_column(Integer, default=25)
    english_attempted: Mapped[int] = mapped_column(Integer, default=0)
    english_correct: Mapped[int] = mapped_column(Integer, default=0)
    english_wrong: Mapped[int] = mapped_column(Integer, default=0)
    english_accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    # GK
    gk_score: Mapped[float] = mapped_column(Float, default=0.0)
    gk_max_marks: Mapped[float] = mapped_column(Float, default=50.0)
    gk_total_questions: Mapped[int] = mapped_column(Integer, default=25)
    gk_attempted: Mapped[int] = mapped_column(Integer, default=0)
    gk_correct: Mapped[int] = mapped_column(Integer, default=0)
    gk_wrong: Mapped[int] = mapped_column(Integer, default=0)
    gk_accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="mock_tests")
