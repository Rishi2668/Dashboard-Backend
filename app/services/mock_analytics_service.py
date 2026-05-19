"""Build mock analytics for full mocks vs sectional mocks separately."""

from __future__ import annotations

from app.models.mock_test import MockTest
from app.schemas.mock_test import MockAIInsight, MockAnalytics, SectionalSubjectTarget
from app.schemas.score_target import TargetAnalyticsResponse
from app.services.mock_ai_engine import MockAIEngine
from app.services.mock_classification import (
    SUBJECT_KEYS,
    filter_mocks_by_type,
    primary_subject,
)
from app.services.sectional_ai_engine import SectionalAIEngine
LABELS = {
    "reasoning": "General Intelligence & Reasoning",
    "quant": "Quantitative Aptitude",
    "english": "English Comprehension",
    "gk": "General Awareness",
}


def _sectional_score(mock: MockTest) -> tuple[float, float, float]:
    key = primary_subject(mock)
    if not key:
        return mock.total_score, mock.max_score, mock.accuracy
    secured = getattr(mock, f"{key}_score", 0)
    max_m = getattr(mock, f"{key}_max_marks", 0) or 1
    acc = getattr(mock, f"{key}_accuracy", 0)
    return secured, max_m, acc


def _pct(actual: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return round(min(actual / target * 100, 100.0), 1)


def _build_subject_targets(
    mocks: list[MockTest], target_data: TargetAnalyticsResponse | None
) -> list[SectionalSubjectTarget]:
    if not target_data:
        return []
    by_subject: dict[str, list[MockTest]] = {k: [] for k in SUBJECT_KEYS}
    for m in mocks:
        key = primary_subject(m)
        if key:
            by_subject[key].append(m)

    rows: list[SectionalSubjectTarget] = []
    for subj in target_data.subjects:
        series = by_subject.get(subj.key, [])
        if series:
            last = series[-1]
            actual = getattr(last, f"{subj.key}_score", 0)
            actual_max = getattr(last, f"{subj.key}_max_marks", subj.target_max)
            has_data = True
            count = len(series)
        else:
            actual = 0.0
            actual_max = subj.target_max
            has_data = False
            count = 0
        gap = round(max(0.0, subj.target - actual), 1)
        rows.append(
            SectionalSubjectTarget(
                key=subj.key,
                label=subj.label,
                target=subj.target,
                target_max=subj.target_max,
                actual=round(actual, 1),
                actual_max=actual_max,
                gap=gap,
                achievement_pct=_pct(actual, subj.target),
                has_sectional_data=has_data,
                sectional_count=count,
            )
        )
    return rows


def build_mock_analytics(
    mocks: list[MockTest],
    test_type: str,
    target_data: TargetAnalyticsResponse | None = None,
) -> MockAnalytics:
    filtered = filter_mocks_by_type(mocks, test_type)

    if test_type == "sectional":
        empty_insights = [
            MockAIInsight(
                title="Start sectional practice",
                message="Log subject-wise sectionals to track accuracy trends per section (separate from full mocks).",
                priority="high",
                category="sectional",
            )
        ]
        empty = _empty_analytics(empty_insights, subject_targets=_build_subject_targets([], target_data))
        if not filtered:
            return empty
        return _build_sectional_analytics(filtered, target_data)

    # Full mock analytics
    target_insights = []
    if target_data:
        target_insights = [
            MockAIInsight(
                title=t.title,
                message=t.message,
                priority=t.priority,
                category=t.category or "target",
            )
            for t in target_data.ai_insights
        ]
    empty_mock_ai = MockAIEngine().generate_insights([])
    if not filtered:
        # No full mocks — do not attach target tracker (would show sectional scores)
        return _empty_analytics(empty_mock_ai, target_analytics=None, target_insights=[])
    return _build_full_analytics(filtered, target_data, target_insights)


def _empty_analytics(
    ai_insights: list[MockAIInsight],
    target_analytics: TargetAnalyticsResponse | None = None,
    target_insights: list[MockAIInsight] | None = None,
    subject_targets: list[SectionalSubjectTarget] | None = None,
) -> MockAnalytics:
    return MockAnalytics(
        latest_score=0,
        highest_score=0,
        average_score=0,
        average_accuracy=0,
        latest_score_percentage=0,
        total_attempted=0,
        total_correct=0,
        total_wrong=0,
        total_negative=0,
        total_mocks=0,
        score_progression=[],
        accuracy_trend=[],
        section_comparison=[],
        subject_accuracy_trends={k: [] for k in SUBJECT_KEYS},
        weekly_trend=[],
        weak_subjects=[],
        strongest_subject=None,
        improvement_delta=None,
        ai_insights=ai_insights,
        target_insights=target_insights or [],
        subject_targets=subject_targets or [],
        target_analytics=target_analytics,
    )


def _build_full_analytics(
    mocks: list[MockTest],
    target_data: TargetAnalyticsResponse | None,
    target_insights: list[MockAIInsight],
) -> MockAnalytics:
    latest = mocks[-1]
    score_progression = [
        {
            "date": str(m.test_date),
            "score": m.total_score,
            "max_score": m.max_score,
            "percentage": round(m.total_score / m.max_score * 100, 1) if m.max_score else 0,
            "name": m.test_name or "",
        }
        for m in mocks
    ]
    accuracy_trend = [{"date": str(m.test_date), "accuracy": m.accuracy} for m in mocks]

    section_comparison = []
    subject_accuracy_trends: dict[str, list] = {k: [] for k in SUBJECT_KEYS}
    for key in SUBJECT_KEYS:
        section_comparison.append(
            {
                "subject": LABELS[key],
                "subject_key": key,
                "score": getattr(latest, f"{key}_score"),
                "max_marks": getattr(latest, f"{key}_max_marks"),
                "accuracy": getattr(latest, f"{key}_accuracy"),
                "attempted": getattr(latest, f"{key}_attempted"),
                "total_questions": getattr(latest, f"{key}_total_questions"),
                "score_percentage": round(
                    getattr(latest, f"{key}_score") / getattr(latest, f"{key}_max_marks") * 100, 1
                )
                if getattr(latest, f"{key}_max_marks")
                else 0,
            }
        )
        for m in mocks:
            subject_accuracy_trends[key].append(
                {
                    "date": str(m.test_date),
                    "accuracy": getattr(m, f"{key}_accuracy"),
                    "score": getattr(m, f"{key}_score"),
                }
            )

    weekly: dict[str, list] = {}
    for m in mocks[-12:]:
        week_key = m.test_date.strftime("%Y-W%W")
        weekly.setdefault(week_key, []).append(m.total_score)
    weekly_trend = [{"week": k, "avg_score": sum(v) / len(v)} for k, v in weekly.items()]

    accs = [(LABELS[k], getattr(latest, f"{k}_accuracy")) for k in SUBJECT_KEYS]
    accs.sort(key=lambda x: x[1])
    weak_subjects = [
        {"subject": s, "accuracy": a, "priority": "high" if a < 60 else "medium"}
        for s, a in accs[:2]
        if a < 75
    ]
    strongest = max(accs, key=lambda x: x[1])[0] if accs else None

    improvement_delta = None
    if len(mocks) >= 2:
        improvement_delta = round(mocks[-1].total_score - mocks[-2].total_score, 1)

    latest_pct = round(latest.total_score / latest.max_score * 100, 1) if latest.max_score else 0

    return MockAnalytics(
        latest_score=latest.total_score,
        highest_score=max(m.total_score for m in mocks),
        average_score=sum(m.total_score for m in mocks) / len(mocks),
        average_accuracy=sum(m.accuracy for m in mocks) / len(mocks),
        latest_score_percentage=latest_pct,
        total_attempted=sum(m.attempted for m in mocks),
        total_correct=sum(m.correct for m in mocks),
        total_wrong=sum(m.wrong for m in mocks),
        total_negative=sum(m.negative_marks for m in mocks),
        total_mocks=len(mocks),
        score_progression=score_progression,
        accuracy_trend=accuracy_trend,
        section_comparison=section_comparison,
        subject_accuracy_trends=subject_accuracy_trends,
        weekly_trend=weekly_trend,
        weak_subjects=weak_subjects,
        strongest_subject=strongest,
        improvement_delta=improvement_delta,
        ai_insights=MockAIEngine().generate_insights(mocks),
        target_insights=target_insights,
        subject_targets=[],
        target_analytics=target_data,
    )


def _build_sectional_analytics(
    mocks: list[MockTest],
    target_data: TargetAnalyticsResponse | None,
) -> MockAnalytics:
    latest = mocks[-1]
    latest_score, latest_max, _ = _sectional_score(latest)

    score_progression = []
    accuracy_trend = []
    for m in mocks:
        sc, mx, acc = _sectional_score(m)
        key = primary_subject(m)
        score_progression.append(
            {
                "date": str(m.test_date),
                "score": sc,
                "max_score": mx,
                "percentage": round(sc / mx * 100, 1) if mx else 0,
                "name": m.test_name or (LABELS.get(key or "", key) or "Sectional"),
                "subject": LABELS.get(key or "", key or ""),
                "subject_key": key or "",
            }
        )
        accuracy_trend.append({"date": str(m.test_date), "accuracy": acc, "subject_key": key or ""})

    subject_stats: dict[str, list[float]] = {k: [] for k in SUBJECT_KEYS}
    subject_accuracy_trends: dict[str, list] = {k: [] for k in SUBJECT_KEYS}
    for m in mocks:
        key = primary_subject(m)
        if not key:
            continue
        acc = getattr(m, f"{key}_accuracy", 0)
        sc = getattr(m, f"{key}_score", 0)
        mx = getattr(m, f"{key}_max_marks", 50)
        subject_stats[key].append(acc)
        subject_accuracy_trends[key].append(
            {
                "date": str(m.test_date),
                "accuracy": acc,
                "score": sc,
                "max_score": mx,
                "name": m.test_name or "",
            }
        )

    section_comparison = []
    subject_targets = _build_subject_targets(mocks, target_data)
    target_by_key = {t.key: t for t in subject_targets}

    for key in SUBJECT_KEYS:
        accs = subject_stats[key]
        tgt = target_by_key.get(key)
        if not accs and not tgt:
            continue
        avg_acc = sum(accs) / len(accs) if accs else 0
        last_m = next((m for m in reversed(mocks) if primary_subject(m) == key), None)
        sc = getattr(last_m, f"{key}_score", 0) if last_m else 0
        mx = getattr(last_m, f"{key}_max_marks", 50) if last_m else (tgt.target_max if tgt else 50)
        section_comparison.append(
            {
                "subject": LABELS[key],
                "subject_key": key,
                "score": sc,
                "max_marks": mx,
                "target_marks": tgt.target if tgt else None,
                "target_max": tgt.target_max if tgt else 50,
                "accuracy": round(avg_acc, 1) if accs else 0,
                "attempted": getattr(last_m, f"{key}_attempted", 0) if last_m else 0,
                "total_questions": getattr(last_m, f"{key}_total_questions", 25) if last_m else 25,
                "score_percentage": round(sc / mx * 100, 1) if mx else 0,
                "sectional_count": len(accs),
                "gap_to_target": tgt.gap if tgt else None,
            }
        )

    weekly: dict[str, list] = {}
    for m in mocks[-12:]:
        sc, _, _ = _sectional_score(m)
        week_key = m.test_date.strftime("%Y-W%W")
        weekly.setdefault(week_key, []).append(sc)
    weekly_trend = [{"week": k, "avg_score": sum(v) / len(v)} for k, v in weekly.items()]

    accs_ranked = [(s["subject"], s["accuracy"]) for s in section_comparison if s.get("sectional_count")]
    accs_ranked.sort(key=lambda x: x[1])
    weak_subjects = [
        {"subject": s, "accuracy": a, "priority": "high" if a < 60 else "medium"}
        for s, a in accs_ranked[:2]
        if a < 75
    ]
    strongest = max(accs_ranked, key=lambda x: x[1])[0] if accs_ranked else None

    improvement_delta = None
    if len(mocks) >= 2:
        s1, _, _ = _sectional_score(mocks[-1])
        s0, _, _ = _sectional_score(mocks[-2])
        improvement_delta = round(s1 - s0, 1)

    latest_pct = round(latest_score / latest_max * 100, 1) if latest_max else 0
    scores = [_sectional_score(m)[0] for m in mocks]

    return MockAnalytics(
        latest_score=latest_score,
        highest_score=max(scores) if scores else 0,
        average_score=sum(scores) / len(scores) if scores else 0,
        average_accuracy=sum(m.accuracy for m in mocks) / len(mocks),
        latest_score_percentage=latest_pct,
        total_attempted=sum(m.attempted for m in mocks),
        total_correct=sum(m.correct for m in mocks),
        total_wrong=sum(m.wrong for m in mocks),
        total_negative=sum(m.negative_marks for m in mocks),
        total_mocks=len(mocks),
        score_progression=score_progression,
        accuracy_trend=accuracy_trend,
        section_comparison=section_comparison,
        subject_accuracy_trends=subject_accuracy_trends,
        weekly_trend=weekly_trend,
        weak_subjects=weak_subjects,
        strongest_subject=strongest,
        improvement_delta=improvement_delta,
        ai_insights=SectionalAIEngine().generate_insights(mocks, target_data),
        target_insights=[],
        subject_targets=subject_targets,
        target_analytics=None,
    )
