import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.cache import cache
from app.core.database import get_db
from app.models.calc_practice import (
    CalcPendingQuestion,
    CalcPracticeSession,
    CalcQuestionAttempt,
    CalcWeakAreaStat,
)
from app.models.streak import Achievement, Streak
from app.schemas.calc_practice import (
    AnswerValidateRequest,
    AnswerValidateResponse,
    AttemptResponse,
    AttemptSubmit,
    CalcAIInsight,
    CalcAnalyticsResponse,
    GeneratedQuestionResponse,
    QuestionGenerateRequest,
    SessionCreate,
    SessionEndResponse,
    SessionResponse,
)
from app.services.calc_ai_engine import CalcAIEngine
from app.services.calc_question_generator import (
    PRACTICE_TYPES,
    CalcQuestionGenerator,
    validate_user_answer,
    _round_answer,
)
from app.utils.db_dates import created_since
from app.utils.sql_helpers import sum_correct

router = APIRouter(prefix="/calc-practice", tags=["calc-practice"])

MODE_DURATION = {"warmup": 300, "speed": 180, "accuracy": None, "endless": None}
MODE_DEFAULT_DIFFICULTY = {"warmup": "easy", "speed": "medium", "accuracy": "medium", "endless": "medium"}


def _session_response(session: CalcPracticeSession) -> SessionResponse:
    acc = 0.0
    avg_ms = 0.0
    if session.total_questions > 0:
        acc = round(session.correct_count / session.total_questions * 100, 1)
        avg_ms = round(session.total_time_ms / session.total_questions, 0)
    return SessionResponse(
        id=session.id,
        mode=session.mode,
        difficulty=session.difficulty,
        practice_types=session.practice_types,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_limit_sec=session.duration_limit_sec,
        total_questions=session.total_questions,
        correct_count=session.correct_count,
        skipped_count=session.skipped_count,
        total_time_ms=session.total_time_ms,
        fastest_time_ms=session.fastest_time_ms,
        xp_earned=session.xp_earned,
        completed=session.completed,
        accuracy_pct=acc,
        avg_time_ms=avg_ms,
    )


async def _update_calc_streak(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(Streak).where(Streak.user_id == user_id, Streak.streak_type == "calc")
    )
    streak = result.scalar_one_or_none()
    if not streak:
        streak = Streak(user_id=user_id, streak_type="calc")
        db.add(streak)
    today = date.today()
    if streak.last_activity_date == today:
        return _safe_int(streak.current_count, 1)
    if streak.last_activity_date == today - timedelta(days=1):
        streak.current_count = _safe_int(streak.current_count) + 1
    else:
        streak.current_count = 1
    streak.last_activity_date = today
    streak.longest_count = max(_safe_int(streak.longest_count), streak.current_count)
    await db.flush()
    return streak.current_count


def _safe_int(value: int | None, default: int = 0) -> int:
    return default if value is None else value


async def _upsert_weak_stat(
    db: AsyncSession,
    user_id: int,
    practice_type: str,
    is_correct: bool,
    time_ms: int,
) -> None:
    result = await db.execute(
        select(CalcWeakAreaStat).where(
            CalcWeakAreaStat.user_id == user_id,
            CalcWeakAreaStat.practice_type == practice_type,
        )
    )
    stat = result.scalar_one_or_none()
    if not stat:
        stat = CalcWeakAreaStat(
            user_id=user_id,
            practice_type=practice_type,
            total_attempts=0,
            correct_count=0,
            total_time_ms=0,
        )
        db.add(stat)
        await db.flush()
    stat.total_attempts = _safe_int(stat.total_attempts) + 1
    if is_correct:
        stat.correct_count = _safe_int(stat.correct_count) + 1
    stat.total_time_ms = _safe_int(stat.total_time_ms) + time_ms
    if is_correct and (
        stat.fastest_time_ms is None or time_ms < stat.fastest_time_ms
    ):
        stat.fastest_time_ms = time_ms
    stat.updated_at = datetime.now(timezone.utc)
    await db.flush()


def _resolve_practice_type(types_list: list[str], requested: str, rng) -> str:
    if requested and requested != "mixed":
        return requested
    pool = [t for t in types_list if t != "mixed"] if types_list else []
    if not pool or pool == ["mixed"]:
        pool = [t for t in PRACTICE_TYPES if t != "mixed"]
    return rng.choice(pool)


