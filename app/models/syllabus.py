from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SyllabusSubject(Base):
    __tablename__ = "syllabus_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_name: Mapped[str] = mapped_column(String(30), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="blue")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    chapters: Mapped[List["SyllabusChapter"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class SyllabusChapter(Base):
    __tablename__ = "syllabus_chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("syllabus_subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), index=True)  # very_high, high, medium, low
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped["SyllabusSubject"] = relationship(back_populates="chapters")
    user_progress: Mapped[List["UserChapterProgress"]] = relationship(back_populates="chapter")


class UserChapterProgress(Base):
    __tablename__ = "user_chapter_progress"
    __table_args__ = (UniqueConstraint("user_id", "chapter_id", name="uq_user_chapter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("syllabus_chapters.id", ondelete="CASCADE"), index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    revision_status: Mapped[str] = mapped_column(String(30), default="not_started")
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    last_revised: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_spent_minutes: Mapped[int] = mapped_column(Integer, default=0)
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="chapter_progress")
    chapter: Mapped["SyllabusChapter"] = relationship(back_populates="user_progress")
