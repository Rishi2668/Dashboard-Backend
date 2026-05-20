import logging
import re
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.routes import api_router
from app.api.routes import auth
from app.core.config import get_settings
from app.core.database import Base, engine
import app.models  # noqa: F401 — register ORM tables before create_all
from app.utils.schema_sync import sync_schema
from app.utils.seed import seed_quotes
from app.utils.seed_syllabus import seed_syllabus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()
_perf_metrics = {
    "requests_total": 0,
    "slow_requests": 0,
    "total_ms": 0.0,
    "by_path": {},
    "web_vitals_events": 0,
}

VERCEL_ORIGIN_REGEX = r"https://.*\.vercel\.app$"

# Env list + common local / production defaults (deduped)
_cors_origins = list(
    dict.fromkeys(
        [
            *settings.cors_origins_list,
            "http://localhost:5173",
            "http://localhost:3000",
            "https://ssc-dashboard-beta-nine.vercel.app",
        ]
    )
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await sync_schema(engine)
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await seed_quotes(db)
        await seed_syllabus(db)
        await db.commit()
    logger.info("Application started")
    yield
    await engine.dispose()


app = FastAPI(
    title="SSC CGL Preparation Dashboard API",
    description="Production API for SSC CGL exam preparation tracking",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=VERCEL_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("CORS origins=%s + regex %s", _cors_origins, VERCEL_ORIGIN_REGEX)


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    return origin in _cors_origins or bool(re.fullmatch(VERCEL_ORIGIN_REGEX, origin))


def _cors_headers_for_origin(origin: str | None) -> dict[str, str]:
    if not _origin_allowed(origin):
        return {}
    return {
        "Access-Control-Allow-Origin": origin or "",
        "Access-Control-Allow-Credentials": "true",
    }


@app.middleware("http")
async def log_preflight(request: Request, call_next):
    started = time.perf_counter()
    if request.method == "OPTIONS":
        logger.info(
            "OPTIONS %s | Origin=%s | allowed=%s",
            request.url.path,
            request.headers.get("origin"),
            _origin_allowed(request.headers.get("origin")),
        )
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    _perf_metrics["requests_total"] += 1
    _perf_metrics["total_ms"] += elapsed_ms
    path = request.url.path
    by_path = _perf_metrics["by_path"]
    item = by_path.get(path, {"count": 0, "total_ms": 0.0, "slow": 0})
    item["count"] += 1
    item["total_ms"] += elapsed_ms
    if elapsed_ms > 400:
        item["slow"] += 1
    by_path[path] = item
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    if elapsed_ms > 400:
        _perf_metrics["slow_requests"] += 1
        logger.warning("Slow request: %s %s took %.1fms", request.method, request.url.path, elapsed_ms)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    origin = request.headers.get("origin")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=_cors_headers_for_origin(origin),
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "ssc-cgl-api",
        "api_features": {
            "study_session_delete": True,
            "revision_management_v2": True,
        },
    }


@app.get("/metrics/perf")
async def perf_metrics():
    req = int(_perf_metrics["requests_total"] or 0)
    avg = (_perf_metrics["total_ms"] / req) if req else 0.0
    top = sorted(
        (
            {
                "path": p,
                "count": v["count"],
                "avg_ms": round(v["total_ms"] / max(v["count"], 1), 1),
                "slow": v["slow"],
            }
            for p, v in _perf_metrics["by_path"].items()
        ),
        key=lambda x: x["avg_ms"],
        reverse=True,
    )[:15]
    return {
        "requests_total": req,
        "avg_ms": round(avg, 1),
        "slow_requests": int(_perf_metrics["slow_requests"] or 0),
        "web_vitals_events": int(_perf_metrics["web_vitals_events"] or 0),
        "top_slowest_paths": top,
    }


@app.post("/api/v1/metrics/web-vitals")
async def web_vitals_ingest(payload: dict):
    _perf_metrics["web_vitals_events"] += 1
    logger.info("WebVitals %s", payload)
    return {"ok": True}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# Primary API: /api/v1/...
app.include_router(api_router)

# Legacy alias when VITE_API_URL omits /api/v1 (e.g. POST /auth/register)
legacy_router = APIRouter()
legacy_router.include_router(auth.router)
app.include_router(legacy_router)
