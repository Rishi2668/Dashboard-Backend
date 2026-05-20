"""Revision status, analytics, and AI-style recommendations."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revision import RevisionItem
from app.models.revision_history import RevisionHistory
from app.models.streak import Streak

STATUSES = ("pending", "upcoming", "completed", "overdue")


def revision_status(item: RevisionItem, today: date | None = None) -> str:
    today = today or date.today()
    if item.completed:
        return "completed"
    due = item.next_revision_date
    if due < today:
        return "overdue"
    if due == today:
        return "pending"
    return "upcoming"


def days_overdue(item: RevisionItem, today: date | None = None) -> int:
    today = today or date.today()
    if item.completed or item.next_revision_date >= today:
        return 0
    return (today - item.next_revision_date).days


def suggested_next_date(item: RevisionItem, today: date | None = None) -> date | None:
    if item.completed:
        return None
    return item.next_revision_date


def item_to_dict(item: RevisionItem, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    status = revision_status(item, today)
    return {
        "id": item.id,
        "topic": item.topic,
        "subject": item.subject,
        "interval_days": item.interval_days,
        "next_revision_date": item.next_revision_date,
        "last_revised": item.last_revised,
        "completed": item.completed,
        "revision_count": item.revision_count,
        "notes": item.notes,
        "priority": item.priority,
        "difficulty": item.difficulty,
        "completed_at": item.completed_at,
        "created_at": item.created_at,
        "status": status,
        "days_overdue": days_overdue(item, today),
        "suggested_next_date": suggested_next_date(item, today),
    }


async def fetch_user_items(db: AsyncSession, user_id: int) -> list[RevisionItem]:
    result = await db.execute(
        select(RevisionItem)
        .where(RevisionItem.user_id == user_id)
        .order_by(RevisionItem.next_revision_date.asc())
    )
    return list(result.scalars().all())


def filter_items(
    items: list[RevisionItem],
    *,
    status: str | None = None,
    subject: str | None = None,
    priority: str | None = None,
    difficulty: str | None = None,
    search: str | None = None,
    today: date | None = None,
) -> list[RevisionItem]:
    today = today or date.today()
    out = items
    if subject:
        out = [i for i in out if i.subject.lower() == subject.lower()]
    if priority:
        out = [i for i in out if (i.priority or "medium").lower() == priority.lower()]
    if difficulty:
        out = [i for i in out if (i.difficulty or "medium").lower() == difficulty.lower()]
    if search:
        q = search.lower().strip()
        out = [
            i
            for i in out
            if q in i.topic.lower() or q in i.subject.lower() or (i.notes and q in i.notes.lower())
        ]
    if status and status in STATUSES:
        out = [i for i in out if revision_status(i, today) == status]
    return out


async def build_dashboard_summary(db: AsyncSession, user_id: int) -> dict[str, Any]:
    items = await fetch_user_items(db, user_id)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=6)

    pending = [i for i in items if revision_status(i, today) == "pending"]
    overdue = [i for i in items if revision_status(i, today) == "overdue"]
    upcoming = [i for i in items if revision_status(i, today) == "upcoming"]
    completed = [i for i in items if i.completed]

    today_items = pending + overdue
    tomorrow_items = [i for i in upcoming if i.next_revision_date == tomorrow]
    week_items = [
        i
        for i in items
        if not i.completed and today <= i.next_revision_date <= week_end
    ]

    active = [i for i in items if not i.completed]
    completion_pct = round((len(completed) / len(items)) * 100, 1) if items else 0.0

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id, Streak.streak_type == "revision")
    )
    streak = streak_result.scalar_one_or_none()
    revision_streak = streak.current_count if streak else 0

    return {
        "today_count": len(today_items),
        "tomorrow_count": len(tomorrow_items),
        "week_count": len(week_items),
        "pending_count": len(pending),
        "upcoming_count": len(upcoming),
        "overdue_count": len(overdue),
        "completed_count": len(completed),
        "total_count": len(items),
        "completion_percentage": completion_pct,
        "revision_streak": revision_streak,
        "today_items": [item_to_dict(i, today) for i in today_items[:8]],
        "tomorrow_items": [item_to_dict(i, today) for i in tomorrow_items[:8]],
        "overdue_items": [item_to_dict(i, today) for i in overdue[:8]],
    }


async def build_analytics(db: AsyncSession, user_id: int) -> dict[str, Any]:
    items = await fetch_user_items(db, user_id)
    today = date.today()
    month_start = today - timedelta(days=29)

    total = len(items)
    completed = sum(1 for i in items if i.completed)
    overdue = sum(1 for i in items if revision_status(i, today) == "overdue")
    pending = sum(1 for i in items if revision_status(i, today) == "pending")
    upcoming = sum(1 for i in items if revision_status(i, today) == "upcoming")
    active = total - completed

    hist_result = await db.execute(
        select(RevisionHistory.completed_on, func.count(RevisionHistory.id))
        .where(
            RevisionHistory.user_id == user_id,
            RevisionHistory.completed_on >= month_start,
        )
        .group_by(RevisionHistory.completed_on)
    )
    active_days = len(hist_result.all())
    consistency = round((active_days / 30) * 100, 1)

    subject_counts: dict[str, int] = {}
    for i in items:
        if i.revision_count > 0 or i.completed:
            subject_counts[i.subject] = subject_counts.get(i.subject, 0) + i.revision_count

    subject_frequency = [
        {"subject": s, "count": c} for s, c in sorted(subject_counts.items(), key=lambda x: -x[1])
    ]

    overdue_pct = round((overdue / active) * 100, 1) if active else 0.0
    completion_pct = round((completed / total) * 100, 1) if total else 0.0

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id, Streak.streak_type == "revision")
    )
    streak = streak_result.scalar_one_or_none()

    return {
        "total_revisions": total,
        "total_completed": completed,
        "pending_count": pending,
        "upcoming_count": upcoming,
        "overdue_count": overdue,
        "completion_percentage": completion_pct,
        "overdue_percentage": overdue_pct,
        "consistency_percentage": consistency,
        "revision_streak": streak.current_count if streak else 0,
        "longest_revision_streak": streak.longest_count if streak else 0,
        "subject_frequency": subject_frequency,
        "total_revision_cycles": sum(i.revision_count for i in items),
    }


def build_ai_recommendations(items: list[RevisionItem], today: date | None = None) -> list[dict[str, str]]:
    today = today or date.today()
    recs: list[dict[str, str]] = []

    for item in items:
        if revision_status(item, today) == "overdue":
            days = days_overdue(item, today)
            recs.append(
                {
                    "title": f"{item.topic} is overdue",
                    "message": f"{item.subject} · {days} day(s) overdue — revise today to stay on track.",
                    "priority": "high",
                    "category": "overdue",
                }
            )

    for item in items:
        if item.completed:
            continue
        if item.last_revised and (today - item.last_revised).days >= 7:
            recs.append(
                {
                    "title": f"Haven't revised {item.topic} recently",
                    "message": f"You haven't revised {item.topic} in {(today - item.last_revised).days} days.",
                    "priority": "medium",
                    "category": "retention",
                }
            )
        elif not item.last_revised and item.revision_count == 0 and item.next_revision_date <= today:
            recs.append(
                {
                    "title": f"First revision due: {item.topic}",
                    "message": f"{item.subject} · scheduled for {item.next_revision_date}.",
                    "priority": "medium",
                    "category": "due",
                }
            )

    subject_done: dict[str, int] = {}
    for item in items:
        if item.last_revised and (today - item.last_revised).days <= 7:
            subject_done[item.subject] = subject_done.get(item.subject, 0) + 1

    for subject, count in subject_done.items():
        if count >= 2:
            recs.append(
                {
                    "title": f"Strong consistency in {subject}",
                    "message": f"You are consistent in {subject} revisions ({count} topics this week).",
                    "priority": "low",
                    "category": "consistency",
                }
            )

    return recs[:12]
