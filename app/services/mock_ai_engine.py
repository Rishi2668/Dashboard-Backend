"""AI insights for full SSC CGL mock tests only (not sectionals)."""

from __future__ import annotations

from app.models.mock_test import MockTest
from app.schemas.mock_test import MockAIInsight

SUBJECT_LABELS = {
    "reasoning": "General Intelligence & Reasoning",
    "quant": "Quantitative Aptitude",
    "english": "English Comprehension",
    "gk": "General Awareness",
}


def _subject_stats(m: MockTest, key: str) -> tuple[float, float, int, int]:
    return (
        getattr(m, f"{key}_score"),
        getattr(m, f"{key}_accuracy"),
        getattr(m, f"{key}_attempted"),
        getattr(m, f"{key}_correct"),
    )


class MockAIEngine:
    def generate_insights(self, mocks: list[MockTest]) -> list[MockAIInsight]:
        if not mocks:
            return [
                MockAIInsight(
                    title="Start your full mock journey",
                    message="Log your first 200-mark full mock to unlock score trends and section insights.",
                    priority="high",
                    category="recommendation",
                )
            ]

        insights: list[MockAIInsight] = []
        latest = mocks[-1]
        subjects = ["reasoning", "quant", "english", "gk"]
        accs = {k: getattr(latest, f"{k}_accuracy") for k in subjects}
        strongest = max(accs, key=accs.get)
        weakest = min(accs, key=accs.get)

        insights.append(
            MockAIInsight(
                title=f"{SUBJECT_LABELS[strongest]} is your strongest section",
                message=(
                    f"You scored {accs[strongest]:.1f}% accuracy in {SUBJECT_LABELS[strongest]} "
                    f"in your latest mock — use this as a confidence anchor."
                ),
                priority="medium",
                category="strength",
            )
        )

        if accs[weakest] < 70:
            msg = {
                "quant": "Quant needs more speed practice — drill 20 timed questions daily.",
                "reasoning": "Reasoning puzzles need pattern practice — solve 2 previous-year sets per week.",
                "english": "English comprehension — revise grammar rules and read editorials daily.",
                "gk": "GK accuracy is inconsistent — use short daily CA quizzes + static GK revision.",
            }
            insights.append(
                MockAIInsight(
                    title=f"Focus on {SUBJECT_LABELS[weakest]}",
                    message=msg.get(weakest, f"Improve {SUBJECT_LABELS[weakest]} with targeted sectionals."),
                    priority="high",
                    category="weak_area",
                )
            )

        if len(mocks) >= 2:
            prev, cur = mocks[-2], mocks[-1]
            for key in subjects:
                prev_a = getattr(prev, f"{key}_accuracy")
                cur_a = getattr(cur, f"{key}_accuracy")
                diff = cur_a - prev_a
                if diff >= 5:
                    insights.append(
                        MockAIInsight(
                            title=f"{SUBJECT_LABELS[key]} accuracy improved",
                            message=(
                                f"{SUBJECT_LABELS[key]} accuracy improved by {diff:.1f}% "
                                f"({prev_a:.1f}% → {cur_a:.1f}%). Keep the same revision plan."
                            ),
                            priority="medium",
                            category="trend",
                        )
                    )
                elif diff <= -5:
                    insights.append(
                        MockAIInsight(
                            title=f"{SUBJECT_LABELS[key]} dipped",
                            message=(
                                f"{SUBJECT_LABELS[key]} dropped {abs(diff):.1f}% vs previous mock. "
                                "Review wrong questions from both tests."
                            ),
                            priority="high",
                            category="trend",
                        )
                    )

            score_diff = cur.total_score - prev.total_score
            if score_diff >= 10:
                insights.append(
                    MockAIInsight(
                        title="Overall score trending up",
                        message=f"Total marks improved by {score_diff:.1f} — maintain mock frequency (2/week).",
                        priority="medium",
                        category="trend",
                    )
                )

        pct = (latest.total_score / latest.max_score * 100) if latest.max_score else 0
        if pct < 50:
            insights.append(
                MockAIInsight(
                    title="Build fundamentals first",
                    message="Below 50% overall — prioritize sectionals and syllabus gaps before full mocks.",
                    priority="high",
                    category="strategy",
                )
            )

        return insights[:6]
