# Service Naming

This bundle keeps the existing implementation but exposes meaningful Python microservice names:

- auth_service
- member_profile_service
- recruiter_company_service
- jobs_service
- applications_service
- messaging_connections_service
- analytics_service
- ai_orchestrator_service

The legacy `owner*` modules are retained internally for compatibility, but Docker Compose and runtime service names use the names above.
