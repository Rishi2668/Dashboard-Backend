from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.weak_area import WeakTopic
from app.services.ai.recommendation_engine import AIRecommendationEngine
from pydantic import BaseModel
from typing import Optional
from fastapi import Depends

router = APIRouter(prefix="/weak-areas", tags=["weak-areas"])


class WeakTopicCreate(BaseModel):
    topic: str
    subject: str
    accuracy: float = 0.0
    mistake_count: int = 0
    priority: str = "high"
    avg_time_seconds: Optional[float] = None


class WeakTopicResponse(BaseModel):
    id: int
    topic: str
    subject: str
    accuracy: float
    mistake_count: int
    priority: str
    needs_revision: bool
    avg_time_seconds: Optional[float]

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[WeakTopicResponse])
async def list_weak_areas(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    subject: str | None = None,
):
    q = select(WeakTopic).where(WeakTopic.user_id == current_user.id)
    if subject:
        q = q.where(WeakTopic.subject == subject)
    result = await db.execute(q.order_by(WeakTopic.accuracy.asc()))
    return result.scalars().all()


@router.post("/", response_model=WeakTopicResponse, status_code=201)
async def create_weak_topic(
    data: WeakTopicCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(WeakTopic).where(
            WeakTopic.user_id == current_user.id,
            WeakTopic.subject == data.subject,
            WeakTopic.topic == data.topic,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f'Weak topic "{data.topic}" already exists for {data.subject}',
        )
    topic = WeakTopic(user_id=current_user.id, needs_revision=True, **data.model_dump())
    db.add(topic)
    await db.flush()
    await db.refresh(topic)
    return topic


@router.post("/auto-detect")
async def auto_detect_weak_areas(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    engine = AIRecommendationEngine()
    detected = await engine.detect_weak_areas_from_mocks(db, current_user.id)
    created = []
    for d in detected:
        topic_name = f"{d['subject']} weak sections"
        existing = await db.execute(
            select(WeakTopic).where(
                WeakTopic.user_id == current_user.id,
                WeakTopic.subject == d["subject"],
                WeakTopic.topic == topic_name,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.accuracy = d["accuracy"]
            row.priority = d["priority"]
            row.needs_revision = True
            created.append(d)
            continue
        topic = WeakTopic(
            user_id=current_user.id,
            topic=topic_name,
            subject=d["subject"],
            accuracy=d["accuracy"],
            priority=d["priority"],
            needs_revision=True,
        )
        db.add(topic)
        created.append(d)
    await db.flush()
    return {"detected": created}


@router.delete("/all", status_code=204)
async def delete_all_weak_topics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WeakTopic).where(WeakTopic.user_id == current_user.id))
    for topic in result.scalars().all():
        await db.delete(topic)
    await db.flush()


@router.delete("/{topic_id}", status_code=204)
async def delete_weak_topic(topic_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WeakTopic).where(WeakTopic.id == topic_id, WeakTopic.user_id == current_user.id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    await db.delete(topic)
    await db.flush()
