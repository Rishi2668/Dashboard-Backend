"""AI insights for sectional tests only (separate from full mock AI)."""

from __future__ import annotations

from app.models.mock_test import MockTest
from app.schemas.mock_test import MockAIInsight
from app.schemas.score_target import TargetAnalyticsResponse

SUBJECT_LABELS = {
    "reasoning": "General Intelligence & Reasoning",
    "quant": "Quantitative Aptitude",
    "english": "English Comprehension",
    "gk": "General Awareness",
}


def _primary_subject(mock: MockTest) -> str | None:
    best_key = None
    best_att = 0
    for key in SUBJECT_LABELS:
        att = getattr(mock, f"{key}_attempted", 0) or 0
        if att > best_att:
            best_att = att
            best_key = key
    return best_key


class SectionalAIEngine:
    def generate_insights(
        self,
        mocks: list[MockTest],
        target_data: TargetAnalyticsResponse | None = None,
    ) -> list[MockAIInsight]:
        if not mocks:
            return [
                MockAIInsight(
                    title="Log your first sectional",
                    message="Pick a subject (e.g. Reasoning) and save marks from a 50-mark sectional to start per-subject trends.",
                    priority="high",
                    category="sectional",
                )
            ]

        insights: list[MockAIInsight] = []
        by_subject: dict[str, list[MockTest]] = {k: [] for k in SUBJECT_LABELS}
        for m in mocks:
            key = _primary_subject(m)
            if key:
                by_subject[key].append(m)

        if target_data:
            for subj in target_data.subjects:
                latest = by_subject.get(subj.key, [])
                if not latest:
                    insights.append(
                        MockAIInsight(
                            title=f"No {subj.label.split()[0]} sectional yet",
                            message=(
                                f"Dashboard target for this section is {subj.target:.0f}/{subj.target_max:.0f} marks. "
                                "Log a sectional to compare actual vs target."
                            ),
                            priority="medium",
                            category="target",
                        )
                    )
                    continue
                last = latest[-1]
                actual = getattr(last, f"{subj.key}_score", 0)
                gap = max(0.0, subj.target - actual)
                if gap <= 3:
                    insights.append(
                        MockAIInsight(
                            title=f"{subj.label}: almost at target",
                            message=(
                                f"Latest sectional {actual:.1f}/{subj.target_max:.0f} — "
                                f"target is {subj.target:.0f} (only {gap:.1f} marks away)."
                            ),
                            priority="medium",
                            category="strength",
                        )
                    )
                elif gap >= 10:
                    insights.append(
                        MockAIInsight(
                            title=f"{subj.label}: largest sectional gap",
                            message=(
                                f"Target {subj.target:.0f}/{subj.target_max:.0f}, latest sectional {actual:.1f}. "
                                f"Gap {gap:.1f} marks — add 2 sectionals/week for this subject."
                            ),
                            priority="high",
                            category="weak_area",
                        )
                    )

        # Per-subject trend vs previous sectional of same subject
        for key, label in SUBJECT_LABELS.items():
            series = by_subject[key]
            if len(series) < 2:
                continue
            prev, cur = series[-2], series[-1]
            prev_s = getattr(prev, f"{key}_score", 0)
            cur_s = getattr(cur, f"{key}_score", 0)
            diff = cur_s - prev_s
            if diff >= 5:
                insights.append(
                    MockAIInsight(
                        title=f"{label} sectional score up",
                        message=f"{label} improved {diff:.1f} marks ({prev_s:.1f} → {cur_s:.1f}) vs your last sectional.",
                        priority="medium",
                        category="trend",
                    )
                )
            elif diff <= -5:
                insights.append(
                    MockAIInsight(
                        title=f"{label} sectional dipped",
                        message=f"{label} dropped {abs(diff):.1f} marks vs previous sectional — review mistakes.",
                        priority="high",
                        category="trend",
                    )
                )

        if not insights:
            insights.append(
                MockAIInsight(
                    title="Keep sectional rhythm",
                    message="Log at least one sectional per weak subject weekly — trends stay separate from full mocks.",
                    priority="medium",
                    category="sectional",
                )
            )

        return insights[:8]
