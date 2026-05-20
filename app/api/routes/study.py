from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.cache import invalidate_dashboard_stats_cache
from app.core.database import get_db
from app.models.streak import Streak
from app.models.study import DailyTarget, StudySession
from app.schemas.study import (
    DailyTargetCreate,
    DailyTargetResponse,
    DailyTargetUpdate,
    StudySessionCreate,
    StudySessionResponse,
)
from fastapi import Depends

router = APIRouter(prefix="/study", tags=["study"])


async def _update_study_streak(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Streak).where(Streak.user_id == user_id, Streak.streak_type == "study")
    )
    streak = result.scalar_one_or_none()
    if not streak:
        streak = Streak(user_id=user_id, streak_type="study")
        db.add(streak)
    today = date.today()
    if streak.last_activity_date == today:
        return
    if streak.last_activity_date == today - timedelta(days=1):
        streak.current_count += 1
    elif streak.last_activity_date != today:
        streak.current_count = 1
    streak.last_activity_date = today
    streak.longest_count = max(streak.longest_count, streak.current_count)
    await db.flush()


@router.get("/sessions", response_model=list[StudySessionResponse])
async def list_sessions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 30,
):
    result = await db.execute(
        select(StudySession)
        .where(StudySession.user_id == current_user.id)
        .order_by(StudySession.date.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/sessions", response_model=StudySessionResponse, status_code=201)
async def create_session(
    data: StudySessionCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    session = StudySession(user_id=current_user.id, **data.model_dump())
    db.add(session)
    await _update_study_streak(db, current_user.id)
    current_user.xp += int(data.hours * 10) + data.tasks_completed * 5
    await db.flush()
    await invalidate_dashboard_stats_cache(current_user.id)
    await db.refresh(session)
    return session


async def _delete_session_impl(
    session_id: int, current_user: CurrentUser, db: AsyncSession
) -> None:
    result = await db.execute(
        select(StudySession).where(
            StudySession.id == session_id, StudySession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")

    earned_xp = int(session.hours * 10) + (session.tasks_completed or 0) * 5
    current_user.xp = max(0, current_user.xp - earned_xp)

    await db.delete(session)
    await invalidate_dashboard_stats_cache(current_user.id)
    await db.flush()


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _delete_session_impl(session_id, current_user, db)


@router.post("/sessions/{session_id}/delete", status_code=204)
async def delete_session_post(
    session_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """POST alias for environments that block DELETE."""
    await _delete_session_impl(session_id, current_user, db)


@router.get("/heatmap")
async def get_heatmap(current_user: CurrentUser, db: AsyncSession = Depends(get_db), days: int = 90):
    start = date.today() - timedelta(days=days)
    result = await db.execute(
        select(StudySession.date, func.sum(StudySession.hours).label("hours"))
        .where(StudySession.user_id == current_user.id, StudySession.date >= start)
        .group_by(StudySession.date)
    )
    return [{"date": str(r.date), "hours": float(r.hours), "level": min(int(r.hours), 4)} for r in result.all()]


@router.get("/targets", response_model=list[DailyTargetResponse])
async def list_targets(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    target_date: date | None = None,
):
    q = select(DailyTarget).where(DailyTarget.user_id == current_user.id)
    if target_date:
        q = q.where(DailyTarget.target_date == target_date)
    else:
        q = q.where(DailyTarget.target_date == date.today())
    result = await db.execute(q.order_by(DailyTarget.priority.desc()))
    return result.scalars().all()


@router.post("/targets", response_model=DailyTargetResponse, status_code=201)
async def create_target(
    data: DailyTargetCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    target = DailyTarget(user_id=current_user.id, **data.model_dump())
    db.add(target)
    await db.flush()
    await db.refresh(target)
    return target


@router.patch("/targets/{target_id}", response_model=DailyTargetResponse)
async def update_target(
    target_id: int,
    data: DailyTargetUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DailyTarget).where(DailyTarget.id == target_id, DailyTarget.user_id == current_user.id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(target, k, v)
    if data.completed:
        current_user.xp += 15
    await db.flush()
    await invalidate_dashboard_stats_cache(current_user.id)
    await db.refresh(target)
    return target


@router.delete("/targets/{target_id}", status_code=204)
async def delete_target(target_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DailyTarget).where(DailyTarget.id == target_id, DailyTarget.user_id == current_user.id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    await db.delete(target)
    await invalidate_dashboard_stats_cache(current_user.id)
