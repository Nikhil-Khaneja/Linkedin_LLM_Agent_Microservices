# syntax=docker/dockerfile:1
# Multi-stage: one publishable image per Python microservice (shared code + single service tree).
# Build: docker build --target auth_service -t myreg/linkedin-sim/auth_service:tag ./backend
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Per-service stages (copy only shared + that service) ---
FROM base AS auth_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/auth_service ./services/auth_service

FROM base AS recruiter_company_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/recruiter_company_service ./services/recruiter_company_service

FROM base AS member_profile_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/member_profile_service ./services/member_profile_service

FROM base AS jobs_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/jobs_service ./services/jobs_service

FROM base AS applications_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/applications_service ./services/applications_service

FROM base AS messaging_connections_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/messaging_connections_service ./services/messaging_connections_service

FROM base AS analytics_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/analytics_service ./services/analytics_service

FROM base AS ai_orchestrator_service
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/ai_orchestrator_service ./services/ai_orchestrator_service
