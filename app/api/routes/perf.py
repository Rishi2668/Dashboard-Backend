"""Web performance metrics (Core Web Vitals) — non-blocking ingest."""

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/perf", tags=["performance"])


@router.get("/cwv")
async def web_vitals_probe():
    """Lets clients verify the endpoint exists (avoids noisy 404 on old probes)."""
    return {"ok": True, "endpoint": "cwv"}


@router.post("/cwv")
async def web_vitals_ingest(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    logger.info("WebVitals %s", payload)
    return {"ok": True}
