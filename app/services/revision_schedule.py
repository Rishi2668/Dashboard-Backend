"""Spaced revision cycle: study today → revise on day 3, then 7, then 15."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

REVISION_SCHEDULE: tuple[int, ...] = (3, 7, 15)
REVISION_FIRST_DAY = REVISION_SCHEDULE[0]


def first_revision_date(from_day: date | None = None) -> date:
    base = from_day or date.today()
    return base + timedelta(days=REVISION_FIRST_DAY)


def advance_revision_item(item, today: date | None = None) -> None:
    """Move item to the next step in 3→7→15, or mark fully completed."""
    today = today or date.today()
    step = item.interval_days

    if step in REVISION_SCHEDULE:
        idx = REVISION_SCHEDULE.index(step)
        if idx < len(REVISION_SCHEDULE) - 1:
            item.interval_days = REVISION_SCHEDULE[idx + 1]
            item.next_revision_date = today + timedelta(days=item.interval_days)
            return
        item.completed = True
        item.completed_at = datetime.now(timezone.utc)
        return

    # Legacy 1→7→30 items still in the database
    if step == 1:
        item.interval_days = 7
        item.next_revision_date = today + timedelta(days=7)
    elif step == 7:
        item.interval_days = 15
        item.next_revision_date = today + timedelta(days=15)
    else:
        item.completed = True
        item.completed_at = datetime.now(timezone.utc)


def revision_stage_label(interval_days: int) -> str:
    if interval_days in REVISION_SCHEDULE:
        return f"Day {interval_days}"
    return f"{interval_days}d"
