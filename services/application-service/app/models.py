"""
models.py — SQLAlchemy ORM models for Owner 5 Application Service.
Database: application_core (MySQL)
"""

from sqlalchemy import (
    Column, String, Text, ForeignKey, TIMESTAMP, UniqueConstraint
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db import Base


class Application(Base):
    """Core application record."""
    __tablename__ = "applications"

    application_id  = Column(String(50),  primary_key=True)
    job_id          = Column(String(50),  nullable=False, index=True)
    member_id       = Column(String(50),  nullable=False, index=True)
    recruiter_id    = Column(String(50),  nullable=True)
    resume_ref      = Column(Text,        nullable=True)
    status          = Column(String(30),  nullable=False, default="submitted")
    idempotency_key = Column(String(100), nullable=False, unique=True)
    trace_id        = Column(String(100), nullable=True)
    submitted_at    = Column(TIMESTAMP,   server_default=func.now())
    updated_at      = Column(TIMESTAMP,   server_default=func.now(), onupdate=func.now())

    # relationships
    answers = relationship("ApplicationAnswer", back_populates="application",
                           cascade="all, delete-orphan")
    notes   = relationship("RecruiterNote",     back_populates="application",
                           cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("job_id", "member_id", name="uq_job_member"),
    )


class ApplicationAnswer(Base):
    """Optional per-question answers on an application."""
    __tablename__ = "application_answers"

    answer_id      = Column(String(50),  primary_key=True)
    application_id = Column(String(50),  ForeignKey("applications.application_id"),
                            nullable=False, index=True)
    question_key   = Column(String(100), nullable=True)
    answer_text    = Column(Text,        nullable=True)
    created_at     = Column(TIMESTAMP,   server_default=func.now())

    application = relationship("Application", back_populates="answers")


class RecruiterNote(Base):
    """Notes a recruiter leaves on an application."""
    __tablename__ = "recruiter_notes"

    note_id        = Column(String(50),  primary_key=True)
    application_id = Column(String(50),  ForeignKey("applications.application_id"),
                            nullable=False, index=True)
    recruiter_id   = Column(String(50),  nullable=False)
    note_text      = Column(Text,        nullable=False)
    created_at     = Column(TIMESTAMP,   server_default=func.now())

    application = relationship("Application", back_populates="notes")


class JobStatusProjection(Base):
    """
    Local copy of job status, populated by consuming Owner 4 Kafka events.
    Lets Owner 5 check if a job is open/closed without a live call to Owner 4.
    """
    __tablename__ = "job_status_projection"

    job_id       = Column(String(50), primary_key=True)
    recruiter_id = Column(String(50), nullable=True)
    status       = Column(String(30), nullable=False)
    updated_at   = Column(TIMESTAMP,  server_default=func.now(), onupdate=func.now())


class ConsumedKafkaEvent(Base):
    """
    Tracks already-processed Kafka event IDs.
    Prevents duplicate DB writes when Kafka replays events (at-least-once delivery).
    """
    __tablename__ = "consumed_kafka_events"

    event_id    = Column(String(100), primary_key=True)
    event_type  = Column(String(100), nullable=True)
    consumed_at = Column(TIMESTAMP,   server_default=func.now())
