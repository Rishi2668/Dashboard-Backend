from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class StudySessionCreate(BaseModel):
    date: date
    hours: float = Field(ge=0, le=24)
    topics_completed: str = ""
    revision_done: bool = False
    productivity_score: int = Field(ge=0, le=100, default=0)
    notes: Optional[str] = None
    tasks_completed: int = Field(ge=0, default=0)
    subject_breakdown: Optional[str] = None


class StudySessionResponse(BaseModel):
    id: int
    date: date
    hours: float
    topics_completed: str
    revision_done: bool
    productivity_score: int
    notes: Optional[str]
    tasks_completed: int
    subject_breakdown: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyTargetCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    target_date: date


class DailyTargetUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class DailyTargetResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    priority: str
    completed: bool
    target_date: date
    created_at: datetime

    model_config = {"from_attributes": True}
