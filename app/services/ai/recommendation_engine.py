from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_insight import AIInsight
from app.models.mock_test import MockTest
from app.models.study import StudySession
from app.models.user import User
from app.models.weak_area import WeakTopic


LEVELS = [
    (0, "Beginner"),
    (500, "Consistent Learner"),
    (1500, "SSC Warrior"),
    (3500, "Rank Hunter"),
    (7000, "Topper Mode"),
]


def get_level_from_xp(xp: int) -> tuple[str, str, float, int, int]:
    """Returns level name, next level name, progress %, XP at current tier start, XP for next tier."""
    current_level = LEVELS[0][1]
    next_level = LEVELS[1][1] if len(LEVELS) > 1 else current_level
    progress = 0.0
    xp_at_level = 0
    xp_for_next = LEVELS[1][0] if len(LEVELS) > 1 else LEVELS[0][0]
    for i, (threshold, name) in enumerate(LEVELS):
        if xp >= threshold:
            current_level = name
            xp_at_level = threshold
            if i + 1 < len(LEVELS):
                next_threshold, next_name = LEVELS[i + 1]
                next_level = next_name
                xp_for_next = next_threshold
                progress = (xp - threshold) / max(next_threshold - threshold, 1) * 100
            else:
                next_level = name
                xp_for_next = threshold
                progress = 100.0
    return current_level, next_level, min(progress, 100.0), xp_at_level, xp_for_next


