"""
Owner 7 — Analytics + Kafka Host Service
Main FastAPI application with lifecycle management.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.utils.db import connect_mongo, connect_redis, close_connections
from app.services.analytics_service import stop_producer
from app.consumers.event_consumer import start_consumer
from app.config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

_consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_task
    settings = get_settings()
    logger.info(f"Starting {settings.SERVICE_NAME} [{settings.ENV}]")

    # Connect datastores
    await connect_mongo()
    await connect_redis()

    # Start Kafka consumer as background task
    _consumer_task = asyncio.create_task(start_consumer())
    logger.info("Kafka consumer background task launched")

    yield  # ── app is running ──

    # Shutdown
    logger.info("Shutting down...")
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    await stop_producer()
    await close_connections()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Owner 7 — Analytics + Kafka Host",
    description="Event ingest, dashboard rollups, benchmark exports, and shared Kafka broker",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
