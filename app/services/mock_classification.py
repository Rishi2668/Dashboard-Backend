"""Classify full mocks vs sectionals (including legacy mis-tagged rows)."""

from __future__ import annotations

from app.models.mock_test import MockTest

SUBJECT_KEYS = ("reasoning", "quant", "english", "gk")
FULL_MOCK_MIN_MAX_SCORE = 100  # SSC CGL full mocks are 200 marks; sectionals are 50 per subject


def _subject_attempted(mock: MockTest, key: str) -> int:
    return int(getattr(mock, f"{key}_attempted", 0) or 0)


def _subject_score(mock: MockTest, key: str) -> float:
    return float(getattr(mock, f"{key}_score", 0) or 0)


def active_subjects(mock: MockTest) -> list[str]:
    """Subjects with attempts or secured marks in that section."""
    active: list[str] = []
    for k in SUBJECT_KEYS:
        if _subject_attempted(mock, k) > 0 or _subject_score(mock, k) > 0:
            active.append(k)
    return active


def is_sectional_mock(mock: MockTest) -> bool:
    """Single-subject / 50-mark tests — never treated as full mocks."""
    max_score = float(mock.max_score or 0)
    # Full SSC mocks are ~200 marks — never treat as sectional regardless of section fill
    if max_score >= FULL_MOCK_MIN_MAX_SCORE:
        return False

    if (mock.test_type or "full") == "sectional":
        return True
    section = getattr(mock, "section_subject", None)
    if section and section in SUBJECT_KEYS:
        return True

    # 50-mark entries are sectionals
    if 0 < max_score <= 50:
        return True

    active = active_subjects(mock)
    if len(active) == 1:
        only = active[0]
        others_empty = all(
            _subject_attempted(mock, k) == 0 and _subject_score(mock, k) == 0
            for k in SUBJECT_KEYS
            if k != only
        )
        if others_empty:
            return True

    return False


def is_full_mock(mock: MockTest) -> bool:
    if is_sectional_mock(mock):
        return False
    max_score = float(mock.max_score or 0)
    return max_score >= FULL_MOCK_MIN_MAX_SCORE


def primary_subject(mock: MockTest) -> str | None:
    section = getattr(mock, "section_subject", None)
    if section and section in SUBJECT_KEYS:
        return section
    active = active_subjects(mock)
    return active[0] if len(active) == 1 else None


_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "reasoning": ("reasoning", "gi ", "intelligence", "logical"),
    "quant": ("quant", "quantitative", "math", "arithmetic", "numer"),
    "english": ("english", "comprehension", "grammar"),
    "gk": ("gk", "general awareness", "awareness", "gs ", "polity", "history"),
}


def infer_section_subject(mock: MockTest) -> str | None:
    """Resolve subject for sectionals (legacy rows may only have total_score)."""
    section = getattr(mock, "section_subject", None)
    if section in SUBJECT_KEYS:
        return section

    key = primary_subject(mock)
    if key:
        return key

    total = float(mock.total_score or 0)
    if total <= 0:
        return None

    for k in SUBJECT_KEYS:
        sc = _subject_score(mock, k)
        if sc > 0 and abs(sc - total) < 0.02:
            return k

    nonzero = [k for k in SUBJECT_KEYS if _subject_score(mock, k) > 0]
    if len(nonzero) == 1:
        return nonzero[0]

    name = (mock.test_name or "").lower()
    for k, hints in _NAME_HINTS.items():
        if any(h in name for h in hints):
            return k

    if float(mock.max_score or 0) <= 50 or (mock.test_type or "") == "sectional":
        for k in SUBJECT_KEYS:
            if _subject_attempted(mock, k) > 0:
                return k
        # Last resort: only one subject column has max_marks set for a 50-mark paper
        with_max = [k for k in SUBJECT_KEYS if float(getattr(mock, f"{k}_max_marks", 0) or 0) >= 40]
        if len(with_max) == 1:
            return with_max[0]

    return None


def classify_from_sections(sections: dict[str, dict]) -> tuple[str, str | None]:
    """Return (test_type, section_subject) from finalized section dicts."""
    active = [
        k
        for k in SUBJECT_KEYS
        if sections[k].get("attempted", 0) > 0 or sections[k].get("secured_marks", 0) > 0
    ]
    if len(active) == 1:
        return "sectional", active[0]
    if len(active) >= 2:
        return "full", None
    return "full", None


def _sync_sectional_totals(mock: MockTest) -> None:
    """Keep per-subject columns aligned with row totals for single-subject sectionals."""
    key = infer_section_subject(mock)
    if not key or key not in SUBJECT_KEYS:
        return
    total = float(mock.total_score or 0)
    max_m = float(mock.max_score or 0)
    if total <= 0 and max_m <= 0:
        return
    setattr(mock, f"{key}_score", total)
    if max_m > 0:
        setattr(mock, f"{key}_max_marks", max_m)
    if mock.accuracy is not None:
        setattr(mock, f"{key}_accuracy", float(mock.accuracy))


def ensure_mock_classification(mock: MockTest) -> None:
    """Persist correct test_type / section_subject on the model before save."""
    if float(mock.max_score or 0) >= FULL_MOCK_MIN_MAX_SCORE:
        mock.test_type = "full"
        mock.section_subject = None
        return
    if is_sectional_mock(mock):
        mock.test_type = "sectional"
        inferred = infer_section_subject(mock)
        if inferred:
            mock.section_subject = inferred
        _sync_sectional_totals(mock)
    else:
        mock.test_type = "full"
        mock.section_subject = None


def filter_mocks_by_type(mocks: list[MockTest], test_type: str) -> list[MockTest]:
    if test_type == "sectional":
        return [m for m in mocks if is_sectional_mock(m)]
    return [m for m in mocks if is_full_mock(m)]
