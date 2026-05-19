"""Compute and sync user XP from activity records."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc_practice import CalcPracticeSession
from app.models.mock_test import MockTest
from app.models.note import Note
from app.models.revision import RevisionItem
from app.models.study import StudySession
from app.models.syllabus import UserChapterProgress
from app.models.user import User
from app.services.ai.recommendation_engine import get_level_from_xp

# XP rules (keep in sync with route handlers)
XP_PER_STUDY_HOUR = 10
XP_PER_STUDY_TASK = 5
XP_PER_MOCK = 50
XP_PER_NOTE = 10
XP_PER_REVISION_COMPLETE = 20
XP_PER_SYLLABUS_CHAPTER = 25
XP_PER_SYLLABUS_REVISION = 10


async def compute_xp_breakdown(db: AsyncSession, user_id: int) -> dict[str, int]:
    calc_r = await db.execute(
        select(func.coalesce(func.sum(CalcPracticeSession.xp_earned), 0)).where(
            CalcPracticeSession.user_id == user_id
        )
    )
    calc_xp = int(calc_r.scalar() or 0)

    study_r = await db.execute(
        select(
            func.coalesce(func.sum(StudySession.hours), 0),
            func.coalesce(func.sum(StudySession.tasks_completed), 0),
        ).where(StudySession.user_id == user_id)
    )
    hours, tasks = study_r.one()
    study_xp = int(float(hours or 0) * XP_PER_STUDY_HOUR) + int(tasks or 0) * XP_PER_STUDY_TASK

    mock_r = await db.execute(
        select(func.count(MockTest.id)).where(MockTest.user_id == user_id)
    )
    mock_xp = int(mock_r.scalar() or 0) * XP_PER_MOCK

    notes_r = await db.execute(select(func.count(Note.id)).where(Note.user_id == user_id))
    notes_xp = int(notes_r.scalar() or 0) * XP_PER_NOTE

    rev_r = await db.execute(
        select(func.coalesce(func.sum(RevisionItem.revision_count), 0)).where(
            RevisionItem.user_id == user_id
        )
    )
    revision_xp = int(rev_r.scalar() or 0) * XP_PER_REVISION_COMPLETE

    completed_r = await db.execute(
        select(func.count(UserChapterProgress.id)).where(
            UserChapterProgress.user_id == user_id,
            UserChapterProgress.completed.is_(True),
        )
    )
    syl_rev_r = await db.execute(
        select(func.coalesce(func.sum(UserChapterProgress.revision_count), 0)).where(
            UserChapterProgress.user_id == user_id
        )
    )
    syllabus_xp = int(completed_r.scalar() or 0) * XP_PER_SYLLABUS_CHAPTER + int(
        syl_rev_r.scalar() or 0
    ) * XP_PER_SYLLABUS_REVISION

    accounted = calc_xp + study_xp + mock_xp + notes_xp + revision_xp + syllabus_xp
    return {
        "calc_practice": calc_xp,
        "study_sessions": study_xp,
        "mock_tests": mock_xp,
        "notes": notes_xp,
        "revision": revision_xp,
        "syllabus": syllabus_xp,
        "accounted_total": accounted,
    }


async def sync_user_xp(db: AsyncSession, user: User) -> dict[str, int]:
    """Set user.xp from current activities (removes ghost XP after deletes)."""
    breakdown = await compute_xp_breakdown(db, user.id)
    user.xp = max(0, breakdown["accounted_total"])
    level, _, _, _, _ = get_level_from_xp(user.xp)
    user.level = level
    await db.flush()
    return breakdown
