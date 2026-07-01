from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.roadmap_task import UserRoadmapTaskProgress
from app.schemas.roadmap_2026 import Roadmap2026Out, RoadmapTaskUpdate
from app.services.roadmap_2026_service import Roadmap2026Service

router = APIRouter(prefix="/roadmap-2026", tags=["roadmap-2026"])


@router.get("/", response_model=Roadmap2026Out)
async def get_roadmap_2026(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    svc = Roadmap2026Service()
    data = await svc.build(db, current_user)
    return data


@router.patch("/tasks/{week_number}/{task_key}", response_model=dict)
async def update_roadmap_task(
    week_number: int,
    task_key: str,
    data: RoadmapTaskUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if week_number < 1 or week_number > 10:
        raise HTTPException(status_code=400, detail="Invalid week number")

    result = await db.execute(
        select(UserRoadmapTaskProgress).where(
            UserRoadmapTaskProgress.user_id == current_user.id,
            UserRoadmapTaskProgress.week_number == week_number,
            UserRoadmapTaskProgress.task_key == task_key,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        task = UserRoadmapTaskProgress(
            user_id=current_user.id,
            week_number=week_number,
            task_key=task_key,
        )
        db.add(task)

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(task, key, val)

    if data.completed is True:
        task.completed = True
    elif data.completed is False:
        task.completed = False

    await db.flush()
    return {
        "week_number": week_number,
        "task_key": task_key,
        "completed": task.completed,
        "score": task.score,
        "accuracy": task.accuracy,
        "time_taken_minutes": task.time_taken_minutes,
        "weak_areas": task.weak_areas,
        "notes": task.notes,
    }
