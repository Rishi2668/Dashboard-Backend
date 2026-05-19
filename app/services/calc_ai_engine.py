"""Rule-based AI insights for calculation practice."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc_practice import CalcQuestionAttempt, CalcWeakAreaStat
from app.models.user import User
from app.schemas.calc_practice import CalcAIInsight
from app.utils.db_dates import created_on, created_since
from app.utils.sql_helpers import sum_correct


def _safe_int(value: int | None, default: int = 0) -> int:
    return default if value is None else value


class CalcAIEngine:
    async def generate_insights(self, db: AsyncSession, user: User) -> list[CalcAIInsight]:
        insights: list[CalcAIInsight] = []
        week_ago = date.today() - timedelta(days=7)

        type_stats = await db.execute(
            select(
                CalcQuestionAttempt.practice_type,
                func.count(CalcQuestionAttempt.id).label("total"),
                sum_correct(CalcQuestionAttempt.is_correct).label("correct"),
                func.avg(CalcQuestionAttempt.time_ms).label("avg_ms"),
            )
            .where(
                CalcQuestionAttempt.user_id == user.id,
                created_since(CalcQuestionAttempt.created_at, week_ago),
            )
            .group_by(CalcQuestionAttempt.practice_type)
        )
        rows = type_stats.all()

        if not rows:
            return [
                CalcAIInsight(
                    title="Start Your Warm-Up",
                    message="Complete a 5-minute warm-up session to activate mental math before study.",
                    priority="high",
                    category="recommendation",
                )
            ]

        weakest_label = None
        weakest_acc = 101.0
        speed_label = None
        for row in rows:
            total = row.total or 0
            correct = int(row.correct or 0)
            if total < 3:
                continue
            acc = correct / total * 100
            label = row.practice_type.replace("_", " ").title()
            if acc < weakest_acc:
                weakest_acc = acc
                weakest_label = label
            if row.avg_ms and float(row.avg_ms) < 8000:
                speed_label = label

        if weakest_label and weakest_acc < 70:
            insights.append(
                CalcAIInsight(
                    title=f"Focus on {weakest_label}",
                    message=(
                        f"Your {weakest_label} accuracy is {weakest_acc:.0f}% this week. "
                        "Practice 10 questions daily in this category."
                    ),
                    priority="high",
                    category="weak_area",
                )
            )

        if speed_label:
            insights.append(
                CalcAIInsight(
                    title="Speed Improving",
                    message=f"Your {speed_label} speed is improving — keep pushing with Speed Mode.",
                    priority="medium",
                    category="speed",
                )
            )

        weak_result = await db.execute(
            select(CalcWeakAreaStat).where(CalcWeakAreaStat.user_id == user.id)
        )
        all_weak = weak_result.scalars().all()
        if all_weak:
            worst = min(
                all_weak,
                key=lambda s: (
                    _safe_int(s.correct_count) / _safe_int(s.total_attempts)
                    if _safe_int(s.total_attempts)
                    else 1
                ),
            )
            if _safe_int(worst.total_attempts) >= 5:
                acc = _safe_int(worst.correct_count) / _safe_int(worst.total_attempts) * 100
                label = worst.practice_type.replace("_", " ").title()
                insights.append(
                    CalcAIInsight(
                        title="Persistent Weak Spot",
                        message=f"Practice {label} more frequently — lifetime accuracy {acc:.0f}%.",
                        priority="high",
                        category="weak_area",
                    )
                )

        today_result = await db.execute(
            select(
                func.count(CalcQuestionAttempt.id),
                sum_correct(CalcQuestionAttempt.is_correct),
            ).where(
                CalcQuestionAttempt.user_id == user.id,
                created_on(CalcQuestionAttempt.created_at, date.today()),
            )
        )
        today_row = today_result.one()
        today_total = today_row[0] or 0
        today_correct = int(today_row[1] or 0)
        if today_total >= 10:
            today_acc = today_correct / today_total * 100
            if today_acc < 65:
                insights.append(
                    CalcAIInsight(
                        title="Accuracy Dip Today",
                        message=(
                            f"Accuracy dropped today ({today_acc:.0f}%). "
                            "Try Accuracy Mode for mistake tracking."
                        ),
                        priority="medium",
                        category="accuracy",
                    )
                )
            else:
                insights.append(
                    CalcAIInsight(
                        title="Strong Session Today",
                        message=f"Great work — {today_acc:.0f}% accuracy across {today_total} questions today.",
                        priority="low",
                        category="motivation",
                    )
                )

        if not insights:
            insights.append(
                CalcAIInsight(
                    title="Daily Warm-Up",
                    message="A 5-minute warm-up before mocks boosts calculation speed in exams.",
                    priority="medium",
                    category="recommendation",
                )
            )

        return insights[:6]
