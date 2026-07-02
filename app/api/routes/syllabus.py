import logging

from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.syllabus import SyllabusChapter, SyllabusSubject, UserChapterProgress
from app.schemas.syllabus import (
    ChapterOut,
    ChapterProgressUpdate,
    ExamTargetsUpdate,
    SubjectOut,
    SyllabusAIInsight,
    SyllabusRoadmapOut,
)
from app.services.syllabus_ai import SyllabusAIEngine
from app.services.xp_breakdown import sync_user_xp
from app.utils.syllabus_seed import PRIORITY_LABELS
from fastapi import Depends

router = APIRouter(prefix="/syllabus", tags=["syllabus"])
logger = logging.getLogger(__name__)


def _revision_status_from_progress(prog: UserChapterProgress | None) -> str:
    if not prog:
        return "not_started"
    if prog.revision_count == 0 and prog.progress_percentage > 0:
        return "pending"
    if prog.last_revised:
        days = (date.today() - prog.last_revised).days
        if days >= 14:
            return "overdue"
        if days >= 7:
            return "due"
    return prog.revision_status or "not_started"


def _chapter_out(ch: SyllabusChapter, prog: UserChapterProgress | None) -> ChapterOut:
    return ChapterOut(
        id=ch.id,
        name=ch.name,
        priority=ch.priority,
        priority_label=PRIORITY_LABELS.get(ch.priority, ch.priority),
        sort_order=ch.sort_order,
        completed=prog.completed if prog else False,
        progress_percentage=prog.progress_percentage if prog else 0.0,
        accuracy=prog.accuracy if prog else 0.0,
        revision_status=_revision_status_from_progress(prog),
        revision_count=prog.revision_count if prog else 0,
        last_revised=prog.last_revised if prog else None,
        is_weak=prog.is_weak if prog else False,
        notes=prog.notes if prog else None,
        time_spent_minutes=prog.time_spent_minutes if prog else 0,
        bookmarked=prog.bookmarked if prog else False,
    )


async def _get_or_create_progress(
    db: AsyncSession, user_id: int, chapter_id: int
) -> UserChapterProgress:
    result = await db.execute(
        select(UserChapterProgress).where(
            UserChapterProgress.user_id == user_id,
            UserChapterProgress.chapter_id == chapter_id,
        )
    )
    prog = result.scalar_one_or_none()
    if not prog:
        prog = UserChapterProgress(user_id=user_id, chapter_id=chapter_id)
        db.add(prog)
        await db.flush()
    return prog


@router.get("/roadmap", response_model=SyllabusRoadmapOut)
async def get_roadmap(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SyllabusSubject)
        .options(selectinload(SyllabusSubject.chapters))
        .order_by(SyllabusSubject.sort_order)
    )
    subjects = result.scalars().all()

    prog_result = await db.execute(
        select(UserChapterProgress).where(UserChapterProgress.user_id == current_user.id)
    )
    progress_by_chapter = {p.chapter_id: p for p in prog_result.scalars().all()}

    subject_outs: list[SubjectOut] = []
    total_all = 0
    completed_all = 0
    accuracy_sum = 0.0
    accuracy_count = 0

    for subj in subjects:
        chapters_sorted = sorted(
            subj.chapters,
            key=lambda c: (
                {"very_high": 0, "high": 1, "medium": 2, "low": 3}.get(c.priority, 9),
                c.sort_order,
            ),
        )
        chapter_outs = []
        completed = 0
        weak = 0
        acc_sum = 0.0
        acc_n = 0

        for ch in chapters_sorted:
            prog = progress_by_chapter.get(ch.id)
            co = _chapter_out(ch, prog)
            chapter_outs.append(co)
            if co.completed:
                completed += 1
            if co.is_weak:
                weak += 1
            if co.accuracy > 0:
                acc_sum += co.accuracy
                acc_n += 1

        total = len(chapters_sorted)
        total_all += total
        completed_all += completed
        if acc_n:
            accuracy_sum += acc_sum / acc_n
            accuracy_count += 1

        subject_outs.append(
            SubjectOut(
                id=subj.id,
                slug=subj.slug,
                name=subj.name,
                short_name=subj.short_name,
                color=subj.color,
                total_chapters=total,
                completed_chapters=completed,
                completion_percentage=round(completed / total * 100, 1) if total else 0,
                average_accuracy=round(acc_sum / acc_n, 1) if acc_n else 0,
                weak_count=weak,
                chapters=chapter_outs,
            )
        )

    days_left = None
    if current_user.exam_date:
        days_left = max((current_user.exam_date - date.today()).days, 0)

    return SyllabusRoadmapOut(
        subjects=subject_outs,
        overall_completion=round(completed_all / total_all * 100, 1) if total_all else 0,
        total_chapters=total_all,
        completed_chapters=completed_all,
        target_marks=current_user.target_marks,
        exam_date=current_user.exam_date,
        days_to_exam=days_left,
    )


