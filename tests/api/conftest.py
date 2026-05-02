import os
import sys
import tempfile
from contextlib import ExitStack
import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def clients():
    tmp = tempfile.TemporaryDirectory()
    os.environ['APP_DATA_DIR'] = tmp.name
    os.environ['APP_ENV'] = 'test'
    os.environ['EVENT_BUS_MODE'] = 'memory'
    os.environ['CACHE_MODE'] = 'memory'
    os.environ['DOC_STORE_MODE'] = 'memory'
    os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'mysql://root:root@localhost:3306/linkedin_sim')

    backend_root = str((Path(__file__).resolve().parents[2] / 'backend'))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

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
