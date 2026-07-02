"""Build SSC CGL 2026 roadmap payload with weeks, phases, analytics."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.roadmap_2026 import (
    CHAPTER_ALIASES,
    DAILY_GS_DAYS,
    DAILY_QR_DAYS,
    DAILY_SCHEDULE,
    DAILY_VOCAB_DAYS,
    ENGLISH_DAILY_BLOCK,
    ENGLISH_PHASES,
    EXAM_LABEL,
    MOCK_TASKS,
    PHASES,
    ROADMAP_END,
    ROADMAP_START,
    SUBJECT_DAILY_PLANS,
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

        def daily_vocab_item(week_num: int, key: str, label: str) -> dict:
            t = tasks_by_key.get((week_num, key))
            return {
                "key": key,
                "label": label,
                "completed": bool(t.completed) if t else False,
            }

        weeks_out = []
        all_topic_items: list[dict] = []
        all_task_items: list[dict] = []
        all_vocab_days: list[dict] = []

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
            daily_vocab = [
                daily_vocab_item(w["number"], key, label) for key, label in DAILY_VOCAB_DAYS
            ]
            daily_gs = [daily_vocab_item(w["number"], key, label) for key, label in DAILY_GS_DAYS]
            daily_qr = [daily_vocab_item(w["number"], key, label) for key, label in DAILY_QR_DAYS]
            all_vocab_days.extend(daily_vocab)
            all_vocab_days.extend(daily_gs)
            all_vocab_days.extend(daily_qr)

            week_total = (
                len(week_topics)
                + len(virtual)
                + len([m for m in mocks if m["required"]])
                + len(daily_vocab)
                + len(daily_gs)
                + len(daily_qr)
            )
            week_done = sum(1 for t in week_topics if t["completed"])
            week_done += sum(1 for v in virtual if v["completed"])
            week_done += sum(1 for m in mocks if m["required"] and m["completed"])
            week_done += sum(1 for d in daily_vocab + daily_gs + daily_qr if d["completed"])

            all_topic_items.extend(week_topics)
            all_task_items.extend(virtual + mocks)

            eng_phase = next((p for p in ENGLISH_PHASES if p["id"] == w.get("english_phase")), None)

            weeks_out.append(
                {
                    "number": w["number"],
                    "phase": w["phase"],
                    "label": w["label"],
                    "start": w["start"],
                    "end": w["end"],
                    "english_phase": w.get("english_phase"),
                    "english_phase_name": eng_phase["name"] if eng_phase else None,
                    "english_phase_note": w.get("english_phase_note"),
                    "sections": sections,
                    "virtual_tasks": virtual,
                    "mock_tasks": mocks,
                    "daily_vocab": daily_vocab,
                    "daily_gs": daily_gs,
                    "daily_qr": daily_qr,
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
        vocab_done = sum(1 for d in all_vocab_days if d["completed"])
        vocab_total = len(all_vocab_days)
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

        current_week_num = _current_week_number(today)
        english_roadmap = self._english_roadmap(weeks_out, all_topic_items, tasks_by_key, current_week_num)
        vocab_streak = self._vocab_streak(weeks_out, current_week_num, today)
        daily_study_hub = self._daily_study_hub(weeks_out, english_roadmap, current_week_num, today)

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
                "vocabulary_total": vocab_total,
                "formula_revision": formula_done,
                "pyq": pyq_count,
            },
            "english_roadmap": english_roadmap,
            "daily_study_hub": daily_study_hub,
            "vocab_streak": vocab_streak,
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
        # Daily vocabulary is always part of the English block
        current_vocab = current.get("daily_vocab", [])
        pending_vocab = [d for d in current_vocab if not d["completed"]]
        if pending_vocab:
            today_tasks.append(f"English: Daily Vocabulary ({pending_vocab[0]['label']})")
        for sec in current.get("sections", []):
            if sec["subject"] != "English":
                continue
            for t in sec["topics"]:
                if not t["completed"]:
                    today_tasks.append(f"English: {t['label']}")
        for sec in current.get("sections", []):
            if sec["subject"] == "English":
                continue
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

    def _english_roadmap(
        self,
        weeks: list[dict],
        all_topics: list[dict],
        tasks_by_key: dict[tuple[int, str], UserRoadmapTaskProgress],
        current_week: int,
    ) -> dict:
        english_topics = {t["label"]: t for t in all_topics if t["subject_key"] == "English"}
        virtual_by_label: dict[str, bool] = {}
        for w in weeks:
            for v in w.get("virtual_tasks", []):
                if v["label"] in {
                    "Topic-wise Previous Year Questions",
                    "Mixed Practice Sets",
                    "Mock Test Revision",
                    "Full English Revision",
                }:
                    virtual_by_label[v["label"]] = v["completed"]

        phases_out = []
        current_phase_id = ENGLISH_PHASES[-1]["id"]
        for phase in ENGLISH_PHASES:
            items = []
            done = 0
            for topic in phase["topics"]:
                if phase.get("virtual"):
                    completed = virtual_by_label.get(topic, False)
                    items.append(
                        {
                            "label": topic,
                            "completed": completed,
                            "chapter_id": None,
                            "virtual": True,
                        }
                    )
                else:
                    item = english_topics.get(topic)
                    completed = bool(item and item["completed"])
                    items.append(
                        {
                            "label": topic,
                            "completed": completed,
                            "chapter_id": item["chapter_id"] if item else None,
                            "virtual": False,
                        }
                    )
                if items[-1]["completed"]:
                    done += 1
            total = len(items)
            pct = round(done / total * 100, 1) if total else 0
            phases_out.append(
                {
                    "id": phase["id"],
                    "name": phase["name"],
                    "subtitle": phase["subtitle"],
                    "weeks": phase["weeks"],
                    "completion_pct": pct,
                    "completed_count": done,
                    "total_count": total,
                    "topics": items,
                }
            )

        for phase in phases_out:
            if phase["completion_pct"] < 100:
                current_phase_id = phase["id"]
                break

        current_week_data = next((w for w in weeks if w["number"] == current_week), weeks[0])
        current_phase = next((p for p in phases_out if p["id"] == current_phase_id), phases_out[0])

        return {
            "phases": phases_out,
            "current_phase_id": current_phase_id,
            "current_phase_name": current_phase["name"],
            "daily_block_minutes": ENGLISH_DAILY_BLOCK,
            "daily_hours": DAILY_SCHEDULE["english_vocab_hours"],
            "current_week_vocab": current_week_data.get("daily_vocab", []),
            "current_week_english_topics": [
                t
                for sec in current_week_data.get("sections", [])
                if sec["subject"] == "English"
                for t in sec["topics"]
            ],
        }

    def _vocab_streak(self, weeks: list[dict], current_week: int, today: date) -> dict:
        """Consecutive Mon–Sat vocab days completed in the current week."""
        current = next((w for w in weeks if w["number"] == current_week), None)
        if not current:
            return {"current_week_days": 0, "best_this_week": 0, "total_logged": 0}

        days = current.get("daily_vocab", [])
        weekday = today.weekday()  # Mon=0 … Sun=6
        total_logged = sum(1 for d in days if d["completed"])

        streak = 0
        if weekday == 6:
            # Sunday: count full Mon–Sat block
            if all(d["completed"] for d in days):
                streak = len(days)
        else:
            for i in range(min(weekday + 1, len(days))):
                if days[i]["completed"]:
                    streak += 1
                else:
                    break

        return {
            "current_week_days": streak,
            "best_this_week": total_logged,
            "total_logged": sum(
                1 for w in weeks for d in w.get("daily_vocab", []) if d["completed"]
            ),
        }

    def _habit_streak(self, days: list[dict], today: date) -> int:
        weekday = today.weekday()
        if weekday == 6:
            return len(days) if days and all(d["completed"] for d in days) else 0
        streak = 0
        for i in range(min(weekday + 1, len(days))):
            if days[i]["completed"]:
                streak += 1
            else:
                break
        return streak

    def _daily_study_hub(
        self,
        weeks: list[dict],
        english_roadmap: dict,
        current_week: int,
        today: date,
    ) -> dict:
        current_week_data = next((w for w in weeks if w["number"] == current_week), weeks[0])
        habit_map = {
            "daily_gs": current_week_data.get("daily_gs", []),
            "daily_vocab": current_week_data.get("daily_vocab", []),
            "daily_qr": current_week_data.get("daily_qr", []),
        }

        def week_topics_for(subject_keys: tuple[str, ...]) -> list[dict]:
            topics: list[dict] = []
            for sec in current_week_data.get("sections", []):
                if sec["subject"] in subject_keys:
                    topics.extend(sec["topics"])
            return topics

        subjects_out = []
        for plan in SUBJECT_DAILY_PLANS:
            habits = habit_map.get(plan["habit_field"], [])
            if plan["subject_key"] == "GS":
                focus_topics = week_topics_for(("GS",))
            elif plan["subject_key"] == "English":
                focus_topics = week_topics_for(("English",))
            else:
                focus_topics = week_topics_for(("Quant", "Reasoning"))

            next_topic = next((t["label"] for t in focus_topics if not t["completed"]), None)
            subjects_out.append(
                {
                    "subject_key": plan["subject_key"],
                    "label": plan["label"],
                    "hours": plan["hours"],
                    "habit_label": plan["habit_label"],
                    "habit_field": plan["habit_field"],
                    "blocks": plan["blocks"],
                    "habits": habits,
                    "habits_done": sum(1 for h in habits if h["completed"]),
                    "streak": self._habit_streak(habits, today),
                    "next_topic": next_topic,
                    "week_topics": focus_topics,
                }
            )

        return {
            "current_week": current_week,
            "subjects": subjects_out,
            "english_phases": english_roadmap.get("phases", []),
            "english_current_phase_id": english_roadmap.get("current_phase_id"),
            "english_current_phase_name": english_roadmap.get("current_phase_name"),
        }