@router.patch("/chapters/{chapter_id}", response_model=ChapterOut)
async def update_chapter_progress(
    chapter_id: int,
    data: ChapterProgressUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ch_result = await db.execute(select(SyllabusChapter).where(SyllabusChapter.id == chapter_id))
    chapter = ch_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    prog = await _get_or_create_progress(db, current_user.id, chapter_id)
    updates = data.model_dump(exclude_unset=True, exclude={"mark_revised"})

    for key, val in updates.items():
        setattr(prog, key, val)

    if data.completed is True:
        prog.progress_percentage = max(prog.progress_percentage, 100.0)
        prog.completed = True
    elif data.completed is False:
        if data.progress_percentage is None:
            prog.progress_percentage = 0.0
        prog.completed = False
    elif data.progress_percentage is not None:
        if data.progress_percentage >= 100:
            prog.completed = True
            prog.progress_percentage = 100.0
        else:
            prog.completed = False

    if data.mark_revised:
        prog.revision_count += 1
        prog.last_revised = date.today()
        prog.revision_status = "revised"

    if data.accuracy is not None and data.accuracy < 55:
        prog.is_weak = True
    elif data.is_weak is False:
        prog.is_weak = False

    prog.updated_at = datetime.now(timezone.utc)
    await db.flush()
    try:
        await sync_user_xp(db, current_user)
    except Exception as exc:
        logger.warning("XP sync skipped after chapter update: %s", exc)
    return _chapter_out(chapter, prog)


@router.get("/chapters/{chapter_id}/history")
async def get_revision_history(
    chapter_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    prog = await _get_or_create_progress(db, current_user.id, chapter_id)
    return {
        "chapter_id": chapter_id,
        "revision_count": prog.revision_count,
        "last_revised": str(prog.last_revised) if prog.last_revised else None,
        "revision_status": _revision_status_from_progress(prog),
        "updated_at": prog.updated_at.isoformat() if prog.updated_at else None,
    }


@router.get("/ai/insights", response_model=list[SyllabusAIInsight])
async def syllabus_ai_insights(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    roadmap = await get_roadmap(current_user, db)
    engine = SyllabusAIEngine()
    raw = await engine.generate_insights(db, current_user, [s.model_dump() for s in roadmap.subjects])
    return [SyllabusAIInsight(**i) for i in raw]


@router.get("/ai/suggestions")
async def syllabus_suggestions(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    engine = SyllabusAIEngine()
    return await engine.suggest_next_chapters(db, current_user.id)


@router.patch("/exam-targets")
async def update_exam_targets(
    data: ExamTargetsUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if data.target_rank is not None:
        current_user.target_rank = data.target_rank
    if data.target_marks is not None:
        current_user.target_marks = data.target_marks
    if data.exam_date is not None:
        current_user.exam_date = data.exam_date
    await db.flush()
    days_left = None
    if current_user.exam_date:
        days_left = max((current_user.exam_date - date.today()).days, 0)
    return {
        "target_rank": current_user.target_rank,
        "target_marks": current_user.target_marks,
        "exam_date": str(current_user.exam_date) if current_user.exam_date else None,
        "days_to_exam": days_left,
    }
