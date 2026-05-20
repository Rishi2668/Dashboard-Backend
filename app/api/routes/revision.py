from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.cache import cache
from app.core.database import get_db
from app.models.revision import RevisionItem
from app.models.revision_history import RevisionHistory
from app.models.streak import Streak
from app.schemas.revision import (
    RevisionAIRecommendation,
    RevisionAnalytics,
    RevisionCreate,
    RevisionDashboardSummary,
    RevisionHistoryResponse,
    RevisionItemResponse,
    RevisionListResponse,
    RevisionUpdate,
)
from app.services.revision_service import (
    build_ai_recommendations,
    build_analytics,
    build_dashboard_summary,
    fetch_user_items,
    filter_items,
    item_to_dict,
    revision_status,
)
from app.services.xp_breakdown import sync_user_xp

router = APIRouter(prefix="/revision", tags=["revision"])


def _response(item: RevisionItem) -> RevisionItemResponse:
    return RevisionItemResponse(**item_to_dict(item))


async def _get_item(db: AsyncSession, user_id: int, item_id: int) -> RevisionItem:
    result = await db.execute(
        select(RevisionItem).where(RevisionItem.id == item_id, RevisionItem.user_id == user_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Revision item not found")
    return item


async def _update_revision_streak(db: AsyncSession, user_id: int) -> None:
    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id, Streak.streak_type == "revision")
    )
    streak = streak_result.scalar_one_or_none()
    if not streak:
        streak = Streak(user_id=user_id, streak_type="revision")
        db.add(streak)
    today = date.today()
    if streak.last_activity_date != today:
        if streak.last_activity_date == today - timedelta(days=1):
            streak.current_count += 1
        else:
            streak.current_count = 1
        streak.last_activity_date = today
        streak.longest_count = max(streak.longest_count, streak.current_count)


async def _invalidate_revision_cache(user_id: int) -> None:
    await cache.delete(f"revision:dashboard:{user_id}")
    await cache.delete(f"revision:analytics:{user_id}")
    await cache.delete(f"dashboard:stats:{user_id}")


@router.get("/dashboard", response_model=RevisionDashboardSummary)
async def revision_dashboard(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    key = f"revision:dashboard:{current_user.id}"
    cached = await cache.get(key)
    if cached is not None:
        return cached
    payload = await build_dashboard_summary(db, current_user.id)
    await cache.set(key, payload, ttl_sec=20)
    return payload


@router.get("/analytics", response_model=RevisionAnalytics)
async def revision_analytics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    key = f"revision:analytics:{current_user.id}"
    cached = await cache.get(key)
    if cached is not None:
        return cached
    payload = await build_analytics(db, current_user.id)
    await cache.set(key, payload, ttl_sec=30)
    return payload


@router.get("/ai-recommendations", response_model=list[RevisionAIRecommendation])
async def revision_ai_recommendations(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    items = await fetch_user_items(db, current_user.id)
    return build_ai_recommendations(items)


@router.get("/history", response_model=list[RevisionHistoryResponse])
async def revision_history(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    result = await db.execute(
        select(RevisionHistory)
        .where(RevisionHistory.user_id == current_user.id)
        .order_by(RevisionHistory.completed_on.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/pending", response_model=list[RevisionItemResponse])
async def pending_revisions(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    items = await fetch_user_items(db, current_user.id)
    today = date.today()
    return [_response(i) for i in items if revision_status(i, today) in ("pending", "overdue")]


@router.get("/overdue", response_model=list[RevisionItemResponse])
async def overdue_revisions(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    items = await fetch_user_items(db, current_user.id)
    today = date.today()
    return [_response(i) for i in items if revision_status(i, today) == "overdue"]


@router.get("/upcoming", response_model=list[RevisionItemResponse])
async def upcoming_revisions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
):
    items = await fetch_user_items(db, current_user.id)
    today = date.today()
    end = today + timedelta(days=days)
    return [
        _response(i)
        for i in items
        if not i.completed and today < i.next_revision_date <= end
    ]


@router.get("/", response_model=RevisionListResponse)
async def list_revisions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    subject: str | None = None,
    priority: str | None = None,
    difficulty: str | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = await fetch_user_items(db, current_user.id)
    filtered = filter_items(
        items,
        status=status,
        subject=subject,
        priority=priority,
        difficulty=difficulty,
        search=search,
    )
    page = filtered[offset : offset + limit]
    return RevisionListResponse(
        items=[_response(i) for i in page],
        total=len(filtered),
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=RevisionItemResponse, status_code=201)
async def create_revision(
    data: RevisionCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    due = data.next_revision_date or (date.today() + timedelta(days=data.interval_days))
    item = RevisionItem(
        user_id=current_user.id,
        topic=data.topic.strip(),
        subject=data.subject,
        interval_days=data.interval_days,
        next_revision_date=due,
        notes=data.notes,
        priority=data.priority or "medium",
        difficulty=data.difficulty or "medium",
    )
    db.add(item)
    await db.flush()
    await _invalidate_revision_cache(current_user.id)
    await db.refresh(item)
    return _response(item)


@router.patch("/{item_id}", response_model=RevisionItemResponse)
async def update_revision(
    item_id: int,
    data: RevisionUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    item = await _get_item(db, current_user.id, item_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.flush()
    await _invalidate_revision_cache(current_user.id)
    await db.refresh(item)
    return _response(item)


@router.post("/{item_id}/complete", response_model=RevisionItemResponse)
async def complete_revision(
    item_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    item = await _get_item(db, current_user.id, item_id)
    today = date.today()

    history = RevisionHistory(
        user_id=current_user.id,
        revision_item_id=item.id,
        topic=item.topic,
        subject=item.subject,
        interval_days=item.interval_days,
        completed_on=today,
        notes=item.notes,
    )
    db.add(history)

    item.last_revised = today
    item.revision_count += 1

    if item.interval_days == 1:
        item.interval_days = 7
        item.next_revision_date = today + timedelta(days=7)
    elif item.interval_days == 7:
        item.interval_days = 30
        item.next_revision_date = today + timedelta(days=30)
    else:
        item.completed = True
        item.completed_at = datetime.now(timezone.utc)

    await _update_revision_streak(db, current_user.id)
    await db.flush()
    await sync_user_xp(db, current_user)
    await _invalidate_revision_cache(current_user.id)
    await db.refresh(item)
    return _response(item)


@router.delete("/{item_id}", status_code=204)
async def delete_revision(
    item_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    item = await _get_item(db, current_user.id, item_id)
    await db.delete(item)
    await db.flush()
    await sync_user_xp(db, current_user)
    await _invalidate_revision_cache(current_user.id)
