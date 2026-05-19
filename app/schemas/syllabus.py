from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChapterProgressUpdate(BaseModel):
    completed: Optional[bool] = None
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    accuracy: Optional[float] = Field(None, ge=0, le=100)
    revision_status: Optional[str] = None
    is_weak: Optional[bool] = None
    notes: Optional[str] = None
    time_spent_minutes: Optional[int] = Field(None, ge=0)
    bookmarked: Optional[bool] = None
    mark_revised: bool = False


class ChapterOut(BaseModel):
    id: int
    name: str
    priority: str
    priority_label: str
    sort_order: int
    completed: bool
    progress_percentage: float
    accuracy: float
    revision_status: str
    revision_count: int
    last_revised: Optional[date]
    is_weak: bool
    notes: Optional[str]
    time_spent_minutes: int
    bookmarked: bool

    model_config = {"from_attributes": True}


class SubjectOut(BaseModel):
    id: int
    slug: str
    name: str
    short_name: str
    color: str
    total_chapters: int
    completed_chapters: int
    completion_percentage: float
    average_accuracy: float
    weak_count: int
    chapters: list[ChapterOut]


class SyllabusRoadmapOut(BaseModel):
    subjects: list[SubjectOut]
    overall_completion: float
    total_chapters: int
    completed_chapters: int
    target_marks: Optional[float]
    exam_date: Optional[date]
    days_to_exam: Optional[int]


class SyllabusAIInsight(BaseModel):
    type: str
    priority: str
    title: str
    message: str
    chapter_id: Optional[int]


class ExamTargetsUpdate(BaseModel):
    target_rank: Optional[int] = Field(None, ge=1, le=500000)
    target_marks: Optional[float] = Field(None, ge=0, le=600)
    exam_date: Optional[date] = None
