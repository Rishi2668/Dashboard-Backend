from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.mock_test import MockTest
from app.models.streak import Streak
from app.schemas.mock_test import (
    MockAnalytics,
    MockTestCreate,
    MockTestResponse,
    SubjectSectionInput,
    SubjectSectionResponse,
)
from app.services.mock_ai_engine import MockAIEngine, SUBJECT_LABELS
from app.services.mock_analytics_service import build_mock_analytics
from app.services.mock_classification import (
    FULL_MOCK_MIN_MAX_SCORE,
    classify_from_sections,
    ensure_mock_classification,
    filter_mocks_by_type,
)
from app.services.mock_reclassify import reclassify_user_mocks
from app.services.user_mock_scores import refresh_user_mock_scores
from app.services.mock_calculations import section_accuracy, section_negative, section_wrong
from app.services.xp_breakdown import sync_user_xp
from app.services.target_score_service import TargetScoreService
from sqlalchemy.orm import selectinload
from app.models.user import User

router = APIRouter(prefix="/mock-tests", tags=["mock-tests"])

SUBJECT_KEYS = ("reasoning", "quant", "english", "gk")


def _finalize_section(sec: SubjectSectionInput) -> dict:
    wrong = section_wrong(sec.attempted, sec.correct, sec.wrong)
    acc = section_accuracy(sec.attempted, sec.correct)
    return {
        "max_marks": sec.max_marks,
        "secured_marks": sec.secured_marks,
        "total_questions": sec.total_questions,
        "attempted": sec.attempted,
        "correct": sec.correct,
        "wrong": wrong,
        "accuracy": acc,
    }


def _apply_section(mock: MockTest, prefix: str, data: dict) -> None:
    setattr(mock, f"{prefix}_score", data["secured_marks"])
    setattr(mock, f"{prefix}_max_marks", data["max_marks"])
    setattr(mock, f"{prefix}_total_questions", data["total_questions"])
    setattr(mock, f"{prefix}_attempted", data["attempted"])
    setattr(mock, f"{prefix}_correct", data["correct"])
    setattr(mock, f"{prefix}_wrong", data["wrong"])
    setattr(mock, f"{prefix}_accuracy", data["accuracy"])


def _section_response(mock: MockTest, key: str) -> SubjectSectionResponse:
    max_m = getattr(mock, f"{key}_max_marks")
    secured = getattr(mock, f"{key}_score")
    return SubjectSectionResponse(
        label=SUBJECT_LABELS[key],
        max_marks=max_m,
        secured_marks=secured,
        total_questions=getattr(mock, f"{key}_total_questions"),
        attempted=getattr(mock, f"{key}_attempted"),
        correct=getattr(mock, f"{key}_correct"),
        wrong=getattr(mock, f"{key}_wrong"),
        accuracy=getattr(mock, f"{key}_accuracy"),
        score_percentage=round(secured / max_m * 100, 1) if max_m else 0,
    )


def _mock_to_response(mock: MockTest) -> MockTestResponse:
    pct = round(mock.total_score / mock.max_score * 100, 1) if mock.max_score else 0
    return MockTestResponse(
        id=mock.id,
        test_name=mock.test_name,
        test_date=mock.test_date,
        test_type=mock.test_type or "full",
        total_score=mock.total_score,
        max_score=mock.max_score,
        total_questions=mock.total_questions,
        accuracy=mock.accuracy,
        attempted=mock.attempted,
        correct=mock.correct,
        wrong=mock.wrong,
        negative_marks=mock.negative_marks,
        score_percentage=pct,
        reasoning=_section_response(mock, "reasoning"),
        quant=_section_response(mock, "quant"),
        english=_section_response(mock, "english"),
        gk=_section_response(mock, "gk"),
        created_at=mock.created_at,
    )


@router.get("/", response_model=list[MockTestResponse])
async def list_mocks(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    test_type: str | None = None,
):
    result = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == current_user.id)
        .order_by(MockTest.test_date.desc())
        .limit(limit * 3 if test_type else limit)
    )
    rows = list(result.scalars().all())
    await reclassify_user_mocks(db, current_user.id)
    if test_type in ("full", "sectional"):
        rows = filter_mocks_by_type(rows, test_type)[:limit]
    return [_mock_to_response(m) for m in rows]


