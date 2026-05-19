from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScoreTargetUpdate(BaseModel):
    overall_max_marks: float = Field(default=200.0, ge=0, le=600)
    overall_target_marks: float = Field(ge=0, le=600)
    reasoning_max_marks: float = Field(default=50.0, ge=0, le=200)
    reasoning_target_marks: float = Field(ge=0, le=200)
    quant_max_marks: float = Field(default=50.0, ge=0, le=200)
    quant_target_marks: float = Field(ge=0, le=200)
    english_max_marks: float = Field(default=50.0, ge=0, le=200)
    english_target_marks: float = Field(ge=0, le=200)
    gk_max_marks: float = Field(default=50.0, ge=0, le=200)
    gk_target_marks: float = Field(ge=0, le=200)


class ScoreTargetResponse(BaseModel):
    overall_max_marks: float
    overall_target_marks: float
    reasoning_max_marks: float
    reasoning_target_marks: float
    quant_max_marks: float
    quant_target_marks: float
    english_max_marks: float
    english_target_marks: float
    gk_max_marks: float
    gk_target_marks: float
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SubjectTargetComparison(BaseModel):
    key: str
    label: str
    actual: float
    actual_max: float
    target: float
    target_max: float
    gap: float
    achievement_pct: float
    target_progress_pct: float


class OverallTargetComparison(BaseModel):
    actual: float
    actual_max: float
    target: float
    target_max: float
    gap: float
    achievement_pct: float
    target_progress_pct: float
    improvement_needed: float


class TargetTrendPoint(BaseModel):
    period: str
    label: str
    avg_score: float
    target: float
    achievement_pct: float


class TargetAIInsight(BaseModel):
    title: str
    message: str
    priority: str
    category: str


class TargetAnalyticsResponse(BaseModel):
    targets: ScoreTargetResponse
    overall: OverallTargetComparison
    subjects: list[SubjectTargetComparison]
    closest_subject: Optional[str] = None
    biggest_gap_subject: Optional[str] = None
    goal_achievement_probability: float = 0.0
    weekly_trend: list[TargetTrendPoint] = Field(default_factory=list)
    monthly_improvement: Optional[float] = None
    score_prediction: Optional[float] = None
    ai_insights: list[TargetAIInsight] = Field(default_factory=list)
    has_mock_data: bool = False
    latest_mock_date: Optional[str] = None
