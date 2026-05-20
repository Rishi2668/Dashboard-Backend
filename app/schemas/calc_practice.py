from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuestionGenerateRequest(BaseModel):
    practice_type: str = "mixed"
    difficulty: str = "medium"
    session_id: Optional[int] = None
    exclude_fingerprints: list[str] = Field(default_factory=list)


class GeneratedQuestionResponse(BaseModel):
    question_id: str
    practice_type: str
    difficulty: str
    question_text: str
    answer_tolerance: float
    explanation: str
    fingerprint: str


class AnswerValidateRequest(BaseModel):
    correct_answer: float
    user_answer: float
    answer_tolerance: float = 0.01


class AnswerValidateResponse(BaseModel):
    is_correct: bool
    correct_answer: float
    display_answer: str


class SessionCreate(BaseModel):
    mode: str = "endless"
    difficulty: str = "medium"
    practice_types: list[str] = Field(default_factory=lambda: ["mixed"])
    duration_limit_sec: Optional[int] = None


class SessionResponse(BaseModel):
    id: int
    mode: str
    difficulty: str
    practice_types: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_limit_sec: Optional[int]
    total_questions: int
    correct_count: int
    skipped_count: int
    total_time_ms: int
    fastest_time_ms: Optional[int]
    xp_earned: int
    completed: bool
    accuracy_pct: float = 0.0
    avg_time_ms: float = 0.0

    model_config = {"from_attributes": True}


class AttemptSubmit(BaseModel):
    session_id: int
    question_id: str
    practice_type: str
    difficulty: str
    question_text: str
    correct_answer: float
    user_answer: Optional[float] = None
    skipped: bool = False
    time_ms: int = 0
    fingerprint: str
    explanation: str = ""


class AttemptResponse(BaseModel):
    id: int
    is_correct: bool
    xp_gained: int
    streak_bonus: bool
    explanation: str
    correct_answer: float
    display_answer: str
    session: SessionResponse

    model_config = {"from_attributes": True}


class SessionEndResponse(BaseModel):
    session: SessionResponse
    xp_earned: int
    badges_earned: list[str]
    message: str


class CalcAnalyticsResponse(BaseModel):
    total_questions: int
    total_correct: int
    accuracy_pct: float
    avg_time_ms: float
    fastest_time_ms: Optional[int]
    calc_streak: int
    total_sessions: int
    total_xp_from_calc: int
    by_type: list[dict]
    weak_areas: list[dict]
    daily_last_7: list[dict]
    badges: list[dict]


class CalcAIInsight(BaseModel):
    title: str
    message: str
    priority: str
    category: str