@router.post("/", response_model=MockTestResponse, status_code=201)
async def create_mock(
    data: MockTestCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await _create_mock_impl(data, current_user, db)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not save mock: {exc!s}") from exc


async def _create_mock_impl(
    data: MockTestCreate,
    current_user: CurrentUser,
    db: AsyncSession,
) -> MockTestResponse:
    sections = {
        "reasoning": _finalize_section(data.reasoning),
        "quant": _finalize_section(data.quant),
        "english": _finalize_section(data.english),
        "gk": _finalize_section(data.gk),
    }

    attempted = data.attempted or sum(s["attempted"] for s in sections.values())
    correct = data.correct or sum(s["correct"] for s in sections.values())
    wrong = data.wrong if data.wrong is not None else section_wrong(attempted, correct)
    accuracy = section_accuracy(attempted, correct)
    negative = (
        data.negative_marks
        if data.negative_marks is not None
        else section_negative(wrong)
    )
    total_score = data.total_score or sum(s["secured_marks"] for s in sections.values())
    max_score = data.max_score or sum(s["max_marks"] for s in sections.values())
    total_questions = data.total_questions or sum(s["total_questions"] for s in sections.values())

    resolved_type, section_key = classify_from_sections(sections)
    if resolved_type == "sectional":
        final_type = "sectional"
        final_section = section_key
    elif data.test_type == "sectional":
        final_type = "sectional"
        final_section = section_key or next(
            (
                k
                for k in SUBJECT_KEYS
                if sections[k]["attempted"] > 0 or sections[k]["secured_marks"] > 0
            ),
            None,
        )
    else:
        final_type = "full"
        final_section = None

    mock = MockTest(
        user_id=current_user.id,
        test_name=data.test_name or f"SSC CGL Mock — {data.test_date}",
        test_date=data.test_date,
        test_type=final_type,
        section_subject=final_section,
        total_score=total_score,
        max_score=max_score,
        total_questions=total_questions,
        attempted=attempted,
        correct=correct,
        wrong=wrong,
        accuracy=accuracy,
        negative_marks=negative,
    )
    for key in SUBJECT_KEYS:
        _apply_section(mock, key, sections[key])

    if data.test_type == "full" or max_score >= FULL_MOCK_MIN_MAX_SCORE:
        mock.test_type = "full"
        mock.section_subject = None
    else:
        ensure_mock_classification(mock)

    final_type = mock.test_type

    db.add(mock)

    is_full = final_type == "full"
    if is_full:
        if total_score > current_user.best_score:
            current_user.best_score = total_score
        current_user.current_mock_score = total_score
        current_user.overall_accuracy = accuracy

    if is_full:
        streak_result = await db.execute(
            select(Streak).where(Streak.user_id == current_user.id, Streak.streak_type == "mock")
        )
        streak = streak_result.scalar_one_or_none()
        if not streak:
            streak = Streak(user_id=current_user.id, streak_type="mock")
            db.add(streak)
        today = date.today()
        if streak.last_activity_date != today:
            if streak.last_activity_date == today - timedelta(days=1):
                streak.current_count += 1
            else:
                streak.current_count = 1
            streak.last_activity_date = today
            streak.longest_count = max(streak.longest_count, streak.current_count)

    await db.flush()
    await refresh_user_mock_scores(db, current_user)
    await sync_user_xp(db, current_user)
    await db.refresh(mock)
    return _mock_to_response(mock)


async def _target_analytics(
    db: AsyncSession, user_id: int, latest_full: MockTest | None = None
):
    user_result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.score_target))
    )
    user = user_result.scalar_one()
    return await TargetScoreService().build_analytics(db, user, latest_full=latest_full)


@router.get("/analytics", response_model=MockAnalytics)
async def get_analytics(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    test_type: str = Query("full", alias="test_type"),
    testType: str | None = Query(None, alias="testType"),
):
    resolved = (testType or test_type or "full").lower()
    if resolved not in ("full", "sectional"):
        resolved = "full"

    await reclassify_user_mocks(db, current_user.id)
    result = await db.execute(
        select(MockTest).where(MockTest.user_id == current_user.id).order_by(MockTest.test_date.asc())
    )
    mocks = list(result.scalars().all())
    full_mocks = filter_mocks_by_type(mocks, "full")

    target_data = None
    if resolved == "full" and full_mocks:
        target_data = await _target_analytics(db, current_user.id, latest_full=full_mocks[-1])
    elif resolved == "sectional":
        user_result = await db.execute(
            select(User).where(User.id == current_user.id).options(selectinload(User.score_target))
        )
        user = user_result.scalar_one()
        target_data = await TargetScoreService().build_analytics(db, user, latest_full=None)

    return build_mock_analytics(mocks, resolved, target_data)


@router.get("/ai-insights")
async def mock_ai_insights(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    test_type: str = Query("full", alias="test_type"),
    testType: str | None = Query(None, alias="testType"),
):
    resolved = (testType or test_type or "full").lower()
    if resolved not in ("full", "sectional"):
        resolved = "full"
    await reclassify_user_mocks(db, current_user.id)
    result = await db.execute(
        select(MockTest).where(MockTest.user_id == current_user.id).order_by(MockTest.test_date.asc())
    )
    all_mocks = list(result.scalars().all())
    mocks = filter_mocks_by_type(all_mocks, resolved)
    target_data = await _target_analytics(db, current_user.id)
    if resolved == "sectional":
        from app.services.sectional_ai_engine import SectionalAIEngine

        return SectionalAIEngine().generate_insights(mocks, target_data)
    insights = MockAIEngine().generate_insights(mocks)
    if target_data:
        return {
            "mock_insights": insights,
            "target_insights": [
                {"title": t.title, "message": t.message, "priority": t.priority, "category": t.category}
                for t in target_data.ai_insights
            ],
        }
    return {"mock_insights": insights, "target_insights": []}


@router.delete("/{mock_id}", status_code=204)
async def delete_mock(mock_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MockTest).where(MockTest.id == mock_id, MockTest.user_id == current_user.id)
    )
    mock = result.scalar_one_or_none()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock test not found")
    await db.delete(mock)
    await db.flush()
    await sync_user_xp(db, current_user)

    # Refresh user mock aggregates from remaining full mocks only (incl. heuristic)
    await refresh_user_mock_scores(db, current_user)
    await db.flush()
