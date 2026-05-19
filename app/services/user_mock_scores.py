"""Sync user-level mock score fields from full mocks only (never sectionals)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_test import MockTest
from app.models.user import User
from app.services.mock_classification import filter_mocks_by_type


async def refresh_user_mock_scores(db: AsyncSession, user: User) -> None:
    result = await db.execute(
        select(MockTest).where(MockTest.user_id == user.id).order_by(MockTest.test_date.desc())
    )
    full_mocks = filter_mocks_by_type(list(result.scalars().all()), "full")
    if full_mocks:
        user.best_score = max(m.total_score for m in full_mocks)
        user.current_mock_score = full_mocks[0].total_score
        user.overall_accuracy = full_mocks[0].accuracy
    else:
        user.best_score = 0
        user.current_mock_score = 0
        user.overall_accuracy = 0
