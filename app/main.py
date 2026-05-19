import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import Base, engine
import app.models  # noqa: F401 — register ORM tables before create_all
from app.utils.schema_sync import sync_schema
from app.utils.seed import seed_quotes
from app.utils.seed_syllabus import seed_syllabus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


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

cors_origins_list = [
    "http://localhost:5173",
    "https://ssc-dashboard-beta-nine.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in settings.cors_origins_list:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ssc-cgl-api"}


app.include_router(api_router)
