# Phase 1 refactor bundle

This bundle does two concrete things:

1. Replaces the debug/test frontend with the React frontend from the shared `linkedin-final.zip` you uploaded, patched to call the Python backend on ports 8001-8008.
2. Refactors `auth_service` into a Python microservice layout with:
   - `app/main.py`
   - `app/routes/`
   - `app/schemas/`
   - `app/services/`
   - `app/repositories/`
   - `app/core/`
   - `app/middleware/`

Other services still run through their legacy wrappers in this bundle. This is a Phase 1 architecture cleanup, not a complete rewrite of every service yet.
