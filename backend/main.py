"""
Carbon Market Eligibility Chatbot — FastAPI Backend
Phase 1: Rules Engine + RAG Foundation + Admin Panel
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from models.mongodb import get_database, close_client
from models.qdrant_client import close_qdrant
from llm.provider import llm_registry

# ── Routers ───────────────────────────────────────────────────────────────────
from api.assess import router as assess_router
from api.admin_llm import router as admin_llm_router
from api.admin_documents import router as admin_docs_router
from api.admin_corpus_seed import router as admin_corpus_router
from api.chat import router as chat_router
from api.leads import router as leads_router
from api.admin_geospatial import router as admin_geo_router
from api.admin_channels import router as admin_channels_router
from api.admin_dashboard import router as admin_dashboard_router
from api.admin_form import router as admin_form_router
from api.whatsapp import router as whatsapp_router
from api.auth import router as auth_router, get_current_admin_user
from api.user import router as user_router
from api.client_auth import router as client_auth_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _background_init():
    """Run DB init and LLM config load in the background after the server
    has already bound its port. This prevents Render port-scan timeouts."""
    # ── MongoDB indexes + Qdrant collections ──────────────────────────────
    try:
        from init_db import init_all
        await init_all()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # ── LLM config: DB first, env-var fallback ────────────────────────────
    try:
        db = get_database()
        await llm_registry.initialize_from_db(db)
    except Exception as e:
        logger.warning(f"DB LLM config load failed ({e}) — falling back to env vars")
        await llm_registry.initialize_from_env()

    logger.info(f"LLM status: {llm_registry.get_status()}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting Carbon Market Eligibility Chatbot API...")

    # Yield immediately so Uvicorn binds the port right away.
    # DB init + LLM config run in the background — this prevents Render's
    # port-scan from timing out while we wait for MongoDB connections.
    task = asyncio.create_task(_background_init())

    logger.info("API ready (background DB init in progress).")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    await close_client()
    await close_qdrant()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Carbon Market Eligibility Chatbot API",
    description=(
        "Deterministic rules engine + RAG for carbon credit eligibility screening. "
        "Phase 1: Rules Engine + Admin Panel."
    ),
    version="1.0.0-phase1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ────────────────────────────────────────────────────────────────
app.include_router(assess_router,      prefix="/api/v1",    tags=["Eligibility"])
app.include_router(chat_router,        prefix="/api/v1",    tags=["Chat Orchestrator"])
app.include_router(user_router,        prefix="/api/v1",    tags=["User Registration"])
app.include_router(client_auth_router, prefix="/api/v1/auth", tags=["Client Authentication"])
app.include_router(whatsapp_router,    prefix="/api/whatsapp", tags=["WhatsApp Webhook"])
app.include_router(auth_router,        prefix="/api/admin", tags=["Admin – Auth"])

# Protect all other admin routes
admin_dependencies = [Depends(get_current_admin_user)]
app.include_router(leads_router,       prefix="/api/admin", tags=["Leads Dashboard"], dependencies=admin_dependencies)
app.include_router(admin_dashboard_router, prefix="/api/admin", tags=["Admin – Dashboard"], dependencies=admin_dependencies)
app.include_router(admin_llm_router,   prefix="/api/admin", tags=["Admin – LLM"], dependencies=admin_dependencies)
app.include_router(admin_docs_router,  prefix="/api/admin", tags=["Admin – Documents"], dependencies=admin_dependencies)
app.include_router(admin_corpus_router, prefix="/api/admin", tags=["Admin – Corpus Seed"], dependencies=admin_dependencies)
app.include_router(admin_geo_router,   prefix="/api/admin", tags=["Admin – Geospatial"], dependencies=admin_dependencies)
app.include_router(admin_form_router,  prefix="/api/admin/form", tags=["Admin – Form Builder"], dependencies=admin_dependencies)
app.include_router(admin_channels_router, prefix="/api/admin/channels", tags=["Admin – Channels"], dependencies=admin_dependencies)

# ── Admin Panel Static Files ──────────────────────────────────────────────────
admin_static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin"))
if os.path.exists(admin_static_path):
    app.mount("/admin", StaticFiles(directory=admin_static_path, html=True), name="admin")
    logger.info("Admin panel mounted at /admin")


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Carbon Market Eligibility Chatbot API",
        "phase": "Phase 1 — Rules Engine + RAG Foundation",
        "docs": "/api/docs",
        "admin": "/admin",
        "health": "/health",
    }


@app.get("/health", tags=["Root"])
async def health():
    return {
        "status": "ok",
        "llm": llm_registry.get_status(),
    }
