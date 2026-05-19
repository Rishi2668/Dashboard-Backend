from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.pyq import PYQProgress
from pydantic import BaseModel
from fastapi import Depends

router = APIRouter(prefix="/pyq", tags=["pyq"])


class PYQCreate(BaseModel):
    subject: str
    topic: str
    year: int
    total_questions: int = 0
    completed_questions: int = 0


class PYQResponse(BaseModel):
    id: int
    subject: str
    topic: str
    year: int
    completed: bool
    total_questions: int
    completed_questions: int
    completion_percentage: float

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[PYQResponse])
async def list_pyq(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PYQProgress).where(PYQProgress.user_id == current_user.id))
    return result.scalars().all()


@router.get("/analytics")
async def pyq_analytics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            PYQProgress.subject,
            func.sum(PYQProgress.completed_questions).label("completed"),
            func.sum(PYQProgress.total_questions).label("total"),
        )
        .where(PYQProgress.user_id == current_user.id)
        .group_by(PYQProgress.subject)
    )
    rows = result.all()
    return [
        {
            "subject": r.subject,
            "completed": int(r.completed or 0),
            "total": int(r.total or 0),
            "percentage": round((r.completed or 0) / max(r.total or 1, 1) * 100, 1),
        }
        for r in rows
    ]


@router.post("/", response_model=PYQResponse, status_code=201)
async def create_pyq(data: PYQCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    pct = (data.completed_questions / data.total_questions * 100) if data.total_questions > 0 else 0
    pyq = PYQProgress(
        user_id=current_user.id,
        completion_percentage=pct,
        completed=data.completed_questions >= data.total_questions and data.total_questions > 0,
        **data.model_dump(),
    )
    db.add(pyq)
    await db.flush()
    await db.refresh(pyq)
    return pyq
