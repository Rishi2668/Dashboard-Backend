from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.score_target import TargetAnalyticsResponse


class SubjectSectionInput(BaseModel):
    max_marks: float = Field(default=50.0, ge=0)
    secured_marks: float = Field(default=0.0, ge=0)
    total_questions: int = Field(default=25, ge=0)
    attempted: int = Field(default=0, ge=0)
    correct: int = Field(default=0, ge=0)
    wrong: Optional[int] = Field(default=None, ge=0)


class MockTestCreate(BaseModel):
    test_name: Optional[str] = None
    test_date: date
    test_type: Literal["full", "sectional"] = "full"
    max_score: float = Field(default=200.0, ge=0)
    total_score: float = Field(ge=0)
    total_questions: int = Field(default=100, ge=0)
    attempted: int = Field(ge=0, default=0)
    correct: int = Field(ge=0, default=0)
    wrong: Optional[int] = Field(default=None, ge=0)
    negative_marks: Optional[float] = Field(default=None, ge=0)
    reasoning: SubjectSectionInput = Field(default_factory=SubjectSectionInput)
    quant: SubjectSectionInput = Field(default_factory=SubjectSectionInput)
    english: SubjectSectionInput = Field(default_factory=SubjectSectionInput)
    gk: SubjectSectionInput = Field(default_factory=SubjectSectionInput)

    # Legacy flat fields (optional)
    quant_score: Optional[float] = None
    reasoning_score: Optional[float] = None
    english_score: Optional[float] = None
    gk_score: Optional[float] = None
    quant_accuracy: Optional[float] = None
    reasoning_accuracy: Optional[float] = None
    english_accuracy: Optional[float] = None
    gk_accuracy: Optional[float] = None

    @field_validator("test_date")
    @classmethod
    def test_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Mock date cannot be in the future")
        return v


class SubjectSectionResponse(BaseModel):
    label: str
    max_marks: float
    secured_marks: float
    total_questions: int
    attempted: int
    correct: int
    wrong: int
    accuracy: float
    score_percentage: float


class MockTestResponse(BaseModel):
    id: int
    test_name: Optional[str]
    test_date: date
    test_type: str
    total_score: float
    max_score: float
    total_questions: int
    accuracy: float
    attempted: int
    correct: int
    wrong: int
    negative_marks: float
    score_percentage: float = 0.0
    reasoning: SubjectSectionResponse
    quant: SubjectSectionResponse
    english: SubjectSectionResponse
    gk: SubjectSectionResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class MockAIInsight(BaseModel):
    title: str
    message: str
    priority: str
    category: str


class MockAnalytics(BaseModel):
    latest_score: float
    highest_score: float
    average_score: float
    average_accuracy: float
    latest_score_percentage: float
    total_attempted: int
    total_correct: int
    total_wrong: int
    total_negative: float
    total_mocks: int
    score_progression: list[dict]
    accuracy_trend: list[dict]
    section_comparison: list[dict]
    subject_accuracy_trends: dict[str, list[dict]]
    weekly_trend: list[dict]
    weak_subjects: list[dict]
    strongest_subject: Optional[str]
    improvement_delta: Optional[float]
    ai_insights: list[MockAIInsight] = Field(default_factory=list)
    target_analytics: Optional[TargetAnalyticsResponse] = None
