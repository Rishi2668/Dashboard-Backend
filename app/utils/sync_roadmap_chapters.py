import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.roadmap_2026 import EXTRA_CHAPTERS
from app.models.syllabus import SyllabusChapter, SyllabusSubject

logger = logging.getLogger(__name__)


async def sync_roadmap_chapters(db: AsyncSession) -> int:
    result = await db.execute(select(SyllabusSubject))
    subjects = {s.slug: s for s in result.scalars().all()}
    if not subjects:
        return 0

    added = 0
    for slug, name, priority in EXTRA_CHAPTERS:
        subject = subjects.get(slug)
        if not subject:
            continue
        existing = await db.execute(
            select(SyllabusChapter).where(
                SyllabusChapter.subject_id == subject.id,
                SyllabusChapter.name == name,
            )
        )
        if existing.scalar_one_or_none():
            continue
        max_result = await db.execute(
            select(func.coalesce(func.max(SyllabusChapter.sort_order), 0)).where(
                SyllabusChapter.subject_id == subject.id
            )
        )
        max_order = int(max_result.scalar() or 0)
        db.add(
            SyllabusChapter(
                subject_id=subject.id,
                name=name,
                priority=priority,
                sort_order=max_order + 1,
            )
        )
        added += 1

    if added:
        await db.flush()
        logger.info("Added %s roadmap 2026 syllabus chapters", added)
    return added
