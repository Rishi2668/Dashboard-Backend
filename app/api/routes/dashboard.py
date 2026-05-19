from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_db
from app.models.streak import Achievement, Streak
from app.models.study import StudySession
from app.models.user import User
from app.services.target_score_service import TargetScoreService
from app.schemas.auth import UserResponse
from app.schemas.dashboard import AchievementResponse, DashboardStats, StreakResponse, XpBreakdown
from app.services.ai.recommendation_engine import get_level_from_xp
from app.services.xp_breakdown import sync_user_xp
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _ensure_streaks(db: AsyncSession, user_id: int) -> list[Streak]:
    types = ["study", "mock", "revision", "focus"]
    result = await db.execute(select(Streak).where(Streak.user_id == user_id))
    existing = {s.streak_type: s for s in result.scalars().all()}
    streaks = []
    for st in types:
        if st not in existing:
            streak = Streak(user_id=user_id, streak_type=st)
            db.add(streak)
            streaks.append(streak)
        else:
            streaks.append(existing[st])
    await db.flush()
    return streaks


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    exam_date = current_user.exam_date
    if not exam_date:
        exam_date = datetime.strptime(settings.EXAM_DATE, "%Y-%m-%d").date()
    days_left = max((exam_date - date.today()).days, 0)

    streaks = await _ensure_streaks(db, current_user.id)
    study_streak = next((s for s in streaks if s.streak_type == "study"), None)

    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    today_result = await db.execute(
        select(func.coalesce(func.sum(StudySession.hours), 0)).where(
            StudySession.user_id == current_user.id, StudySession.date == today
        )
    )
    today_hours = float(today_result.scalar() or 0)

    week_result = await db.execute(
        select(func.coalesce(func.sum(StudySession.hours), 0)).where(
            StudySession.user_id == current_user.id, StudySession.date >= week_start
        )
    )
    week_hours = float(week_result.scalar() or 0)

    heatmap_result = await db.execute(
        select(StudySession.date, func.sum(StudySession.hours).label("hours"))
        .where(StudySession.user_id == current_user.id, StudySession.date >= month_start)
        .group_by(StudySession.date)
    )
    heatmap_data = [{"date": str(r.date), "hours": float(r.hours)} for r in heatmap_result.all()]

    active_days = len(heatmap_data)
    month_consistency = round((active_days / 30) * 100, 1)

    ach_result = await db.execute(
        select(Achievement).where(Achievement.user_id == current_user.id).limit(10)
    )
    achievements = ach_result.scalars().all()

    level, next_level, progress, xp_at_level, xp_for_next = get_level_from_xp(current_user.xp)
    breakdown = await sync_user_xp(db, current_user)

    user_result = await db.execute(
        select(User).where(User.id == current_user.id).options(selectinload(User.score_target))
    )
    user_loaded = user_result.scalar_one()
    target_analytics = await TargetScoreService().build_analytics(db, user_loaded)

    return DashboardStats(
        user=UserResponse.model_validate(current_user),
        days_left=days_left,
        study_streak=study_streak.current_count if study_streak else 0,
        mock_streak=next((s.current_count for s in streaks if s.streak_type == "mock"), 0),
        revision_streak=next((s.current_count for s in streaks if s.streak_type == "revision"), 0),
        focus_streak=next((s.current_count for s in streaks if s.streak_type == "focus"), 0),
        today_hours=today_hours,
        week_hours=week_hours,
        month_consistency=month_consistency,
        heatmap_data=heatmap_data,
        xp=current_user.xp,
        level=level,
        level_progress=progress,
        next_level=next_level,
        xp_at_level=xp_at_level,
        xp_for_next=xp_for_next,
        xp_breakdown=XpBreakdown(**breakdown),
        achievements=[AchievementResponse.model_validate(a) for a in achievements],
        streaks=[StreakResponse.model_validate(s) for s in streaks],
        target_analytics=target_analytics,
    )
