import random

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.cache import cache
from app.models.quote import Quote
from app.schemas.dashboard import QuoteResponse
from fastapi import Depends

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("/random", response_model=QuoteResponse)
async def random_quote(db: AsyncSession = Depends(get_db), category: str | None = None):
    key = f"quotes:random:{category or 'all'}"

    async def _producer():
        q = select(Quote)
        if category:
            q = q.where(Quote.category == category)
        result = await db.execute(q)
        quotes = list(result.scalars().all())
        if not quotes:
            return QuoteResponse(
                id=0,
                text="Success is the sum of small efforts repeated day in and day out.",
                author="Robert Collier",
                category="consistency",
            )
        return random.choice(quotes)

    return await cache.get_or_set(key, 600, _producer)


@router.get("/", response_model=list[QuoteResponse])
async def list_quotes(db: AsyncSession = Depends(get_db), category: str | None = None):
    key = f"quotes:list:{category or 'all'}"

    async def _producer():
        q = select(Quote)
        if category:
            q = q.where(Quote.category == category)
        result = await db.execute(q)
        return result.scalars().all()

    return await cache.get_or_set(key, 600, _producer)
