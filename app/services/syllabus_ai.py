from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.syllabus import SyllabusChapter, SyllabusSubject, UserChapterProgress
from app.models.user import User
from app.utils.syllabus_seed import PRIORITY_LABELS, PRIORITY_ORDER


class SyllabusAIEngine:
    async def generate_insights(
        self, db: AsyncSession, user: User, subjects_data: list[dict]
    ) -> list[dict[str, Any]]:
        insights: list[dict[str, Any]] = []
        weak_chapters: list[dict] = []
        incomplete_vh: list[dict] = []
        needs_revision: list[dict] = []

        for subject in subjects_data:
            for ch in subject.get("chapters", []):
                if ch.get("is_weak") or (ch.get("accuracy", 0) > 0 and ch["accuracy"] < 55):
                    weak_chapters.append({**ch, "subject_name": subject["name"]})
                if ch.get("priority") == "very_high" and not ch.get("completed") and ch.get("progress_percentage", 0) < 50:
                    incomplete_vh.append({**ch, "subject_name": subject["name"]})
                if ch.get("revision_status") in ("due", "overdue"):
                    needs_revision.append({**ch, "subject_name": subject["name"]})

        if incomplete_vh:
            top = incomplete_vh[0]
            insights.append({
                "type": "chapter_recommendation",
                "priority": "high",
                "title": "Focus on Very High Priority",
                "message": f"Complete '{top['name']}' in {top['subject_name']} first — it's critical for Tier-1.",
                "chapter_id": top["id"],
            })

        for w in weak_chapters[:3]:
            insights.append({
                "type": "weak_area",
                "priority": "high",
                "title": f"Weak: {w['name']}",
                "message": f"{w['subject_name']} — {w['accuracy']:.0f}% accuracy. Revise before moving to lower-priority topics.",
                "chapter_id": w["id"],
            })

        if needs_revision:
            r = needs_revision[0]
            insights.append({
                "type": "revision_reminder",
                "priority": "medium",
                "title": "Revision due",
                "message": f"'{r['name']}' needs revision. Spaced repetition keeps retention high.",
                "chapter_id": r["id"],
            })

        total = sum(s.get("total_chapters", 0) for s in subjects_data)
        done = sum(s.get("completed_chapters", 0) for s in subjects_data)
        if total > 0:
            pct = done / total * 100
            if pct < 30:
                insights.append({
                    "type": "study_insight",
                    "priority": "medium",
                    "title": "Roadmap progress",
                    "message": f"Only {pct:.0f}% of syllabus complete. Prioritize Very High chapters in Quant & Reasoning this week.",
                    "chapter_id": None,
                })
            elif pct >= 70:
                insights.append({
                    "type": "motivation",
                    "priority": "low",
                    "title": "Strong progress!",
                    "message": f"{pct:.0f}% syllabus covered. Shift focus to weak areas and full mocks.",
                    "chapter_id": None,
                })

        if user.target_marks and user.current_mock_score < user.target_marks * 0.6:
            insights.append({
                "type": "target_gap",
                "priority": "high",
                "title": "Target marks gap",
                "message": f"Current mock ({user.current_mock_score:.0f}) is below 60% of your target ({user.target_marks:.0f}). Drill high-priority Quant chapters.",
                "chapter_id": None,
            })

        return insights[:8]

    async def suggest_next_chapters(self, db: AsyncSession, user_id: int, limit: int = 5) -> list[dict]:
        result = await db.execute(
            select(SyllabusChapter)
            .options(selectinload(SyllabusChapter.subject))
            .join(SyllabusSubject)
            .order_by(SyllabusSubject.sort_order, SyllabusChapter.sort_order)
        )
        chapters = result.scalars().all()

        progress_map: dict[int, UserChapterProgress] = {}
        prog_result = await db.execute(
            select(UserChapterProgress).where(UserChapterProgress.user_id == user_id)
        )
        for p in prog_result.scalars().all():
            progress_map[p.chapter_id] = p

        candidates = []
        for ch in chapters:
            prog = progress_map.get(ch.id)
            if prog and prog.completed:
                continue
            score = PRIORITY_ORDER.get(ch.priority, 9) * 100 + ch.sort_order
            if prog and prog.is_weak:
                score -= 50
            candidates.append((score, ch, prog))

        candidates.sort(key=lambda x: x[0])
        suggestions = []
        for _, ch, prog in candidates[:limit]:
            suggestions.append({
                "chapter_id": ch.id,
                "name": ch.name,
                "subject": ch.subject.name,
                "priority": ch.priority,
                "priority_label": PRIORITY_LABELS[ch.priority],
                "reason": "Very high priority — complete first" if ch.priority == "very_high" else "Recommended next",
                "current_progress": prog.progress_percentage if prog else 0,
            })
        return suggestions
