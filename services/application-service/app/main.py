"""
main.py — FastAPI application entry point for Owner 5 Application Service.
Port: 8005
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import engine, Base
from app.routes.applications import router as applications_router
from app.schemas import HealthResponse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [owner5] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables on startup if they don't exist."""
    logger.info("Starting Owner 5 Application Service...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")
    yield
    logger.info("Owner 5 Application Service shutting down.")


app = FastAPI(
    title="Owner 5 — Application Service",
    description=(
        "LinkedIn Simulation project — Owner 5.\n\n"
        "Handles job applications: submit, duplicate prevention, status updates, "
        "recruiter notes, and Kafka event publishing."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(applications_router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health():
    """Health check — used by Docker Compose and load tests."""
    return {"service": "owner5-application-service", "status": "ok"}
