from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    calc_practice,
    dashboard,
    perf,
    roadmap_2026,
    score_targets,
    mock_tests,
    notes,
    pyq,
    quotes,
    revision,
    study,
    syllabus,
    weak_areas,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(score_targets.router)
api_router.include_router(study.router)
api_router.include_router(mock_tests.router)
api_router.include_router(notes.router)
api_router.include_router(revision.router)
api_router.include_router(weak_areas.router)
api_router.include_router(ai.router)
api_router.include_router(quotes.router)
api_router.include_router(pyq.router)
api_router.include_router(syllabus.router)
api_router.include_router(calc_practice.router)
api_router.include_router(roadmap_2026.router)
api_router.include_router(perf.router)
