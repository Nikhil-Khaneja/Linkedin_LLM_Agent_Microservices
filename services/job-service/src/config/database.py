"""
Database configuration and connection management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Enable connection health checks
    echo=settings.debug  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency function for FastAPI to get database session.
    Yields a session and closes it after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager for getting database session outside of FastAPI requests.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """Initialize database connection pool"""
    try:
        # Test connection
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


async def close_db():
    """Close database connection pool"""
    engine.dispose()
    logger.info("Database connection pool closed")
