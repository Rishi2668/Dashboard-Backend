from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

RevisionStatus = Literal["pending", "upcoming", "completed", "overdue"]


class RevisionCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=255)
    subject: str
    interval_days: int = Field(default=3, ge=1, le=90)
    next_revision_date: Optional[date] = None
    notes: Optional[str] = None
    priority: str = "medium"
    difficulty: str = "medium"


class RevisionUpdate(BaseModel):
    topic: Optional[str] = None
    subject: Optional[str] = None
    interval_days: Optional[int] = Field(default=None, ge=1, le=90)
    next_revision_date: Optional[date] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    difficulty: Optional[str] = None


class RevisionItemResponse(BaseModel):
    id: int
    topic: str
    subject: str
    interval_days: int
    next_revision_date: date
    last_revised: Optional[date]
    completed: bool
    revision_count: int
    notes: Optional[str] = None
    priority: str = "medium"
    difficulty: str = "medium"
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    status: RevisionStatus
    days_overdue: int = 0
    suggested_next_date: Optional[date] = None

    model_config = {"from_attributes": True}


class RevisionListResponse(BaseModel):
    items: list[RevisionItemResponse]
    total: int
    limit: int
    offset: int


class RevisionDashboardSummary(BaseModel):
    today_count: int
    tomorrow_count: int
    week_count: int
    pending_count: int
    upcoming_count: int
    overdue_count: int
    completed_count: int
    total_count: int
    completion_percentage: float
    revision_streak: int
    today_items: list[RevisionItemResponse]
    tomorrow_items: list[RevisionItemResponse]
    overdue_items: list[RevisionItemResponse]


class RevisionAnalytics(BaseModel):
    total_revisions: int
    total_completed: int
    pending_count: int
    upcoming_count: int
    overdue_count: int
    completion_percentage: float
    overdue_percentage: float
    consistency_percentage: float
    revision_streak: int
    longest_revision_streak: int
    subject_frequency: list[dict]
    total_revision_cycles: int


class RevisionAIRecommendation(BaseModel):
    title: str
    message: str
    priority: str
    category: str


class RevisionHistoryResponse(BaseModel):
    id: int
    revision_item_id: int
    topic: str
    subject: str
    interval_days: int
    completed_on: date
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
