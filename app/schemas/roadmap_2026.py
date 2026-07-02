from typing import Optional

from pydantic import BaseModel, Field


class RoadmapTopicOut(BaseModel):
    label: str
    subject_key: str
    chapter_id: Optional[int] = None
    completed: bool = False
    progress_percentage: float = 0.0


class RoadmapSectionOut(BaseModel):
    subject: str
    topics: list[RoadmapTopicOut]


class RoadmapTaskOut(BaseModel):
    key: Optional[str] = None
    task_key: Optional[str] = None
    label: str
    required: bool = False
    completed: bool = False
    score: Optional[float] = None
    accuracy: Optional[float] = None
    time_taken_minutes: Optional[int] = None
    weak_areas: Optional[str] = None
    notes: Optional[str] = None


class DailyVocabDayOut(BaseModel):
    key: str
    label: str
    completed: bool = False


class RoadmapWeekOut(BaseModel):
    number: int
    phase: int
    label: str
    start: str
    end: str
    english_phase: Optional[int] = None
    english_phase_name: Optional[str] = None
    english_phase_note: Optional[str] = None
    sections: list[RoadmapSectionOut]
    virtual_tasks: list[RoadmapTaskOut]
    mock_tasks: list[RoadmapTaskOut]
    daily_vocab: list[DailyVocabDayOut] = []
    completion_pct: float
    completed_count: int
    total_count: int
    is_current: bool


class RoadmapPhaseOut(BaseModel):
    id: int
    name: str
    subtitle: str
    weeks: list[int]
    color: str
    completion_pct: float
    completed_count: int
    total_count: int


class Roadmap2026Out(BaseModel):
    exam_label: str
    roadmap_start: str
    roadmap_end: str
    days_remaining: int
    current_week: int
    daily_schedule: dict
    overall_completion: float
    overall_completed: int
    overall_total: int
    phases: list[RoadmapPhaseOut]
    weeks: list[RoadmapWeekOut]
    subject_progress: dict
    mocks_completed: int
    hours_studied: float
    completion_streak: int
    counters: dict
    english_roadmap: dict
    vocab_streak: dict
    productivity: dict
    analytics: dict


class RoadmapTaskUpdate(BaseModel):
    completed: Optional[bool] = None
    score: Optional[float] = Field(None, ge=0)
    accuracy: Optional[float] = Field(None, ge=0, le=100)
    time_taken_minutes: Optional[int] = Field(None, ge=0)
    weak_areas: Optional[str] = None
    notes: Optional[str] = None
