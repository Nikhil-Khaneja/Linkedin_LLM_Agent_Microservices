# Service Structure

This bundle keeps only the named Python services:

- auth_service
- member_profile_service
- recruiter_company_service
- jobs_service
- applications_service
- messaging_connections_service
- analytics_service
- ai_orchestrator_service

Legacy owner1..owner8 folders were removed.

Each service should be launched through `services.<service>.app.main:app`.
