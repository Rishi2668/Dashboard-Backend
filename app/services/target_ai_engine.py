"""AI insights for target score vs mock performance (rule-based + optional LLM)."""

from __future__ import annotations

from app.models.mock_test import MockTest
from app.schemas.score_target import (
    OverallTargetComparison,
    SubjectTargetComparison,
    TargetAIInsight,
    TargetTrendPoint,
)
from app.services.ai.llm_provider import generate_llm_insight, parse_insights_json


class TargetAIEngine:
    async def generate_insights(
        self,
        subjects: list[SubjectTargetComparison],
        overall: OverallTargetComparison,
        closest: SubjectTargetComparison | None,
        biggest: SubjectTargetComparison | None,
        weekly: list[TargetTrendPoint],
        mocks: list[MockTest] | None = None,
    ) -> list[TargetAIInsight]:
        rule = self._rule_insights(subjects, overall, closest, biggest, weekly, mocks or [])
        llm = await self._llm_insights(subjects, overall, closest, biggest, weekly, mocks or [])
        if llm:
            return self._merge(rule, llm)
        return rule

    def _merge(self, rule: list[TargetAIInsight], llm: list[TargetAIInsight]) -> list[TargetAIInsight]:
        seen: set[str] = set()
        merged: list[TargetAIInsight] = []
        for ins in llm + rule:
            key = ins.title.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(ins)
        return merged[:8]

    async def _llm_insights(
        self,
        subjects: list[SubjectTargetComparison],
        overall: OverallTargetComparison,
        closest: SubjectTargetComparison | None,
        biggest: SubjectTargetComparison | None,
        weekly: list[TargetTrendPoint],
        mocks: list[MockTest],
    ) -> list[TargetAIInsight] | None:
        subject_lines = "\n".join(
            f"- {s.label}: actual {s.actual}/{s.actual_max}, target {s.target}/{s.target_max}, gap {s.gap}"
            for s in subjects
        )
        weekly_lines = "\n".join(
            f"- {w.label}: avg {w.avg_score} vs target {w.target} ({w.achievement_pct}%)"
            for w in weekly[-4:]
        )
        mock_lines = ""
        if mocks:
            latest = mocks[-1]
            mock_lines = (
                f"Latest mock ({latest.test_date}): {latest.total_score}/{latest.max_score}, "
                f"accuracy {latest.accuracy:.1f}%.\n"
            )
            if len(mocks) >= 2:
                prev = mocks[-2]
                mock_lines += f"Previous mock: {prev.total_score}/{prev.max_score}.\n"

        prompt = f"""You are an SSC CGL exam coach. Analyze target vs actual performance and return exactly 3 insights.

{mock_lines}Overall: actual {overall.actual}/{overall.actual_max}, target {overall.target}/{overall.target_max}, gap {overall.gap}, achievement {overall.achievement_pct}%.
Closest to target: {closest.label if closest else "N/A"} (gap {closest.gap if closest else 0}).
Biggest gap: {biggest.label if biggest else "N/A"} (gap {biggest.gap if biggest else 0}).

Subjects:
{subject_lines}

Weekly trend:
{weekly_lines or "No weekly data yet."}

Respond with ONLY a JSON array (no markdown), each object:
{{"title": "short title", "message": "actionable 1-2 sentences", "priority": "high|medium|low", "category": "target|weak_area|trend|strategy"}}

Examples of tone:
- "You are closest to your English target."
- "Quant requires the biggest improvement."
- "GK target gap is increasing — add daily CA."
"""

        raw = await generate_llm_insight(prompt)
        items = parse_insights_json(raw or "")
        if not items:
            return None

        insights: list[TargetAIInsight] = []
        for item in items[:4]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            message = str(item.get("message", "")).strip()
            if not title or not message:
                continue
            insights.append(
                TargetAIInsight(
                    title=title[:120],
                    message=message[:400],
                    priority=str(item.get("priority", "medium"))[:10] or "medium",
                    category=str(item.get("category", "target"))[:20] or "target",
                )
            )
        return insights or None

    def _rule_insights(
        self,
        subjects: list[SubjectTargetComparison],
        overall: OverallTargetComparison,
        closest: SubjectTargetComparison | None,
        biggest: SubjectTargetComparison | None,
        weekly: list[TargetTrendPoint],
        mocks: list[MockTest],
    ) -> list[TargetAIInsight]:
        insights: list[TargetAIInsight] = []

        if not mocks:
            insights.append(
                TargetAIInsight(
                    title="Log a mock to unlock target AI",
                    message="Save your first mock test to compare actual scores against your Reasoning, Quant, English, and GK targets.",
                    priority="high",
                    category="target",
                )
            )
            return insights

        if closest and closest.gap <= 5:
            short = closest.label.split()[0] if closest.label else closest.key
            insights.append(
                TargetAIInsight(
                    title=f"You are closest to your {short} target",
                    message=f"Only {closest.gap:.1f} marks away ({closest.actual}/{closest.target}). One strong sectional can close this gap.",
                    priority="medium",
                    category="strength",
                )
            )

        if biggest and biggest.gap >= 8:
            msg = {
                "quant": "Quant requires the biggest improvement — add 20 timed questions daily.",
                "gk": "GK target gap is increasing — daily CA quiz + static GK revision.",
                "reasoning": "Reasoning target can be achieved with more mocks and puzzle practice.",
                "english": "English is near target — maintain comprehension drills to lock the gap.",
            }
            insights.append(
                TargetAIInsight(
                    title=f"{biggest.label} needs the most work",
                    message=msg.get(biggest.key, f"Focus {biggest.label}: gap of {biggest.gap:.1f} marks."),
                    priority="high",
                    category="weak_area",
                )
            )

        if len(mocks) >= 2:
            latest, prev = mocks[-1], mocks[-2]
            for key, label in [
                ("gk", "General Awareness"),
                ("quant", "Quantitative Aptitude"),
                ("reasoning", "Reasoning"),
                ("english", "English"),
            ]:
                cur_s = getattr(latest, f"{key}_score", 0)
                prev_s = getattr(prev, f"{key}_score", 0)
                tgt = next((s for s in subjects if s.key == key), None)
                if tgt and cur_s < prev_s and cur_s < tgt.target:
                    insights.append(
                        TargetAIInsight(
                            title=f"{label} target gap is widening",
                            message=f"Marks dropped from {prev_s:.1f} to {cur_s:.1f} vs target {tgt.target:.0f}. Review last mock mistakes in this section.",
                            priority="high",
                            category="trend",
                        )
                    )
                    break

        if weekly and len(weekly) >= 2:
            if weekly[-1].achievement_pct < weekly[-2].achievement_pct - 5:
                insights.append(
                    TargetAIInsight(
                        title="Weekly target progress dipped",
                        message="Latest week scored below the previous week vs your target. Schedule one sectional this week.",
                        priority="high",
                        category="trend",
                    )
                )
            elif weekly[-1].achievement_pct > weekly[-2].achievement_pct + 3:
                insights.append(
                    TargetAIInsight(
                        title="Weekly momentum toward target",
                        message="You are moving closer to your overall target week over week. Keep 2 mocks per week.",
                        priority="medium",
                        category="trend",
                    )
                )

        if overall.gap > 0:
            insights.append(
                TargetAIInsight(
                    title="Overall target gap",
                    message=(
                        f"{overall.gap:.1f} marks remaining to hit {overall.target:.0f}/{overall.target_max:.0f}. "
                        f"At {overall.achievement_pct:.0f}% of target achievement."
                    ),
                    priority="medium",
                    category="overall",
                )
            )
        else:
            insights.append(
                TargetAIInsight(
                    title="Target achieved!",
                    message="Your latest mock meets or exceeds your overall target. Raise targets or maintain consistency.",
                    priority="low",
                    category="overall",
                )
            )

        return insights[:6]
