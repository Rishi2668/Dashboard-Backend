from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.revision import RevisionItem
from app.models.streak import Streak
from app.services.xp_breakdown import sync_user_xp
from pydantic import BaseModel
from typing import Optional
from fastapi import Depends

router = APIRouter(prefix="/revision", tags=["revision"])


class RevisionCreate(BaseModel):
    topic: str
    subject: str
    interval_days: int = 1


class RevisionResponse(BaseModel):
    id: int
    topic: str
    subject: str
    interval_days: int
    next_revision_date: date
    last_revised: Optional[date]
    completed: bool
    revision_count: int

    model_config = {"from_attributes": True}


INTERVALS = {1: 1, 7: 7, 30: 30}


@router.get("/pending", response_model=list[RevisionResponse])
async def pending_revisions(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RevisionItem).where(
            RevisionItem.user_id == current_user.id,
            RevisionItem.completed == False,
            RevisionItem.next_revision_date <= date.today(),
        )
    )
    return result.scalars().all()


@router.get("/", response_model=list[RevisionResponse])
async def list_revisions(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RevisionItem)
        .where(RevisionItem.user_id == current_user.id)
        .order_by(RevisionItem.next_revision_date.asc())
    )
    return result.scalars().all()


@router.post("/", response_model=RevisionResponse, status_code=201)
async def create_revision(data: RevisionCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    item = RevisionItem(
        user_id=current_user.id,
        topic=data.topic,
        subject=data.subject,
        interval_days=data.interval_days,
        next_revision_date=date.today() + timedelta(days=data.interval_days),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.post("/{item_id}/complete", response_model=RevisionResponse)
async def complete_revision(item_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RevisionItem).where(RevisionItem.id == item_id, RevisionItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Revision item not found")

    item.last_revised = date.today()
    item.revision_count += 1
    if item.interval_days == 1:
        item.interval_days = 7
        item.next_revision_date = date.today() + timedelta(days=7)
    elif item.interval_days == 7:
        item.interval_days = 30
        item.next_revision_date = date.today() + timedelta(days=30)
    else:
        item.completed = True

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == current_user.id, Streak.streak_type == "revision")
    )
    streak = streak_result.scalar_one_or_none()
    if streak:
        today = date.today()
        if streak.last_activity_date != today:
            streak.current_count = streak.current_count + 1 if streak.last_activity_date == today - timedelta(days=1) else 1
            streak.last_activity_date = today

    await db.flush()
    await sync_user_xp(db, current_user)
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_revision(item_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RevisionItem).where(
            RevisionItem.id == item_id,
            RevisionItem.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Revision item not found")
    await db.delete(item)
    await db.flush()
    await sync_user_xp(db, current_user)