@router.get("/types")
async def list_practice_types():
    from app.services.calc_question_generator import DIFFICULTIES, PRACTICE_TYPES

    return {"practice_types": PRACTICE_TYPES, "difficulties": DIFFICULTIES, "modes": list(MODE_DURATION.keys())}


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    difficulty = data.difficulty
    if data.mode in MODE_DEFAULT_DIFFICULTY and difficulty == "medium":
        difficulty = MODE_DEFAULT_DIFFICULTY.get(data.mode, difficulty)
    if data.mode == "warmup":
        difficulty = "easy" if difficulty == "medium" else difficulty

    duration = data.duration_limit_sec or MODE_DURATION.get(data.mode)
    types = data.practice_types or ["mixed"]
    session = CalcPracticeSession(
        user_id=current_user.id,
        mode=data.mode,
        difficulty=difficulty,
        practice_types=json.dumps(types),
        duration_limit_sec=duration,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return _session_response(session)


@router.get("/sessions/active", response_model=SessionResponse | None)
async def get_active_session(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CalcPracticeSession)
        .where(
            CalcPracticeSession.user_id == current_user.id,
            CalcPracticeSession.completed == False,  # noqa: E712
        )
        .order_by(CalcPracticeSession.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    return _session_response(session) if session else None


@router.post("/questions/generate", response_model=GeneratedQuestionResponse)
async def generate_question(
    data: QuestionGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    difficulty = data.difficulty
    practice_type = data.practice_type

    gen = CalcQuestionGenerator()
    if data.session_id:
        result = await db.execute(
            select(CalcPracticeSession).where(
                CalcPracticeSession.id == data.session_id,
                CalcPracticeSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "Session not found")
        difficulty = session.difficulty
        types_list = json.loads(session.practice_types)
        if session.mode == "endless" and session.total_questions > 0:
            acc = session.correct_count / max(session.total_questions, 1)
            if acc >= 0.85 and difficulty != "hard":
                difficulty = "medium" if difficulty == "easy" else "hard"
            elif acc < 0.5 and difficulty != "easy":
                difficulty = "easy"
        practice_type = _resolve_practice_type(types_list, practice_type, gen._rng)

    q = gen.generate(
        practice_type=practice_type,
        difficulty=difficulty,
        exclude_fingerprints=set(data.exclude_fingerprints),
    )
    pending = CalcPendingQuestion(
        question_id=q.question_id,
        user_id=current_user.id,
        practice_type=q.practice_type,
        difficulty=q.difficulty,
        question_text=q.question_text,
        correct_answer=q.correct_answer,
        answer_tolerance=q.answer_tolerance,
        explanation=q.explanation,
        fingerprint=q.fingerprint,
    )
    db.add(pending)
    await db.flush()
    return GeneratedQuestionResponse(
        question_id=q.question_id,
        practice_type=q.practice_type,
        difficulty=q.difficulty,
        question_text=q.question_text,
        answer_tolerance=q.answer_tolerance,
        explanation="",
        fingerprint=q.fingerprint,
    )


@router.post("/questions/validate", response_model=AnswerValidateResponse)
async def validate_answer(data: AnswerValidateRequest):
    is_correct = validate_user_answer(data.correct_answer, data.user_answer, data.answer_tolerance)
    ans = _round_answer(data.correct_answer)
    display = str(int(ans)) if ans == int(ans) else f"{ans:.2f}".rstrip("0").rstrip(".")
    return AnswerValidateResponse(is_correct=is_correct, correct_answer=ans, display_answer=display)


@router.post("/attempts", response_model=AttemptResponse)
async def submit_attempt(
    data: AttemptSubmit,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalcPracticeSession).where(
            CalcPracticeSession.id == data.session_id,
            CalcPracticeSession.user_id == current_user.id,
            CalcPracticeSession.completed == False,  # noqa: E712
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Active session not found")

    pending_result = await db.execute(
        select(CalcPendingQuestion).where(
            CalcPendingQuestion.question_id == data.question_id,
            CalcPendingQuestion.user_id == current_user.id,
        )
    )
    pending = pending_result.scalar_one_or_none()
    if not pending:
        raise HTTPException(400, "Question expired — generate a new one")

    correct_answer = pending.correct_answer
    explanation = pending.explanation or data.explanation

    is_correct = False
    if not data.skipped and data.user_answer is not None:
        is_correct = validate_user_answer(
            correct_answer, data.user_answer, pending.answer_tolerance
        )

    attempt = CalcQuestionAttempt(
        session_id=session.id,
        user_id=current_user.id,
        practice_type=pending.practice_type,
        difficulty=pending.difficulty,
        question_text=pending.question_text,
        correct_answer=correct_answer,
        user_answer=data.user_answer,
        is_correct=is_correct,
        skipped=data.skipped,
        time_ms=data.time_ms,
        fingerprint=pending.fingerprint,
        explanation=explanation,
    )
    db.add(attempt)
    await db.delete(pending)

    session.total_questions = _safe_int(session.total_questions) + 1
    if data.skipped:
        session.skipped_count = _safe_int(session.skipped_count) + 1
    elif is_correct:
        session.correct_count = _safe_int(session.correct_count) + 1
    session.total_time_ms = _safe_int(session.total_time_ms) + data.time_ms
    if is_correct and data.time_ms > 0:
        if session.fastest_time_ms is None or data.time_ms < session.fastest_time_ms:
            session.fastest_time_ms = data.time_ms

    xp = 0
    if is_correct:
        xp = 5 + max(0, 10 - data.time_ms // 3000)
    elif not data.skipped:
        xp = 1
    session.xp_earned = _safe_int(session.xp_earned) + xp
    current_user.xp = _safe_int(current_user.xp) + xp

    await _upsert_weak_stat(db, current_user.id, pending.practice_type, is_correct, data.time_ms)
    streak_count = await _update_calc_streak(db, current_user.id)
    streak_bonus = streak_count >= 3 and is_correct

    if streak_bonus:
        bonus = 5
        session.xp_earned = _safe_int(session.xp_earned) + bonus
        current_user.xp = _safe_int(current_user.xp) + bonus
        xp += bonus

    await db.flush()

    ans = _round_answer(correct_answer)
    display = str(int(ans)) if ans == int(ans) else f"{ans:.2f}".rstrip("0").rstrip(".")

    if data.skipped:
        explanation = f"Skipped. Correct answer: {display}. {explanation}".strip()
    elif not is_correct:
        explanation = f"Correct answer: {display}. {explanation}".strip()

    return AttemptResponse(
        id=attempt.id,
        is_correct=is_correct,
        xp_gained=xp,
        streak_bonus=streak_bonus,
        explanation=explanation,
        correct_answer=ans,
        display_answer=display,
        session=_session_response(session),
    )


@router.post("/sessions/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CalcPracticeSession).where(
            CalcPracticeSession.id == session_id,
            CalcPracticeSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.completed:
        return SessionEndResponse(
            session=_session_response(session),
            xp_earned=session.xp_earned,
            badges_earned=[],
            message="Session already completed",
        )

    session.completed = True
    session.ended_at = datetime.now(timezone.utc)

    badges: list[str] = []
    acc = session.correct_count / session.total_questions * 100 if session.total_questions else 0

    if session.mode == "warmup" and session.total_questions >= 5:
        bonus = 25
        session.xp_earned = _safe_int(session.xp_earned) + bonus
        current_user.xp = _safe_int(current_user.xp) + bonus
        badges.append("warmup_warrior")

    if acc >= 90 and session.total_questions >= 10:
        badges.append("accuracy_master")
        current_user.xp = _safe_int(current_user.xp) + 30
        session.xp_earned = _safe_int(session.xp_earned) + 30

    if session.fastest_time_ms and session.fastest_time_ms < 3000 and session.correct_count >= 5:
        badges.append("speed_demon")
        current_user.xp = _safe_int(current_user.xp) + 20
        session.xp_earned = _safe_int(session.xp_earned) + 20

    for badge_id in badges:
        existing = await db.execute(
            select(Achievement).where(
                Achievement.user_id == current_user.id,
                Achievement.badge_id == badge_id,
            )
        )
        if not existing.scalar_one_or_none():
            titles = {
                "warmup_warrior": ("Warm-Up Warrior", "Completed daily calculation warm-up"),
                "accuracy_master": ("Accuracy Master", "90%+ accuracy in a practice session"),
                "speed_demon": ("Speed Demon", "Solved a question in under 3 seconds"),
            }
            title, desc = titles.get(badge_id, (badge_id, ""))
            db.add(
                Achievement(
                    user_id=current_user.id,
                    badge_id=badge_id,
                    title=title,
                    description=desc,
                )
            )

    await db.flush()
    await db.refresh(session)

    msg = f"Session complete! {session.correct_count}/{session.total_questions} correct ({acc:.0f}%)"
    return SessionEndResponse(
        session=_session_response(session),
        xp_earned=session.xp_earned,
        badges_earned=badges,
        message=msg,
    )


@router.get("/analytics", response_model=CalcAnalyticsResponse)
async def get_analytics(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    cache_key = f"calc:analytics:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached
    total_q = await db.execute(
        select(func.count(CalcQuestionAttempt.id)).where(
            CalcQuestionAttempt.user_id == current_user.id
        )
    )
    total_correct = await db.execute(
        select(func.count(CalcQuestionAttempt.id)).where(
            CalcQuestionAttempt.user_id == current_user.id,
            CalcQuestionAttempt.is_correct == True,  # noqa: E712
        )
    )
    avg_time = await db.execute(
        select(func.avg(CalcQuestionAttempt.time_ms)).where(
            CalcQuestionAttempt.user_id == current_user.id,
            CalcQuestionAttempt.is_correct == True,  # noqa: E712
        )
    )
    fastest = await db.execute(
        select(func.min(CalcQuestionAttempt.time_ms)).where(
            CalcQuestionAttempt.user_id == current_user.id,
            CalcQuestionAttempt.is_correct == True,  # noqa: E712
        )
    )
    sessions_count = await db.execute(
        select(func.count(CalcPracticeSession.id)).where(
            CalcPracticeSession.user_id == current_user.id,
            CalcPracticeSession.completed == True,  # noqa: E712
        )
    )
    xp_sum = await db.execute(
        select(func.sum(CalcPracticeSession.xp_earned)).where(
            CalcPracticeSession.user_id == current_user.id
        )
    )

    streak_result = await db.execute(
        select(Streak).where(
            Streak.user_id == current_user.id, Streak.streak_type == "calc"
        )
    )
    streak = streak_result.scalar_one_or_none()
    calc_streak = _safe_int(streak.current_count) if streak else 0

    by_type_result = await db.execute(
        select(
            CalcQuestionAttempt.practice_type,
            func.count(CalcQuestionAttempt.id),
            sum_correct(CalcQuestionAttempt.is_correct).label("correct"),
            func.avg(CalcQuestionAttempt.time_ms),
        )
        .where(CalcQuestionAttempt.user_id == current_user.id)
        .group_by(CalcQuestionAttempt.practice_type)
    )
    by_type = []
    for row in by_type_result.all():
        t, cnt, cor, avt = row
        cnt = cnt or 0
        cor = int(cor or 0)
        by_type.append(
            {
                "practice_type": t,
                "label": t.replace("_", " ").title(),
                "total": cnt,
                "correct": cor,
                "accuracy_pct": round(cor / cnt * 100, 1) if cnt else 0,
                "avg_time_ms": round(float(avt or 0), 0),
            }
        )

    weak_result = await db.execute(
        select(CalcWeakAreaStat).where(CalcWeakAreaStat.user_id == current_user.id)
    )
    weak_areas = []
    for s in weak_result.scalars().all():
        attempts = _safe_int(s.total_attempts)
        correct = _safe_int(s.correct_count)
        total_ms = _safe_int(s.total_time_ms)
        acc = round(correct / attempts * 100, 1) if attempts else 0
        weak_areas.append(
            {
                "practice_type": s.practice_type,
                "label": s.practice_type.replace("_", " ").title(),
                "accuracy_pct": acc,
                "total_attempts": attempts,
                "avg_time_ms": round(total_ms / attempts, 0) if attempts else 0,
            }
        )
    weak_areas.sort(key=lambda x: x["accuracy_pct"])

    daily = []
    start_day = date.today() - timedelta(days=6)
    daily_result = await db.execute(
        select(
            func.date(CalcQuestionAttempt.created_at).label("d"),
            func.count(CalcQuestionAttempt.id).label("cnt"),
            sum_correct(CalcQuestionAttempt.is_correct).label("cor"),
        )
        .where(
            CalcQuestionAttempt.user_id == current_user.id,
            created_since(CalcQuestionAttempt.created_at, start_day),
        )
        .group_by(func.date(CalcQuestionAttempt.created_at))
    )
    daily_map = {
        str(row.d): (int(row.cnt or 0), int(row.cor or 0))
        for row in daily_result.all()
    }
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        cnt, cor = daily_map.get(d.isoformat(), (0, 0))
        daily.append({"date": d.isoformat(), "questions": cnt, "accuracy_pct": round(cor / cnt * 100, 1) if cnt else 0})

    tq = total_q.scalar() or 0
    tc = total_correct.scalar() or 0
    avg_ms = avg_time.scalar()
    fastest_ms = fastest.scalar()
    badges = []
    if tc >= 100:
        badges.append({"id": "century", "title": "Century", "earned": True})
    if calc_streak >= 7:
        badges.append({"id": "week_streak", "title": "7-Day Calc Streak", "earned": True})

    payload = CalcAnalyticsResponse(
        total_questions=tq,
        total_correct=tc,
        accuracy_pct=round(tc / tq * 100, 1) if tq else 0,
        avg_time_ms=round(float(avg_ms or 0), 0),
        fastest_time_ms=int(fastest_ms) if fastest_ms is not None else None,
        calc_streak=calc_streak,
        total_sessions=sessions_count.scalar() or 0,
        total_xp_from_calc=int(xp_sum.scalar() or 0),
        by_type=by_type,
        weak_areas=weak_areas,
        daily_last_7=daily,
        badges=badges,
    )
    await cache.set(cache_key, payload, ttl_sec=20)
    return payload


@router.get("/ai-insights", response_model=list[CalcAIInsight])
async def ai_insights(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    cache_key = f"calc:ai:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached
    engine = CalcAIEngine()
    insights = await engine.generate_insights(db, current_user)
    await cache.set(cache_key, insights, ttl_sec=60)
    return insights
