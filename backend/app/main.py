"""FastAPI application entry point.

Wires up routers, event handlers, CORS, and database initialization.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, dashboard, ingestion
from app.core.config import settings
from app.core.database import engine, Base
from app.services.ingestion import register_ingestion_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # Import models so SQLAlchemy sees them before create_all
    import app.models.conversation  # noqa: F401
    import app.models.inference_log  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    # Register event-driven ingestion handlers
    register_ingestion_handlers()
    logger.info("Ingestion event handlers registered")

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React frontend to talk to the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(conversations.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(ingestion.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/providers")
async def list_providers():
    """Return available providers based on configured API keys."""
    providers = []
    if settings.OPENAI_API_KEY:
        providers.append({
            "id": "openai",
            "name": "OpenAI",
            "models": ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"],
        })
    if settings.ANTHROPIC_API_KEY:
        providers.append({
            "id": "anthropic",
            "name": "Anthropic",
            "models": [
                "claude-sonnet-4-20250514",
                "claude-3-5-haiku-20241022",
            ],
        })
    if settings.GOOGLE_API_KEY:
        providers.append({
            "id": "google",
            "name": "Google",
            "models": ["gemini-2.0-flash", "gemini-2.5-flash-preview-05-20"],
        })
    return {"providers": providers, "default_provider": settings.DEFAULT_PROVIDER, "default_model": settings.DEFAULT_MODEL}
