"""Persist correct test_type for all user mocks (fixes legacy mis-tagged rows)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_test import MockTest
from app.services.mock_classification import ensure_mock_classification


async def reclassify_user_mocks(db: AsyncSession, user_id: int) -> int:
    """Re-run classification and flush. Returns number of rows updated."""
    result = await db.execute(select(MockTest).where(MockTest.user_id == user_id))
    rows = list(result.scalars().all())
    changed = 0
    for mock in rows:
        before_type = mock.test_type
        before_subject = getattr(mock, "section_subject", None)
        ensure_mock_classification(mock)
        if mock.test_type != before_type or getattr(mock, "section_subject", None) != before_subject:
            changed += 1
    if changed:
        await db.flush()
    return changed
