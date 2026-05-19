from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.ai_insight import AIInsight
from app.schemas.dashboard import AIInsightResponse
from app.schemas.overall_analysis import DomainAnalysisOut, OverallAnalysisOut
from app.services.ai.overall_analysis_engine import OverallAnalysisEngine
from app.services.ai.recommendation_engine import AIRecommendationEngine
from fastapi import Depends

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/insights", response_model=list[AIInsightResponse])
async def get_insights(current_user: CurrentUser, db: AsyncSession = Depends(get_db), limit: int = 10):
    result = await db.execute(
        select(AIInsight)
        .where(AIInsight.user_id == current_user.id)
        .order_by(AIInsight.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/generate", response_model=list[AIInsightResponse])
async def generate_insights(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    engine = AIRecommendationEngine()
    insights = await engine.generate_insights(db, current_user)
    return insights


@router.get("/overall-analysis", response_model=OverallAnalysisOut)
async def overall_analysis(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    engine = OverallAnalysisEngine()
    data = await engine.generate(db, current_user)
    return data


@router.get("/analysis/{domain}", response_model=DomainAnalysisOut)
async def domain_analysis(domain: str, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    engine = OverallAnalysisEngine()
    domain_map = {
        "mock": engine.mock_analysis_only,
        "revision": engine.revision_analysis_only,
        "weak-areas": engine.weak_areas_analysis_only,
        "syllabus": engine.syllabus_analysis_only,
    }
    fn = domain_map.get(domain)
    if not fn:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Unknown analysis domain")
    insights = await fn(db, current_user)
    return DomainAnalysisOut(domain=domain, insights=insights)


@router.patch("/insights/{insight_id}/read")
async def mark_insight_read(insight_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AIInsight).where(AIInsight.id == insight_id, AIInsight.user_id == current_user.id)
    )
    insight = result.scalar_one_or_none()
    if insight:
        insight.is_read = True
        await db.flush()
    return {"ok": True}
