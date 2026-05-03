import os
import sys
import tempfile
from contextlib import ExitStack
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _clear_cached_services() -> None:
    """Fresh service instances per test (lru_cache survives importlib.reload of app.main)."""
    for mod_name in (
        'services.auth_service.app.core.deps',
        'services.member_profile_service.app.core.deps',
        'services.recruiter_company_service.app.core.deps',
        'services.jobs_service.app.core.deps',
        'services.applications_service.app.core.deps',
        'services.messaging_connections_service.app.core.deps',
        'services.analytics_service.app.core.deps',
        'services.ai_orchestrator_service.app.core.deps',
    ):
        mod = importlib.import_module(mod_name)
        for obj in list(vars(mod).values()):
            if callable(obj) and hasattr(obj, 'cache_clear'):
                obj.cache_clear()
    try:
        import services.jobs_service.app.services.job_command_service as _job_cmd

        _job_cmd._service = None
    except Exception:
        pass


@pytest.fixture()
def clients():
    tmp = tempfile.TemporaryDirectory()
    os.environ['APP_DATA_DIR'] = tmp.name
    os.environ['APP_ENV'] = 'test'
    os.environ['EVENT_BUS_MODE'] = 'memory'
    os.environ['CACHE_MODE'] = 'memory'
    os.environ['DOC_STORE_MODE'] = 'memory'
    os.environ['APPLICATION_SUBMIT_KAFKA_FIRST'] = 'false'
    os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'mysql://root:root@localhost:3306/linkedin_sim')

    backend_root = str((Path(__file__).resolve().parents[2] / 'backend'))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    # run_api_tests_host.sh sets MYSQL_HOST=127.0.0.1; PyMongo must not use Docker hostname "mongo" from .env.
    if os.environ.get('MYSQL_HOST') in ('127.0.0.1', 'localhost'):
        os.environ['MONGO_URL'] = 'mongodb://127.0.0.1:27017'
        os.environ['MONGO_URI'] = os.environ['MONGO_URL']
        try:
            import services.shared.notifications as _notif
            _notif._CLIENT = None
        except Exception:
            pass
        try:
            from services.member_profile_service.app.routes import members as _members_routes
            _members_routes._MONGO_CLIENT = None
        except Exception:
            pass

    import services.shared.common as common
    import services.shared.kafka_bus as kafka_bus
    import services.shared.cache as cache
    import services.shared.document_store as document_store
    import services.shared.relational as relational
    import services.shared.auth as auth
    importlib.reload(auth)
    importlib.reload(common)
    importlib.reload(kafka_bus)
    importlib.reload(cache)
    importlib.reload(document_store)
    importlib.reload(relational)
    kafka_bus.reset_memory_bus()
    cache.reset_memory_cache()
    document_store.reset_memory_store()
    common.IDEMPOTENCY.clear()
    _clear_cached_services()

    module_names = [
        'services.auth_service.app.main',
        'services.member_profile_service.app.main',
        'services.recruiter_company_service.app.main',
        'services.jobs_service.app.main',
        'services.applications_service.app.main',
        'services.messaging_connections_service.app.main',
        'services.analytics_service.app.main',
        'services.ai_orchestrator_service.app.main',
    ]
    mods = {name: importlib.reload(importlib.import_module(name)) for name in module_names}
    _clear_cached_services()

    with ExitStack() as stack:
        out = {
            'owner1': stack.enter_context(TestClient(mods['services.auth_service.app.main'].app)),
            'owner2': stack.enter_context(TestClient(mods['services.member_profile_service.app.main'].app)),
            'owner3': stack.enter_context(TestClient(mods['services.recruiter_company_service.app.main'].app)),
            'owner4': stack.enter_context(TestClient(mods['services.jobs_service.app.main'].app)),
            'owner5': stack.enter_context(TestClient(mods['services.applications_service.app.main'].app)),
            'owner6': stack.enter_context(TestClient(mods['services.messaging_connections_service.app.main'].app)),
            'owner7': stack.enter_context(TestClient(mods['services.analytics_service.app.main'].app)),
            'owner8': stack.enter_context(TestClient(mods['services.ai_orchestrator_service.app.main'].app)),
            'headers': {
                'member': {'Authorization': f"Bearer {auth.issue_access_token(sub='mem_501', role='member', email='member@example.com')}"},
                'recruiter': {'Authorization': f"Bearer {auth.issue_access_token(sub='rec_120', role='recruiter', email='recruiter@example.com')}"},
                'admin': {'Authorization': f"Bearer {auth.issue_access_token(sub='adm_1', role='admin', email='admin@example.com')}"},
            }
        }
        yield out
    tmp.cleanup()
