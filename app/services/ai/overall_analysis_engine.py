"""Unified AI analysis across mocks, revision, weak areas, syllabus, and study habits."""

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mock_test import MockTest
from app.models.revision import RevisionItem
from app.models.study import StudySession
from app.models.syllabus import SyllabusChapter, SyllabusSubject, UserChapterProgress
from app.models.user import User
from app.models.weak_area import WeakTopic
from app.services.ai.recommendation_engine import AIRecommendationEngine
from app.services.syllabus_ai import SyllabusAIEngine
from app.utils.syllabus_seed import PRIORITY_ORDER


class OverallAnalysisEngine:
    async def generate(self, db: AsyncSession, user: User) -> dict[str, Any]:
        mocks = await self._mocks(db, user.id)
        sessions = await self._sessions(db, user.id)
        weak = await self._weak(db, user.id)
        pending_rev = await self._pending_revision(db, user.id)
        syllabus_stats = await self._syllabus_stats(db, user.id)

        mock_insights = self._analyze_mocks(mocks, user)
        revision_insights = self._analyze_revision(pending_rev, syllabus_stats)
        weak_insights = self._analyze_weak_areas(weak, mocks)
        syllabus_insights = self._analyze_syllabus(syllabus_stats)
        study_insights = self._analyze_study(sessions, user)

        all_sections = [
            {"id": "mock", "title": "Mock Test Analysis", "icon": "chart", "insights": mock_insights},
            {"id": "revision", "title": "Revision Planner", "icon": "rotate", "insights": revision_insights},
            {"id": "weak_areas", "title": "Weak Areas", "icon": "alert", "insights": weak_insights},
            {"id": "syllabus", "title": "Syllabus Roadmap", "icon": "map", "insights": syllabus_insights},
            {"id": "study", "title": "Study & Productivity", "icon": "clock", "insights": study_insights},
        ]

        readiness = self._readiness_score(mocks, syllabus_stats, sessions, weak, user)
        action_plan = self._build_action_plan(mock_insights, revision_insights, weak_insights, syllabus_insights)

        return {
            "readiness_score": readiness,
            "readiness_label": self._readiness_label(readiness),
            "summary": self._executive_summary(user, readiness, mocks, syllabus_stats),
            "sections": all_sections,
            "action_plan": action_plan,
            "priority_focus": action_plan[:5],
            "generated_at": date.today().isoformat(),
        }

    async def mock_analysis_only(self, db: AsyncSession, user: User) -> list[dict]:
        mocks = await self._mocks(db, user.id)
        return self._analyze_mocks(mocks, user)

    async def revision_analysis_only(self, db: AsyncSession, user: User) -> list[dict]:
        pending = await self._pending_revision(db, user.id)
        stats = await self._syllabus_stats(db, user.id)
        return self._analyze_revision(pending, stats)

    async def weak_areas_analysis_only(self, db: AsyncSession, user: User) -> list[dict]:
        weak = await self._weak(db, user.id)
        mocks = await self._mocks(db, user.id)
        return self._analyze_weak_areas(weak, mocks)

    async def syllabus_analysis_only(self, db: AsyncSession, user: User) -> list[dict]:
        stats = await self._syllabus_stats(db, user.id)
        base = self._analyze_syllabus(stats)
        engine = SyllabusAIEngine()
        subjects_data = [{"name": s["name"], "chapters": [], "total_chapters": s["total"], "completed_chapters": s["completed"]} for s in stats["by_subject"]]
        ai_extra = await engine.generate_insights(db, user, subjects_data)
        for item in ai_extra[:4]:
            base.append({
                "type": item.get("type", "syllabus"),
                "priority": item.get("priority", "medium"),
                "title": item.get("title", ""),
                "message": item.get("message", ""),
            })
        return base[:8]

    async def _mocks(self, db: AsyncSession, user_id: int) -> list[MockTest]:
        r = await db.execute(select(MockTest).where(MockTest.user_id == user_id).order_by(MockTest.test_date.desc()).limit(15))
        return list(r.scalars().all())

    async def _sessions(self, db: AsyncSession, user_id: int) -> list[StudySession]:
        r = await db.execute(select(StudySession).where(StudySession.user_id == user_id).order_by(StudySession.date.desc()).limit(30))
        return list(r.scalars().all())

    async def _weak(self, db: AsyncSession, user_id: int) -> list[WeakTopic]:
        r = await db.execute(select(WeakTopic).where(WeakTopic.user_id == user_id).order_by(WeakTopic.accuracy.asc()).limit(10))
        return list(r.scalars().all())

    async def _pending_revision(self, db: AsyncSession, user_id: int) -> list[RevisionItem]:
        r = await db.execute(
            select(RevisionItem).where(
                RevisionItem.user_id == user_id,
                RevisionItem.completed == False,
                RevisionItem.next_revision_date <= date.today(),
            )
        )
        return list(r.scalars().all())

    async def _syllabus_stats(self, db: AsyncSession, user_id: int) -> dict:
        r = await db.execute(select(SyllabusSubject).options(selectinload(SyllabusSubject.chapters)))
        subjects = r.scalars().all()
        prog_r = await db.execute(select(UserChapterProgress).where(UserChapterProgress.user_id == user_id))
        prog_map = {p.chapter_id: p for p in prog_r.scalars().all()}

        total = completed = vh_total = vh_done = 0
        by_subject = []
        weak_chapters = []

        for subj in subjects:
            sub_total = len(subj.chapters)
            sub_done = 0
            for ch in subj.chapters:
                total += 1
                p = prog_map.get(ch.id)
                if ch.priority == "very_high":
                    vh_total += 1
                    if p and p.completed:
                        vh_done += 1
                if p and p.completed:
                    completed += 1
                    sub_done += 1
                elif p and (p.is_weak or (p.accuracy > 0 and p.accuracy < 55)):
                    weak_chapters.append({"topic": ch.name, "subject": subj.short_name, "accuracy": p.accuracy})

            by_subject.append({
                "name": subj.name,
                "short_name": subj.short_name,
                "total": sub_total,
                "completed": sub_done,
                "pct": round(sub_done / sub_total * 100, 1) if sub_total else 0,
            })

        return {
            "total": total,
            "completed": completed,
            "pct": round(completed / total * 100, 1) if total else 0,
            "vh_total": vh_total,
            "vh_done": vh_done,
            "by_subject": by_subject,
            "weak_chapters": weak_chapters[:8],
        }

    def _analyze_mocks(self, mocks: list[MockTest], user: User) -> list[dict]:
        insights = []
        if not mocks:
            insights.append({
                "type": "mock",
                "priority": "high",
                "title": "Start mock tests",
                "message": "No mocks recorded. Take 2 sectionals this week, then 1 full mock to establish baseline.",
            })
            return insights

        latest = mocks[0]
        avg_score = sum(m.total_score for m in mocks) / len(mocks)
        avg_acc = sum(m.accuracy for m in mocks) / len(mocks)

        sections = [
            ("Quant", latest.quant_accuracy),
            ("Reasoning", latest.reasoning_accuracy),
            ("English", latest.english_accuracy),
            ("GK", latest.gk_accuracy),
        ]
        weakest = min(sections, key=lambda x: x[1])
        strongest = max(sections, key=lambda x: x[1])

        insights.append({
            "type": "mock",
            "priority": "medium",
            "title": "Latest mock performance",
            "message": f"Score {latest.total_score:.0f}/{latest.max_score:.0f} · {latest.accuracy:.1f}% accuracy. "
            f"Average of last {len(mocks)} mocks: {avg_score:.0f} marks, {avg_acc:.1f}% accuracy.",
        })

        if weakest[1] < 60:
            insights.append({
                "type": "mock",
                "priority": "high",
                "title": f"Weakest section: {weakest[0]}",
                "message": f"{weakest[0]} at {weakest[1]:.0f}% in latest mock. Allocate 40% of tomorrow's study to {weakest[0]} PYQs + concepts.",
            })

        if len(mocks) >= 3:
            recent_avg = sum(m.total_score for m in mocks[:3]) / 3
            older_avg = sum(m.total_score for m in mocks[3:6]) / max(len(mocks[3:6]), 1)
            diff = recent_avg - older_avg
            if diff < -10:
                insights.append({
                    "type": "mock",
                    "priority": "high",
                    "title": "Score trend declining",
                    "message": f"Last 3 mocks avg {recent_avg:.0f} vs earlier {older_avg:.0f}. Review mistakes; avoid new topics — revise weak areas first.",
                })
            elif diff > 10:
                insights.append({
                    "type": "mock",
                    "priority": "low",
                    "title": "Score trend improving",
                    "message": f"Last 3 mocks up {diff:.0f} marks vs previous batch. Maintain schedule; add 1 full mock weekly.",
                })

        if user.target_marks and avg_score < user.target_marks * 0.7:
            gap = user.target_marks - avg_score
            insights.append({
                "type": "mock",
                "priority": "high",
                "title": "Gap to target marks",
                "message": f"You need ~{gap:.0f} more marks on average to reach your target of {user.target_marks:.0f}. Focus high-weightage Quant & Reasoning topics.",
            })

        insights.append({
            "type": "mock",
            "priority": "medium",
            "title": f"Strongest section: {strongest[0]}",
            "message": f"{strongest[0]} at {strongest[1]:.0f}% — maintain with weekly revision; don't neglect weaker sections.",
        })
        return insights

    def _analyze_revision(self, pending: list[RevisionItem], syllabus: dict) -> list[dict]:
        insights = []
        if pending:
            insights.append({
                "type": "revision",
                "priority": "high",
                "title": f"{len(pending)} revisions due today",
                "message": f"Complete: {', '.join(p.topic for p in pending[:3])}{'…' if len(pending) > 3 else ''}. Spaced repetition prevents forgetting.",
            })
        else:
            insights.append({
                "type": "revision",
                "priority": "medium",
                "title": "No revisions due today",
                "message": "Add topics from today's study to the revision planner (Day 3 → 7 → 15 cycle).",
            })

        if syllabus["vh_total"] > syllabus["vh_done"]:
            left = syllabus["vh_total"] - syllabus["vh_done"]
            insights.append({
                "type": "revision",
                "priority": "high",
                "title": "Very-high syllabus gaps",
                "message": f"{left} very-high priority chapters incomplete. Schedule revision slots before attempting new mocks.",
            })
        return insights

    def _analyze_weak_areas(self, weak: list[WeakTopic], mocks: list[MockTest]) -> list[dict]:
        insights = []
        if not weak and mocks:
            latest = mocks[0]
            auto = []
            for name, acc in [("Quant", latest.quant_accuracy), ("Reasoning", latest.reasoning_accuracy),
                              ("English", latest.english_accuracy), ("GK", latest.gk_accuracy)]:
                if acc < 65:
                    auto.append(f"{name} ({acc:.0f}%)")
            if auto:
                insights.append({
                    "type": "weak_area",
                    "priority": "high",
                    "title": "AI-detected weak sections",
                    "message": f"From latest mock: {', '.join(auto)}. Add specific topics to Weak Areas tracker.",
                })
        for w in weak[:4]:
            insights.append({
                "type": "weak_area",
                "priority": "high" if w.accuracy < 50 else "medium",
                "title": w.topic,
                "message": f"{w.subject} · {w.accuracy:.0f}% accuracy · {w.mistake_count} mistakes. "
                f"{'Urgent revision needed.' if w.needs_revision else 'Monitor progress.'}",
            })
        if not insights:
            insights.append({
                "type": "weak_area",
                "priority": "low",
                "title": "No weak areas tracked",
                "message": "Run AI auto-detect from mocks or add topics where you make repeated mistakes.",
            })
        return insights

    def _analyze_syllabus(self, stats: dict) -> list[dict]:
        insights = []
        insights.append({
            "type": "syllabus",
            "priority": "medium",
            "title": "Syllabus completion",
            "message": f"{stats['completed']}/{stats['total']} chapters ({stats['pct']}%). "
            f"Very-high priority: {stats['vh_done']}/{stats['vh_total']} done.",
        })
        weakest_subj = min(stats["by_subject"], key=lambda s: s["pct"]) if stats["by_subject"] else None
        if weakest_subj and weakest_subj["pct"] < 40:
            insights.append({
                "type": "syllabus",
                "priority": "high",
                "title": f"Focus subject: {weakest_subj['short_name']}",
                "message": f"Only {weakest_subj['pct']}% of {weakest_subj['name']} complete. Prioritize very-high chapters in this subject.",
            })
        for wc in stats["weak_chapters"][:2]:
            insights.append({
                "type": "syllabus",
                "priority": "high",
                "title": f"Chapter weak: {wc['topic']}",
                "message": f"{wc['subject']} at {wc['accuracy']:.0f}% — revise before marking complete.",
            })
        return insights

    def _analyze_study(self, sessions: list[StudySession], user: User) -> list[dict]:
        insights = []
        week_ago = date.today() - timedelta(days=7)
        week_hours = sum(s.hours for s in sessions if s.date >= week_ago)
        if week_hours < 14:
            insights.append({
                "type": "study",
                "priority": "high",
                "title": "Low study hours",
                "message": f"Only {week_hours:.1f} hours this week. Target 20+ hours for SSC CGL Tier-1 readiness.",
            })
        else:
            insights.append({
                "type": "study",
                "priority": "low",
                "title": "Study consistency",
                "message": f"{week_hours:.1f} hours studied this week. Good momentum — keep daily 3+ hour blocks.",
            })
        if user.exam_date:
            days = max((user.exam_date - date.today()).days, 0)
            insights.append({
                "type": "study",
                "priority": "medium" if days > 60 else "high",
                "title": "Exam timeline",
                "message": f"{days} days until exam ({user.exam_date}). "
                f"{'Intensify mocks + revision.' if days < 90 else 'Balance syllabus coverage with mocks.'}",
            })
        return insights

    def _readiness_score(self, mocks, syllabus, sessions, weak, user) -> float:
        score = 0.0
        if mocks:
            avg = sum(m.total_score for m in mocks) / len(mocks)
            score += min(avg / 200 * 35, 35)
            score += min(sum(m.accuracy for m in mocks) / len(mocks) / 100 * 15, 15)
        score += syllabus["pct"] * 0.25
        week_hours = sum(s.hours for s in sessions if s.date >= date.today() - timedelta(days=7))
        score += min(week_hours / 25 * 15, 15)
        if not weak:
            score += 10
        elif len(weak) <= 2:
            score += 5
        if user.target_marks and mocks:
            avg = sum(m.total_score for m in mocks) / len(mocks)
            if avg >= user.target_marks * 0.85:
                score += 10
        return round(min(score, 100), 1)

    def _readiness_label(self, score: float) -> str:
        if score >= 80:
            return "Exam Ready"
        if score >= 60:
            return "On Track"
        if score >= 40:
            return "Building Foundation"
        return "Needs Intensive Prep"

    def _executive_summary(self, user, readiness, mocks, syllabus) -> str:
        name = user.name.split()[0]
        rank_txt = f"target rank #{user.target_rank}" if user.target_rank else "your rank goal"
        marks_txt = f"target {user.target_marks:.0f} marks" if user.target_marks else "your score goal"
        mock_txt = f"latest mock {mocks[0].total_score:.0f}" if mocks else "no mocks yet"
        return (
            f"{name}, your overall readiness is {readiness}% ({self._readiness_label(readiness)}). "
            f"Syllabus {syllabus['pct']}% complete with {mock_txt}. "
            f"Aligned to {rank_txt} and {marks_txt}. Follow the action plan below by priority."
        )

    def _build_action_plan(self, *insight_lists) -> list[dict]:
        all_items = []
        for lst in insight_lists:
            for ins in lst:
                if ins.get("priority") in ("high", "medium"):
                    all_items.append(ins)
        order = {"high": 0, "medium": 1, "low": 2}
        all_items.sort(key=lambda x: order.get(x.get("priority", "low"), 9))
        return all_items[:10]
