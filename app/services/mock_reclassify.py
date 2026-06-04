"""Persist correct test_type for all user mocks (fixes legacy mis-tagged rows)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_test import MockTest
from app.services.mock_classification import ensure_mock_classification, primary_subject


def _sectional_score_key(mock: MockTest) -> str | None:
    key = getattr(mock, "section_subject", None) or primary_subject(mock)
    return key if key else None


async def reclassify_user_mocks(db: AsyncSession, user_id: int) -> int:
    """Re-run classification and flush. Returns number of rows updated."""
    result = await db.execute(select(MockTest).where(MockTest.user_id == user_id))
    rows = list(result.scalars().all())
    changed = 0
    for mock in rows:
        before_type = mock.test_type
        before_subject = getattr(mock, "section_subject", None)
        sk = _sectional_score_key(mock)
        before_score = getattr(mock, f"{sk}_score", None) if sk else None
        ensure_mock_classification(mock)
        after_subject = getattr(mock, "section_subject", None)
        sk2 = _sectional_score_key(mock)
        after_score = getattr(mock, f"{sk2}_score", None) if sk2 else None
        if (
            mock.test_type != before_type
            or after_subject != before_subject
            or before_score != after_score
        ):
            changed += 1
    if changed:
        await db.flush()
    return changed
