from datetime import date
from typing import Any, Optional

from typing import Optional

from pydantic import BaseModel

from app.schemas.auth import UserResponse
from app.schemas.score_target import TargetAnalyticsResponse


class StreakResponse(BaseModel):
    streak_type: str
    current_count: int
    longest_count: int
    last_activity_date: Optional[date]

    model_config = {"from_attributes": True}


class AchievementResponse(BaseModel):
    id: int
    badge_id: str
    title: str
    description: str
    earned_at: Any

    model_config = {"from_attributes": True}


class XpBreakdown(BaseModel):
    calc_practice: int = 0
    study_sessions: int = 0
    mock_tests: int = 0
    notes: int = 0
    revision: int = 0
    syllabus: int = 0
    accounted_total: int = 0


class DashboardStats(BaseModel):
    user: UserResponse
    days_left: int
    study_streak: int
    mock_streak: int
    revision_streak: int
    focus_streak: int
    today_hours: float
    week_hours: float
    month_consistency: float
    heatmap_data: list[dict]
    xp: int
    level: str
    level_progress: float
    next_level: str
    xp_at_level: int = 0
    xp_for_next: int = 500
    xp_breakdown: XpBreakdown
    achievements: list[AchievementResponse]
    streaks: list[StreakResponse]
    target_analytics: Optional[TargetAnalyticsResponse] = None


class QuoteResponse(BaseModel):
    id: int
    text: str
    author: str
    category: str

    model_config = {"from_attributes": True}


class AIInsightResponse(BaseModel):
    id: int
    insight_type: str
    title: str
    message: str
    priority: str
    is_read: bool
    action_url: Optional[str]
    created_at: Any

    model_config = {"from_attributes": True}
