import logging
import re
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
    if request.method == "OPTIONS":
        logger.info(
            "OPTIONS %s | Origin=%s | allowed=%s",
            request.url.path,
            request.headers.get("origin"),
            _origin_allowed(request.headers.get("origin")),
        )
    return await call_next(request)


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
    return {"status": "healthy", "service": "ssc-cgl-api"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# Primary API: /api/v1/...
app.include_router(api_router)

# Legacy alias when VITE_API_URL omits /api/v1 (e.g. POST /auth/register)
legacy_router = APIRouter()
legacy_router.include_router(auth.router)
app.include_router(legacy_router)
