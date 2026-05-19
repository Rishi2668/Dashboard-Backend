from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
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
async def list_mocks(current_user: CurrentUser, db: AsyncSession = Depends(get_db), limit: int = 50):
    result = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == current_user.id)
        .order_by(MockTest.test_date.desc())
        .limit(limit)
    )
    return [_mock_to_response(m) for m in result.scalars().all()]


@router.post("/", response_model=MockTestResponse, status_code=201)
async def create_mock(
    data: MockTestCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
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

    mock = MockTest(
        user_id=current_user.id,
        test_name=data.test_name or f"SSC CGL Mock — {data.test_date}",
        test_date=data.test_date,
        test_type=data.test_type,
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

    db.add(mock)

    if total_score > current_user.best_score:
        current_user.best_score = total_score
    current_user.current_mock_score = total_score
    current_user.overall_accuracy = accuracy

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
    await sync_user_xp(db, current_user)
    await db.refresh(mock)
    return _mock_to_response(mock)


async def _target_analytics(db: AsyncSession, user_id: int):
    user_result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.score_target))
    )
    user = user_result.scalar_one()
    return await TargetScoreService().build_analytics(db, user)


@router.get("/analytics", response_model=MockAnalytics)
async def get_analytics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    target_data = await _target_analytics(db, current_user.id)
    result = await db.execute(
        select(MockTest).where(MockTest.user_id == current_user.id).order_by(MockTest.test_date.asc())
    )
    mocks = list(result.scalars().all())
    empty = MockAnalytics(
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
        ai_insights=MockAIEngine.merge_target_insights(
            MockAIEngine().generate_insights([]), target_data
        ),
        target_analytics=target_data,
    )
    if not mocks:
        return empty

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
    labels = {
        "reasoning": "Reasoning",
        "quant": "Quant",
        "english": "English",
        "gk": "GK",
    }
    for key in SUBJECT_KEYS:
        section_comparison.append(
            {
                "subject": labels[key],
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

    accs = [(labels[k], getattr(latest, f"{k}_accuracy")) for k in SUBJECT_KEYS]
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
        ai_insights=MockAIEngine.merge_target_insights(
            MockAIEngine().generate_insights(mocks), target_data
        ),
        target_analytics=target_data,
    )


@router.get("/ai-insights")
async def mock_ai_insights(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == current_user.id)
        .order_by(MockTest.test_date.asc())
    )
    mocks = list(result.scalars().all())
    target_data = await _target_analytics(db, current_user.id)
    return MockAIEngine.merge_target_insights(
        MockAIEngine().generate_insights(mocks), target_data
    )


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

    # Refresh user mock aggregates from remaining tests
    remaining = await db.execute(
        select(MockTest)
        .where(MockTest.user_id == current_user.id)
        .order_by(MockTest.test_date.desc())
        .limit(1)
    )
    last = remaining.scalar_one_or_none()
    all_scores = await db.execute(
        select(MockTest.total_score).where(MockTest.user_id == current_user.id)
    )
    scores = [row[0] for row in all_scores.all()]
    if scores:
        current_user.best_score = max(scores)
        current_user.current_mock_score = last.total_score if last else scores[0]
        current_user.overall_accuracy = last.accuracy if last else 0
    else:
        current_user.current_mock_score = 0
        current_user.best_score = 0
        current_user.overall_accuracy = 0
    await db.flush()
