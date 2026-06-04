from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.cache import invalidate_dashboard_stats_cache
from app.core.database import get_db
from app.models.user import User
from app.schemas.score_target import ScoreTargetResponse, ScoreTargetUpdate, TargetAnalyticsResponse
from app.services.target_score_service import TargetScoreService, get_or_create_targets

router = APIRouter(prefix="/score-targets", tags=["score-targets"])


async def _load_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.score_target))
    )
    return result.scalar_one()


@router.get("/", response_model=ScoreTargetResponse)
async def get_targets(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    user = await _load_user(db, current_user.id)
    t = await get_or_create_targets(db, user)
    if user.target_marks and user.target_marks != t.overall_target_marks:
        t.overall_target_marks = user.target_marks
        await db.flush()
    return ScoreTargetResponse.model_validate(t)


@router.put("/", response_model=ScoreTargetResponse)
async def update_targets(
    data: ScoreTargetUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    user = await _load_user(db, current_user.id)
    t = await get_or_create_targets(db, user)
    for key, val in data.model_dump().items():
        setattr(t, key, val)
    current_user.target_marks = data.overall_target_marks
    await db.flush()
    await db.refresh(t)
    await invalidate_dashboard_stats_cache(current_user.id)
    return ScoreTargetResponse.model_validate(t)


@router.get("/analytics", response_model=TargetAnalyticsResponse)
async def target_analytics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    user = await _load_user(db, current_user.id)
    svc = TargetScoreService()
    return await svc.build_analytics(db, user)