class AIRecommendationEngine:
    """Rule-based analytics and recommendation engine with optional LLM hooks."""

    async def generate_insights(self, db: AsyncSession, user: User) -> list[AIInsight]:
        insights: list[AIInsight] = []
        mocks = await self._get_recent_mocks(db, user.id, limit=10)
        sessions = await self._get_recent_sessions(db, user.id, limit=30)
        weak_topics = await self._get_weak_topics(db, user.id)

        insights.extend(await self._mock_trend_insights(user.id, mocks))
        insights.extend(await self._productivity_insights(user.id, sessions))
        insights.extend(await self._weak_area_insights(user.id, weak_topics, mocks))
        insights.extend(await self._study_plan_insights(user.id, mocks, weak_topics))

        for insight in insights:
            db.add(insight)
        await db.flush()
        return insights

    async def _get_recent_mocks(self, db: AsyncSession, user_id: int, limit: int) -> list[MockTest]:
        result = await db.execute(
            select(MockTest)
            .where(MockTest.user_id == user_id)
            .order_by(MockTest.test_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_recent_sessions(self, db: AsyncSession, user_id: int, limit: int) -> list[StudySession]:
        result = await db.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_weak_topics(self, db: AsyncSession, user_id: int) -> list[WeakTopic]:
        result = await db.execute(
            select(WeakTopic)
            .where(WeakTopic.user_id == user_id, WeakTopic.needs_revision == True)
            .order_by(WeakTopic.accuracy.asc())
            .limit(5)
        )
        return list(result.scalars().all())

    async def _mock_trend_insights(self, user_id: int, mocks: list[MockTest]) -> list[AIInsight]:
        insights = []
        if len(mocks) < 2:
            return insights

        recent = mocks[:5]
        older = mocks[5:10] if len(mocks) > 5 else []

        for section, attr in [
            ("Geometry/Quant", "quant_accuracy"),
            ("Reasoning", "reasoning_accuracy"),
            ("English", "english_accuracy"),
            ("General Awareness", "gk_accuracy"),
        ]:
            recent_avg = sum(getattr(m, attr) for m in recent) / len(recent)
            if older:
                older_avg = sum(getattr(m, attr) for m in older) / len(older)
                diff = recent_avg - older_avg
                if diff < -5:
                    insights.append(
                        AIInsight(
                            user_id=user_id,
                            insight_type="mock_trend",
                            title=f"{section} accuracy dropped",
                            message=f"Your {section} accuracy dropped {abs(diff):.1f}% in the last {len(recent)} mocks. Focus revision here today.",
                            priority="high",
                        )
                    )
                elif diff > 5:
                    insights.append(
                        AIInsight(
                            user_id=user_id,
                            insight_type="mock_trend",
                            title=f"{section} improving!",
                            message=f"Great progress! {section} accuracy improved {diff:.1f}% over recent mocks. Maintain momentum.",
                            priority="low",
                        )
                    )

        avg_recent = sum(m.total_score for m in recent) / len(recent)
        if avg_recent < 100:
            insights.append(
                AIInsight(
                    user_id=user_id,
                    insight_type="mock_analysis",
                    title="Focus on sectionals",
                    message="Your average mock score is below 100. Focus on Algebra and sectionals today instead of full mocks.",
                    priority="high",
                    action_url="/analytics",
                )
            )
        return insights

    async def _productivity_insights(self, user_id: int, sessions: list[StudySession]) -> list[AIInsight]:
        insights = []
        if not sessions:
            insights.append(
                AIInsight(
                    user_id=user_id,
                    insight_type="productivity",
                    title="Start your streak",
                    message="No study sessions logged yet. Log 2 hours today to begin your consistency streak.",
                    priority="medium",
                )
            )
            return insights

        hour_buckets: dict[int, float] = {}
        for s in sessions:
            if s.subject_breakdown:
                hour_buckets[19] = hour_buckets.get(19, 0) + s.hours
            hour_buckets[19] = hour_buckets.get(19, 0) + s.hours * 0.3
            hour_buckets[20] = hour_buckets.get(20, 0) + s.hours * 0.4
            hour_buckets[21] = hour_buckets.get(21, 0) + s.hours * 0.3

        peak_hour = max(hour_buckets, key=hour_buckets.get) if hour_buckets else 19
        peak_end = (peak_hour + 3) % 24
        insights.append(
            AIInsight(
                user_id=user_id,
                insight_type="productivity",
                title="Peak productivity window",
                message=f"Your best productivity hours are between {peak_hour}:00 and {peak_end}:00. Schedule tough topics then.",
                priority="medium",
            )
        )

        week_ago = date.today() - timedelta(days=7)
        recent_hours = sum(s.hours for s in sessions if s.date >= week_ago)
        if recent_hours < 14:
            insights.append(
                AIInsight(
                    user_id=user_id,
                    insight_type="productivity",
                    title="Increase study hours",
                    message=f"You studied only {recent_hours:.1f} hours this week. Target 20+ hours for SSC CGL Tier-1 readiness.",
                    priority="high",
                )
            )
        return insights

    async def _weak_area_insights(
        self, user_id: int, weak_topics: list[WeakTopic], mocks: list[MockTest]
    ) -> list[AIInsight]:
        insights = []
        for wt in weak_topics[:3]:
            insights.append(
                AIInsight(
                    user_id=user_id,
                    insight_type="weak_area",
                    title=f"Revise: {wt.topic}",
                    message=f"{wt.subject} — {wt.topic} at {wt.accuracy:.0f}% accuracy ({wt.mistake_count} mistakes). Priority: {wt.priority}.",
                    priority="high" if wt.accuracy < 50 else "medium",
                    action_url="/weak-areas",
                )
            )
        return insights

    async def _study_plan_insights(
        self, user_id: int, mocks: list[MockTest], weak_topics: list[WeakTopic]
    ) -> list[AIInsight]:
        insights = []
        subjects = ["Quant", "Reasoning", "English", "GK"]
        focus_subject = weak_topics[0].subject if weak_topics else "Quant"
        insights.append(
            AIInsight(
                user_id=user_id,
                insight_type="daily_plan",
                title="Today's AI study plan",
                message=f"1) 45 min {focus_subject} weak topics  2) 1 sectional mock  3) 30 min revision. Skip full mock if accuracy < 60%.",
                priority="medium",
                action_url="/",
            )
        )
        if mocks:
            last = mocks[0]
            insights.append(
                AIInsight(
                    user_id=user_id,
                    insight_type="motivation",
                    title="Personalized motivation",
                    message=f"Last mock: {last.total_score:.0f}/{last.max_score:.0f}. Every mock is data — analyze wrong questions and come back stronger.",
                    priority="low",
                )
            )
        return insights

    async def detect_weak_areas_from_mocks(self, db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
        result = await db.execute(
            select(
                MockTest.quant_accuracy,
                MockTest.reasoning_accuracy,
                MockTest.english_accuracy,
                MockTest.gk_accuracy,
            )
            .where(MockTest.user_id == user_id)
            .order_by(MockTest.test_date.desc())
            .limit(5)
        )
        rows = result.all()
        if not rows:
            return []
        sections = ["Quant", "Reasoning", "English", "GK"]
        attrs = ["quant_accuracy", "reasoning_accuracy", "english_accuracy", "gk_accuracy"]
        weak = []
        for i, section in enumerate(sections):
            avg = sum(r[i] for r in rows) / len(rows)
            if avg < 65:
                weak.append({"subject": section, "accuracy": round(avg, 1), "priority": "high"})
        return weak
