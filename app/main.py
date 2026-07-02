import os
import asyncio
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database.db_manager import DatabaseManager
from app.config.settings import settings
from app.config.logging_config import setup_logging
from app.scheduler.scheduler import start_scheduler, scheduler

logger = logging.getLogger(__name__)

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = DatabaseManager(settings.SQLITE_DB_PATH)
    db.initialize()
    db.close() # Initialize schema and close this transient connection

    start_scheduler()

    # Pre-warm the embedding model in a background thread so the first
    # chat request doesn't block for 30-60 seconds while it loads.
    async def _prewarm():
        try:
            logger.info("Pre-warming embedding model in background…")
            from app.api.chat_routes import get_chat_engine
            await asyncio.get_event_loop().run_in_executor(None, get_chat_engine)
            logger.info("Embedding model pre-warm complete.")
        except Exception as e:
            logger.warning(f"Embedding pre-warm failed (non-fatal): {e}")

    asyncio.create_task(_prewarm())

    yield
    # Shutdown
    if scheduler.running:
        scheduler.shutdown()

app = FastAPI(title="AI Review Analyser", version="1.0.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS — allow the Vercel frontend to call this API.
# allow_origin_regex covers all Vercel preview URLs (*.vercel.app) so that
# every preview deployment works without needing to whitelist it manually.
# Set ALLOWED_ORIGINS in Render env for any extra origins (comma-separated).
# ---------------------------------------------------------------------------
_raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://localhost:3000"
)
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

from app.api.dashboard_routes import router as dashboard_router
from app.api.chat_routes import router as chat_router
from app.api.health_routes import router as health_router

app.include_router(dashboard_router, prefix="/api/dashboard")
app.include_router(chat_router, prefix="/api/chat")
app.include_router(health_router, prefix="/api/health", tags=["Health"])
