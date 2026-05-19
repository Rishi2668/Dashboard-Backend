"""Target score comparison, trends, and AI insights."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_test import MockTest
from app.models.score_target import UserScoreTarget
from app.models.user import User
from app.schemas.score_target import (
    OverallTargetComparison,
    ScoreTargetResponse,
    SubjectTargetComparison,
    TargetAnalyticsResponse,
    TargetTrendPoint,
)
from app.services.target_ai_engine import TargetAIEngine

SUBJECTS = (
    ("reasoning", "General Intelligence & Reasoning", "reasoning_score", "reasoning_max_marks", "reasoning_target_marks"),
    ("quant", "Quantitative Aptitude", "quant_score", "quant_max_marks", "quant_target_marks"),
    ("english", "English Comprehension", "english_score", "english_max_marks", "english_target_marks"),
    ("gk", "General Awareness", "gk_score", "gk_max_marks", "gk_target_marks"),
)


def _pct(actual: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return round(min(actual / target * 100, 100.0), 1)


def _gap(target: float, actual: float) -> float:
    return round(max(0.0, target - actual), 1)


async def get_or_create_targets(db: AsyncSession, user: User) -> UserScoreTarget:
    if user.score_target:
        return user.score_target
    overall = user.target_marks if user.target_marks and user.target_marks > 0 else 170.0
    row = UserScoreTarget(user_id=user.id, overall_target_marks=overall)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


def _targets_response(t: UserScoreTarget) -> ScoreTargetResponse:
    return ScoreTargetResponse.model_validate(t)


async def _latest_mock(db: AsyncSession, user_id: int) -> MockTest | None:
    result = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == user_id)
        .order_by(MockTest.test_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _recent_mocks(db: AsyncSession, user_id: int, limit: int = 10) -> list[MockTest]:
    result = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == user_id)
        .order_by(MockTest.test_date.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


def _subject_comparison(
    key: str,
    label: str,
    actual: float,
    actual_max: float,
    target: float,
    target_max: float,
) -> SubjectTargetComparison:
    gap = _gap(target, actual)
    return SubjectTargetComparison(
        key=key,
        label=label,
        actual=round(actual, 1),
        actual_max=actual_max,
        target=target,
        target_max=target_max,
        gap=gap,
        achievement_pct=_pct(actual, target),
        target_progress_pct=_pct(actual, target),
    )


class TargetScoreService:
    async def build_analytics(
        self, db: AsyncSession, user: User, targets: UserScoreTarget | None = None
    ) -> TargetAnalyticsResponse:
        t = targets or await get_or_create_targets(db, user)
        latest = await _latest_mock(db, user.id)

        if latest:
            actual_overall = latest.total_score
            actual_max = latest.max_score
        else:
            actual_overall = user.current_mock_score
            actual_max = t.overall_max_marks

        overall_target = t.overall_target_marks
        overall_gap = _gap(overall_target, actual_overall)
        overall = OverallTargetComparison(
            actual=round(actual_overall, 1),
            actual_max=actual_max,
            target=overall_target,
            target_max=t.overall_max_marks,
            gap=overall_gap,
            achievement_pct=_pct(actual_overall, overall_target),
            target_progress_pct=_pct(actual_overall, overall_target),
            improvement_needed=overall_gap,
        )

        subjects: list[SubjectTargetComparison] = []
        for key, label, score_attr, max_attr, target_attr in SUBJECTS:
            t_max = getattr(t, max_attr)
            t_tgt = getattr(t, target_attr)
            if latest:
                actual = getattr(latest, score_attr)
                a_max = getattr(latest, f"{key}_max_marks", t_max)
            else:
                actual = 0.0
                a_max = t_max
            subjects.append(_subject_comparison(key, label, actual, a_max, t_tgt, t_max))

        closest = min(subjects, key=lambda s: s.gap) if subjects else None
        biggest = max(subjects, key=lambda s: s.gap) if subjects else None

        weekly = await self._weekly_trend(db, user.id, overall_target)
        monthly_imp = await self._monthly_improvement(db, user.id)
        prediction = await self._score_prediction(db, user.id, actual_overall)
        probability = self._goal_probability(overall.achievement_pct, monthly_imp, len(weekly))

        mocks = await _recent_mocks(db, user.id)
        insights = await TargetAIEngine().generate_insights(
            subjects, overall, closest, biggest, weekly, mocks
        )

        return TargetAnalyticsResponse(
            targets=_targets_response(t),
            overall=overall,
            subjects=subjects,
            closest_subject=closest.label if closest else None,
            biggest_gap_subject=biggest.label if biggest else None,
            goal_achievement_probability=probability,
            weekly_trend=weekly,
            monthly_improvement=monthly_imp,
            score_prediction=prediction,
            ai_insights=insights,
            has_mock_data=latest is not None,
            latest_mock_date=str(latest.test_date) if latest else None,
        )

    async def _weekly_trend(
        self, db: AsyncSession, user_id: int, target: float
    ) -> list[TargetTrendPoint]:
        since = date.today() - timedelta(days=28)
        result = await db.execute(
            select(MockTest)
            .where(MockTest.user_id == user_id, MockTest.test_date >= since)
            .order_by(MockTest.test_date.asc())
        )
        mocks = list(result.scalars().all())
        buckets: dict[str, list[float]] = {}
        for m in mocks:
            week = m.test_date.strftime("%Y-W%W")
            buckets.setdefault(week, []).append(m.total_score)
        points = []
        for week, scores in buckets.items():
            avg = sum(scores) / len(scores)
            points.append(
                TargetTrendPoint(
                    period=week,
                    label=week,
                    avg_score=round(avg, 1),
                    target=target,
                    achievement_pct=_pct(avg, target),
                )
            )
        return points[-6:]

    async def _monthly_improvement(self, db: AsyncSession, user_id: int) -> float | None:
        result = await db.execute(
            select(MockTest)
            .where(MockTest.user_id == user_id)
            .order_by(MockTest.test_date.desc())
            .limit(10)
        )
        mocks = list(result.scalars().all())
        if len(mocks) < 2:
            return None
        recent = mocks[:3]
        older = mocks[3:6] if len(mocks) > 3 else mocks[1:3]
        if not older:
            return None
        r_avg = sum(m.total_score for m in recent) / len(recent)
        o_avg = sum(m.total_score for m in older) / len(older)
        return round(r_avg - o_avg, 1)

    async def _score_prediction(self, db: AsyncSession, user_id: int, current: float) -> float | None:
        result = await db.execute(
            select(MockTest)
            .where(MockTest.user_id == user_id)
            .order_by(MockTest.test_date.desc())
            .limit(5)
        )
        mocks = list(result.scalars().all())
        if len(mocks) < 2:
            return round(current, 1) if current else None
        mocks = list(reversed(mocks))
        deltas = [mocks[i].total_score - mocks[i - 1].total_score for i in range(1, len(mocks))]
        avg_delta = sum(deltas) / len(deltas)
        return round(max(0, mocks[-1].total_score + avg_delta * 2), 1)

    def _goal_probability(
        self, achievement_pct: float, monthly_imp: float | None, weeks: int
    ) -> float:
        base = achievement_pct * 0.6
        if monthly_imp is not None:
            base += min(25, max(-15, monthly_imp * 2))
        if weeks >= 3:
            base += 5
        return round(min(95, max(5, base)), 1)
