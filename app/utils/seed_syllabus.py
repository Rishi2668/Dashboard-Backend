from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.syllabus import SyllabusChapter, SyllabusSubject
from app.utils.syllabus_seed import SYLLABUS_DATA


async def seed_syllabus(db: AsyncSession) -> None:
    result = await db.execute(select(SyllabusSubject).limit(1))
    if result.scalar_one_or_none():
        return

    for subj_data in SYLLABUS_DATA:
        subject = SyllabusSubject(
            slug=subj_data["slug"],
            name=subj_data["name"],
            short_name=subj_data["short_name"],
            color=subj_data["color"],
            sort_order=subj_data["sort_order"],
        )
        db.add(subject)
        await db.flush()

        for name, priority, sort_order in subj_data["chapters"]:
            db.add(
                SyllabusChapter(
                    subject_id=subject.id,
                    name=name,
                    priority=priority,
                    sort_order=sort_order,
                )
            )
