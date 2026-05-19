from typing import Any, Optional

from pydantic import BaseModel


class AnalysisInsight(BaseModel):
    type: str
    priority: str
    title: str
    message: str


class AnalysisSection(BaseModel):
    id: str
    title: str
    icon: str
    insights: list[AnalysisInsight]


class OverallAnalysisOut(BaseModel):
    readiness_score: float
    readiness_label: str
    summary: str
    sections: list[AnalysisSection]
    action_plan: list[AnalysisInsight]
    priority_focus: list[AnalysisInsight]
    generated_at: str


class DomainAnalysisOut(BaseModel):
    domain: str
    insights: list[AnalysisInsight]
