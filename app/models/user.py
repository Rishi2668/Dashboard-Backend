from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.study import StudySession, DailyTarget
    from app.models.mock_test import MockTest
    from app.models.streak import Streak, Achievement
    from app.models.note import Note
    from app.models.revision import RevisionItem
    from app.models.weak_area import WeakTopic
    from app.models.pyq import PYQProgress
    from app.models.ai_insight import AIInsight
    from app.models.syllabus import UserChapterProgress
    from app.models.calc_practice import CalcPracticeSession, CalcQuestionAttempt, CalcWeakAreaStat
    from app.models.score_target import UserScoreTarget
    from app.models.roadmap_task import UserRoadmapTaskProgress


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    target_year: Mapped[int] = mapped_column(Integer, default=2026)
    target_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_mock_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(50), default="Beginner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    study_sessions: Mapped[List["StudySession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    daily_targets: Mapped[List["DailyTarget"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mock_tests: Mapped[List["MockTest"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    streaks: Mapped[List["Streak"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    achievements: Mapped[List["Achievement"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notes: Mapped[List["Note"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    revision_items: Mapped[List["RevisionItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weak_topics: Mapped[List["WeakTopic"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    pyq_progress: Mapped[List["PYQProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_insights: Mapped[List["AIInsight"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chapter_progress: Mapped[List["UserChapterProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    calc_sessions: Mapped[List["CalcPracticeSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    calc_attempts: Mapped[List["CalcQuestionAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    calc_weak_stats: Mapped[List["CalcWeakAreaStat"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    score_target: Mapped[Optional["UserScoreTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    roadmap_tasks: Mapped[List["UserRoadmapTaskProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
