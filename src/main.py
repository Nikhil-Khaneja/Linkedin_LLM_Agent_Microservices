"""
Job Service - Main Application
Owner 4 - LinkedIn Simulation Project

This service handles:
- Job CRUD operations
- Job search with filters
- Saved jobs management
- Redis caching (cache-aside pattern)
- Kafka event publishing
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid

from src.config.settings import get_settings
from src.config.database import init_db, close_db
from src.config.redis_config import init_redis, close_redis
from src.config.kafka_config import init_kafka_producer, close_kafka_producer
from src.routes.jobs import router as jobs_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events"""
    # Startup
    logger.info(f"Starting {settings.service_name}...")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    try:
        await init_redis()
        logger.info("Redis initialized")
    except Exception as e:
        logger.warning(f"Redis initialization failed (service will continue): {e}")

    try:
        init_kafka_producer()
        logger.info("Kafka producer initialized")
    except Exception as e:
        logger.warning(f"Kafka initialization failed (service will continue): {e}")

    logger.info(f"{settings.service_name} started successfully on port {settings.service_port}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.service_name}...")
    close_kafka_producer()
    await close_redis()
    await close_db()
    logger.info(f"{settings.service_name} shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Job Service",
    description="""
    ## Owner 4 - Job Service

    Part of the LinkedIn Simulation + Agentic AI Services project.

    ### Features
    - **Job CRUD**: Create, read, update, and close job postings
    - **Job Search**: Search with filters (location, type, skills, keywords)
    - **Saved Jobs**: Members can save jobs for later
    - **Redis Caching**: Cache-aside pattern for hot job data
    - **Kafka Events**: Publishes job lifecycle events

    ### Kafka Topics Published
    - `job.created` - New job posting created
    - `job.updated` - Job details modified
    - `job.closed` - Job position closed (consumed by Owner 5)
    - `job.viewed` - Job detail page viewed
    - `job.saved` - Member saved a job
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    request_id = request.headers.get("X-Trace-Id", str(uuid.uuid4())[:8])
    start_time = time.time()

    # Add request ID to state
    request.state.request_id = request_id

    response = await call_next(request)

    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s - "
        f"Request ID: {request_id}"
    )

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-Id"] = request_id

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception: {exc}, request_id: {request_id}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "trace_id": f"trc_{request_id}",
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred",
                "details": {},
                "retryable": True
            }
        }
    )


# Include routers
app.include_router(jobs_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": settings.service_name,
        "version": "1.0.0",
        "description": "Job Service - Owner 4 - LinkedIn Simulation",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.debug
    )
