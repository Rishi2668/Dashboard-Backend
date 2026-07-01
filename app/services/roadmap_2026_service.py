"""Build SSC CGL 2026 roadmap payload with weeks, phases, analytics."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.roadmap_2026 import (
    CHAPTER_ALIASES,
    DAILY_SCHEDULE,
    EXAM_LABEL,
    MOCK_TASKS,
    PHASES,
    ROADMAP_END,
    ROADMAP_START,
    SUBJECT_SLUG,
    VIRTUAL_TASK_PREFIX,
    WEEKS,
)
from app.models.mock_test import MockTest
from app.models.pyq import PYQProgress
from app.models.roadmap_task import UserRoadmapTaskProgress
from app.models.study import StudySession
from app.models.syllabus import SyllabusChapter, SyllabusSubject, UserChapterProgress
from app.models.user import User
from app.models.weak_area import WeakTopic
from app.services.mock_classification import filter_mocks_by_type


def _resolve_chapter_name(label: str) -> str:
    return CHAPTER_ALIASES.get(label, label)


def _current_week_number(today: date | None = None) -> int:
    today = today or date.today()
    if today < ROADMAP_START:
        return 1
    if today > ROADMAP_END:
        return WEEKS[-1]["number"]
    for w in WEEKS:
        start = date.fromisoformat(w["start"])
        end = date.fromisoformat(w["end"])
        if start <= today <= end:
            return w["number"]
    return WEEKS[-1]["number"]


def _days_remaining(today: date | None = None) -> int:
    today = today or date.today()
    return max((ROADMAP_END - today).days, 0)


class Roadmap2026Service:
    async def build(
        self,
        db: AsyncSession,
        user: User,
    ) -> dict:
        today = date.today()

        subj_result = await db.execute(
            select(SyllabusSubject).options(selectinload(SyllabusSubject.chapters))
        )
        subjects = list(subj_result.scalars().all())
        chapter_by_name: dict[tuple[str, str], SyllabusChapter] = {}
        for subj in subjects:
            for ch in subj.chapters:
                chapter_by_name[(subj.slug, ch.name)] = ch

        prog_result = await db.execute(
            select(UserChapterProgress).where(UserChapterProgress.user_id == user.id)
        )
        progress_by_chapter = {p.chapter_id: p for p in prog_result.scalars().all()}

        task_result = await db.execute(
            select(UserRoadmapTaskProgress).where(UserRoadmapTaskProgress.user_id == user.id)
        )
        tasks_by_key: dict[tuple[int, str], UserRoadmapTaskProgress] = {
            (t.week_number, t.task_key): t for t in task_result.scalars().all()
        }

        def lookup_chapter(subject_key: str, topic_label: str) -> SyllabusChapter | None:
            slug = SUBJECT_SLUG.get(subject_key, subject_key.lower())
            resolved = _resolve_chapter_name(topic_label)
            ch = chapter_by_name.get((slug, resolved))
            if ch:
                return ch
            if topic_label != resolved:
                return chapter_by_name.get((slug, topic_label))
            return None

        def topic_item(subject_key: str, label: str) -> dict:
            ch = lookup_chapter(subject_key, label)
            prog = progress_by_chapter.get(ch.id) if ch else None
            return {
                "label": label,
                "subject_key": subject_key,
                "chapter_id": ch.id if ch else None,
                "completed": bool(prog.completed) if prog else False,
                "progress_percentage": float(prog.progress_percentage) if prog else 0.0,
            }

        def virtual_item(week_num: int, label: str) -> dict:
            key = f"{VIRTUAL_TASK_PREFIX}{label.lower().replace(' ', '_')}"
            t = tasks_by_key.get((week_num, key))
            return {
                "label": label,
                "task_key": key,
                "completed": bool(t.completed) if t else False,
                "score": t.score if t else None,
                "accuracy": t.accuracy if t else None,
                "time_taken_minutes": t.time_taken_minutes if t else None,
                "weak_areas": t.weak_areas if t else None,
                "notes": t.notes if t else None,
            }

        def mock_item(week_num: int, spec: dict) -> dict:
            t = tasks_by_key.get((week_num, spec["key"]))
            return {
                "key": spec["key"],
                "label": spec["label"],
                "required": spec["required"],
                "completed": bool(t.completed) if t else False,
                "score": t.score if t else None,
                "accuracy": t.accuracy if t else None,
                "time_taken_minutes": t.time_taken_minutes if t else None,
                "weak_areas": t.weak_areas if t else None,
                "notes": t.notes if t else None,
            }

        weeks_out = []
        all_topic_items: list[dict] = []
        all_task_items: list[dict] = []

        for w in WEEKS:
            sections = []
            week_topics: list[dict] = []
            for subject_key in ("GS", "English", "Quant", "Reasoning"):
                labels = w.get("topics", {}).get(subject_key, [])
                if not labels:
                    continue
                items = [topic_item(subject_key, lbl) for lbl in labels]
                week_topics.extend(items)
                sections.append({"subject": subject_key, "topics": items})

            virtual = [virtual_item(w["number"], lbl) for lbl in w.get("virtual", [])]
            mocks = [mock_item(w["number"], spec) for spec in MOCK_TASKS]

            week_total = len(week_topics) + len(virtual) + len([m for m in mocks if m["required"]])
            week_done = sum(1 for t in week_topics if t["completed"])
            week_done += sum(1 for v in virtual if v["completed"])
            week_done += sum(1 for m in mocks if m["required"] and m["completed"])

            all_topic_items.extend(week_topics)
            all_task_items.extend(virtual + mocks)

            weeks_out.append(
                {
                    "number": w["number"],
                    "phase": w["phase"],
                    "label": w["label"],
                    "start": w["start"],
                    "end": w["end"],
                    "sections": sections,
                    "virtual_tasks": virtual,
                    "mock_tasks": mocks,
                    "completion_pct": round(week_done / week_total * 100, 1) if week_total else 0,
                    "completed_count": week_done,
                    "total_count": week_total,
                    "is_current": w["number"] == _current_week_number(today),
                }
            )

        # Subject progress for roadmap topics only
        roadmap_chapter_ids = {t["chapter_id"] for t in all_topic_items if t["chapter_id"]}
        subject_stats = self._subject_progress(subjects, roadmap_chapter_ids, progress_by_chapter)

        phase_stats = []
        for phase in PHASES:
            phase_weeks = [wk for wk in weeks_out if wk["phase"] == phase["id"]]
            total = sum(w["total_count"] for w in phase_weeks)
            done = sum(w["completed_count"] for w in phase_weeks)
            phase_stats.append(
                {
                    **phase,
                    "completion_pct": round(done / total * 100, 1) if total else 0,
                    "completed_count": done,
                    "total_count": total,
                }
            )

        overall_total = sum(w["total_count"] for w in weeks_out)
        overall_done = sum(w["completed_count"] for w in weeks_out)

        # Study hours since roadmap start
        hours_result = await db.execute(
            select(func.coalesce(func.sum(StudySession.hours), 0)).where(
                StudySession.user_id == user.id,
                StudySession.date >= ROADMAP_START,
            )
        )
        hours_studied = float(hours_result.scalar() or 0)

        # Mock count (Sundays / full mocks in range)
        mock_result = await db.execute(
            select(MockTest).where(
                MockTest.user_id == user.id,
                MockTest.test_date >= ROADMAP_START,
                MockTest.test_date <= ROADMAP_END,
            )
        )
        mocks_in_range = filter_mocks_by_type(list(mock_result.scalars().all()), "full")
        mandatory_done = sum(
            1 for t in tasks_by_key.values() if t.task_key == "mandatory_mock" and t.completed
        )

        # Counters
        vocab_done = sum(
            1
            for t in all_topic_items
            if "vocab" in t["label"].lower() and t["completed"]
        )
        pyq_result = await db.execute(
            select(func.coalesce(func.sum(PYQProgress.completed_questions), 0)).where(
                PYQProgress.user_id == user.id
            )
        )
        pyq_count = int(pyq_result.scalar() or 0)
        formula_done = sum(
            1 for t in all_topic_items if "formula" in t["label"].lower() and t["completed"]
        )

        weak_result = await db.execute(
            select(func.count()).select_from(WeakTopic).where(
                WeakTopic.user_id == user.id, WeakTopic.needs_revision.is_(True)
            )
        )
        weak_count = int(weak_result.scalar() or 0)

        streak = self._completion_streak(weeks_out, _current_week_number(today))

        productivity = self._productivity(
            weeks_out, today, weak_count, _current_week_number(today)
        )

        analytics = await self._analytics(db, user, weeks_out, mocks_in_range, hours_studied)

        return {
            "exam_label": EXAM_LABEL,
            "roadmap_start": str(ROADMAP_START),
            "roadmap_end": str(ROADMAP_END),
            "days_remaining": _days_remaining(today),
            "current_week": _current_week_number(today),
            "daily_schedule": DAILY_SCHEDULE,
            "overall_completion": round(overall_done / overall_total * 100, 1) if overall_total else 0,
            "overall_completed": overall_done,
            "overall_total": overall_total,
            "phases": phase_stats,
            "weeks": weeks_out,
            "subject_progress": subject_stats,
            "mocks_completed": max(len(mocks_in_range), mandatory_done),
            "hours_studied": round(hours_studied, 1),
            "completion_streak": streak,
            "counters": {
                "vocabulary": vocab_done,
                "formula_revision": formula_done,
                "pyq": pyq_count,
            },
            "productivity": productivity,
            "analytics": analytics,
        }

    def _subject_progress(
        self,
        subjects: list[SyllabusSubject],
        roadmap_ids: set[int],
        progress_by_chapter: dict[int, UserChapterProgress],
    ) -> dict[str, dict]:
        slug_to_key = {v: k for k, v in SUBJECT_SLUG.items()}
        out: dict[str, dict] = {}
        for subj in subjects:
            key = slug_to_key.get(subj.slug, subj.short_name)
            chapters = [c for c in subj.chapters if c.id in roadmap_ids]
            if not chapters:
                continue
            done = sum(
                1 for c in chapters if progress_by_chapter.get(c.id) and progress_by_chapter[c.id].completed
            )
            out[key] = {
                "label": key,
                "completion_pct": round(done / len(chapters) * 100, 1),
                "completed": done,
                "total": len(chapters),
            }
        # Vocabulary tracked across english vocab topics
        vocab_topics = [t for t in roadmap_ids]  # placeholder
        vocab_chapters = [
            c
            for subj in subjects
            if subj.slug == "english"
            for c in subj.chapters
            if c.id in roadmap_ids and "vocab" in c.name.lower()
        ]
        if vocab_chapters:
            vdone = sum(
                1
                for c in vocab_chapters
                if progress_by_chapter.get(c.id) and progress_by_chapter[c.id].completed
            )
            out["Vocabulary"] = {
                "label": "Vocabulary",
                "completion_pct": round(vdone / len(vocab_chapters) * 100, 1),
                "completed": vdone,
                "total": len(vocab_chapters),
            }
        return out

    def _completion_streak(self, weeks: list[dict], current_week: int) -> int:
        streak = 0
        for w in reversed([wk for wk in weeks if wk["number"] <= current_week]):
            if w["completion_pct"] >= 80:
                streak += 1
            elif w["number"] == current_week and w["completion_pct"] > 0:
                continue
            else:
                break
        return streak

    def _productivity(
        self,
        weeks: list[dict],
        today: date,
        weak_count: int,
        current_week: int,
    ) -> dict:
        current = next((w for w in weeks if w["number"] == current_week), weeks[0])
        today_tasks: list[str] = []
        for sec in current.get("sections", []):
            for t in sec["topics"]:
                if not t["completed"]:
                    today_tasks.append(f"{sec['subject']}: {t['label']}")
        for v in current.get("virtual_tasks", []):
            if not v["completed"]:
                today_tasks.append(v["label"])
        if today.weekday() == 6:  # Sunday
            for m in current.get("mock_tasks", []):
                if not m["completed"]:
                    today_tasks.insert(0, m["label"])

        upcoming: list[str] = []
        for w in weeks:
            if w["number"] <= current_week:
                continue
            for sec in w.get("sections", []):
                for t in sec["topics"][:2]:
                    upcoming.append(f"Week {w['number']} — {t['label']}")
            if len(upcoming) >= 8:
                break

        missed: list[str] = []
        for w in weeks:
            if w["number"] >= current_week:
                continue
            if w["completion_pct"] < 100:
                missed.append(f"Week {w['number']} ({w['completion_pct']:.0f}% done)")

        return {
            "today_tasks": today_tasks[:12],
            "upcoming_tasks": upcoming[:8],
            "missed_tasks": missed[:6],
            "weak_topic_count": weak_count,
            "mock_reminder": today.weekday() == 6,
            "revision_reminder": weak_count > 0,
        }

    async def _analytics(
        self,
        db: AsyncSession,
        user: User,
        weeks: list[dict],
        mocks: list[MockTest],
        hours_studied: float,
    ) -> dict:
        # Study hours by week
        weekly_hours = []
        for w in WEEKS:
            start = date.fromisoformat(w["start"])
            end = date.fromisoformat(w["end"])
            hr = await db.execute(
                select(func.coalesce(func.sum(StudySession.hours), 0)).where(
                    StudySession.user_id == user.id,
                    StudySession.date >= start,
                    StudySession.date <= end,
                )
            )
            weekly_hours.append(
                {"week": w["number"], "label": w["label"], "hours": round(float(hr.scalar() or 0), 1)}
            )

        week_progress = [{"week": w["number"], "label": w["label"], "pct": w["completion_pct"]} for w in weeks]

        mock_scores = [
            {
                "date": str(m.test_date),
                "score": m.total_score,
                "max_score": m.max_score,
                "accuracy": m.accuracy,
            }
            for m in sorted(mocks, key=lambda x: x.test_date)
        ]

        weak_result = await db.execute(
            select(WeakTopic.subject, func.count())
            .where(WeakTopic.user_id == user.id, WeakTopic.needs_revision.is_(True))
            .group_by(WeakTopic.subject)
        )
        weak_areas = [{"subject": r[0] or "General", "count": r[1]} for r in weak_result.all()]

        return {
            "study_hours_weekly": weekly_hours,
            "weekly_progress": week_progress,
            "mock_scores": mock_scores,
            "accuracy_trend": [
                {"date": str(m.test_date), "accuracy": m.accuracy} for m in sorted(mocks, key=lambda x: x.test_date)
            ],
            "weak_areas": weak_areas,
            "total_hours": hours_studied,
        }
